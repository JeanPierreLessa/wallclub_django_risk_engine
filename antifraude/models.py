"""
Models para Sistema Antifraude
Fase 2 - Semana 7: Estrutura base de análise de risco
"""
from django.db import models
from datetime import datetime


class TransacaoRisco(models.Model):
    """
    Armazena dados de transações para análise de risco
    Normaliza dados de POS, App e Web em formato único
    """
    
    # Identificação
    transacao_id = models.CharField(max_length=100, db_index=True, help_text="ID único da transação (NSU, order_id, etc)")
    origem = models.CharField(max_length=20, choices=[
        ('POS', 'Terminal POS'),
        ('APP', 'Aplicativo Mobile'),
        ('WEB', 'Checkout Web')
    ], db_index=True)
    
    # Dados do Cliente
    cliente_id = models.IntegerField(null=True, blank=True, db_index=True)
    cpf = models.CharField(max_length=11, db_index=True)
    cliente_nome = models.CharField(max_length=200, null=True, blank=True)
    
    # Dados da Transação
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    modalidade = models.CharField(max_length=20, help_text="PIX, CREDITO, DEBITO, etc")
    parcelas = models.IntegerField(default=1)
    
    # Dados de Localização
    ip_address = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    device_fingerprint = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    user_agent = models.TextField(null=True, blank=True)
    
    # Dados do Cartão (se aplicável)
    bin_cartao = models.CharField(max_length=6, null=True, blank=True, db_index=True, help_text="Primeiros 6 dígitos")
    bandeira = models.CharField(max_length=50, null=True, blank=True)
    
    # Dados de Contexto
    loja_id = models.IntegerField(null=True, blank=True, db_index=True)
    canal_id = models.IntegerField(null=True, blank=True, db_index=True)
    terminal = models.CharField(max_length=50, null=True, blank=True)
    
    # Timestamps
    data_transacao = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'antifraude_transacao_risco'
        verbose_name = 'Transação de Risco'
        verbose_name_plural = 'Transações de Risco'
        ordering = ['-data_transacao']
        indexes = [
            models.Index(fields=['cpf', 'data_transacao']),
            models.Index(fields=['ip_address', 'data_transacao']),
            models.Index(fields=['device_fingerprint', 'data_transacao']),
            models.Index(fields=['bin_cartao', 'data_transacao']),
        ]
    
    def __str__(self):
        return f"{self.origem} - {self.transacao_id} - R$ {self.valor}"


class RegraAntifraude(models.Model):
    """
    Regras configuráveis de antifraude
    """
    
    # Identificação
    nome = models.CharField(max_length=100, unique=True)
    descricao = models.TextField()
    tipo = models.CharField(max_length=50, choices=[
        ('VELOCIDADE', 'Velocidade de Transações'),
        ('VALOR', 'Valor Suspeito'),
        ('LOCALIZACAO', 'Localização Anômala'),
        ('DISPOSITIVO', 'Dispositivo Novo/Suspeito'),
        ('HORARIO', 'Horário Incomum'),
        ('CARTAO', 'Cartão Suspeito'),
        ('CUSTOM', 'Regra Customizada')
    ], db_index=True)
    
    # Configuração da Regra
    parametros = models.JSONField(help_text="Parâmetros da regra em JSON")
    peso = models.IntegerField(default=1, help_text="Peso da regra no score final (1-10)")
    acao = models.CharField(max_length=20, choices=[
        ('APROVAR', 'Aprovar Automaticamente'),
        ('REPROVAR', 'Reprovar Automaticamente'),
        ('REVISAR', 'Solicitar Revisão Manual'),
        ('ALERTAR', 'Alertar mas Aprovar')
    ], default='ALERTAR')
    
    # Controle
    is_active = models.BooleanField(default=True, db_index=True)
    prioridade = models.IntegerField(default=50, help_text="Ordem de execução (1-100)")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'antifraude_regra'
        verbose_name = 'Regra Antifraude'
        verbose_name_plural = 'Regras Antifraude'
        ordering = ['prioridade', 'nome']
    
    def __str__(self):
        status = "🟢" if self.is_active else "🔴"
        return f"{status} {self.nome} ({self.tipo}) - Peso: {self.peso}"


