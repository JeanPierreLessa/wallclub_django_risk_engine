"""
Views para Revisão Manual de Transações
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from datetime import datetime
from .models import DecisaoAntifraude
from .notifications import NotificacaoService


@api_view(['GET'])
def listar_pendentes(request):
    """
    Lista todas as transações aguardando revisão manual
    
    GET /api/antifraude/revisao/pendentes/
    """
    decisoes = DecisaoAntifraude.objects.filter(
        decisao='REVISAO',
        revisado_por__isnull=True
    ).select_related('transacao').order_by('-created_at')
    
    resultado = []
    for decisao in decisoes:
        transacao = decisao.transacao
        resultado.append({
            'id': decisao.id,
            'transacao_id': transacao.transacao_id,
            'origem': transacao.origem,
            'cliente_id': transacao.cliente_id,
            'cpf': transacao.cpf,
            'valor': str(transacao.valor),
            'modalidade': transacao.modalidade,
            'score_risco': decisao.score_risco,
            'motivo': decisao.motivo,
            'regras_acionadas': decisao.regras_acionadas,
            'data_transacao': transacao.data_transacao.isoformat(),
            'created_at': decisao.created_at.isoformat()
        })
    
    return Response({
        'total': len(resultado),
        'pendentes': resultado
    })


@api_view(['POST'])
def aprovar_revisao(request, decisao_id):
    """
    Aprova transação após revisão manual
    
    POST /api/antifraude/revisao/<decisao_id>/aprovar/
    
    Body:
    {
        "usuario_id": 123,
        "observacao": "Cliente verificado por telefone"
    }
    """
    decisao = get_object_or_404(DecisaoAntifraude, id=decisao_id)
    
    if decisao.revisado_por:
        return Response({
            'erro': 'Transação já foi revisada'
        }, status=400)
    
    # Atualizar decisão
    decisao.decisao = 'APROVADO'
    decisao.revisado_por = request.data.get('usuario_id')
    decisao.revisado_em = datetime.now()
    decisao.observacao_revisao = request.data.get('observacao', '')
    decisao.save()
    
    # Notificar app principal
    NotificacaoService.notificar_app_principal(decisao)
    
    return Response({
        'mensagem': 'Transação aprovada com sucesso',
        'transacao_id': decisao.transacao.transacao_id,
        'decisao_final': 'APROVADO'
    })


@api_view(['POST'])
def reprovar_revisao(request, decisao_id):
    """
    Reprova transação após revisão manual
    
    POST /api/antifraude/revisao/<decisao_id>/reprovar/
    
    Body:
    {
        "usuario_id": 123,
        "observacao": "CPF em blacklist de outras operadoras"
    }
    """
    decisao = get_object_or_404(DecisaoAntifraude, id=decisao_id)
    
    if decisao.revisado_por:
        return Response({
            'erro': 'Transação já foi revisada'
        }, status=400)
    
    # Atualizar decisão
    decisao.decisao = 'REPROVADO'
    decisao.revisado_por = request.data.get('usuario_id')
    decisao.revisado_em = datetime.now()
    decisao.observacao_revisao = request.data.get('observacao', '')
    decisao.save()
    
    # Notificar app principal
    NotificacaoService.notificar_app_principal(decisao)
    
    return Response({
        'mensagem': 'Transação reprovada',
        'transacao_id': decisao.transacao.transacao_id,
        'decisao_final': 'REPROVADO'
    })


@api_view(['GET'])
def historico_revisoes(request):
    """
    Histórico de revisões realizadas
    
    GET /api/antifraude/revisao/historico/?limit=50
    """
    limit = int(request.GET.get('limit', 50))
    
    decisoes = DecisaoAntifraude.objects.filter(
        revisado_por__isnull=False
    ).select_related('transacao').order_by('-revisado_em')[:limit]
    
    resultado = []
    for decisao in decisoes:
        transacao = decisao.transacao
        resultado.append({
            'id': decisao.id,
            'transacao_id': transacao.transacao_id,
            'cpf': transacao.cpf,
            'valor': str(transacao.valor),
            'score_risco': decisao.score_risco,
            'decisao_original': 'REVISAO',
            'decisao_final': decisao.decisao,
            'revisado_por': decisao.revisado_por,
            'revisado_em': decisao.revisado_em.isoformat() if decisao.revisado_em else None,
            'observacao': decisao.observacao_revisao
        })
    
    return Response({
        'total': len(resultado),
        'revisoes': resultado
    })
