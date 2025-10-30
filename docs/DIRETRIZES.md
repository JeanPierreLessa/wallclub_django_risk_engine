# WALLCLUB RISK ENGINE - DIRETRIZES DE DESENVOLVIMENTO

**Versão:** 1.2  
**Data:** 23/10/2025  
**Status:** Container isolado + Sistema de Segurança Multi-Portal operacional em produção

**Atualizações Recentes (23/10):**
- ✅ Campo `transacao_id` aceito diretamente na normalização WEB
- ✅ Integração completa com Checkout Web (Link de Pagamento)
- ✅ OAuth 2.0 entre containers validado em produção

---

## 📋 VISÃO GERAL

Este documento define as diretrizes técnicas e padrões de código do **WallClub Risk Engine**, sistema de análise antifraude em tempo real que opera em container Django separado (porta 8004).

---

## 🏗️ ARQUITETURA DO SISTEMA

### Container Isolado
- **Porta:** 8004
- **Network:** `wallclub-network` (compartilhada com Django principal)
- **Banco:** MySQL compartilhado (schema `wallclub`)
- **Cache:** Redis compartilhado (DB 1)
- **Deploy:** Independente do Django principal
- **Escalabilidade:** Pode escalar horizontalmente sem afetar app principal

### Comunicação entre Containers
```
Django Principal (8003) → OAuth 2.0 → Risk Engine (8004)
                          ↓
                    Bearer Token
                          ↓
                    Análise de Risco
                          ↓
                    Response JSON
```

---

## 📊 ESTRUTURA DO PROJETO

```
wallclub-riskengine/
├── riskengine/                 # Configurações Django
│   ├── settings.py            # Settings único (não split)
│   ├── urls.py                # Rotas principais
│   └── wsgi.py
├── antifraude/                # Sistema antifraude
│   ├── models.py              # TransacaoRisco, RegraAntifraude, DecisaoAntifraude
│   │                          # BloqueioSeguranca, AtividadeSuspeita (Semana 23)
│   ├── models_config.py       # ConfiguracaoAntifraude, HistoricoConfiguracao (30/10)
│   ├── services.py            # AnaliseRiscoService (9 regras + score autenticação)
│   ├── services_coleta.py     # ColetaDadosService (normalização POS/APP/WEB)
│   ├── services_maxmind.py    # MaxMindService (score externo + cache)
│   ├── services_3ds.py        # Auth3DSService (3D Secure 2.0)
│   ├── services_cliente_auth.py # ClienteAutenticacaoService (consulta Django OAuth)
│   ├── services_notificacao.py # NotificacaoService (Email + Slack)
│   ├── views.py               # Views legadas (manter compatibilidade)
│   ├── views_api.py           # API REST pública (POST /analyze/)
│   ├── views_seguranca.py     # APIs segurança (validate-login, suspicious, blocks)
│   ├── views_teste.py         # Endpoints de teste/debug
│   ├── tasks.py               # Celery tasks (detectores automáticos)
│   └── urls.py                # Rotas antifraude
├── comum/                     # Módulos compartilhados
│   └── oauth/                 # Sistema OAuth 2.0
│       ├── models.py          # OAuthClient, OAuthToken
│       ├── views.py           # POST /oauth/token/
│       ├── services.py        # OAuthService
│       └── urls.py            # Rotas OAuth
├── docs/                      # Documentação técnica
│   ├── README.md              # Overview completo do sistema
│   ├── DIRETRIZES.md          # Este arquivo
│   ├── engine_antifraude.md   # Funcionamento do motor
│   ├── integracao_autenticacao_fraude.md # Integração autenticação (30/10)
│   ├── semana_8_coleta_dados.md
│   ├── semana_9_maxmind.md
│   ├── semana_13_3ds_api.md
│   └── semana_23_atividades_suspeitas.md
├── scripts/                   # Scripts utilitários
│   ├── testar_maxmind_producao.py
│   ├── seed_regras_antifraude.py
│   ├── seed_configuracoes_antifraude.py  # 29 configs (30/10)
│   └── seed_regras_autenticacao.py       # 4 regras auth (30/10)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── manage.py
```

---

## 🛡️ SISTEMA DE SEGURANÇA MULTI-PORTAL

### 1. Arquitetura de Segurança (Semana 23)

**Objetivo:** Detectar, monitorar e bloquear atividades suspeitas em tempo real.

