"""
Teste básico da integração MaxMind
Execute: python testar_maxmind.py
"""
import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'riskengine.settings')
django.setup()

from antifraude.services_maxmind import MaxMindService
from decimal import Decimal

print("=" * 60)
print("TESTE MAXMIND - WALLCLUB RISK ENGINE")
print("=" * 60)
print()

# Dados de teste
dados_teste = {
    'transacao_id': 'TEST-001',
    'cliente_id': 123,
    'cpf': '12345678900',
    'cliente_nome': 'João Silva',
    'valor': Decimal('150.00'),
    'modalidade': 'PIX',
    'ip_address': '177.10.20.30',  # IP brasileiro fictício
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'device_fingerprint': 'test_device_123',
    'bin_cartao': '411111',
    'loja_id': 1
}

print("📋 Dados de teste:")
print(f"   CPF: {dados_teste['cpf']}")
print(f"   Valor: R$ {dados_teste['valor']}")
print(f"   IP: {dados_teste['ip_address']}")
print()

print("🔄 Consultando MaxMind...")
print()

try:
    # Consultar MaxMind (sem usar cache para ver resposta real)
    resultado = MaxMindService.consultar_score(dados_teste, usar_cache=False)
    
    print("✅ RESULTADO:")
    print(f"   Score: {resultado['score']}")
    print(f"   Risk Score: {resultado['risk_score']:.2f}")
    print(f"   Fonte: {resultado['fonte']}")
    print(f"   Tempo: {resultado['tempo_consulta_ms']}ms")
    print()
    
    if resultado['fonte'] == 'maxmind':
        print("🎉 SUCESSO! MaxMind está funcionando!")
        print()
        print("Detalhes:")
        for key, value in resultado['detalhes'].items():
            print(f"   {key}: {value}")
    
    elif resultado['fonte'] == 'fallback':
        print("⚠️  FALLBACK ATIVADO")
        print()
        print("Motivo:")
        print(f"   {resultado['detalhes'].get('motivo', 'Desconhecido')}")
        print()
        print("Possíveis causas:")
        print("   1. Credenciais não configuradas no .env")
        print("   2. Credenciais incorretas")
        print("   3. Timeout/erro de rede")
        print()
        print("Verifique:")
        print("   - MAXMIND_ACCOUNT_ID no .env")
        print("   - MAXMIND_LICENSE_KEY no .env")
    
    elif resultado['fonte'] == 'cache':
        print("📦 Resultado do cache (consulta anterior)")

except Exception as e:
    print(f"❌ ERRO: {str(e)}")
    import traceback
    traceback.print_exc()

print()
print("=" * 60)
print()

# Testar estatísticas
print("📊 Estatísticas do cache:")
stats = MaxMindService.obter_estatisticas_cache()
for key, value in stats.items():
    print(f"   {key}: {value}")

print()
print("=" * 60)
