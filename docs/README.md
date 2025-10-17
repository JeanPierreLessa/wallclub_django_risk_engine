# WallClub Risk Engine

**Sistema de análise antifraude em tempo real para fintech - Container Django isolado**

**Versão:** 1.0  
**Status:** ✅ Operacional em produção desde 16/10/2025

---

## 📋 Sobre o Projeto

O **WallClub Risk Engine** é um sistema independente de análise de risco que opera em container Django isolado, analisando transações em tempo real e decidindo se devem ser aprovadas, reprovadas ou enviadas para revisão manual.

**Principais características:**
- ✅ Container isolado (porta 8004) para deploy independente
- ✅ OAuth 2.0 para autenticação entre containers
- ✅ MaxMind minFraud integration com cache Redis
- ✅ 5 regras antifraude básicas configuráveis
- ✅ 3D Secure 2.0 support
- ✅ Normalização automática de dados (POS/APP/WEB)
- ✅ Portal Admin com revisão manual
- ✅ Fail-open em caso de erro (segurança operacional)

---

## 🏗️ Arquitetura

```
Django Principal (8003)
         ↓
   OAuth 2.0 Token
         ↓
Risk Engine (8004) → MaxMind API
         ↓
   Análise Regras
         ↓
Decisão + Score → Response
```

**Recursos compartilhados:**
- **Network:** `wallclub-network`
- **Banco:** MySQL (schema `wallclub`)
- **Cache:** Redis (DB 1)

**Recursos isolados:**
- **Container:** Independente
- **Porta:** 8004
- **Deploy:** Pode escalar separadamente
- **Logs:** `/app/logs/antifraude.log`

---

## 🎯 Fluxo de Decisão

### Score de Risco (0-100)

```
MaxMind Score base (0-100)
    +
Regras internas (cada regra adiciona pontos)
    =
Score final (0-100)
```

### Thresholds de Decisão

| Score | Decisão | Ação |
|-------|---------|------|
| 0-59 | ✅ APROVADO | Libera transação automaticamente |
| 60-79 | ⚠️ REVISAO | Envia para análise manual |
| 80-100 | 🚫 REPROVADO | Bloqueia transação automaticamente |

**Exceção:** Se alguma regra tem `acao=REPROVAR` → REPROVADO (independente do score)

---

## 📊 Regras Antifraude

### 5 Regras Básicas Implementadas

| # | Nome | Tipo | Peso | Pontos | Ação |
|---|------|------|------|--------|------|
| 1 | Velocidade Alta | VELOCIDADE | 8 | +80 | REVISAR |
| 2 | Valor Suspeito | VALOR | 7 | +70 | REVISAR |
| 3 | Dispositivo Novo | DISPOSITIVO | 5 | +50 | ALERTAR |
| 4 | Horário Incomum | HORARIO | 4 | +40 | ALERTAR |
| 5 | IP Suspeito | LOCALIZACAO | 9 | +90 | REVISAR |

**Cálculo:** `score += peso * 10`

### 1. Velocidade Alta
- **Lógica:** Mais de 3 transações em 10 minutos (mesmo CPF)
- **Exemplo:** Cliente faz 4 compras em 8 minutos → +80 pontos

### 2. Valor Suspeito
- **Lógica:** Valor > (média do cliente * 3)
- **Exemplo:** Cliente costuma gastar R$ 50, faz compra de R$ 200 → +70 pontos

### 3. Dispositivo Novo
- **Lógica:** Device fingerprint nunca usado pelo cliente
- **Exemplo:** Cliente sempre usa iPhone, agora aparece Android → +50 pontos

### 4. Horário Incomum
- **Lógica:** Transação entre 00h-05h
- **Exemplo:** Compra às 3h da manhã → +40 pontos

### 5. IP Suspeito
- **Lógica:** Mais de 5 CPFs diferentes no mesmo IP em 24h
- **Exemplo:** 10 CPFs em 1 IP → +90 pontos (possível fraudador usando proxy)

---

## 🔗 Integrações Ativas

### POSP2 (Terminal POS) ✅
**Arquivo:** `wallclub_django/posp2/services_antifraude.py` (374 linhas)

**Interceptação:** Antes do Pinbank em `services_transacao.py` linha ~333

**Dados enviados:**
- CPF, valor, modalidade, parcelas
- Terminal, loja_id, canal_id
- BIN cartão, bandeira, NSU

