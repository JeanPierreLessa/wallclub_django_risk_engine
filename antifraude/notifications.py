"""
Sistema de Notificações para Revisões Manuais
"""
import requests
from django.conf import settings
from django.core.mail import send_mail
from datetime import datetime


class NotificacaoService:
    """Notifica equipe quando transação precisa de revisão manual"""
    
    @staticmethod
    def notificar_revisao_pendente(decisao):
        """
        Envia notificações sobre decisão pendente de revisão
        
        Args:
            decisao: DecisaoAntifraude instance
        """
        transacao = decisao.transacao
        
        mensagem = f"""
        🔴 REVISÃO MANUAL NECESSÁRIA
        
        Transação ID: {transacao.transacao_id}
        Origem: {transacao.origem}
        Cliente ID: {transacao.cliente_id}
        CPF: {transacao.cpf}
        Valor: R$ {transacao.valor}
        Score de Risco: {decisao.score_risco}/100
        
        Motivo: {decisao.motivo}
        
        Regras Acionadas:
        {NotificacaoService._formatar_regras(decisao.regras_acionadas)}
        
        Acesse o painel admin para revisar.
        """
        
        # Email
        NotificacaoService._enviar_email(mensagem)
        
        # Slack (se configurado)
        NotificacaoService._enviar_slack(mensagem, decisao)
    
    @staticmethod
    def _formatar_regras(regras):
        """Formata lista de regras para exibição"""
        if not regras:
            return "Nenhuma"
        
        linhas = []
        for regra in regras:
            linhas.append(f"- {regra['nome']} (Peso: {regra['peso']}, Ação: {regra['acao']})")
        
        return "\n".join(linhas)
    
    @staticmethod
    def _enviar_email(mensagem):
        """Envia email para equipe"""
        try:
            send_mail(
                subject='[ANTIFRAUDE] Revisão Manual Necessária',
                message=mensagem,
                from_email='noreply@wallclub.com.br',
                recipient_list=[settings.NOTIFICACAO_EMAIL],
                fail_silently=True
            )
        except Exception as e:
            print(f"Erro ao enviar email: {e}")
    
    @staticmethod
    def _enviar_slack(mensagem, decisao):
        """Envia mensagem para Slack"""
        if not settings.SLACK_WEBHOOK_URL:
            return
        
        try:
            payload = {
                "text": mensagem,
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*🔴 REVISÃO MANUAL NECESSÁRIA*\n\nTransação: `{decisao.transacao.transacao_id}`\nScore: *{decisao.score_risco}/100*"
                        }
                    },
                    {
                        "type": "section",
                        "fields": [
                            {"type": "mrkdwn", "text": f"*Cliente:*\n{decisao.transacao.cpf}"},
                            {"type": "mrkdwn", "text": f"*Valor:*\nR$ {decisao.transacao.valor}"},
                            {"type": "mrkdwn", "text": f"*Origem:*\n{decisao.transacao.origem}"},
                            {"type": "mrkdwn", "text": f"*Score:*\n{decisao.score_risco}/100"}
                        ]
                    }
                ]
            }
            
            requests.post(settings.SLACK_WEBHOOK_URL, json=payload, timeout=5)
        except Exception as e:
            print(f"Erro ao enviar Slack: {e}")
    
    @staticmethod
    def notificar_app_principal(decisao):
        """
        Callback para app principal após revisão manual
        
        Args:
            decisao: DecisaoAntifraude instance
        """
        if not decisao.revisado_por:
            return  # Só notifica após revisão manual
        
        try:
            payload = {
                'transacao_id': decisao.transacao.transacao_id,
                'decisao_final': decisao.decisao,
                'score_risco': decisao.score_risco,
                'revisado_por': decisao.revisado_por,
                'revisado_em': decisao.revisado_em.isoformat() if decisao.revisado_em else None,
                'observacao': decisao.observacao_revisao
            }
            
            url = f"{settings.CALLBACK_URL_PRINCIPAL}/api/antifraude/callback/"
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code != 200:
                print(f"Erro no callback: {response.status_code} - {response.text}")
        
        except Exception as e:
            print(f"Erro ao notificar app principal: {e}")
