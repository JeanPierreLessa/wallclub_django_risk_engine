"""
Service: Whitelist Automática
Semana 12: Cria whitelist automática após 10+ transações aprovadas
"""
from datetime import datetime, timedelta
from django.db.models import Count, Q
from .models import TransacaoRisco, DecisaoAntifraude, WhitelistAntifraude
import logging

logger = logging.getLogger(__name__)


class WhitelistAutoService:
    """
    Gerencia criação automática de whitelist baseada em histórico positivo
    """
    
    # Configurações
    MIN_TRANSACOES_APROVADAS = 10
    JANELA_DIAS = 30
    
    @staticmethod
    def verificar_e_criar_whitelist(transacao: TransacaoRisco, decisao: DecisaoAntifraude):
        """
        Verifica se cliente/IP/device deve ser adicionado à whitelist automática
        Chama este método após cada transação APROVADA
        
        Args:
            transacao: TransacaoRisco aprovada
            decisao: DecisaoAntifraude com decisao='APROVADO'
        """
        if decisao.decisao != 'APROVADO':
            return
        
        # Verificar cada tipo de whitelist
        WhitelistAutoService._verificar_cpf(transacao)
        WhitelistAutoService._verificar_ip(transacao)
        WhitelistAutoService._verificar_device(transacao)
    
    @staticmethod
    def _verificar_cpf(transacao: TransacaoRisco):
        """Verifica e cria whitelist de CPF se necessário"""
        if not transacao.cpf:
            return
        
        # Verificar se já existe whitelist ativa para este CPF
        whitelist_existente = WhitelistAntifraude.objects.filter(
            tipo='CPF',
            valor=transacao.cpf,
            is_active=True
        ).first()
        
        if whitelist_existente:
            # Atualizar contador e última transação
            whitelist_existente.transacoes_aprovadas += 1
            whitelist_existente.ultima_transacao = datetime.now()
            whitelist_existente.save()
            
            logger.info(f"Whitelist CPF atualizada: {transacao.cpf} - Total: {whitelist_existente.transacoes_aprovadas}")
            return
        
        # Contar transações aprovadas nos últimos 30 dias
        janela_inicio = datetime.now() - timedelta(days=WhitelistAutoService.JANELA_DIAS)
        
        transacoes_aprovadas = DecisaoAntifraude.objects.filter(
            transacao__cpf=transacao.cpf,
            transacao__data_transacao__gte=janela_inicio,
            decisao='APROVADO'
        ).count()
        
        # Criar whitelist se atingiu mínimo
        if transacoes_aprovadas >= WhitelistAutoService.MIN_TRANSACOES_APROVADAS:
            WhitelistAntifraude.objects.create(
                tipo='CPF',
                valor=transacao.cpf,
                cliente_id=transacao.cliente_id,
                origem='AUTO',
                transacoes_aprovadas=transacoes_aprovadas,
                ultima_transacao=datetime.now(),
                is_active=True,
                motivo=f'Whitelist automática: {transacoes_aprovadas} transações aprovadas em {WhitelistAutoService.JANELA_DIAS} dias'
            )
            
            logger.info(f"✅ Whitelist CPF criada automaticamente: {transacao.cpf} - {transacoes_aprovadas} aprovações")
    
    @staticmethod
    def _verificar_ip(transacao: TransacaoRisco):
        """Verifica e cria whitelist de IP se necessário"""
        if not transacao.ip_address:
            return
        
        # Verificar se já existe whitelist ativa para este IP
        whitelist_existente = WhitelistAntifraude.objects.filter(
            tipo='IP',
            valor=str(transacao.ip_address),
            is_active=True
        ).first()
        
        if whitelist_existente:
            whitelist_existente.transacoes_aprovadas += 1
            whitelist_existente.ultima_transacao = datetime.now()
            whitelist_existente.save()
            return
        
        # Contar transações aprovadas deste IP (mesmo CPF) nos últimos 30 dias
        janela_inicio = datetime.now() - timedelta(days=WhitelistAutoService.JANELA_DIAS)
        
        transacoes_aprovadas = DecisaoAntifraude.objects.filter(
            transacao__ip_address=str(transacao.ip_address),
            transacao__cpf=transacao.cpf,  # Mesmo CPF (evitar IPs públicos)
            transacao__data_transacao__gte=janela_inicio,
            decisao='APROVADO'
        ).count()
        
        # Criar whitelist se atingiu mínimo
        if transacoes_aprovadas >= WhitelistAutoService.MIN_TRANSACOES_APROVADAS:
            WhitelistAntifraude.objects.create(
                tipo='IP',
                valor=str(transacao.ip_address),
                cliente_id=transacao.cliente_id,
                origem='AUTO',
                transacoes_aprovadas=transacoes_aprovadas,
                ultima_transacao=datetime.now(),
                is_active=True,
                motivo=f'Whitelist automática: {transacoes_aprovadas} transações aprovadas do mesmo CPF'
            )
            
            logger.info(f"✅ Whitelist IP criada automaticamente: {transacao.ip_address}")
    
    @staticmethod
    def _verificar_device(transacao: TransacaoRisco):
        """Verifica e cria whitelist de dispositivo se necessário"""
        if not transacao.device_fingerprint:
            return
        
        # Verificar se já existe whitelist ativa para este device
        whitelist_existente = WhitelistAntifraude.objects.filter(
            tipo='DEVICE',
            valor=transacao.device_fingerprint,
            is_active=True
        ).first()
        
        if whitelist_existente:
            whitelist_existente.transacoes_aprovadas += 1
            whitelist_existente.ultima_transacao = datetime.now()
            whitelist_existente.save()
            return
        
        # Contar transações aprovadas deste device (mesmo CPF) nos últimos 30 dias
        janela_inicio = datetime.now() - timedelta(days=WhitelistAutoService.JANELA_DIAS)
        
        transacoes_aprovadas = DecisaoAntifraude.objects.filter(
            transacao__device_fingerprint=transacao.device_fingerprint,
            transacao__cpf=transacao.cpf,  # Mesmo CPF
            transacao__data_transacao__gte=janela_inicio,
            decisao='APROVADO'
        ).count()
        
        # Criar whitelist se atingiu mínimo
        if transacoes_aprovadas >= WhitelistAutoService.MIN_TRANSACOES_APROVADAS:
            WhitelistAntifraude.objects.create(
                tipo='DEVICE',
                valor=transacao.device_fingerprint,
                cliente_id=transacao.cliente_id,
                origem='AUTO',
                transacoes_aprovadas=transacoes_aprovadas,
                ultima_transacao=datetime.now(),
                is_active=True,
                motivo=f'Whitelist automática: {transacoes_aprovadas} transações aprovadas do mesmo CPF'
            )
            
            logger.info(f"✅ Whitelist DEVICE criada automaticamente: {transacao.device_fingerprint}")
    
    @staticmethod
    def limpar_whitelists_inativas():
        """
        Remove whitelists automáticas sem atividade há mais de 90 dias
        Executar periodicamente (cron job)
        """
        data_limite = datetime.now() - timedelta(days=90)
        
        removidas = WhitelistAntifraude.objects.filter(
            origem='AUTO',
            ultima_transacao__lt=data_limite,
            is_active=True
        ).update(is_active=False)
        
        logger.info(f"🧹 Limpeza: {removidas} whitelists automáticas desativadas (90+ dias sem uso)")
        
        return removidas
