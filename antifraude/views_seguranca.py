"""
APIs para Sistema de Atividades Suspeitas
Fase 4 - Semana 23
"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from datetime import datetime, timedelta
import json
import logging

from .models import BloqueioSeguranca, AtividadeSuspeita

logger = logging.getLogger('antifraude.seguranca')


@csrf_exempt
@require_http_methods(["POST"])
def validate_login(request):
    """
    API 1: Valida se IP ou CPF está bloqueado
    
    Request:
    {
        "ip": "192.168.1.100",
        "cpf": "12345678901",
        "portal": "vendas"
    }
    
    Response:
    {
        "permitido": true/false,
        "bloqueado": true/false,
        "tipo": "ip" ou "cpf",
        "motivo": "...",
        "bloqueio_id": 123
    }
    """
    try:
        data = json.loads(request.body)
        ip = data.get('ip')
        cpf = data.get('cpf')
        portal = data.get('portal', 'desconhecido')
        
        if not ip or not cpf:
            return JsonResponse({
                'error': 'IP e CPF são obrigatórios'
            }, status=400)
        
        # Verificar bloqueios ativos
        bloqueio_ip = BloqueioSeguranca.objects.filter(
            tipo='ip',
            valor=ip,
            ativo=True
        ).first()
        
        bloqueio_cpf = BloqueioSeguranca.objects.filter(
            tipo='cpf',
            valor=cpf,
            ativo=True
        ).first()
        
        # Se encontrou bloqueio
        if bloqueio_ip or bloqueio_cpf:
            bloqueio = bloqueio_ip or bloqueio_cpf
            
            logger.warning(
                f"🚫 Login bloqueado - {bloqueio.tipo.upper()}: {bloqueio.valor} | "
                f"Portal: {portal} | Motivo: {bloqueio.motivo[:100]}"
            )
            
            return JsonResponse({
                'permitido': False,
                'bloqueado': True,
                'tipo': bloqueio.tipo,
                'motivo': bloqueio.motivo,
                'bloqueio_id': bloqueio.id,
                'portal': portal
            })
        
        # Sem bloqueios - permitir
        logger.info(f"✅ Login permitido - IP: {ip} | CPF: {cpf[:3]}*** | Portal: {portal}")
        
        return JsonResponse({
            'permitido': True,
            'bloqueado': False,
            'tipo': None,
            'motivo': None,
            'bloqueio_id': None,
            'portal': portal
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)
    except Exception as e:
        logger.error(f"❌ Erro em validate_login: {str(e)}")
        # Fail-open: em caso de erro, permitir acesso
        return JsonResponse({
            'permitido': True,
            'bloqueado': False,
            'erro': str(e)
        })


@csrf_exempt
@require_http_methods(["GET"])
def list_suspicious(request):
    """
    API 2: Lista atividades suspeitas com filtros
    
    Query params:
    - status: pendente, investigado, bloqueado, falso_positivo, ignorado
    - tipo: login_multiplo, tentativas_falhas, ip_novo, horario_suspeito
    - portal: admin, lojista, vendas, app
    - dias: últimos N dias (padrão: 7)
    - limit: limite de resultados (padrão: 50)
    """
    try:
        # Parâmetros de filtro
        status = request.GET.get('status')
        tipo = request.GET.get('tipo')
        portal = request.GET.get('portal')
        dias = int(request.GET.get('dias', 7))
        limit = int(request.GET.get('limit', 50))
        
        # Query base
        query = AtividadeSuspeita.objects.all()
        
        # Filtros
        if status:
            query = query.filter(status=status)
        if tipo:
            query = query.filter(tipo=tipo)
        if portal:
            query = query.filter(portal=portal)
        
        # Filtro de período
        data_limite = datetime.now() - timedelta(days=dias)
        query = query.filter(detectado_em__gte=data_limite)
        
        # Limitar resultados
        atividades = query[:limit]
        
        # Serializar
        resultado = []
        for atividade in atividades:
            resultado.append({
                'id': atividade.id,
                'tipo': atividade.tipo,
                'tipo_label': dict(atividade.TIPO_CHOICES).get(atividade.tipo),
                'cpf': atividade.cpf,
                'cpf_mascarado': f"{atividade.cpf[:3]}***{atividade.cpf[-2:]}",
                'ip': atividade.ip,
                'portal': atividade.portal,
                'detalhes': atividade.detalhes,
                'severidade': atividade.severidade,
                'status': atividade.status,
                'status_label': dict(atividade.STATUS_CHOICES).get(atividade.status),
                'detectado_em': atividade.detectado_em.isoformat(),
                'analisado_em': atividade.analisado_em.isoformat() if atividade.analisado_em else None,
                'analisado_por': atividade.analisado_por,
                'observacoes': atividade.observacoes,
                'acao_tomada': atividade.acao_tomada,
                'bloqueio_relacionado_id': atividade.bloqueio_relacionado_id
            })
        
        # Estatísticas
        total = query.count()
        pendentes = query.filter(status='pendente').count()
        
        logger.info(f"📊 Listagem atividades suspeitas: {total} total, {pendentes} pendentes")
        
        return JsonResponse({
            'success': True,
            'total': total,
            'pendentes': pendentes,
            'atividades': resultado,
            'filtros': {
                'status': status,
                'tipo': tipo,
                'portal': portal,
                'dias': dias,
                'limit': limit
            }
        })
        
    except Exception as e:
        logger.error(f"❌ Erro em list_suspicious: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def create_block(request):
    """
    API 3: Cria bloqueio manual
    
    Request:
    {
        "tipo": "ip" ou "cpf",
        "valor": "192.168.1.100" ou "12345678901",
        "motivo": "Tentativas de ataque",
        "bloqueado_por": "admin_usuario",
        "portal": "vendas"
    }
    """
    try:
        data = json.loads(request.body)
        tipo = data.get('tipo')
        valor = data.get('valor')
        motivo = data.get('motivo')
        bloqueado_por = data.get('bloqueado_por', 'sistema')
        portal = data.get('portal')
        detalhes = data.get('detalhes', {})
        
        # Validações
        if tipo not in ['ip', 'cpf']:
            return JsonResponse({'error': 'Tipo deve ser "ip" ou "cpf"'}, status=400)
        
        if not valor or not motivo:
            return JsonResponse({'error': 'Valor e motivo são obrigatórios'}, status=400)
        
        # Verificar se já existe bloqueio ativo
        bloqueio_existente = BloqueioSeguranca.objects.filter(
            tipo=tipo,
            valor=valor,
            ativo=True
        ).first()
        
        if bloqueio_existente:
            return JsonResponse({
                'error': 'Já existe bloqueio ativo para este valor',
                'bloqueio_id': bloqueio_existente.id
            }, status=400)
        
        # Criar bloqueio
        bloqueio = BloqueioSeguranca.objects.create(
            tipo=tipo,
            valor=valor,
            motivo=motivo,
            bloqueado_por=bloqueado_por,
            portal=portal,
            detalhes=detalhes,
            ativo=True
        )
        
        logger.warning(
            f"🚫 Bloqueio criado - {tipo.upper()}: {valor} | "
            f"Por: {bloqueado_por} | Motivo: {motivo[:100]}"
        )
        
        return JsonResponse({
            'success': True,
            'bloqueio_id': bloqueio.id,
            'tipo': bloqueio.tipo,
            'valor': bloqueio.valor,
            'bloqueado_em': bloqueio.bloqueado_em.isoformat(),
            'message': f'Bloqueio de {tipo} criado com sucesso'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)
    except Exception as e:
        logger.error(f"❌ Erro em create_block: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def investigate_activity(request):
    """
    API 4: Investiga/age sobre atividade suspeita
    
    Request:
    {
        "atividade_id": 123,
        "acao": "marcar_investigado" | "bloquear_ip" | "bloquear_cpf" | "falso_positivo" | "ignorar",
        "usuario_id": 456,
        "observacoes": "Análise realizada..."
    }
    
    Response:
    {
        "success": true,
        "atividade_id": 123,
        "novo_status": "investigado",
        "bloqueio_criado_id": 789 (se aplicável)
    }
    """
    try:
        data = json.loads(request.body)
        atividade_id = data.get('atividade_id')
        acao = data.get('acao')
        usuario_id = data.get('usuario_id')
        observacoes = data.get('observacoes', '')
        
        # Validações
        if not atividade_id or not acao:
            return JsonResponse({'error': 'atividade_id e acao são obrigatórios'}, status=400)
        
        acoes_validas = ['marcar_investigado', 'bloquear_ip', 'bloquear_cpf', 'falso_positivo', 'ignorar']
        if acao not in acoes_validas:
            return JsonResponse({'error': f'Ação inválida. Opções: {", ".join(acoes_validas)}'}, status=400)
        
        # Buscar atividade
        try:
            atividade = AtividadeSuspeita.objects.get(id=atividade_id)
        except AtividadeSuspeita.DoesNotExist:
            return JsonResponse({'error': 'Atividade não encontrada'}, status=404)
        
        bloqueio_criado_id = None
        novo_status = atividade.status
        acao_tomada = acao
        
        # Executar ação
        if acao == 'marcar_investigado':
            atividade.status = 'investigado'
            novo_status = 'investigado'
            logger.info(f"🔍 Atividade {atividade_id} marcada como investigada")
        
        elif acao == 'bloquear_ip':
            # Criar bloqueio de IP
            bloqueio = BloqueioSeguranca.objects.create(
                tipo='ip',
                valor=atividade.ip,
                motivo=f"Atividade suspeita detectada: {dict(atividade.TIPO_CHOICES).get(atividade.tipo)}",
                bloqueado_por=f"usuario_{usuario_id}" if usuario_id else "sistema",
                portal=atividade.portal,
                detalhes={'atividade_id': atividade_id, 'detalhes_atividade': atividade.detalhes}
            )
            atividade.status = 'bloqueado'
            atividade.bloqueio_relacionado = bloqueio
            bloqueio_criado_id = bloqueio.id
            novo_status = 'bloqueado'
            logger.warning(f"🚫 IP {atividade.ip} bloqueado - Atividade {atividade_id}")
        
        elif acao == 'bloquear_cpf':
            # Criar bloqueio de CPF
            bloqueio = BloqueioSeguranca.objects.create(
                tipo='cpf',
                valor=atividade.cpf,
                motivo=f"Atividade suspeita detectada: {dict(atividade.TIPO_CHOICES).get(atividade.tipo)}",
                bloqueado_por=f"usuario_{usuario_id}" if usuario_id else "sistema",
                portal=atividade.portal,
                detalhes={'atividade_id': atividade_id, 'detalhes_atividade': atividade.detalhes}
            )
            atividade.status = 'bloqueado'
            atividade.bloqueio_relacionado = bloqueio
            bloqueio_criado_id = bloqueio.id
            novo_status = 'bloqueado'
            logger.warning(f"🚫 CPF {atividade.cpf[:3]}*** bloqueado - Atividade {atividade_id}")
        
        elif acao == 'falso_positivo':
            atividade.status = 'falso_positivo'
            novo_status = 'falso_positivo'
            logger.info(f"✅ Atividade {atividade_id} marcada como falso positivo")
        
        elif acao == 'ignorar':
            atividade.status = 'ignorado'
            novo_status = 'ignorado'
            logger.info(f"⚪ Atividade {atividade_id} ignorada")
        
        # Atualizar campos de análise
        atividade.analisado_em = datetime.now()
        atividade.analisado_por = usuario_id
        atividade.observacoes = observacoes
        atividade.acao_tomada = acao_tomada
        atividade.save()
        
        return JsonResponse({
            'success': True,
            'atividade_id': atividade.id,
            'novo_status': novo_status,
            'acao_executada': acao,
            'bloqueio_criado_id': bloqueio_criado_id,
            'message': f'Ação "{acao}" executada com sucesso'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)
    except Exception as e:
        logger.error(f"❌ Erro em investigate_activity: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def list_blocks(request):
    """
    API 5 (EXTRA): Lista bloqueios com filtros
    
    Query params:
    - tipo: ip, cpf
    - ativo: true, false
    - dias: últimos N dias
    """
    try:
        tipo = request.GET.get('tipo')
        ativo = request.GET.get('ativo')
        dias = int(request.GET.get('dias', 30))
        
        query = BloqueioSeguranca.objects.all()
        
        if tipo:
            query = query.filter(tipo=tipo)
        if ativo is not None:
            query = query.filter(ativo=ativo.lower() == 'true')
        
        data_limite = datetime.now() - timedelta(days=dias)
        query = query.filter(bloqueado_em__gte=data_limite)
        
        bloqueios = query[:100]
        
        resultado = []
        for bloqueio in bloqueios:
            resultado.append({
                'id': bloqueio.id,
                'tipo': bloqueio.tipo,
                'valor': bloqueio.valor,
                'motivo': bloqueio.motivo,
                'bloqueado_por': bloqueio.bloqueado_por,
                'portal': bloqueio.portal,
                'ativo': bloqueio.ativo,
                'bloqueado_em': bloqueio.bloqueado_em.isoformat(),
                'desbloqueado_em': bloqueio.desbloqueado_em.isoformat() if bloqueio.desbloqueado_em else None,
                'desbloqueado_por': bloqueio.desbloqueado_por
            })
        
        return JsonResponse({
            'success': True,
            'total': query.count(),
            'bloqueios': resultado
        })
        
    except Exception as e:
        logger.error(f"❌ Erro em list_blocks: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)
