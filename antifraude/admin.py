"""
Admin do Sistema Antifraude
"""
from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Q
from datetime import datetime, timedelta
from .models import TransacaoRisco, RegraAntifraude, DecisaoAntifraude, BlacklistAntifraude, WhitelistAntifraude


@admin.register(TransacaoRisco)
class TransacaoRiscoAdmin(admin.ModelAdmin):
    list_display = ('transacao_id', 'origem', 'cpf', 'valor', 'modalidade', 'data_transacao', 'created_at')
    list_filter = ('origem', 'modalidade', 'data_transacao')
    search_fields = ('transacao_id', 'cpf', 'ip_address', 'device_fingerprint')
    readonly_fields = ('created_at',)
    date_hierarchy = 'data_transacao'


@admin.register(RegraAntifraude)
class RegraAntifraudeAdmin(admin.ModelAdmin):
    list_display = ('nome', 'tipo', 'peso', 'acao', 'is_active', 'prioridade')
    list_filter = ('tipo', 'acao', 'is_active')
    search_fields = ('nome', 'descricao')
    list_editable = ('is_active', 'prioridade')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(DecisaoAntifraude)
class DecisaoAntifraudeAdmin(admin.ModelAdmin):
    list_display = ('transacao', 'decisao', 'score_risco', 'tempo_analise_ms', 'created_at')
    list_filter = ('decisao', 'created_at')
    search_fields = ('transacao__transacao_id', 'transacao__cpf')
    readonly_fields = ('created_at', 'tempo_analise_ms', 'regras_acionadas')
    date_hierarchy = 'created_at'


@admin.register(BlacklistAntifraude)
class BlacklistAntifraudeAdmin(admin.ModelAdmin):
    list_display = ('status_icon', 'tipo', 'valor_display', 'motivo_short', 'origem', 'permanente_icon', 'data_expiracao', 'created_at')
    list_filter = ('tipo', 'origem', 'permanente', 'is_active', 'created_at')
    search_fields = ('valor', 'motivo')
    list_editable = ('is_active',)
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'
    actions = ['ativar_bloqueios', 'desativar_bloqueios', 'tornar_permanente', 'expirar_em_7_dias']
    
    fieldsets = (
        ('Identificação', {
            'fields': ('tipo', 'valor')
        }),
        ('Detalhes', {
            'fields': ('motivo', 'origem')
        }),
        ('Configuração', {
            'fields': ('permanente', 'data_expiracao', 'is_active')
        }),
        ('Metadados', {
            'fields': ('criado_por', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def status_icon(self, obj):
        if obj.is_active:
            if obj.permanente:
                return format_html('<span style="color: red; font-size: 16px;">🔴🔒</span>')
            else:
                return format_html('<span style="color: orange; font-size: 16px;">🟠⏰</span>')
        return format_html('<span style="color: gray; font-size: 16px;">⚪</span>')
    status_icon.short_description = 'Status'
    
    def valor_display(self, obj):
        if obj.tipo == 'CPF':
            # Mascarar CPF: 123.456.789-00 → 123.***.***-00
            cpf = obj.valor
            if len(cpf) == 11:
                return f"{cpf[:3]}.***.**-{cpf[-2:]}"
        return obj.valor
    valor_display.short_description = 'Valor'
    
    def motivo_short(self, obj):
        return obj.motivo[:50] + '...' if len(obj.motivo) > 50 else obj.motivo
    motivo_short.short_description = 'Motivo'
    
    def permanente_icon(self, obj):
        if obj.permanente:
            return format_html('<span style="color: red;">🔒 Permanente</span>')
        return format_html('<span style="color: orange;">⏰ Temporário</span>')
    permanente_icon.short_description = 'Tipo'
    
    def ativar_bloqueios(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} bloqueio(s) ativado(s).')
    ativar_bloqueios.short_description = '✅ Ativar bloqueios selecionados'
    
    def desativar_bloqueios(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} bloqueio(s) desativado(s).')
    desativar_bloqueios.short_description = '❌ Desativar bloqueios selecionados'
    
    def tornar_permanente(self, request, queryset):
        updated = queryset.update(permanente=True, data_expiracao=None)
        self.message_user(request, f'{updated} bloqueio(s) tornados permanentes.')
    tornar_permanente.short_description = '🔒 Tornar permanente'
    
    def expirar_em_7_dias(self, request, queryset):
        data_exp = datetime.now() + timedelta(days=7)
        updated = queryset.update(permanente=False, data_expiracao=data_exp)
        self.message_user(request, f'{updated} bloqueio(s) configurados para expirar em 7 dias.')
    expirar_em_7_dias.short_description = '⏰ Expirar em 7 dias'


@admin.register(WhitelistAntifraude)
class WhitelistAntifraudeAdmin(admin.ModelAdmin):
    list_display = ('status_icon', 'tipo', 'valor_display', 'origem_icon', 'cliente_id', 'transacoes_aprovadas', 'ultima_transacao', 'created_at')
    list_filter = ('tipo', 'origem', 'is_active', 'created_at')
    search_fields = ('valor', 'cliente_id')
    list_editable = ('is_active',)
    readonly_fields = ('transacoes_aprovadas', 'ultima_transacao', 'created_at', 'updated_at')
    date_hierarchy = 'created_at'
    actions = ['ativar_whitelist', 'desativar_whitelist', 'resetar_contador']
    
    fieldsets = (
        ('Identificação', {
            'fields': ('tipo', 'valor', 'cliente_id')
        }),
        ('Origem', {
            'fields': ('origem', 'motivo')
        }),
        ('Estatísticas', {
            'fields': ('transacoes_aprovadas', 'ultima_transacao'),
            'classes': ('collapse',)
        }),
        ('Controle', {
            'fields': ('is_active', 'criado_por')
        }),
        ('Metadados', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def status_icon(self, obj):
        if obj.is_active:
            return format_html('<span style="color: green; font-size: 16px;">✅</span>')
        return format_html('<span style="color: gray; font-size: 16px;">⚪</span>')
    status_icon.short_description = 'Status'
    
    def valor_display(self, obj):
        if obj.tipo == 'CPF':
            cpf = obj.valor
            if len(cpf) == 11:
                return f"{cpf[:3]}.***.**-{cpf[-2:]}"
        return obj.valor
    valor_display.short_description = 'Valor'
    
    def origem_icon(self, obj):
        icons = {
            'MANUAL': '👤 Manual',
            'AUTO': '🤖 Automática',
            'CLIENTE_VIP': '⭐ VIP'
        }
        origem_text = icons.get(obj.origem, obj.origem)
        
        if obj.origem == 'AUTO':
            return format_html('<span style="color: blue;">{}</span>', origem_text)
        elif obj.origem == 'CLIENTE_VIP':
            return format_html('<span style="color: gold;">{}</span>', origem_text)
        return origem_text
    origem_icon.short_description = 'Origem'
    
    def ativar_whitelist(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} whitelist(s) ativada(s).')
    ativar_whitelist.short_description = '✅ Ativar whitelist selecionadas'
    
    def desativar_whitelist(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} whitelist(s) desativada(s).')
    desativar_whitelist.short_description = '❌ Desativar whitelist selecionadas'
    
    def resetar_contador(self, request, queryset):
        updated = queryset.update(transacoes_aprovadas=0)
        self.message_user(request, f'{updated} contador(es) resetado(s).')
    resetar_contador.short_description = '🔄 Resetar contador de transações'
