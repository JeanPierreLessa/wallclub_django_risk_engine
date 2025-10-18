"""
URLs do Sistema Antifraude
"""
from django.urls import path
from . import views, views_revisao, views_teste, views_api, views_seguranca

urlpatterns = [
    # API REST Pública (Semana 13)
    path('analyze/', views_api.analyze, name='antifraude_analyze'),
    path('decision/<str:transacao_id>/', views_api.decision, name='antifraude_decision'),
    path('validate-3ds/', views_api.validate_3ds, name='antifraude_validate_3ds'),
    path('health/', views_api.health, name='antifraude_health'),

    # Análise automática (legado - manter compatibilidade)
    path('analisar/', views.analisar_transacao, name='antifraude_analisar'),
    path('decisao/<str:transacao_id>/', views.consultar_decisao, name='antifraude_decisao'),
    path('historico/<int:cliente_id>/', views.historico_cliente, name='antifraude_historico'),
    path('dashboard/', views.dashboard_metricas, name='antifraude_dashboard'),
    
    # Revisão manual
    path('revisao/pendentes/', views_revisao.listar_pendentes, name='revisao_pendentes'),
    path('revisao/<int:decisao_id>/aprovar/', views_revisao.aprovar_revisao, name='revisao_aprovar'),
    path('revisao/<int:decisao_id>/reprovar/', views_revisao.reprovar_revisao, name='revisao_reprovar'),
    path('revisao/historico/', views_revisao.historico_revisoes, name='revisao_historico'),
    
    # Endpoints de teste (Semana 8)
    path('teste/normalizar/', views_teste.testar_normalizacao, name='teste_normalizacao'),
    path('teste/bin/', views_teste.testar_extracao_bin, name='teste_bin'),
    path('teste/exemplos/', views_teste.exemplo_payloads, name='teste_exemplos'),
    
    # APIs de Segurança (Semana 23)
    path('validate-login/', views_seguranca.validate_login, name='seguranca_validate_login'),
    path('suspicious/', views_seguranca.list_suspicious, name='seguranca_list_suspicious'),
    path('block/', views_seguranca.create_block, name='seguranca_create_block'),
    path('investigate/', views_seguranca.investigate_activity, name='seguranca_investigate'),
    path('blocks/', views_seguranca.list_blocks, name='seguranca_list_blocks'),
]
