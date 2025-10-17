#!/bin/bash
# Script para atualizar credenciais MaxMind no servidor

echo "=== ATUALIZAÇÃO MAXMIND CREDENTIALS ==="
echo ""
echo "1. Cole o ACCOUNT_ID:"
read ACCOUNT_ID

echo ""
echo "2. Cole a nova LICENSE_KEY (minFraud Services):"
read LICENSE_KEY

echo ""
echo "Atualizando .env..."

# Atualizar .env
sed -i.bak "s/^MAXMIND_ACCOUNT_ID=.*/MAXMIND_ACCOUNT_ID=$ACCOUNT_ID/" .env
sed -i.bak "s/^MAXMIND_LICENSE_KEY=.*/MAXMIND_LICENSE_KEY=$LICENSE_KEY/" .env

echo "✅ .env atualizado"
echo ""
echo "Reiniciando container..."

docker restart wallclub-riskengine

echo "⏳ Aguardando 5 segundos..."
sleep 5

echo ""
echo "Testando credenciais..."
docker exec wallclub-riskengine python scripts/testar_maxmind_producao.py

echo ""
echo "=== CONCLUÍDO ==="