**Fluxo:**
```
1. Transação POS iniciada
2. Parse dados
3. Calcular valores
4. → INTERCEPTAÇÃO ANTIFRAUDE ←
5. Processar cashback
6. Retornar comprovante
```

### Checkout Web ✅
**Arquivo:** `wallclub_django/checkout/services_antifraude.py` (271 linhas)

**Interceptação:** Antes do Pinbank em `services.py` linha ~540

**Dados enviados:**
- CPF, valor, modalidade, parcelas
- Número cartão, bandeira
- IP, user_agent, device_fingerprint
- Cliente nome, email

**Decisões:**
- APROVADO: Continua Pinbank
- REPROVADO: Bloqueia com mensagem "Transação bloqueada por segurança"
- REVISAR: Processa mas marca para revisão

### Portal Admin (Revisão Manual) ✅
**Arquivos:** `wallclub_django/portais/admin/views_antifraude.py`

**Funcionalidades:**
- Dashboard com métricas (pendentes, taxa de aprovação, score médio)
- Lista de transações em revisão
- Aprovar/Reprovar com observação
- Histórico de revisões

**Endpoints:**
- `/admin/antifraude/` - Dashboard
- `/admin/antifraude/pendentes/` - Lista pendentes
- `/admin/antifraude/historico/` - Histórico

---

## 📡 API REST

### Autenticação OAuth 2.0

Todos endpoints requerem Bearer token:

```bash
# 1. Obter token
curl -X POST http://localhost:8004/oauth/token/ \
  -d "grant_type=client_credentials" \
  -d "client_id=wallclub_django_internal" \
  -d "client_secret=Kx9mP2vQnL8yR5sT4jWbF7cH3zN6aE1dG0uX8pY2vM5qK7rT9wL4hN3jC6fB0sA"

# Response:
{
  "access_token": "abc123...",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

### Endpoints Principais

#### POST /api/antifraude/analyze/
Analisa transação e retorna decisão

**Request:**
```json
{
  "transaction_id": "TRX-123",
  "cpf": "12345678900",
  "valor": 150.00,
  "modalidade": "CREDITO",
  "numero_cartao": "5111111111111111",
  "bandeira": "MASTERCARD",
  "loja_id": 1,
  "ip_address": "192.168.1.100",
  "user_agent": "Mozilla/5.0..."
}
```

**Response:**
```json
{
  "sucesso": true,
  "transacao_id": "TRX-123",
  "decisao": "APROVADO",
  "score_risco": 35,
  "motivo": "Transação normal, sem regras disparadas",
  "regras_acionadas": [],
  "tempo_analise_ms": 125,
  "requer_3ds": false
}
```

#### GET /api/antifraude/decision/<transacao_id>/
Consulta decisão de transação específica

**Response:**
```json
{
  "transacao_id": "TRX-123",
  "decisao": "APROVADO",
  "score_risco": 35,
  "motivo": "...",
  "data_analise": "2025-10-16T14:30:00"
}
```

#### POST /api/antifraude/validate-3ds/
Valida resultado autenticação 3D Secure

**Request:**
```json
{
  "auth_id": "3DS-AUTH-123",
  "transacao_id": "TRX-123"
}
```

#### GET /api/antifraude/health/
Health check do serviço

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-10-16T22:30:00",
  "services": {
    "database": "ok",
    "redis": "ok",
    "maxmind": "ok",
    "threeds": "disabled"
  }
}
```

---

## 🔧 Configuração

### Variáveis de Ambiente

```bash
# Django
SECRET_KEY=django-secret-key
DEBUG=False
ALLOWED_HOSTS=*

# Banco compartilhado
DB_NAME=wallclub
DB_USER=root
DB_PASSWORD=senha
DB_HOST=mysql
DB_PORT=3306

# Redis compartilhado
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=1

# MaxMind minFraud - ⚠️ NÃO CONFIGURAR AQUI
# Credenciais são lidas automaticamente do AWS Secrets Manager
# Adicione no secret 'wall/prod/db' as chaves:
#   - MAXMIND_ACCOUNT_ID
#   - MAXMIND_LICENSE_KEY

# 3D Secure 2.0 (opcional)
THREEDS_ENABLED=False
THREEDS_GATEWAY_URL=
THREEDS_MERCHANT_ID=
THREEDS_MERCHANT_KEY=
THREEDS_TIMEOUT=30

# Callbacks e notificações
CALLBACK_URL_PRINCIPAL=http://wallclub-prod-release300:8000
NOTIFICACAO_EMAIL=admin@wallclub.com.br,fraude@wallclub.com.br
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T00000/B00000/XXXX
```

