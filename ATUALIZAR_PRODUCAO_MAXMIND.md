# MIGRAÇÃO CREDENCIAIS MAXMIND PARA AWS SECRETS MANAGER

## O QUE FOI ALTERADO:

✅ Credenciais MaxMind agora são lidas do **AWS Secrets Manager**  
✅ Removidas do `.env` (mais seguro)  
✅ ConfigManager expandido com método `get_maxmind_config()`

---

## PASSO 1: ADICIONAR CREDENCIAIS NO AWS SECRETS MANAGER

### No Console AWS:

1. Acesse: **Secrets Manager** → `wall/prod/db`

2. Clique em **"Retrieve secret value"** → **"Edit"**

3. Adicione as duas chaves no JSON:

```json
{
  "DB_DATABASE_PYTHON": "wallclub_django",
  "DB_USER_PYTHON": "root",
  "DB_PASS_PYTHON": "sua_senha",
  "DB_HOST": "mysql",
  "MAXMIND_ACCOUNT_ID": "1241178",
  "MAXMIND_LICENSE_KEY": "COLE_SUA_LICENSE_KEY_AQUI"
}
```

4. Clique em **"Save"**

---

## PASSO 2: ATUALIZAR CÓDIGO NO SERVIDOR

```bash
# 1. Conectar no servidor
ssh ubuntu@ip-10-0-1-46

# 2. Ir para o diretório
cd /var/www/wallclub_django_risk_engine

# 3. Fazer backup do .env atual
cp .env .env.backup

# 4. Atualizar código do repositório
git pull origin main

# 5. Verificar se boto3 está instalado (já deve estar)
docker exec wallclub-riskengine pip show boto3

# 6. Verificar variáveis de ambiente AWS no container
docker exec wallclub-riskengine printenv | grep -E "AWS|ENVIRONMENT"

# Deve mostrar:
#   ENVIRONMENT=production
#   AWS_REGION=us-east-1
#   AWS_SECRET_NAME_PROD=wall/prod/db

# Se não tiver, adicionar no .env:
echo "ENVIRONMENT=production" >> .env
echo "AWS_REGION=us-east-1" >> .env
echo "AWS_SECRET_NAME_PROD=wall/prod/db" >> .env

# 7. Rebuild do container (para carregar novo código)
docker stop wallclub-riskengine && docker rm wallclub-riskengine
docker build -t wallclub-riskengine:v1.1 .

docker run -d \
  --name wallclub-riskengine \
  --network wallclub-network \
  -p 8004:8004 \
  --env-file .env \
  --restart=always \
  -v $(pwd)/logs:/app/logs \
  --memory=512m \
  --memory-swap=512m \
  --cpus="0.5" \
  wallclub-riskengine:v1.1

# 8. Aguardar container iniciar
sleep 10

# 9. Testar credenciais MaxMind
docker exec wallclub-riskengine python scripts/testar_maxmind_producao.py
```

---

## RESULTADO ESPERADO:

```
================================================================================
TESTE DE CREDENCIAIS MAXMIND
================================================================================

1. CONFIGURAÇÃO:
   Account ID: 1241178... (encontrado)
   License Key: aijmuD_G... (encontrado)

2. TESTANDO API MAXMIND:
   URL: https://minfraud.maxmind.com/minfraud/v2.0/score

3. RESULTADO:
   ✅ Status: SUCESSO
   Score: 15/100  ← Valor real da API
   Risk Score: 0.15
   Fonte: maxmind  ← IMPORTANTE: deve ser "maxmind", NÃO "fallback"
   Tempo: 180ms

✅ MAXMIND FUNCIONANDO CORRETAMENTE!
   Detalhes: {'ip_risk': None, 'warnings': [], 'id': '...'}}
================================================================================
```

---

## TROUBLESHOOTING:

### ❌ ERRO: "Credenciais não configuradas"

**Causa:** ConfigManager não conseguiu ler do AWS Secrets Manager

**Solução:**
```bash
# Verificar role IAM do EC2
aws sts get-caller-identity

# Verificar se o secret existe
aws secretsmanager get-secret-value --secret-id wall/prod/db --region us-east-1

# Verificar logs do container
docker logs wallclub-riskengine | grep -i maxmind
```

---

### ❌ ERRO: "Status 401 AUTHORIZATION_INVALID"

**Causa:** License Key com escopo errado ou inválida

**Solução:**

1. Acesse: https://www.maxmind.com/en/accounts/current/license-key

2. Gere uma **NOVA** license key

3. **IMPORTANTE:** Essa key precisa ter acesso a **minFraud Services**

4. Atualize no AWS Secrets Manager (não no .env)

5. **NÃO é necessário** reiniciar container (ConfigManager busca em tempo real)

6. Teste novamente:
   ```bash
   docker exec wallclub-riskengine python scripts/testar_maxmind_producao.py
   ```

---

## ROLLBACK (se necessário):

```bash
# Voltar para versão anterior
cd /var/www/wallclub_django_risk_engine
git reset --hard HEAD~1

# Restaurar .env com credenciais
cp .env.backup .env

# Rebuild container
docker stop wallclub-riskengine && docker rm wallclub-riskengine
docker build -t wallclub-riskengine:v1.0 .
docker run -d --name wallclub-riskengine --network wallclub-network -p 8004:8004 --env-file .env --restart=always wallclub-riskengine:v1.0
```

---

## SEGURANÇA:

✅ **Antes (INSEGURO):**
- Credenciais no `.env` (texto plano)
- Visível em `docker inspect`
- Logs podem expor credenciais

✅ **Depois (SEGURO):**
- Credenciais no AWS Secrets Manager (criptografado)
- Acesso via IAM Role (sem credenciais hardcoded)
- Rotação de secrets facilitada
- Auditoria via CloudTrail

---

**Data:** 2025-10-17  
**Versão:** 1.1
