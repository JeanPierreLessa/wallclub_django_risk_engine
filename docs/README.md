# WallClub Risk Engine

**Sistema de análise antifraude em tempo real para fintech - Container Django isolado**

**Versão:** 1.3  
**Status:** ✅ Operacional em produção desde 16/10/2025  
**Última atualização:** 30/10/2025 (transaction_id normalizado + Checkout 2FA)

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
- ✅ Sistema de Segurança Multi-Portal (Bloqueios + Atividades Suspeitas)
- ✅ Celery Tasks com 6 detectores automáticos
- ✅ Middleware de validação de login em tempo real
- ✅ Fail-open em caso de erro (segurança operacional)
- ✅ Integração Checkout Web (Link de Pagamento) - 23/10/2025
- ✅ Normalização `transacao_id` por origem: POS=NSU, WEB=checkout_transactions.id - 30/10/2025
- ✅ Sistema de telefone 2FA integrado (autogerenciamento + inativação automática)

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
| 6 | Dispositivo Novo - Alto Valor | DISPOSITIVO | 7 | +70 | REVISAR |
| 7 | IP Novo + Histórico Bloqueios | LOCALIZACAO | 8 | +80 | REVISAR |
| 8 | Múltiplas Tentativas Falhas | CUSTOM | 6 | +60 | REVISAR |
| 9 | Cliente com Bloqueio Recente | CUSTOM | 9 | +90 | REVISAR |

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

### Checkout Web - Link de Pagamento ✅ (22/10/2025)
**Arquivo:** `wallclub_django/checkout/services_antifraude.py` (268 linhas)

**Interceptação:** Antes do Pinbank em `checkout/link_pagamento_web/services.py` linha 117-183

**Dados enviados:**
- CPF, valor, modalidade, parcelas
- Número cartão, bandeira
- IP, user_agent, device_fingerprint
- Cliente nome, transaction_id
- Loja ID, Canal ID

**Decisões:**
- **APROVADO:** Processa normalmente no Pinbank
- **REPROVADO:** Bloqueia imediatamente
  - Status: `BLOQUEADA_ANTIFRAUDE`
  - Não processa pagamento
  - Retorna erro ao cliente
- **REVISAR:** Processa mas marca para revisão manual
  - Status: `PENDENTE_REVISAO`
  - Processa no Pinbank
  - Notifica analista

**Campos no Modelo (checkout_transactions):**
- `score_risco` - Score 0-100
- `decisao_antifraude` - APROVADO/REPROVADO/REVISAR
- `motivo_bloqueio` - Motivo da decisão
- `antifraude_response` - Resposta completa JSON
- `revisado_por` - ID do analista
- `revisado_em` - Data/hora da revisão
- `observacao_revisao` - Observação do analista

**SQL Migration:** `scripts/sql/adicionar_campos_antifraude_checkout.sql`

### Autenticação Cliente ✅ (30/10/2025)
**Arquivo:** `wallclub_django/apps/cliente/services_autenticacao_analise.py`, `wallclub_django/apps/cliente/views_autenticacao_analise.py`

**Endpoint Django:** `GET /cliente/api/v1/autenticacao/analise/<cpf>/`

**Autenticação:** OAuth 2.0 exclusivo (`@require_oauth_riskengine`)

**Service Risk Engine:** `antifraude/services_cliente_auth.py` (ClienteAutenticacaoService)

**Dados retornados:**
- Status atual (bloqueado, tentativas login)
- Histórico 24h (taxa falha, IPs distintos, devices)
- Dispositivos conhecidos (confiáveis ou não)
- Bloqueios histórico (30 dias)
- **9 flags de risco** (conta bloqueada, bloqueio recente, múltiplos bloqueios, alta taxa falha, etc)

**Score de Autenticação (0-50 pontos):**
- Conta bloqueada: +30
- Bloqueio recente (7 dias): +20
- Múltiplos bloqueios (2+ em 30 dias): +15
- Alta taxa falha (≥30%): +15
- Múltiplas tentativas falhas (5+ em 24h): +10
- Múltiplos IPs (3+ em 24h): +10
- Múltiplos devices (2+ em 24h): +10
- Todos devices novos (<7 dias): +10
- Nenhum device confiável (10+ logins): +5

**Integração AnaliseRiscoService:**
- Score de autenticação somado ao score total
- Fail-safe: erro na consulta = score 0 (não penaliza)
- Timeout configurável (2s padrão)
- Configurações centralizadas via `ConfiguracaoAntifraude`

**4 Novas Regras Criadas:**
1. Dispositivo Novo + Alto Valor (peso 7)
2. IP Novo + Histórico Bloqueios (peso 8)
3. Múltiplas Tentativas Falhas (peso 6)
4. Cliente com Bloqueio Recente (peso 9)

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

### Sistema de Segurança Multi-Portal ✅ (Fase 4 - Semana 23)
**Arquivos:** 
- Risk Engine: `antifraude/views_seguranca.py`, `antifraude/tasks.py`
- Django: `comum/middleware/security_validation.py`, `portais/admin/views_seguranca.py`

**Funcionalidades:**

#### Detectores Automáticos (Celery - a cada 5min):
1. **Login Múltiplo** - Mesmo CPF em 3+ IPs diferentes
2. **Tentativas Falhas** - 5+ reprovações em 5min (bloqueio automático)
3. **IP Novo** - CPF usando IP nunca visto
4. **Horário Suspeito** - Transações 02:00-05:00 AM
5. **Velocidade Transação** - 10+ transações em 5min
6. **Localização Anômala** - Preparado para MaxMind

