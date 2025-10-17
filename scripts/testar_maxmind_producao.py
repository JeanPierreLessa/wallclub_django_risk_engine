"""
Script para testar credenciais MaxMind em produção
Executa dentro do container Risk Engine
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'riskengine.settings')
django.setup()

from antifraude.services_maxmind import MaxMindService
from decimal import Decimal

print("=" * 80)
print("TESTE DE CREDENCIAIS MAXMIND")
print("=" * 80)

# Verificar configuração
from django.conf import settings
account_id = getattr(settings, 'MAXMIND_ACCOUNT_ID', None)
license_key = getattr(settings, 'MAXMIND_LICENSE_KEY', None)

print(f"\n1. CONFIGURAÇÃO:")
print(f"   Account ID: {account_id[:8]}... (encontrado)" if account_id else "   Account ID: NÃO CONFIGURADO")
print(f"   License Key: {license_key[:8]}... (encontrado)" if license_key else "   License Key: NÃO CONFIGURADO")

if not account_id or not license_key:
    print("\n❌ ERRO: Credenciais não configuradas")
    print("\nAdicione no .env:")
    print("MAXMIND_ACCOUNT_ID=seu_account_id")
    print("MAXMIND_LICENSE_KEY=sua_license_key")
    sys.exit(1)

# Testar com dados reais
print(f"\n2. TESTANDO API MAXMIND:")
print(f"   URL: {MaxMindService.API_URL}")

dados_teste = {
    'transacao_id': 'TEST-001',
    'cpf': '12345678900',
    'valor': Decimal('100.00'),
    'ip_address': '8.8.8.8',  # IP público para teste
    'cliente_id': 1,
    'loja_id': 1,
    'user_agent': 'Mozilla/5.0 (Test)',
    'device_fingerprint': 'test123'
}

try:
    resultado = MaxMindService.consultar_score(dados_teste, usar_cache=False)
    
    print(f"\n3. RESULTADO:")
    print(f"   ✅ Status: SUCESSO")
    print(f"   Score: {resultado['score']}/100")
    print(f"   Risk Score: {resultado['risk_score']:.2f}")
    print(f"   Fonte: {resultado['fonte']}")
    print(f"   Tempo: {resultado['tempo_consulta_ms']}ms")
    
    if resultado['fonte'] == 'maxmind':
        print(f"\n✅ MAXMIND FUNCIONANDO CORRETAMENTE!")
        print(f"   Detalhes: {resultado['detalhes']}")
    elif resultado['fonte'] == 'fallback':
        print(f"\n⚠️  USANDO FALLBACK")
        print(f"   Motivo: {resultado['detalhes'].get('motivo')}")
        if 'erro' in resultado['detalhes']:
            print(f"   Erro: {resultado['detalhes']['erro']}")
    
except Exception as e:
    print(f"\n❌ ERRO AO TESTAR:")
    print(f"   {str(e)}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
