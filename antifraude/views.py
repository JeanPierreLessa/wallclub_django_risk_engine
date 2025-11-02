"""
Views para API Antifraude
Fase 2 - Semana 7
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from wallclub_core.oauth.decorators import require_oauth_token
from wallclub_core.decorators.api_decorators import handle_api_errors, validate_required_params
from .services_coleta import ColetaDadosService
from .services import AnaliseRiscoService
from .models import TransacaoRisco, DecisaoAntifraude


@api_view(['POST'])
@require_oauth_token
@handle_api_errors
@validate_required_params(['cpf', 'valor', 'modalidade'])
def analisar_transacao(request):
    """
    Analisa risco de transação com normalização automática
    
    POST /api/antifraude/analisar/
    
    Body (POS):
    {
        "nsu": "123456",
        "cpf": "12345678900",
        "cliente_id": 123,
        "valor": 150.00,
        "modalidade": "PIX",
        "parcelas": 1,
        "numero_cartao": "4111111111111111",
        "bandeira": "VISA",
        "terminal": "POS001",
        "loja_id": 1,
        "canal_id": 6
    }
    
    Body (APP/WEB):
    {
        "transaction_id": "ORD-2025-001",
        "cpf": "12345678900",
        "cliente_id": 123,
        "valor": 150.00,
        "modalidade": "CREDITO",
        "parcelas": 3,
        "numero_cartao": "5111111111111111",
        "bandeira": "MASTERCARD",
        "ip_address": "192.168.1.1",
        "device_fingerprint": "abc123",
        "user_agent": "Mozilla/5.0...",
        "loja_id": 1,
        "canal_id": 6
    }
    
    Returns:
    {
        "sucesso": true,
        "transacao_id": "123456",
        "decisao": "APROVADO",
        "score_risco": 45,
        "motivo": "Transação normal",
        "regras_acionadas": [],
        "tempo_analise_ms": 125
    }
    """
    dados = request.data
    origem = dados.get('origem')  # Opcional, detecta automaticamente
    
    # Normalizar dados (detecta origem automaticamente se não informada)
    dados_normalizados = ColetaDadosService.normalizar_dados(dados, origem)
    
    # Validar dados mínimos
    valido, erro = ColetaDadosService.validar_dados_minimos(dados_normalizados)
    if not valido:
        return Response({
            'sucesso': False,
            'mensagem': f'Dados inválidos: {erro}'
        }, status=400)
    
    # Criar registro de transação
    try:
        transacao = TransacaoRisco.objects.create(**dados_normalizados)
    except Exception as e:
        return Response({
            'sucesso': False,
            'mensagem': f'Erro ao registrar transação: {str(e)}'
        }, status=500)
    
    # Analisar risco
    try:
        decisao = AnaliseRiscoService.analisar_transacao(transacao)
    except Exception as e:
        return Response({
            'sucesso': False,
            'mensagem': f'Erro na análise de risco: {str(e)}'
        }, status=500)
    
    return Response({
        'sucesso': True,
        'transacao_id': transacao.transacao_id,
        'decisao': decisao.decisao,
        'score_risco': decisao.score_risco,
        'motivo': decisao.motivo,
        'regras_acionadas': decisao.regras_acionadas,
        'tempo_analise_ms': decisao.tempo_analise_ms
    })


@api_view(['GET'])
@require_oauth_token
@handle_api_errors
def consultar_decisao(request, transacao_id):
    """
    Consulta decisão de uma transação
    
    GET /api/antifraude/decisao/<transacao_id>/
    """
    try:
        transacao = TransacaoRisco.objects.get(transacao_id=transacao_id)
        decisao = DecisaoAntifraude.objects.filter(transacao=transacao).latest('created_at')
        
        return Response({
            'transacao_id': transacao.transacao_id,
            'origem': transacao.origem,
            'valor': str(transacao.valor),
            'decisao': decisao.decisao,
            'score_risco': decisao.score_risco,
            'motivo': decisao.motivo,
            'created_at': decisao.created_at.isoformat()
        })
    except TransacaoRisco.DoesNotExist:
        return Response({'erro': 'Transação não encontrada'}, status=404)
    except DecisaoAntifraude.DoesNotExist:
        return Response({'erro': 'Decisão não encontrada'}, status=404)


@api_view(['GET'])
@require_oauth_token
@handle_api_errors
def historico_cliente(request, cliente_id):
    """
    Histórico de transações e decisões de um cliente
    
    GET /api/antifraude/historico/<cliente_id>/?limit=10
    """
    limit = int(request.GET.get('limit', 10))
    
    transacoes = TransacaoRisco.objects.filter(
        cliente_id=cliente_id
    ).select_related('decisoes').order_by('-data_transacao')[:limit]
    
    resultado = []
    for transacao in transacoes:
        try:
            decisao = transacao.decisoes.latest('created_at')
            resultado.append({
                'transacao_id': transacao.transacao_id,
                'origem': transacao.origem,
                'valor': str(transacao.valor),
                'data_transacao': transacao.data_transacao.isoformat(),
                'decisao': decisao.decisao,
                'score_risco': decisao.score_risco
            })
        except DecisaoAntifraude.DoesNotExist:
            continue
    
    return Response({
        'cliente_id': cliente_id,
        'total': len(resultado),
        'transacoes': resultado
    })


@api_view(['GET'])
@require_oauth_token
@handle_api_errors
def dashboard_metricas(request):
    """
    Dashboard com métricas do sistema antifraude
    
    GET /api/antifraude/dashboard/?dias=7
    
    Returns:
    {
        "periodo": {
            "dias": 7,
            "data_inicio": "2025-10-09",
            "data_fim": "2025-10-16"
        },
        "transacoes": {
            "total": 1250,
            "por_origem": {"POS": 800, "APP": 350, "WEB": 100}
        },
        "decisoes": {
            "aprovadas": 1100,
            "reprovadas": 50,
            "revisao": 100,
            "taxa_aprovacao": 88.0
        },
        "scores": {
            "medio": 35.5,
            "min": 0,
            "max": 100
        },
        "performance": {
            "tempo_medio_ms": 125,
            "tempo_p95_ms": 450
        },
        "blacklist": {
            "total": 15,
            "ativos": 12,
            "bloqueios_periodo": 8
        },
        "whitelist": {
            "total": 45,
            "automaticas": 30,
            "manuais": 15
        },
        "regras": [
            {"nome": "Velocidade Alta", "acionamentos": 25},
            {"nome": "IP Suspeito", "acionamentos": 18}
        ]
    }
    """
    from datetime import datetime, timedelta
    from django.db.models import Avg, Count, Min, Max, Q
    from .models import BlacklistAntifraude, WhitelistAntifraude
    import json
    
    # Parâmetros
    dias = int(request.GET.get('dias', 7))
    data_fim = datetime.now()
    data_inicio = data_fim - timedelta(days=dias)
    
    # Filtro base
    filtro_periodo = Q(created_at__gte=data_inicio, created_at__lte=data_fim)
    
    # 1. Transações
    transacoes_total = TransacaoRisco.objects.filter(
        data_transacao__gte=data_inicio,
        data_transacao__lte=data_fim
    ).count()
    
    transacoes_por_origem = dict(
        TransacaoRisco.objects.filter(
            data_transacao__gte=data_inicio,
            data_transacao__lte=data_fim
        ).values('origem').annotate(total=Count('id')).values_list('origem', 'total')
    )
    
    # 2. Decisões
    decisoes = DecisaoAntifraude.objects.filter(filtro_periodo)
    
    decisoes_stats = decisoes.values('decisao').annotate(total=Count('id'))
    decisoes_dict = {item['decisao']: item['total'] for item in decisoes_stats}
    
    aprovadas = decisoes_dict.get('APROVADO', 0)
    reprovadas = decisoes_dict.get('REPROVADO', 0)
    revisao = decisoes_dict.get('REVISAO', 0)
    total_decisoes = aprovadas + reprovadas + revisao
    
    taxa_aprovacao = (aprovadas / total_decisoes * 100) if total_decisoes > 0 else 0
    
    # 3. Scores
    scores_stats = decisoes.aggregate(
        medio=Avg('score_risco'),
        minimo=Min('score_risco'),
        maximo=Max('score_risco')
    )
    
    # 4. Performance
    tempo_stats = decisoes.aggregate(
        medio=Avg('tempo_analise_ms')
    )
    
    # P95 (aproximado - pegar o percentil 95)
    tempos_ordenados = list(decisoes.order_by('tempo_analise_ms').values_list('tempo_analise_ms', flat=True))
    p95_index = int(len(tempos_ordenados) * 0.95) if tempos_ordenados else 0
    tempo_p95 = tempos_ordenados[p95_index] if p95_index < len(tempos_ordenados) else 0
    
    # 5. Blacklist
    blacklist_total = BlacklistAntifraude.objects.count()
    blacklist_ativos = BlacklistAntifraude.objects.filter(is_active=True).count()
    
    # Contar bloqueios que aconteceram no período
    bloqueios_periodo = DecisaoAntifraude.objects.filter(
        filtro_periodo,
        decisao='REPROVADO',
        regras_acionadas__contains='BLACKLIST'
    ).count()
    
    # 6. Whitelist
    whitelist_total = WhitelistAntifraude.objects.filter(is_active=True).count()
    whitelist_stats = WhitelistAntifraude.objects.filter(is_active=True).values('origem').annotate(total=Count('id'))
    whitelist_dict = {item['origem']: item['total'] for item in whitelist_stats}
    
    # 7. Top regras acionadas
    regras_top = []
    todas_decisoes = decisoes.values_list('regras_acionadas', flat=True)
    regras_count = {}
    
    for regras_json in todas_decisoes:
        if isinstance(regras_json, str):
            try:
                regras_json = json.loads(regras_json)
            except:
                continue
        
        if isinstance(regras_json, list):
            for regra in regras_json:
                if isinstance(regra, dict):
                    nome = regra.get('nome', 'Desconhecida')
                    regras_count[nome] = regras_count.get(nome, 0) + 1
    
    # Top 5 regras
    regras_top = [{'nome': nome, 'acionamentos': count} 
                  for nome, count in sorted(regras_count.items(), key=lambda x: x[1], reverse=True)[:5]]
    
    return Response({
        'periodo': {
            'dias': dias,
            'data_inicio': data_inicio.strftime('%Y-%m-%d'),
            'data_fim': data_fim.strftime('%Y-%m-%d')
        },
        'transacoes': {
            'total': transacoes_total,
            'por_origem': transacoes_por_origem
        },
        'decisoes': {
            'aprovadas': aprovadas,
            'reprovadas': reprovadas,
            'revisao': revisao,
            'total': total_decisoes,
            'taxa_aprovacao': round(taxa_aprovacao, 2)
        },
        'scores': {
            'medio': round(scores_stats['medio'] or 0, 2),
            'minimo': scores_stats['minimo'] or 0,
            'maximo': scores_stats['maximo'] or 0
        },
        'performance': {
            'tempo_medio_ms': int(tempo_stats['medio'] or 0),
            'tempo_p95_ms': tempo_p95
        },
        'blacklist': {
            'total': blacklist_total,
            'ativos': blacklist_ativos,
            'bloqueios_periodo': bloqueios_periodo
        },
        'whitelist': {
            'total': whitelist_total,
            'automaticas': whitelist_dict.get('AUTO', 0),
            'manuais': whitelist_dict.get('MANUAL', 0),
            'vip': whitelist_dict.get('CLIENTE_VIP', 0)
        },
        'regras_top': regras_top
    })