**Componentes:**
- **Risk Engine:** Análise e armazenamento de eventos
- **Django WallClub:** Middleware de validação + Portal Admin
- **Celery:** Detectores automáticos executados periodicamente

### 2. Models de Segurança

#### BloqueioSeguranca
```python
class BloqueioSeguranca(models.Model):
    tipo = models.CharField(max_length=10)  # 'ip' ou 'cpf'
    valor = models.CharField(max_length=100)
    motivo = models.TextField()
    bloqueado_por = models.CharField(max_length=100)
    portal = models.CharField(max_length=50)  # 'admin', 'lojista', 'vendas'
    detalhes = models.JSONField()
    ativo = models.BooleanField(default=True)
    bloqueado_em = models.DateTimeField(auto_now_add=True)
    desbloqueado_em = models.DateTimeField(null=True)
```

#### AtividadeSuspeita
```python
class AtividadeSuspeita(models.Model):
    tipo = models.CharField(max_length=50)  # 'login_multiplo', 'tentativas_falhas', etc
    cpf = models.CharField(max_length=11)
    ip = models.CharField(max_length=45)
    portal = models.CharField(max_length=50)
    detalhes = models.JSONField()
    severidade = models.IntegerField()  # 1-5
    status = models.CharField(max_length=20)  # 'pendente', 'investigado', etc
    detectado_em = models.DateTimeField(auto_now_add=True)
    bloqueio_relacionado = models.ForeignKey(BloqueioSeguranca, null=True)
```

### 3. APIs de Segurança

