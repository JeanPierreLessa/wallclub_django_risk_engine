#!/usr/bin/env python
"""
Script: Popular Regras Antifraude Iniciais
Semana 10-11: Engine de Decisão
"""
import os
import sys
import django
from datetime import datetime

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'riskengine.settings')
django.setup()

from antifraude.models import RegraAntifraude

def criar_regras_iniciais():
    """Cria as 5 regras básicas do sistema"""
    
    regras = [
        {
            'nome': 'Velocidade Alta - Múltiplas Transações',
            'descricao': 'Detecta múltiplas transações do mesmo CPF em curto período',
            'tipo': 'VELOCIDADE',
            'parametros': {
                'max_transacoes': 3,
                'janela_minutos': 10
            },
            'peso': 8,
            'acao': 'REVISAR',
            'prioridade': 10
        },
        {
            'nome': 'IP Suspeito - Múltiplos CPFs',
            'descricao': 'Detecta múltiplos CPFs usando mesmo IP (possível proxy/fraudador)',
            'tipo': 'LOCALIZACAO',
            'parametros': {
                'max_cpfs_por_ip': 5,
                'janela_horas': 24
            },
            'peso': 9,
            'acao': 'REVISAR',
            'prioridade': 15
        },
        {
            'nome': 'Valor Suspeito - Acima do Normal',
            'descricao': 'Detecta valores muito acima da média do cliente',
            'tipo': 'VALOR',
            'parametros': {
                'multiplicador_media': 3
            },
            'peso': 7,
            'acao': 'REVISAR',
            'prioridade': 20
        },
        {
            'nome': 'Dispositivo Novo',
            'descricao': 'Detecta primeiro uso de dispositivo pelo cliente',
            'tipo': 'DISPOSITIVO',
            'parametros': {
                'permitir_primeiro_uso': True
            },
            'peso': 5,
            'acao': 'ALERTAR',
            'prioridade': 30
        },
        {
            'nome': 'Horário Incomum',
            'descricao': 'Detecta transações em horário suspeito (madrugada)',
            'tipo': 'HORARIO',
            'parametros': {
                'hora_inicio': 0,
                'hora_fim': 5
            },
            'peso': 4,
            'acao': 'ALERTAR',
            'prioridade': 40
        }
    ]
    
    criadas = 0
    existentes = 0
    
    print("=" * 80)
    print("SEED: REGRAS ANTIFRAUDE")
    print("=" * 80)
    print()
    
    for regra_data in regras:
        nome = regra_data['nome']
        
        # Verificar se já existe
        if RegraAntifraude.objects.filter(nome=nome).exists():
            print(f"⏭️  {nome}")
            print(f"   Status: Já existe")
            existentes += 1
        else:
            # Criar nova regra
            regra = RegraAntifraude.objects.create(**regra_data)
            print(f"✅ {nome}")
            print(f"   Tipo: {regra.tipo}")
            print(f"   Peso: {regra.peso}")
            print(f"   Ação: {regra.acao}")
            print(f"   Prioridade: {regra.prioridade}")
            criadas += 1
        
        print()
    
    print("=" * 80)
    print(f"RESULTADO: {criadas} criadas, {existentes} já existiam")
    print("=" * 80)
    print()
    
    # Listar todas as regras ativas
    print("REGRAS ATIVAS NO SISTEMA:")
    print("-" * 80)
    
    regras_ativas = RegraAntifraude.objects.filter(is_active=True).order_by('prioridade')
    
    for idx, regra in enumerate(regras_ativas, 1):
        status = "🟢" if regra.is_active else "🔴"
        print(f"{idx}. {status} {regra.nome}")
        print(f"   Tipo: {regra.tipo} | Peso: {regra.peso} | Ação: {regra.acao} | Prior.: {regra.prioridade}")
    
    print()
    print(f"Total: {regras_ativas.count()} regras ativas")
    print()

if __name__ == '__main__':
    criar_regras_iniciais()