### MaxMind minFraud

**Cache Redis:** 1 hora (reduz 90% das chamadas)

**Fallback automático:** Score neutro 50 se:
- Credenciais não configuradas
- Timeout (>3s)
- Erro HTTP
- Exceção inesperada

**Custo estimado:** R$ 50-75/mês com cache

### 3D Secure 2.0

**Regras de Recomendação:**
- Score > 60: Sempre usa 3DS
- Valor > R$ 500: Sempre usa 3DS
- Score 40-60 + Valor > R$ 200: Usa 3DS
- Score < 40 + Valor < R$ 200: Não usa 3DS

**Status:**
- **Y** (Yes): Autenticação OK → APROVADO
- **A** (Attempt): Tentativa → APROVADO
- **N** (No): Falhou → REPROVADO
- **U** (Unavailable): Indisponível → Continua sem 3DS
- **R** (Reject): Rejeitado → REPROVADO

---

## 🚀 Deploy

### Desenvolvimento

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Configurar .env
cp .env.example .env
# Editar .env com credenciais

# 3. Criar tabelas
python manage.py migrate

# 4. Seed regras antifraude
python scripts/seed_regras_antifraude.py

# 5. Rodar servidor
python manage.py runserver 0.0.0.0:8004
```

### Produção com Docker

```bash
# Build
cd /var/www/wallclub_django_risk_engine
git pull origin main
docker build -t wallclub-riskengine:v1.0 .

# Run
docker run -d \
  --name wallclub-riskengine \
  --network wallclub-network \
  -p 8004:8004 \
  --env-file .env \
  --restart=always \
  -v $(pwd)/logs:/app/logs \
  --memory=512m \
  --cpus="0.5" \
  wallclub-riskengine:v1.0

# Verificar
docker logs wallclub-riskengine --tail 100
curl http://localhost:8004/api/antifraude/health/
```

### Docker Compose

```bash
docker-compose up -d
docker-compose logs -f wallclub-riskengine
```

---

## 🧪 Testes

### Health Check

```bash
curl http://localhost:8004/api/antifraude/health/ \
  -H "Authorization: Bearer <token>"
```

### Testar Análise

```bash
# 1. Obter token OAuth
TOKEN=$(curl -X POST http://localhost:8004/oauth/token/ \
  -d "grant_type=client_credentials" \
  -d "client_id=wallclub_django_internal" \
  -d "client_secret=secret" \
  | jq -r '.access_token')

# 2. Analisar transação
curl -X POST http://localhost:8004/api/antifraude/analyze/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "cpf": "12345678900",
    "valor": 100.00,
    "modalidade": "PIX",
    "transaction_id": "TEST-001"
  }'
```

### Testar MaxMind

```bash
docker exec wallclub-riskengine python scripts/testar_maxmind_producao.py
```

### Endpoints de Teste (Development only)

```bash
# Testar normalização de dados
curl -X POST http://localhost:8004/api/antifraude/teste/normalizar/ \
  -H "Content-Type: application/json" \
  -d '{
    "nsu": "123456",
    "cpf": "12345678900",
    "valor": 150,
    "modalidade": "PIX"
  }'

# Testar extração de BIN
curl -X POST http://localhost:8004/api/antifraude/teste/bin/ \
  -H "Content-Type: application/json" \
  -d '{
    "numeros_cartao": [
      "4111111111111111",
      "4111 1111 1111 1111"
    ]
  }'

# Ver exemplos de payload
curl http://localhost:8004/api/antifraude/teste/exemplos/
```

---

## 📈 Performance

### Metas de Latência

| Operação | Meta | P95 |
|----------|------|-----|
| Análise de risco | <200ms | <500ms |
| Consulta MaxMind | <300ms | <600ms |
| Verificação 3DS | <1s | <2s |
| Cache hit | <10ms | <20ms |

### Recursos do Container

```yaml
resources:
  limits:
    memory: 512m
    cpus: "0.5"
  reservations:
    memory: 256m
    cpus: "0.25"