class DecisaoAntifraude(models.Model):
    """
    Decisões tomadas pelo sistema antifraude
    """
    
    # Referência
    transacao = models.ForeignKey(TransacaoRisco, on_delete=models.CASCADE, related_name='decisoes')
    
    # Análise
    score_risco = models.IntegerField(help_text="Score de 0-100 (maior = mais arriscado)")
    decisao = models.CharField(max_length=20, choices=[
        ('APROVADO', 'Aprovado'),
        ('REPROVADO', 'Reprovado'),
        ('REVISAO', 'Em Revisão Manual'),
        ('PENDENTE', 'Pendente de Análise')
    ], db_index=True)
    
    # Detalhes
    regras_acionadas = models.JSONField(help_text="Lista de regras que dispararam")
    motivo = models.TextField(help_text="Motivo da decisão")
    tempo_analise_ms = models.IntegerField(help_text="Tempo de análise em milissegundos")
    
    # Revisão Manual (se aplicável)
    revisado_por = models.IntegerField(null=True, blank=True, help_text="ID do usuário que revisou")
    revisado_em = models.DateTimeField(null=True, blank=True)
    observacao_revisao = models.TextField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        db_table = 'antifraude_decisao'
        verbose_name = 'Decisão Antifraude'
        verbose_name_plural = 'Decisões Antifraude'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['decisao', 'created_at']),
            models.Index(fields=['score_risco', 'created_at']),
        ]
    
    def __str__(self):
        emoji = {
            'APROVADO': '✅',
            'REPROVADO': '❌',
            'REVISAO': '⚠️',
            'PENDENTE': '⏳'
        }.get(self.decisao, '❓')
        return f"{emoji} {self.transacao.transacao_id} - Score: {self.score_risco}"


class BlacklistAntifraude(models.Model):
    """
    Lista negra de CPFs, IPs, dispositivos bloqueados
    """
    
    # Tipo de Bloqueio
    tipo = models.CharField(max_length=20, choices=[
        ('CPF', 'CPF Bloqueado'),
        ('IP', 'IP Bloqueado'),
        ('DEVICE', 'Dispositivo Bloqueado'),
        ('BIN', 'BIN de Cartão Bloqueado'),
        ('EMAIL', 'Email Bloqueado')
    ], db_index=True)
    
    # Valor Bloqueado
    valor = models.CharField(max_length=255, db_index=True, help_text="CPF, IP, device_fingerprint, etc")
    
    # Motivo e Contexto
    motivo = models.TextField(help_text="Por que foi bloqueado")
    origem = models.CharField(max_length=50, default='MANUAL', help_text="MANUAL, AUTO_FRAUDE, BUREAU, etc")
    
    # Severidade
    permanente = models.BooleanField(default=True, help_text="Se False, expira após data_expiracao")
    data_expiracao = models.DateTimeField(null=True, blank=True, help_text="Quando bloqueio expira (se não permanente)")
    
    # Controle
    is_active = models.BooleanField(default=True, db_index=True)
    criado_por = models.IntegerField(null=True, blank=True, help_text="ID do usuário que criou")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'antifraude_blacklist'
        verbose_name = 'Blacklist'
        verbose_name_plural = 'Blacklist'
        unique_together = [['tipo', 'valor']]
        indexes = [
            models.Index(fields=['tipo', 'valor', 'is_active']),
        ]
    
    def __str__(self):
        status = "🔴" if self.is_active else "⚪"
        permanencia = "🔒" if self.permanente else "⏰"
        return f"{status}{permanencia} {self.tipo}: {self.valor}"


class WhitelistAntifraude(models.Model):
    """
    Lista branca de CPFs, IPs confiáveis
    Pode ser manual (criado por admin) ou automática (10+ transações aprovadas)
    """
    
    # Tipo
    tipo = models.CharField(max_length=20, choices=[
        ('CPF', 'CPF Confiável'),
        ('IP', 'IP Confiável'),
        ('DEVICE', 'Dispositivo Confiável'),
        ('EMAIL', 'Email Confiável')
    ], db_index=True)
    
    # Valor
    valor = models.CharField(max_length=255, db_index=True)
    
    # Cliente Relacionado
    cliente_id = models.IntegerField(null=True, blank=True, db_index=True)
    
    # Origem
    origem = models.CharField(max_length=50, choices=[
        ('MANUAL', 'Adicionado Manualmente'),
        ('AUTO', 'Whitelist Automática (10+ trans OK)'),
        ('CLIENTE_VIP', 'Cliente VIP/Premium')
    ], default='MANUAL')
    
    # Estatísticas (se automático)
    transacoes_aprovadas = models.IntegerField(default=0, help_text="Contador de transações aprovadas")
    ultima_transacao = models.DateTimeField(null=True, blank=True)
    
    # Controle
    is_active = models.BooleanField(default=True, db_index=True)
    criado_por = models.IntegerField(null=True, blank=True)
    motivo = models.TextField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'antifraude_whitelist'
        verbose_name = 'Whitelist'
        verbose_name_plural = 'Whitelist'
        unique_together = [['tipo', 'valor']]
        indexes = [
            models.Index(fields=['tipo', 'valor', 'is_active']),
            models.Index(fields=['cliente_id', 'is_active']),
        ]
    
    def __str__(self):
        status = "✅" if self.is_active else "⚪"
        origem_emoji = {"MANUAL": "👤", "AUTO": "🤖", "CLIENTE_VIP": "⭐"}.get(self.origem, "")
        return f"{status}{origem_emoji} {self.tipo}: {self.valor}"
