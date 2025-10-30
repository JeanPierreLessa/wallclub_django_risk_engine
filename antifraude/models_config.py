"""
Configurações centralizadas do sistema antifraude
Evita valores hardcoded espalhados pelo código
"""
from django.db import models
from django.core.exceptions import ValidationError


class ConfiguracaoAntifraude(models.Model):
    """
    Configurações globais do sistema antifraude
    Todos os parâmetros de regras devem estar aqui
    """
    
    # Identificação
    chave = models.CharField(
        max_length=100, 
        unique=True, 
        db_index=True,
        help_text="Chave única da configuração (ex: VALOR_ALTO_MINIMO)"
    )
    descricao = models.TextField(
        help_text="Descrição do que esta configuração controla"
    )
    categoria = models.CharField(
        max_length=50,
        choices=[
            ('VALOR', 'Limites de Valor'),
            ('DISPOSITIVO', 'Dispositivo e Fingerprint'),
            ('LOCALIZACAO', 'IP e Localização'),
            ('VELOCIDADE', 'Velocidade de Transações'),
            ('AUTENTICACAO', 'Autenticação e Login'),
            ('SCORE', 'Score e Limites de Decisão'),
            ('GERAL', 'Configurações Gerais')
        ],
        db_index=True
    )
    
    # Valor da configuração
    tipo_valor = models.CharField(
        max_length=20,
        choices=[
            ('INT', 'Número Inteiro'),
            ('FLOAT', 'Número Decimal'),
            ('BOOL', 'Booleano'),
            ('STRING', 'Texto'),
            ('JSON', 'JSON')
        ]
    )
    valor_texto = models.TextField(
        help_text="Valor armazenado como texto (será convertido conforme tipo_valor)"
    )
    
    # Controle
    is_active = models.BooleanField(default=True)
    alterado_por = models.IntegerField(null=True, blank=True, help_text="ID do usuário que alterou")
    
    # Auditoria
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'antifraude_configuracao'
        verbose_name = 'Configuração Antifraude'
        verbose_name_plural = 'Configurações Antifraude'
        ordering = ['categoria', 'chave']
        indexes = [
            models.Index(fields=['categoria', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.chave} = {self.valor_texto}"
    
    def get_valor(self):
        """Retorna valor convertido para o tipo correto"""
        try:
            if self.tipo_valor == 'INT':
                return int(self.valor_texto)
            elif self.tipo_valor == 'FLOAT':
                return float(self.valor_texto)
            elif self.tipo_valor == 'BOOL':
                return self.valor_texto.lower() in ['true', '1', 'sim', 'yes']
            elif self.tipo_valor == 'JSON':
                import json
                return json.loads(self.valor_texto)
            else:  # STRING
                return self.valor_texto
        except (ValueError, TypeError) as e:
            raise ValidationError(f"Erro ao converter valor: {str(e)}")
    
    @classmethod
    def get_config(cls, chave, default=None):
        """
        Busca configuração por chave
        
        Args:
            chave: Chave da configuração
            default: Valor padrão se não encontrar
        
        Returns:
            Valor convertido ou default
        """
        try:
            config = cls.objects.get(chave=chave, is_active=True)
            return config.get_valor()
        except cls.DoesNotExist:
            return default
    
    @classmethod
    def get_configs_categoria(cls, categoria):
        """
        Retorna todas configurações de uma categoria
        
        Args:
            categoria: Categoria das configurações
        
        Returns:
            dict: {chave: valor}
        """
        configs = cls.objects.filter(categoria=categoria, is_active=True)
        return {config.chave: config.get_valor() for config in configs}


class HistoricoConfiguracao(models.Model):
    """
    Auditoria de alterações em configurações
    Rastreabilidade de mudanças críticas
    """
    configuracao = models.ForeignKey(
        ConfiguracaoAntifraude,
        on_delete=models.CASCADE,
        related_name='historico'
    )
    
    # Estado anterior
    valor_anterior = models.TextField()
    
    # Estado novo
    valor_novo = models.TextField()
    
    # Contexto
    alterado_por = models.IntegerField(help_text="ID do usuário")
    motivo = models.TextField(help_text="Motivo da alteração")
    
    # Timestamp
    alterado_em = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        db_table = 'antifraude_historico_config'
        verbose_name = 'Histórico de Configuração'
        verbose_name_plural = 'Histórico de Configurações'
        ordering = ['-alterado_em']
    
    def __str__(self):
        return f"{self.configuracao.chave}: {self.valor_anterior} → {self.valor_novo}"