```

---

## 📊 Monitoramento

### Logs

```bash
# Todos logs
docker logs wallclub-riskengine --tail 100

# Apenas antifraude
docker exec wallclub-riskengine tail -f logs/antifraude.log

# Apenas MaxMind
docker logs wallclub-riskengine | grep maxmind
```

### Métricas Sugeridas

1. **Taxa de Aprovação**
   - Meta: >90% aprovação automática
   - Alerta: <80% aprovação

2. **Score Médio**
   - Por origem (POS, APP, WEB)
   - Por horário

3. **Tempo de Análise**
   - Média: <200ms
   - P95: <500ms

4. **Taxa de Fraude Real**
   - Transações reprovadas confirmadas como fraude
   - Falsos positivos (bloqueou transação legítima)

5. **Tempo de Revisão Manual**
   - Média: <15 minutos
   - SLA: <30 minutos

---

## 🔒 Segurança

### PCI-DSS Compliance

**NUNCA armazenar:**
- Número completo do cartão
- CVV
- Data de validade completa

**SEMPRE armazenar apenas:**
- BIN (6 primeiros dígitos)
- 4 últimos dígitos (se necessário)

### LGPD

**Dados sensíveis:**
- CPF mascarado nos logs (`123.***.**-00`)
- IP não exposto em APIs públicas
- Dados de transação anonimizados após 90 dias

### OAuth 2.0

**Grant type:** `client_credentials`  
**Token expiration:** 3600s (1 hora)  
**Header:** `Authorization: Bearer <token>`

---

## 🔧 Troubleshooting

### MaxMind não funciona (score sempre 50)

```bash
# 1. Verificar credenciais
docker exec wallclub-riskengine env | grep MAXMIND

# 2. Testar credenciais
docker exec wallclub-riskengine python scripts/testar_maxmind_producao.py

# 3. Ver logs
docker logs wallclub-riskengine | grep maxmind
```

### Container não sobe

```bash
# Ver logs de erro
docker logs wallclub-riskengine

# Verificar network
docker network inspect wallclub-network

# Verificar variáveis
docker exec wallclub-riskengine env
```

### Alta latência

```bash
# Redis funcionando?
docker exec wallclub-riskengine redis-cli -h redis ping

# MaxMind timeout?
docker logs wallclub-riskengine | grep "Timeout"

# Banco lento?
docker exec wallclub-riskengine python manage.py dbshell
```

### Erro de autenticação OAuth

```bash
# Verificar client_id e secret
docker exec wallclub-riskengine python manage.py shell
>>> from comum.oauth.models import OAuthClient
>>> OAuthClient.objects.filter(client_id='wallclub_django_internal').first()
```

---

## 📚 Documentação Técnica

- **DIRETRIZES.md** - Padrões de código e arquitetura
- **docs/engine_antifraude.md** - Funcionamento do motor
- **docs/semana_8_coleta_dados.md** - Normalização de dados
- **docs/semana_9_maxmind.md** - Integração MaxMind
- **docs/semana_13_3ds_api.md** - 3D Secure 2.0

---

## 🚀 Próximas Evoluções

1. **Machine Learning**
   - Treinar modelo com histórico de fraudes
   - Detectar padrões complexos

2. **Regras Dinâmicas**
   - Auto-ajustar pesos baseado em eficácia
   - Criar regras novas automaticamente

3. **Análise Comportamental**
   - Perfil de gasto do cliente
   - Horários habituais de compra
   - Locais frequentes

4. **Integração Bureau**
   - Consulta CPF em Serasa/SPC
   - Verificação de BIN de cartão

---

## 📝 Status do Projeto

**Versão atual:** 1.0  
**Data de lançamento:** 16/10/2025  
**Status:** ✅ Operacional em produção  

**Integrações ativas:**
- ✅ POSP2 (Terminal POS)
- ✅ Checkout Web
- ✅ Portal Admin (revisão manual)
- ✅ OAuth 2.0 entre containers
- ✅ MaxMind minFraud (credenciais ativas)
- ⏳ 3D Secure (configuração pendente)

**Próximas integrações:**
- [ ] Apps Mobile
- [ ] Testes E2E completos
- [ ] Dashboard de métricas

---

**Repositório:** `/var/www/wallclub_django_risk_engine`  
**Responsável:** Jean Lessa + Claude AI  
**Suporte:** admin@wallclub.com.br
