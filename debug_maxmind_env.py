#!/usr/bin/env python3
"""
Script para debugar variáveis de ambiente MaxMind
"""
import os
import sys
import django

sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'riskengine.settings')
django.setup()

from django.conf import settings
import requests

print("=" * 80)
print("DEBUG: VARIÁVEIS MAXMIND")
print("=" * 80)

# 1. Verificar variáveis de ambiente diretas
print("\n1. VARIÁVEIS DE AMBIENTE (.env):")
account_id_env = os.getenv('MAXMIND_ACCOUNT_ID')
license_key_env = os.getenv('MAXMIND_LICENSE_KEY')

print(f"   MAXMIND_ACCOUNT_ID = '{account_id_env}'")
print(f"   Tipo: {type(account_id_env)}")
print(f"   Tamanho: {len(account_id_env) if account_id_env else 0} caracteres")

print(f"\n   MAXMIND_LICENSE_KEY = '{license_key_env}'")
print(f"   Tipo: {type(license_key_env)}")
print(f"   Tamanho: {len(license_key_env) if license_key_env else 0} caracteres")

# 2. Verificar settings Django
print("\n2. DJANGO SETTINGS:")
account_id_django = getattr(settings, 'MAXMIND_ACCOUNT_ID', None)
license_key_django = getattr(settings, 'MAXMIND_LICENSE_KEY', None)

print(f"   settings.MAXMIND_ACCOUNT_ID = '{account_id_django}'")
print(f"   settings.MAXMIND_LICENSE_KEY = '{license_key_django}'")

# 3. Verificar espaços ou caracteres invisíveis
if license_key_env:
    print("\n3. ANÁLISE DA LICENSE KEY:")
    print(f"   Primeiro char: repr={repr(license_key_env[0])} ord={ord(license_key_env[0])}")
    print(f"   Último char: repr={repr(license_key_env[-1])} ord={ord(license_key_env[-1])}")
    print(f"   Contém espaços? {' ' in license_key_env}")
    print(f"   Contém tabs? {'\\t' in license_key_env}")
    print(f"   Stripped = '{license_key_env.strip()}'")
    print(f"   Tamanho stripped: {len(license_key_env.strip())} caracteres")

# 4. Teste direto com requests
print("\n4. TESTE DIRETO API (requests):")
if account_id_env and license_key_env:
    try:
        response = requests.post(
            "https://minfraud.maxmind.com/minfraud/v2.0/score",
            auth=(account_id_env.strip(), license_key_env.strip()),
            json={
                "device": {"ip_address": "8.8.8.8"},
                "event": {"transaction_id": "test", "type": "purchase"}
            },
            timeout=5
        )
        print(f"   Status Code: {response.status_code}")
        print(f"   Response: {response.text[:200]}")
        
        if response.status_code == 200:
            print("\n   ✅ CREDENCIAIS VÁLIDAS!")
        elif response.status_code == 401:
            print("\n   ❌ ERRO 401: Credenciais inválidas")
            print(f"   Auth usado: ('{account_id_env.strip()}', '{license_key_env.strip()[:8]}...')")
    except Exception as e:
        print(f"   ❌ Erro: {e}")

print("\n" + "=" * 80)
