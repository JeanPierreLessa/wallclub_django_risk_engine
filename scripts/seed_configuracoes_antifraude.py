"""
Script para popular configurações iniciais do antifraude
Centraliza todos os parâmetros usados nas regras

Uso:
    python manage.py shell < scripts/seed_configuracoes_antifraude.py
"""
import os
import sys
import django

# Setup Django
sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'riskengine.settings')
django.setup()

from antifraude.models_config import ConfiguracaoAntifraude


def seed_configuracoes():
    """Popula configurações iniciais do antifraude"""
    
    configuracoes = [
        # CATEGORIA: VALOR
        {
            'chave': 'VALOR_ALTO_MINIMO',
            'descricao': 'Valor mínimo para considerar transação de alto valor (requer mais validações)',
            'categoria': 'VALOR',
            'tipo_valor': 'FLOAT',
            'valor_texto': '500.00'
        },
        {
            'chave': 'VALOR_MUITO_ALTO_MINIMO',
            'descricao': 'Valor mínimo para considerar transação de valor muito alto (revisão obrigatória)',
            'categoria': 'VALOR',
            'tipo_valor': 'FLOAT',
            'valor_texto': '2000.00'
        },
        {
            'chave': 'VALOR_SUSPEITO_PERCENTIL',
            'descricao': 'Percentil para identificar valores suspeitos para o cliente (padrão histórico)',
            'categoria': 'VALOR',
            'tipo_valor': 'FLOAT',
            'valor_texto': '90.0'
        },
        
        # CATEGORIA: DISPOSITIVO
        {
            'chave': 'DISPOSITIVO_NOVO_DIAS',
            'descricao': 'Número de dias para considerar dispositivo como novo',
            'categoria': 'DISPOSITIVO',
            'tipo_valor': 'INT',
            'valor_texto': '7'
        },
        {
            'chave': 'DISPOSITIVO_MIN_TRANSACOES_CONFIAVEL',
            'descricao': 'Número mínimo de transações aprovadas para considerar dispositivo confiável',
            'categoria': 'DISPOSITIVO',
            'tipo_valor': 'INT',
            'valor_texto': '10'
        },
        {
            'chave': 'DISPOSITIVO_MAX_TENTATIVAS_FALHAS',
            'descricao': 'Máximo de tentativas falhas permitidas em um dispositivo antes de bloquear',
            'categoria': 'DISPOSITIVO',
            'tipo_valor': 'INT',
            'valor_texto': '5'
        },
        
        # CATEGORIA: LOCALIZACAO
        {
            'chave': 'IP_NOVO_DIAS',
            'descricao': 'Número de dias para considerar IP como novo',
            'categoria': 'LOCALIZACAO',
            'tipo_valor': 'INT',
            'valor_texto': '3'
        },
        {
            'chave': 'IP_MAX_TENTATIVAS_HORA',
            'descricao': 'Máximo de tentativas de login por IP na última hora',
            'categoria': 'LOCALIZACAO',
            'tipo_valor': 'INT',
            'valor_texto': '10'
        },
        {
            'chave': 'IP_MAX_TRANSACOES_DIA',
            'descricao': 'Máximo de transações permitidas por IP por dia',
            'categoria': 'LOCALIZACAO',
            'tipo_valor': 'INT',
            'valor_texto': '50'
        },
        
        # CATEGORIA: VELOCIDADE
        {
            'chave': 'VELOCIDADE_MAX_TRANSACOES_HORA',
            'descricao': 'Máximo de transações por cliente na última hora',
            'categoria': 'VELOCIDADE',
            'tipo_valor': 'INT',
            'valor_texto': '5'
        },
        {
            'chave': 'VELOCIDADE_MAX_TRANSACOES_DIA',
            'descricao': 'Máximo de transações por cliente por dia',
            'categoria': 'VELOCIDADE',
            'tipo_valor': 'INT',
            'valor_texto': '20'
        },
        {
            'chave': 'VELOCIDADE_INTERVALO_MIN_SEGUNDOS',
            'descricao': 'Intervalo mínimo em segundos entre transações do mesmo cliente',
            'categoria': 'VELOCIDADE',
            'tipo_valor': 'INT',
            'valor_texto': '30'
        },
        
        # CATEGORIA: AUTENTICACAO
        {
            'chave': 'AUTH_MAX_TENTATIVAS_FALHAS_24H',
            'descricao': 'Máximo de tentativas de login falhas em 24 horas antes de marcar como suspeito',
            'categoria': 'AUTENTICACAO',
            'tipo_valor': 'INT',
            'valor_texto': '5'
        },
        {
            'chave': 'AUTH_TAXA_FALHA_SUSPEITA',
            'descricao': 'Taxa de falha mínima (0.0-1.0) para considerar comportamento suspeito',
            'categoria': 'AUTENTICACAO',
            'tipo_valor': 'FLOAT',
            'valor_texto': '0.3'
        },
        {
            'chave': 'AUTH_DIAS_ULTIMO_BLOQUEIO',
            'descricao': 'Dias desde último bloqueio para considerar histórico suspeito',
            'categoria': 'AUTENTICACAO',
            'tipo_valor': 'INT',
            'valor_texto': '7'
        },
        {
            'chave': 'AUTH_MAX_BLOQUEIOS_30_DIAS',
            'descricao': 'Máximo de bloqueios em 30 dias antes de aumentar score de risco',
            'categoria': 'AUTENTICACAO',
            'tipo_valor': 'INT',
            'valor_texto': '2'
        },
        {
            'chave': 'AUTH_MAX_IPS_DISTINTOS_24H',
            'descricao': 'Máximo de IPs distintos em 24 horas antes de considerar suspeito',
            'categoria': 'AUTENTICACAO',
            'tipo_valor': 'INT',
            'valor_texto': '3'
        },
        {
            'chave': 'AUTH_MAX_DEVICES_DISTINTOS_24H',
            'descricao': 'Máximo de dispositivos distintos em 24 horas antes de considerar suspeito',
            'categoria': 'AUTENTICACAO',
            'tipo_valor': 'INT',
            'valor_texto': '2'
        },
        
        # CATEGORIA: SCORE
        {
            'chave': 'SCORE_LIMITE_APROVACAO_AUTO',
            'descricao': 'Score máximo para aprovação automática (0-100)',
            'categoria': 'SCORE',
            'tipo_valor': 'INT',
            'valor_texto': '30'
        },
        {
            'chave': 'SCORE_LIMITE_REVISAO',
            'descricao': 'Score mínimo para enviar para revisão manual (0-100)',
            'categoria': 'SCORE',
            'tipo_valor': 'INT',
            'valor_texto': '31'
        },
        {
            'chave': 'SCORE_LIMITE_REPROVACAO',
            'descricao': 'Score mínimo para reprovação automática (0-100)',
            'categoria': 'SCORE',
            'tipo_valor': 'INT',
            'valor_texto': '70'
        },
        {
            'chave': 'SCORE_DESCONTO_WHITELIST',
            'descricao': 'Desconto de pontos por item na whitelist',
            'categoria': 'SCORE',
            'tipo_valor': 'INT',
            'valor_texto': '20'
        },
        {
            'chave': 'SCORE_DESCONTO_MAX_WHITELIST',
            'descricao': 'Desconto máximo total por whitelist',
            'categoria': 'SCORE',
            'tipo_valor': 'INT',
            'valor_texto': '40'
        },
        
        # CATEGORIA: GERAL
        {
            'chave': 'MAXMIND_TIMEOUT_SEGUNDOS',
            'descricao': 'Timeout para consultas ao MaxMind em segundos',
            'categoria': 'GERAL',
            'tipo_valor': 'INT',
            'valor_texto': '3'
        },
        {
            'chave': 'MAXMIND_FALLBACK_SCORE',
            'descricao': 'Score padrão quando MaxMind falha ou está indisponível',
            'categoria': 'GERAL',
            'tipo_valor': 'INT',
            'valor_texto': '50'
        },
        {
            'chave': 'CONSULTA_AUTH_TIMEOUT_SEGUNDOS',
            'descricao': 'Timeout para consultas de autenticação ao Django em segundos',
            'categoria': 'GERAL',
            'tipo_valor': 'INT',
            'valor_texto': '2'
        },
        {
            'chave': 'FAIL_OPEN_ENABLED',
            'descricao': 'Se true, aprova transação em caso de falha técnica (fail-open)',
            'categoria': 'GERAL',
            'tipo_valor': 'BOOL',
            'valor_texto': 'true'
        },
        {
            'chave': 'LOG_REQUESTS_ENABLED',
            'descricao': 'Se true, loga todas as requisições de análise',
            'categoria': 'GERAL',
            'tipo_valor': 'BOOL',
            'valor_texto': 'true'
        },
    ]
    
    criadas = 0
    atualizadas = 0
    
    for config_data in configuracoes:
        config, created = ConfiguracaoAntifraude.objects.update_or_create(
            chave=config_data['chave'],
            defaults={
                'descricao': config_data['descricao'],
                'categoria': config_data['categoria'],
                'tipo_valor': config_data['tipo_valor'],
                'valor_texto': config_data['valor_texto'],
                'is_active': True
            }
        )
        
        if created:
            criadas += 1
            print(f"✅ Criada: {config.chave} = {config.valor_texto}")
        else:
            atualizadas += 1
            print(f"🔄 Atualizada: {config.chave} = {config.valor_texto}")
    
    print(f"\n📊 Resumo:")
    print(f"   Criadas: {criadas}")
    print(f"   Atualizadas: {atualizadas}")
    print(f"   Total: {len(configuracoes)}")
    print(f"\n✅ Configurações antifraude populadas com sucesso!")


if __name__ == '__main__':
    seed_configuracoes()
