"""
Script para criar regras antifraude baseadas em dados de autenticação
Integração entre cliente authentication e riskengine

Uso:
    python manage.py shell < scripts/seed_regras_autenticacao.py
"""
import os
import sys
import django

# Setup Django
sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'riskengine.settings')
django.setup()

from antifraude.models import RegraAntifraude
from antifraude.models_config import ConfiguracaoAntifraude


def seed_regras_autenticacao():
    """Cria regras antifraude baseadas em autenticação do cliente"""
    
    # Buscar configurações
    valor_alto = ConfiguracaoAntifraude.get_config('VALOR_ALTO_MINIMO', 500.00)
    device_novo_dias = ConfiguracaoAntifraude.get_config('DISPOSITIVO_NOVO_DIAS', 7)
    ip_novo_dias = ConfiguracaoAntifraude.get_config('IP_NOVO_DIAS', 3)
    max_bloqueios = ConfiguracaoAntifraude.get_config('AUTH_MAX_BLOQUEIOS_30_DIAS', 2)
    max_tentativas_falhas = ConfiguracaoAntifraude.get_config('AUTH_MAX_TENTATIVAS_FALHAS_24H', 5)
    dias_ultimo_bloqueio = ConfiguracaoAntifraude.get_config('AUTH_DIAS_ULTIMO_BLOQUEIO', 7)
    
    regras = [
        {
            'nome': 'Dispositivo Novo - Alto Valor',
            'descricao': 'Transação de alto valor em dispositivo novo (menos de 7 dias)',
            'tipo': 'DISPOSITIVO',
            'parametros': {
                'device_age_days': device_novo_dias,
                'valor_minimo': float(valor_alto)
            },
            'peso': 7,
            'acao': 'REVISAR',
            'prioridade': 20
        },
        {
            'nome': 'IP Novo + Histórico de Bloqueios',
            'descricao': 'IP novo (menos de 3 dias) em cliente com bloqueios recentes (2+ em 30 dias)',
            'tipo': 'LOCALIZACAO',
            'parametros': {
                'ip_age_days': ip_novo_dias,
                'bloqueios_ultimos_30_dias': max_bloqueios
            },
            'peso': 8,
            'acao': 'REVISAR',
            'prioridade': 15
        },
        {
            'nome': 'Múltiplas Tentativas Falhas Recentes',
            'descricao': 'Cliente com 5+ tentativas de login falhas em 24h (taxa de falha >= 30%)',
            'tipo': 'CUSTOM',
            'parametros': {
                'tentativas_falhas_24h': max_tentativas_falhas,
                'taxa_falha_minima': 0.3
            },
            'peso': 6,
            'acao': 'REVISAR',
            'prioridade': 25
        },
        {
            'nome': 'Cliente com Bloqueio Recente',
            'descricao': 'Cliente teve bloqueio nos últimos 7 dias',
            'tipo': 'CUSTOM',
            'parametros': {
                'dias_desde_ultimo_bloqueio': dias_ultimo_bloqueio
            },
            'peso': 9,
            'acao': 'REVISAR',
            'prioridade': 10
        }
    ]
    
    criadas = 0
    atualizadas = 0
    
    for regra_data in regras:
        regra, created = RegraAntifraude.objects.update_or_create(
            nome=regra_data['nome'],
            defaults={
                'descricao': regra_data['descricao'],
                'tipo': regra_data['tipo'],
                'parametros': regra_data['parametros'],
                'peso': regra_data['peso'],
                'acao': regra_data['acao'],
                'prioridade': regra_data['prioridade'],
                'is_active': True
            }
        )
        
        if created:
            criadas += 1
            print(f"✅ Criada: {regra.nome} (Peso: {regra.peso}, Prioridade: {regra.prioridade})")
        else:
            atualizadas += 1
            print(f"🔄 Atualizada: {regra.nome} (Peso: {regra.peso}, Prioridade: {regra.prioridade})")
    
    print(f"\n📊 Resumo:")
    print(f"   Criadas: {criadas}")
    print(f"   Atualizadas: {atualizadas}")
    print(f"   Total: {len(regras)}")
    print(f"\n✅ Regras de autenticação configuradas com sucesso!")
    
    # Mostrar estatísticas
    total_regras = RegraAntifraude.objects.filter(is_active=True).count()
    print(f"\n📈 Total de regras ativas no sistema: {total_regras}")


if __name__ == '__main__':
    seed_regras_autenticacao()