#### Middleware de Validação:
- Intercepta logins em todos portais (admin, lojista, vendas)
- Valida IP/CPF com Risk Engine antes de permitir acesso
- Fail-open: permite acesso em caso de erro do Risk Engine

#### Telas de Gerenciamento:
- **Atividades Suspeitas** (`/admin/seguranca/atividades/`)
  - Dashboard com estatísticas
  - Filtros: status, tipo, portal, período
  - Investigar e tomar ações (bloquear IP/CPF, falso positivo)
  
- **Bloqueios** (`/admin/seguranca/bloqueios/`)
  - Criar bloqueio manual de IP ou CPF
  - Listar histórico de bloqueios
  - Desbloquear IPs/CPFs

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

### Endpoints de Segurança (Semana 23)

#### POST /api/antifraude/validate-login/
Valida se IP ou CPF está bloqueado

**Request:**
```json
{
  "ip": "192.168.1.100",
  "cpf": "12345678901",
  "portal": "admin"
}
```

**Response:**
```json
{
  "permitido": false,
  "bloqueado": true,
  "tipo": "ip",
  "motivo": "Tentativas de ataque",
  "bloqueio_id": 123,
  "portal": "admin"
}
```

#### GET /api/antifraude/suspicious/
Lista atividades suspeitas

**Query params:** `status`, `tipo`, `portal`, `dias`, `limit`

**Response:**
```json
{
  "success": true,
  "total": 45,
  "pendentes": 12,
  "atividades": [...]
}
```

#### POST /api/antifraude/block/
Cria bloqueio manual

**Request:**
```json
{
  "tipo": "ip",
  "valor": "192.168.1.100",
  "motivo": "Tentativas de ataque",
  "bloqueado_por": "admin_joao",
  "portal": "admin"
}
```

#### POST /api/antifraude/investigate/
Investiga atividade e toma ação

**Ações disponíveis:**
- `marcar_investigado`
- `bloquear_ip`
- `bloquear_cpf`
- `falso_positivo`
- `ignorar`

#### GET /api/antifraude/blocks/
Lista bloqueios ativos e inativos

**Query params:** `tipo`, `ativo`, `dias`

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

## 🤖 Celery Tasks

### Workers e Scheduler

**Iniciar Worker:**
```bash
celery -A riskengine worker --loglevel=info
```

**Iniciar Beat Scheduler:**
```bash
celery -A riskengine beat --loglevel=info
```

### Tasks Agendadas

**detectar_atividades_suspeitas()**
- **Schedule:** A cada 5 minutos
- **Função:** Executa 6 detectores automáticos
- **Output:** Cria registros em AtividadeSuspeita

**bloquear_automatico_critico()**
- **Schedule:** A cada 10 minutos
- **Função:** Bloqueia IPs com atividades de severidade 5 (crítico)
- **Output:** Cria bloqueios automáticos

### Supervisor (Produção)

```ini
[program:celery-worker]
command=celery -A riskengine worker --loglevel=info
autostart=true
autorestart=true

[program:celery-beat]
command=celery -A riskengine beat --loglevel=info
autostart=true
autorestart=true
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

# Celery tasks
docker logs wallclub-riskengine | grep celery
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

**Versão atual:** 1.3  
**Data de lançamento:** 16/10/2025  
**Última atualização:** 30/10/2025 (Integração Autenticação Cliente + Configurações Centralizadas)  
**Status:** ✅ Operacional em produção  

**Integrações ativas:**
- ✅ POSP2 (Terminal POS)
- ✅ Checkout Web - Link de Pagamento (22/10/2025)
  - 7 campos antifraude em checkout_transactions
  - 2 status novos: BLOQUEADA_ANTIFRAUDE, PENDENTE_REVISAO
  - Interceptação linha 117-183 antes do Pinbank
  - Fail-open implementado
- ✅ Autenticação Cliente (30/10/2025)
  - Endpoint OAuth exclusivo: GET /cliente/api/v1/autenticacao/analise/<cpf>/
  - Score 0-50 pontos baseado em comportamento (9 flags)
  - 4 regras novas: dispositivo novo, IP novo, tentativas falhas, bloqueio recente
  - Configurações centralizadas (29 parâmetros sem hardcode)
  - Integrado ao AnaliseRiscoService
- ✅ Portal Admin (revisão manual + segurança)
- ✅ OAuth 2.0 entre containers
- ✅ MaxMind minFraud (credenciais ativas)
- ✅ Sistema de Segurança Multi-Portal
  - ✅ Middleware de validação de login
  - ✅ 6 detectores automáticos (Celery)
  - ✅ Telas de gerenciamento (Atividades + Bloqueios)
  - ✅ APIs REST de segurança
- ⏳ 3D Secure (configuração pendente)

**Próximas evoluções:**
- [ ] Apps Mobile integrados
- [ ] Machine Learning para detecção de fraude
- [ ] Dashboard de métricas em tempo real
- [ ] Notificações (Email/Slack) para eventos críticos
- [ ] Integração MaxMind GeoIP para localização anômala

---

**Repositório:** `/var/www/wallclub_django_risk_engine`  
**Responsável:** Jean Lessa + Claude AI  
**Suporte:** admin@wallclub.com.br