**POST /api/antifraude/validate-login/**
- Valida se IP ou CPF está bloqueado antes do login
- Fail-open: permite acesso em caso de erro

**GET /api/antifraude/suspicious/**
- Lista atividades suspeitas com filtros
- Paginação e ordenação

**POST /api/antifraude/block/**
- Cria bloqueio manual de IP ou CPF

**POST /api/antifraude/investigate/**
- Investiga atividade e toma ações (bloquear, ignorar, falso positivo)

**GET /api/antifraude/blocks/**
- Lista bloqueios ativos e inativos

### 4. Detectores Automáticos (Celery)

**Task: detectar_atividades_suspeitas()** (a cada 5min)

1. **Login Múltiplo** (Severidade 4)
   - Mesmo CPF em 3+ IPs diferentes em 10 minutos

2. **Tentativas Falhas** (Severidade 5 - Crítico)
   - 5+ transações reprovadas do mesmo IP em 5 minutos
   - Bloqueio automático ativado

3. **IP Novo** (Severidade 3)
   - CPF usando IP nunca visto no histórico

4. **Horário Suspeito** (Severidade 2)
   - Transações entre 02:00-05:00 AM

5. **Velocidade Transação** (Severidade 4)
   - 10+ transações do mesmo CPF em 5 minutos

6. **Localização Anômala** (Preparado)
   - IP de país diferente em menos de 1 hora

**Task: bloquear_automatico_critico()** (a cada 10min)
- Bloqueia automaticamente IPs com atividades de severidade 5

### 5. Middleware de Validação (Django)

**SecurityValidationMiddleware** intercepta:
- `/oauth/token/`
- `/admin/login/`
- `/lojista/login/`
- `/vendas/login/`
- `/api/login/`

**Fluxo:**
1. Extrai IP e CPF do request
2. Chama API validate-login
3. Se bloqueado → HTTP 403
4. Se permitido → continua
5. Fail-open em erros

### 6. Portal Admin - Telas de Segurança

**Atividades Suspeitas** (`/admin/seguranca/atividades/`)
- Dashboard com estatísticas
- Filtros (status, tipo, portal, período)
- Modal de investigação com ações

**Bloqueios** (`/admin/seguranca/bloqueios/`)
- Criar bloqueio manual
- Listar histórico
- Desbloquear IPs/CPFs

---

## 🎯 REGRAS DE NEGÓCIO

### 1. Motor de Decisão

**Score de Risco (0-100):**
```python
# MaxMind Score base: 0-100
# + Regras internas: cada regra adiciona pontos
# = Score final: 0-100

Decisão:
- Score < 60:  APROVADO (baixo risco)
- Score 60-79: REVISAO (risco médio - análise manual)
- Score ≥ 80:  REPROVADO (alto risco - bloqueio)
```

**Exceção:** Se alguma regra tem `acao=REPROVAR` → REPROVADO (independente do score)

### 2. Regras Antifraude (9 regras)

| # | Nome | Tipo | Peso | Ação | Pontos |
|---|------|------|------|------|--------|
| 1 | Velocidade Alta | VELOCIDADE | 8 | REVISAR | +80 |
| 2 | Valor Suspeito | VALOR | 7 | REVISAR | +70 |
| 3 | Dispositivo Novo | DISPOSITIVO | 5 | ALERTAR | +50 |
| 4 | Horário Incomum | HORARIO | 4 | ALERTAR | +40 |
| 5 | IP Suspeito | LOCALIZACAO | 9 | REVISAR | +90 |
| 6 | Dispositivo Novo - Alto Valor | DISPOSITIVO | 7 | REVISAR | +70 |
| 7 | IP Novo + Histórico Bloqueios | LOCALIZACAO | 8 | REVISAR | +80 |
| 8 | Múltiplas Tentativas Falhas | CUSTOM | 6 | REVISAR | +60 |
| 9 | Cliente com Bloqueio Recente | CUSTOM | 9 | REVISAR | +90 |

**Cálculo:** `score += peso * 10`

### 3. Normalização de Dados

**Origens suportadas:**
- **POS:** Terminal físico (NSU como transacao_id)
- **APP:** Mobile (order_id + device_fingerprint)
- **WEB:** Checkout (checkout_transactions.id como transacao_id)

**transaction_id por origem (30/10/2025):**
```python
# POS
'transacao_id': dados.get('nsu')  # Exemplo: "156311526"

# WEB (Checkout)
'transacao_id': str(transacao.id)  # Exemplo: "19" (checkout_transactions.id)

# APP
'transacao_id': dados.get('order_id')  # Definido pelo app
```

**Detecção automática:**
```python
# ColetaDadosService.normalizar_dados(dados)
if 'nsu' in dados and 'terminal' in dados:
    origem = 'POS'
elif 'device_fingerprint' in dados and 'mobile' in user_agent:
    origem = 'APP'
else:
    origem = 'WEB'
```

### 4. Integração Checkout Web - Link de Pagamento (✅ 22/10/2025 + Atualização 30/10)

**Arquivo Django:** `checkout/link_pagamento_web/services.py`

**Interceptação:** Linha 117-183, ANTES de processar no Pinbank

**Service Antifraude:** `checkout/services_antifraude.py` (268 linhas)

**transaction_id:** Usa `checkout_transactions.id` (ID numérico da tabela)
```python
# Linha 146 de services.py
transaction_id=str(transacao.id)  # Exemplo: "19"
```

**Fluxo de Análise:**
```python
# 1. Coletar dados da sessão e cartão
# 2. Chamar CheckoutAntifraudeService.analisar_transacao()
# 3. Salvar resultado em checkout_transactions
# 4. Tratar decisão:
#    - REPROVADO → Bloqueia (status='BLOQUEADA_ANTIFRAUDE')
#    - REVISAR → Processa + marca (status='PENDENTE_REVISAO')
#    - APROVADO → Processa normalmente
```

**Campos Salvos (checkout_transactions):**
- `score_risco` (INT) - Score 0-100 retornado pelo Risk Engine
- `decisao_antifraude` (VARCHAR) - APROVADO/REPROVADO/REVISAR
- `motivo_bloqueio` (TEXT) - Motivo detalhado da decisão
- `antifraude_response` (JSON) - Resposta completa do Risk Engine
- `revisado_por` (BIGINT) - ID do analista (revisão manual)
- `revisado_em` (DATETIME) - Timestamp da revisão
- `observacao_revisao` (TEXT) - Observação do analista

**Status Novos:**
- `BLOQUEADA_ANTIFRAUDE` - Reprovado automaticamente, pagamento não processado
- `PENDENTE_REVISAO` - Processado mas aguarda análise manual do analista

**Fail-Open:** Em caso de erro/timeout no Risk Engine, a transação é APROVADA (não bloqueia operação).

**SQL Migration:** `wallclub_django/scripts/sql/adicionar_campos_antifraude_checkout.sql`

### 5. MaxMind minFraud

**Cache Redis:** 1 hora (chave: `maxmind:{cpf}:{valor}:{ip}`)

**Fallback:** Score neutro 50 se:
- Credenciais não configuradas
- Timeout (>3s)
- Erro HTTP
- Exceção inesperada

**Princípio:** Sistema NUNCA bloqueia por falha técnica.

### 6. 3D Secure 2.0

**Regras de Recomendação:**
- Score > 60: **Sempre usa 3DS**
- Valor > R$ 500: **Sempre usa 3DS**
- Score 40-60 + Valor > R$ 200: **Usa 3DS**
- Score < 40 + Valor < R$ 200: **Não usa 3DS**

**Status 3DS:**
- **Y** (Yes): Autenticação OK → APROVADO
- **A** (Attempt): Tentativa → APROVADO
- **N** (No): Falhou → REPROVADO
- **U** (Unavailable): Indisponível → Continua sem 3DS
- **R** (Reject): Rejeitado → REPROVADO

---

## 💻 PADRÕES DE CÓDIGO

### 1. Services Layer

**SEMPRE usar services para lógica de negócio:**

```python
# ✅ CORRETO
class AnaliseRiscoService:
    @staticmethod
    def analisar_transacao(transacao: TransacaoRisco) -> DecisaoAntifraude:
        """Analisa transação e retorna decisão"""
        # Lógica aqui
        pass

# ❌ ERRADO - Lógica na view
def analyze(request):
    # Não colocar lógica de negócio aqui
    pass
```

### 2. Normalização de Dados

**SEMPRE usar ColetaDadosService:**

```python
# ✅ CORRETO
from antifraude.services_coleta import ColetaDadosService

dados_normalizados = ColetaDadosService.normalizar_dados(dados, origem='POS')
valido, erro = ColetaDadosService.validar_dados_minimos(dados_normalizados)
```

### 3. Cache Redis

**SEMPRE usar cache para consultas externas:**

```python
# ✅ CORRETO
from django.core.cache import cache

cache_key = f"maxmind:{cpf}:{valor}:{ip}"
cached_score = cache.get(cache_key)

if cached_score is None:
    # Consultar API
    score = consultar_api_externa()
    cache.set(cache_key, score, timeout=3600)  # 1 hora
```

### 4. Tratamento de Erros

**SEMPRE usar fallback seguro:**

```python
# ✅ CORRETO
try:
    score = MaxMindService.consultar_score(dados)
except Exception as e:
    logger.error(f'Erro MaxMind: {e}')
    score = {
        'score': 50,  # Fallback neutro
        'fonte': 'fallback',
        'detalhes': {'erro': str(e)}
    }

# ❌ ERRADO - Deixar exceção subir
score = MaxMindService.consultar_score(dados)  # Pode quebrar
```

### 5. Logging

**SEMPRE logar operações críticas:**

```python
import logging

logger = logging.getLogger('antifraude')

# ✅ CORRETO
logger.info(f'Analisando transação {transacao_id} - CPF: {cpf_masked}')
logger.warning(f'Score alto ({score}) - Transação {transacao_id}')
logger.error(f'Erro ao consultar MaxMind: {erro}')
```

### 6. Mascaramento de Dados Sensíveis

**SEMPRE mascarar CPF e dados pessoais nos logs:**

```python
# ✅ CORRETO
def mascarar_cpf(cpf: str) -> str:
    """123.456.789-00 → 123.***.**-00"""
    return f"{cpf[:3]}.***.**-{cpf[-2:]}"

logger.info(f'CPF: {mascarar_cpf(cpf)}')

# ❌ ERRADO - Expor dados
logger.info(f'CPF: {cpf}')  # Viola LGPD
```

### 7. Timeouts

**SEMPRE definir timeout em chamadas externas:**

```python
# ✅ CORRETO
response = requests.post(
    url,
    json=payload,
    timeout=3  # 3 segundos
)

# ❌ ERRADO - Sem timeout
response = requests.post(url, json=payload)  # Pode travar
```

### 8. Type Hints

**SEMPRE usar type hints:**

```python
# ✅ CORRETO
def analisar_transacao(
    transacao: TransacaoRisco,
    usar_cache: bool = True
) -> Tuple[str, int, str]:
    """
    Returns:
        (decisao, score, motivo)
    """
    pass

# ❌ ERRADO - Sem type hints
def analisar_transacao(transacao, usar_cache=True):
    pass
```

### 9. Docstrings

**SEMPRE documentar métodos públicos:**

```python
# ✅ CORRETO
def consultar_score(transacao_data: Dict, usar_cache: bool = True) -> Dict:
    """
    Consulta score de risco na API MaxMind
    
    Args:
        transacao_data: Dados da transação (cpf, valor, ip, etc)
        usar_cache: Se deve usar cache Redis (padrão: True)
    
    Returns:
        Dict com score e detalhes:
        {
            'score': 65,
            'risk_score': 0.65,
            'fonte': 'maxmind' | 'cache' | 'fallback',
            'detalhes': {...},
            'tempo_consulta_ms': 250
        }
    """
    pass
```

### 10. Validação de Entrada

**SEMPRE validar dados de entrada:**

```python
# ✅ CORRETO
def analisar_transacao(dados: Dict) -> Dict:
    # Validar campos obrigatórios
    if not dados.get('cpf'):
        return {'sucesso': False, 'erro': 'CPF obrigatório'}
    
    if not dados.get('valor') or dados['valor'] <= 0:
        return {'sucesso': False, 'erro': 'Valor inválido'}
    
    # Processar...
```

---

## 🔒 SEGURANÇA

### 1. OAuth 2.0

**Todos endpoints requerem autenticação:**

```python
# Header obrigatório
Authorization: Bearer <token>
```

**Grant type:** `client_credentials`

**Token expiration:** 3600s (1 hora)

### 2. PCI-DSS Compliance

**NUNCA armazenar:**
- Número completo do cartão
- CVV
- Data de validade completa

**SEMPRE armazenar apenas:**
- BIN (6 primeiros dígitos)
- 4 últimos dígitos (se necessário)

```python
# ✅ CORRETO
bin_cartao = numero_cartao[:6]  # 411111
ultimos_4 = numero_cartao[-4:]  # 1111

# ❌ ERRADO
armazenar_numero_completo(numero_cartao)  # Viola PCI-DSS
```

### 3. LGPD

**Dados sensíveis:**
- CPF mascarado nos logs
- IP não exposto em APIs públicas
- Dados de transação anonimizados após 90 dias

---

## 📊 PERFORMANCE

### 1. Metas de Latência

| Operação | Meta | P95 |
|----------|------|-----|
| Análise de risco | <200ms | <500ms |
| Consulta MaxMind | <300ms | <600ms |
| Verificação 3DS | <1s | <2s |
| Cache hit | <10ms | <20ms |

### 2. Cache Strategy

**Redis DB 1:**
- MaxMind: 1 hora
- Regras: 5 minutos
- Tokens OAuth: 1 hora

### 3. Índices do Banco

**Obrigatórios:**
```sql
-- TransacaoRisco
INDEX idx_cpf_data (cpf, data_transacao)
INDEX idx_ip_data (ip_address, data_transacao)
INDEX idx_device_data (device_fingerprint, data_transacao)
INDEX idx_bin_data (bin_cartao, data_transacao)

-- DecisaoAntifraude
INDEX idx_decisao (decisao, data_decisao)
INDEX idx_score (score_risco)
```

---

## 🧪 TESTES

### 1. Endpoints de Teste

**Development only:**
```
POST /api/antifraude/teste/normalizar/
POST /api/antifraude/teste/bin/
GET  /api/antifraude/teste/exemplos/
```

**NUNCA expor em produção.**

### 2. Health Check

```bash
curl http://localhost:8004/api/antifraude/health/ \
  -H "Authorization: Bearer <token>"
```

Response:
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

## 🤖 CELERY E TASKS

### 1. Configuração Celery

**Arquivo:** `riskengine/celery.py`

```python
from celery import Celery
from celery.schedules import crontab

app = Celery('riskengine')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'detectar-atividades-suspeitas': {
        'task': 'antifraude.tasks.detectar_atividades_suspeitas',
        'schedule': 300.0,  # 5 minutos
    },
    'bloquear-automatico-critico': {
        'task': 'antifraude.tasks.bloquear_automatico_critico',
        'schedule': 600.0,  # 10 minutos
    },
}
```

### 2. Iniciar Workers

**Worker:**
```bash
celery -A riskengine worker --loglevel=info
```

**Beat Scheduler:**
```bash
celery -A riskengine beat --loglevel=info
```

**Supervisor (Produção):**
```ini
[program:celery-worker]
command=celery -A riskengine worker --loglevel=info

[program:celery-beat]
command=celery -A riskengine beat --loglevel=info
```

---

## 🚀 DEPLOY

### 1. Variáveis de Ambiente

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

# 3D Secure (opcional)
THREEDS_ENABLED=False
THREEDS_GATEWAY_URL=
THREEDS_MERCHANT_ID=
THREEDS_MERCHANT_KEY=

# Callbacks e notificações
CALLBACK_URL_PRINCIPAL=http://wallclub-prod-release300:8000
NOTIFICACAO_EMAIL=admin@wallclub.com.br
SLACK_WEBHOOK_URL=
```

### 2. Docker Build

```bash
cd /var/www/wallclub_django_risk_engine
git pull origin main
docker stop wallclub-riskengine && docker rm wallclub-riskengine
docker build -t wallclub-riskengine:v1.0 .

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
```

### 3. Validação Pós-Deploy

```bash
# 1. Health check
curl http://localhost:8004/api/antifraude/health/

# 2. Testar OAuth
curl -X POST http://localhost:8004/oauth/token/ \
  -d "grant_type=client_credentials" \
  -d "client_id=wallclub_django_internal" \
  -d "client_secret=secret"

# 3. Testar análise (com token)
curl -X POST http://localhost:8004/api/antifraude/analyze/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"cpf":"12345678900","valor":100,"modalidade":"PIX"}'

# 4. Verificar logs
docker logs wallclub-riskengine --tail 100
```

---

## 📝 CONVENÇÕES

### 1. Nomenclatura

**Models:** `PascalCase`
```python
TransacaoRisco, DecisaoAntifraude, RegraAntifraude
```

**Services:** `PascalCase` + `Service`
```python
AnaliseRiscoService, MaxMindService, Auth3DSService
```

**Métodos:** `snake_case`
```python
analisar_transacao(), consultar_score(), validar_dados()
```

**Constantes:** `UPPER_SNAKE_CASE`
```python
SCORE_NEUTRO = 50
TIMEOUT_MAXMIND = 3
```

### 2. Estrutura de Response

**SEMPRE usar formato padronizado:**

```python
# Sucesso
{
    "sucesso": true,
    "transacao_id": "TRX-123",
    "decisao": "APROVADO",
    "score_risco": 35,
    "motivo": "Score baixo, sem regras disparadas",
    "regras_acionadas": [...],
    "tempo_analise_ms": 125
}

# Erro
{
    "sucesso": false,
    "erro": "CPF obrigatório",
    "codigo_erro": "VALIDATION_ERROR"
}
```

### 3. Status HTTP

| Status | Uso |
|--------|-----|
| 200 | Análise concluída (mesmo se REPROVADO) |
| 400 | Dados inválidos |
| 401 | Token inválido/expirado |
| 403 | Sem permissão |
| 404 | Transação não encontrada |
| 500 | Erro interno (exceção não tratada) |

---

## 🔧 TROUBLESHOOTING

### 1. MaxMind não funciona

**Sintoma:** Score sempre 50 (fallback)

**Verificar:**
```bash
# 1. Credenciais configuradas?
docker exec wallclub-riskengine env | grep MAXMIND

# 2. Testar credenciais
docker exec wallclub-riskengine python scripts/testar_maxmind_producao.py

# 3. Ver logs
docker logs wallclub-riskengine | grep maxmind
```

### 2. Container não sobe

**Verificar:**
```bash
# Logs
docker logs wallclub-riskengine

# Rede
docker network inspect wallclub-network

# Variáveis
docker exec wallclub-riskengine env
```

### 3. Alta latência

**Verificar:**
```bash
# Redis funcionando?
docker exec wallclub-riskengine redis-cli -h redis ping

# MaxMind timeout?
docker logs wallclub-riskengine | grep "Timeout"

# Banco lento?
docker exec wallclub-riskengine mysql -h mysql -u root -p -e "SHOW PROCESSLIST;"
```

---

## 📚 REFERÊNCIAS

- **MaxMind minFraud:** https://dev.maxmind.com/minfraud
- **3D Secure 2.0:** https://www.emvco.com/emv-technologies/3d-secure/
- **PCI DSS:** https://www.pcisecuritystandards.org/
- **OAuth 2.0:** https://oauth.net/2/
- **LGPD:** https://www.gov.br/cidadania/pt-br/acesso-a-informacao/lgpd

---

**Documentação:** `/docs/`  
**Última atualização:** 30/10/2025  
**Versão:** 1.3 (com Integração Autenticação + Configurações Centralizadas)  
**Responsável:** Jean Lessa + Claude AI
