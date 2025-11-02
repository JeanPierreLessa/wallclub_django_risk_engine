"""
API REST Pública para Análise Antifraude
Fase 2 - Semana 13

Endpoints para integração externa (POSP2, Apps, Checkout)
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from wallclub_core.oauth.decorators import require_oauth_token
from wallclub_core.decorators.api_decorators import handle_api_errors, validate_required_params
from .services_coleta import ColetaDadosService
from .services import AnaliseRiscoService
from .services_3ds import Auth3DSService
from .models import TransacaoRisco, DecisaoAntifraude
from datetime import datetime
from decimal import Decimal
import time


@api_view(['POST'])
@require_oauth_token
@handle_api_errors
@validate_required_params(['cpf', 'valor', 'modalidade'])
def analyze(request):
    """
    Endpoint principal de análise de risco
    
    POST /api/antifraude/analyze/
    
    Headers:
        Authorization: Bearer <oauth_token>
        Content-Type: application/json
    
    Body:
    {
        "transaction_id": "TRX-123",  # Opcional, gerado se não fornecido
        "origem": "POS",  # POS, APP, WEB (opcional, detecta automaticamente)
        "cpf": "12345678900",
        "cliente_id": 123,
        "valor": 150.00,
        "modalidade": "CREDITO",
        "parcelas": 3,
        "numero_cartao": "5111111111111111",  # Opcional
        "bandeira": "MASTERCARD",  # Opcional
        "terminal": "POS001",  # Para POS
        "loja_id": 1,
        "canal_id": 6,
        "ip_address": "192.168.1.1",  # Para APP/WEB
        "device_fingerprint": "abc123",  # Opcional
        "user_agent": "Mozilla/5.0...",  # Opcional
        "requer_3ds": false,  # Forçar 3DS (opcional)
        "dados_cliente": {  # Opcional, para 3DS
            "nome": "João Silva",
            "email": "joao@email.com",
            "telefone": "11999999999"
        }
    }
    
    Returns:
    {
        "sucesso": true,
        "transacao_id": "TRX-123",
        "decisao": "APROVADO",  # APROVADO, REPROVADO, REVISAO, REQUER_3DS
        "score_risco": 35,
        "motivo": "Transação normal",
        "regras_acionadas": [
            {"nome": "Velocidade", "pontos": 10}
        ],
        "tempo_analise_ms": 125,
        "requer_3ds": false,
        "dados_3ds": null  # Presente se requer_3ds=true
    }
    """
    inicio = time.time()
    dados = request.data
    
    # Normalizar dados
    origem = dados.get('origem')
    dados_normalizados = ColetaDadosService.normalizar_dados(dados, origem)
    
    # Validar dados mínimos
    valido, erro = ColetaDadosService.validar_dados_minimos(dados_normalizados)
    if not valido:
        return Response({
            'sucesso': False,
            'mensagem': f'Dados inválidos: {erro}'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Criar registro de transação
    try:
        transacao = TransacaoRisco.objects.create(**dados_normalizados)
    except Exception as e:
        return Response({
            'sucesso': False,
            'mensagem': f'Erro ao registrar transação: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    # Analisar risco
    try:
        decisao = AnaliseRiscoService.analisar_transacao(transacao)
    except Exception as e:
        return Response({
            'sucesso': False,
            'mensagem': f'Erro na análise de risco: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    # Verificar necessidade de 3DS
    requer_3ds = dados.get('requer_3ds', False)
    dados_3ds = None
    
    # Usar BIN já extraído no model (não temos numero_cartao completo)
    if transacao.bin_cartao:
        bin_cartao = transacao.bin_cartao
        
        if bin_cartao:
            auth_3ds = Auth3DSService()
            
            # Verificar se 3DS está habilitado e recomendar uso
            if auth_3ds.esta_habilitado():
                deve_usar, motivo_3ds = auth_3ds.recomendar_3ds(
                    score_risco=decisao.score_risco,
                    valor=transacao.valor,
                    bin_cartao=bin_cartao
                )
                
                if deve_usar or requer_3ds:
                    requer_3ds = True
                    
                    # Verificar elegibilidade
                    elegibilidade = auth_3ds.verificar_elegibilidade(bin_cartao, transacao.valor)
                    
                    if elegibilidade['elegivel']:
                        # Iniciar autenticação 3DS
                        dados_cliente_3ds = dados.get('dados_cliente', {})
                        if not dados_cliente_3ds:
                            dados_cliente_3ds = {
                                'cpf': transacao.cpf,
                                'ip_address': transacao.ip_address,
                                'user_agent': transacao.user_agent
                            }
                        
                        auth_resultado = auth_3ds.iniciar_autenticacao(
                            transacao_id=transacao.transacao_id,
                            bin_cartao=bin_cartao,
                            valor=transacao.valor,
                            dados_cliente=dados_cliente_3ds
                        )
                        
                        if auth_resultado['sucesso']:
                            dados_3ds = {
                                'auth_id': auth_resultado['auth_id'],
                                'redirect_url': auth_resultado['redirect_url'],
                                'metodo': auth_resultado['metodo'],
                                'expiracao': auth_resultado['expiracao'],
                                'motivo': motivo_3ds
                            }
                            
                            # Atualizar decisão para REQUER_3DS
                            decisao.decisao = 'REQUER_3DS'
                            decisao.motivo = f"{decisao.motivo} + 3DS obrigatório ({motivo_3ds})"
                            decisao.save()
                    else:
                        # Cartão não elegível, continuar sem 3DS
                        requer_3ds = False
    
    tempo_total = int((time.time() - inicio) * 1000)
    
    return Response({
        'sucesso': True,
        'transacao_id': transacao.transacao_id,
        'decisao': decisao.decisao,
        'score_risco': decisao.score_risco,
        'motivo': decisao.motivo,
        'regras_acionadas': decisao.regras_acionadas,
        'tempo_analise_ms': tempo_total,
        'requer_3ds': requer_3ds,
        'dados_3ds': dados_3ds
    })


@api_view(['GET'])
@require_oauth_token
@handle_api_errors
def decision(request, transacao_id):
    """
    Consulta decisão de uma transação específica
    
    GET /api/antifraude/decision/<transacao_id>/
    
    Headers:
        Authorization: Bearer <oauth_token>
    
    Returns:
    {
        "transacao_id": "TRX-123",
        "origem": "POS",
        "cliente_id": 123,
        "cpf": "123.456.789-00",
        "valor": "150.00",
        "modalidade": "CREDITO",
        "parcelas": 3,
        "decisao": "APROVADO",
        "score_risco": 35,
        "motivo": "Transação normal",
        "regras_acionadas": [...],
        "created_at": "2025-10-16T20:00:00",
        "tempo_analise_ms": 125
    }
    """
    try:
        transacao = TransacaoRisco.objects.get(transacao_id=transacao_id)
        decisao = DecisaoAntifraude.objects.filter(transacao=transacao).latest('created_at')
        
        return Response({
            'transacao_id': transacao.transacao_id,
            'origem': transacao.origem,
            'cliente_id': transacao.cliente_id,
            'cpf': f"{transacao.cpf[:3]}.{transacao.cpf[3:6]}.{transacao.cpf[6:9]}-{transacao.cpf[9:]}",
            'valor': str(transacao.valor),
            'modalidade': transacao.modalidade,
            'parcelas': transacao.parcelas,
            'decisao': decisao.decisao,
            'score_risco': decisao.score_risco,
            'motivo': decisao.motivo,
            'regras_acionadas': decisao.regras_acionadas,
            'created_at': decisao.created_at.isoformat(),
            'tempo_analise_ms': decisao.tempo_analise_ms
        })
    
    except TransacaoRisco.DoesNotExist:
        return Response({
            'sucesso': False,
            'mensagem': 'Transação não encontrada'
        }, status=status.HTTP_404_NOT_FOUND)
    
    except DecisaoAntifraude.DoesNotExist:
        return Response({
            'sucesso': False,
            'mensagem': 'Decisão não encontrada'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@require_oauth_token
@handle_api_errors
@validate_required_params(['auth_id'])
def validate_3ds(request):
    """
    Valida resultado da autenticação 3DS
    
    POST /api/antifraude/validate-3ds/
    
    Headers:
        Authorization: Bearer <oauth_token>
        Content-Type: application/json
    
    Body:
    {
        "auth_id": "3DS-AUTH-123",
        "transacao_id": "TRX-123"  # Opcional
    }
    
    Returns:
    {
        "sucesso": true,
        "auth_id": "3DS-AUTH-123",
        "status": "Y",
        "autenticado": true,
        "eci": "05",
        "cavv": "AAABCZIhcQAAAABZlyFxAAAAAAA=",
        "xid": "MDAwMDAwMDAwMDAwMDAwMzIyNzY=",
        "mensagem": "Autenticação bem-sucedida"
    }
    """
    auth_id = request.data.get('auth_id')
    transacao_id = request.data.get('transacao_id')
    
    auth_3ds = Auth3DSService()
    
    if not auth_3ds.esta_habilitado():
        return Response({
            'sucesso': False,
            'mensagem': '3DS não está habilitado'
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    
    # Validar autenticação
    resultado = auth_3ds.validar_autenticacao(auth_id)
    
    # Se transacao_id foi fornecido, atualizar decisão
    if transacao_id and resultado['sucesso']:
        try:
            transacao = TransacaoRisco.objects.get(transacao_id=transacao_id)
            decisao = DecisaoAntifraude.objects.filter(transacao=transacao).latest('created_at')
            
            # Atualizar decisão baseado no resultado 3DS
            if resultado['status'] == 'Y':
                decisao.decisao = 'APROVADO'
                decisao.motivo = f"{decisao.motivo} + 3DS autenticado com sucesso"
            elif resultado['status'] == 'A':
                decisao.decisao = 'APROVADO'
                decisao.motivo = f"{decisao.motivo} + 3DS tentativa de autenticação"
            else:
                decisao.decisao = 'REPROVADO'
                decisao.motivo = f"{decisao.motivo} + 3DS falhou"
            
            decisao.save()
        
        except (TransacaoRisco.DoesNotExist, DecisaoAntifraude.DoesNotExist):
            pass  # Não bloqueia validação se transação não encontrada
    
    return Response({
        'sucesso': resultado['sucesso'],
        'auth_id': auth_id,
        'status': resultado['status'],
        'autenticado': resultado['sucesso'],
        'eci': resultado['eci'],
        'cavv': resultado['cavv'],
        'xid': resultado['xid'],
        'mensagem': resultado['mensagem']
    })


@api_view(['GET'])
@require_oauth_token
@handle_api_errors
def health(request):
    """
    Health check do serviço antifraude
    
    GET /api/antifraude/health/
    
    Returns:
    {
        "status": "healthy",
        "servicos": {
            "maxmind": true,
            "3ds": true,
            "redis": true
        },
        "timestamp": "2025-10-16T20:00:00"
    }
    """
    from .services_maxmind import MaxMindService
    from django.core.cache import cache
    
    servicos = {}
    
    # Verificar MaxMind
    maxmind = MaxMindService()
    servicos['maxmind'] = maxmind.esta_disponivel()
    
    # Verificar 3DS
    auth_3ds = Auth3DSService()
    servicos['3ds'] = auth_3ds.esta_habilitado()
    
    # Verificar Redis
    try:
        cache.set('health_check', 'ok', 10)
        servicos['redis'] = cache.get('health_check') == 'ok'
    except:
        servicos['redis'] = False
    
    status_geral = 'healthy' if all(servicos.values()) else 'degraded'
    
    return Response({
        'status': status_geral,
        'servicos': servicos,
        'timestamp': datetime.now().isoformat()
    })
