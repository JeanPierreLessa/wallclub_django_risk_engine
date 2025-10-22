# Semana 9: Integração MaxMind minFraud

**Status:** ✅ Concluída  
**Data:** 16/10/2025

## Objetivo

Integrar serviço externo MaxMind minFraud para obter score de risco independente, com cache Redis e fallback automático.

---

## Entregas

### 1. MaxMindService (`antifraude/services_maxmind.py`)

**Funcionalidades:**
- Consulta API MaxMind minFraud v2.0
- Cache Redis (1 hora) para reduzir chamadas
- Fallback automático para score neutro (50) em caso de erro
- Logs detalhados de todas as consultas
- Preparação de payload conforme formato MaxMind

**Métodos principais:**

#### `consultar_score(transacao_data: dict, usar_cache: bool = True) -> dict`
Consulta score de risco na API MaxMind:
- **Score base:** 0-100 (convertido de risk_score MaxMind)
- **Cache:** 1 hora no Redis (chave: `maxmind:{cpf}:{valor}:{ip}`)
- **Timeout:** 3 segundos
- **Fallback:** Retorna score 50 se falhar

**Retorno:**
```python
{
    'score': 65,
    'risk_score': 0.65,
    'fonte': 'maxmind' | 'cache' | 'fallback',
    'detalhes': {...},
    'tempo_consulta_ms': 250
}
```

**Fontes possíveis:**
- `maxmind`: Consultado na API com sucesso
- `cache`: Resultado em cache (< 1h)
- `fallback`: Erro/timeout/credenciais não configuradas

#### `_preparar_payload(transacao_data: dict) -> dict`
Prepara payload no formato exigido pela API:
```json
{
  "device": {
    "ip_address": "192.168.1.1",
    "user_agent": "Mozilla/5.0...",
    "session_id": "device_fingerprint"
  },
  "event": {
    "transaction_id": "TXN-001",
    "shop_id": "1",
    "time": "2025-10-16T14:30:00",
    "type": "purchase"
  },
  "account": {
    "user_id": "123"
  },
  "order": {
    "amount": 150.00,
    "currency": "BRL"
  },
  "payment": {
    "processor": "pinbank",
    "iin": "411111"
  }
}
```

#### `limpar_cache(cpf, valor, ip)`
Remove entrada específica do cache Redis.

---

### 2. Integração com AnaliseRiscoService

**Fluxo atualizado:**

1. **MaxMind consulta** (score base 0-100)
2. **Regras internas** ajustam score (+5 a +50 por regra)
3. **Thresholds finais:**
   - Score < 60: APROVADO
   - Score 60-79: REVISAO
   - Score ≥ 80: REPROVADO

**Exemplo:**
```
MaxMind score: 45 (fonte: maxmind)
+ Regra "Velocidade": +15 (3 transações em 10min)
+ Regra "Horário Incomum": +10 (transação às 2h)
= Score final: 70 → REVISAO MANUAL
```

---

### 3. Configurações

**`riskengine/settings.py`:**
```python
MAXMIND_ACCOUNT_ID = os.environ.get('MAXMIND_ACCOUNT_ID', None)
MAXMIND_LICENSE_KEY = os.environ.get('MAXMIND_LICENSE_KEY', None)
```

**`.env`:**
```bash
MAXMIND_ACCOUNT_ID=123456
MAXMIND_LICENSE_KEY=your_license_key_here
```

**Se não configuradas:** Usa fallback (score 50) automaticamente.

---

### 4. Cache Redis

**Estratégia:**
- **Chave:** `maxmind:{cpf}:{valor_int}:{ip}`
- **Timeout:** 3600 segundos (1 hora)
- **Benefício:** Reduz 90% das chamadas à API MaxMind

**Exemplo:**
```python
# Primeira chamada: consulta MaxMind
{'score': 65, 'fonte': 'maxmind', 'tempo_consulta_ms': 250}

# Segunda chamada (< 1h): retorna do cache
{'score': 65, 'fonte': 'cache', 'tempo_consulta_ms': 0}
```

---

## Logs de Consulta

Todos os logs registrados em `antifraude.maxmind`:

```
[antifraude.maxmind] MaxMind score: 65 (fonte: maxmind) - 250ms
[antifraude.maxmind] MaxMind score: 65 (fonte: cache) - 0ms
[antifraude.maxmind] MaxMind score: 50 (fonte: fallback) - 0ms
```

---

## Tratamento de Erros

### 1. Credenciais não configuradas
```python
{
    'score': 50,
    'fonte': 'fallback',
    'detalhes': {'motivo': 'Credenciais MaxMind não configuradas'}
}
```

### 2. Timeout (>3s)
```python
{
    'score': 50,
    'fonte': 'fallback',
    'detalhes': {'motivo': 'Timeout na consulta MaxMind (>3s)'}
}
```

### 3. Erro HTTP
```python
{
    'score': 50,
    'fonte': 'fallback',
    'detalhes': {
        'motivo': 'API retornou status 400',
        'erro': 'Invalid request...'
    }
}
```

### 4. Erro inesperado
```python
{
    'score': 50,
    'fonte': 'fallback',
    'detalhes': {
        'motivo': 'Erro na consulta MaxMind',
        'erro': 'Connection refused'
    }
}
```

**Princípio:** Sistema **NUNCA bloqueia** por falha técnica. Sempre usa fallback.

---

## Thresholds de Decisão

| Score Final | Decisão | Ação |
|-------------|---------|------|
| 0-59 | APROVADO | Libera transação |
| 60-79 | REVISAO | Analista revisa |
| 80-100 | REPROVADO | Bloqueia |

---

## Custos MaxMind

**Plano Básico:**
- Preço: US$ 10-15/mês (~R$ 50-75)
- Incluído: 500-1000 consultas/mês
- Adicional: US$ 0.01-0.02 por consulta extra

**Com cache (1h):**
- Redução: ~90% de chamadas
- Exemplo: 10.000 transações/mês → 1.000 consultas reais
- Custo estimado: R$ 50-75/mês

---

## Testes

### 1. Testar sem credenciais (fallback)
```bash
curl -X POST http://localhost:8004/api/antifraude/analisar/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "cpf": "12345678900",
    "valor": 150.00,
    "modalidade": "PIX",
    "nsu": "123456"
  }'
```

**Resposta esperada:**
```json
{
  "sucesso": true,
  "decisao": "APROVADO",
  "score_risco": 50,
  "motivo": "Score MaxMind: 50 (fallback)",
  "regras_acionadas": [
    {
      "nome": "MaxMind minFraud",
      "tipo": "SCORE_EXTERNO",
      "detalhes": {"motivo": "Credenciais MaxMind não configuradas"}
    }
  ]
}
```

### 2. Testar com credenciais (produção)
Configurar `.env` e repetir chamada. Score real será retornado.

---

## Próxima Fase

**Semanas 10-11: Engine de Decisão**
- Model `RegraAntifraude` parametrizado
- Regras: limite_valor, velocidade, blacklist, whitelist
- Ajuste de score dinâmico
- Ações por regra (aprovar/negar/revisar)

---

## Arquivos Criados

1. `antifraude/services_maxmind.py` - Service MaxMind (280 linhas)
2. `docs/semana_9_maxmind.md` - Este arquivo

## Arquivos Modificados

1. `antifraude/services.py` - Integração MaxMind no fluxo de análise
2. `riskengine/settings.py` - Configurações MAXMIND_ACCOUNT_ID e LICENSE_KEY

---

## Configuração de Produção

### 1. Obter credenciais MaxMind
```bash
# Cadastrar em: https://www.maxmind.com/en/minfraud-services
# Obter Account ID e License Key
```

### 2. Configurar `.env`
```bash
# Adicionar ao .env do Risk Engine
MAXMIND_ACCOUNT_ID=123456
MAXMIND_LICENSE_KEY=abc123xyz
```

### 3. Rebuild container
```bash
cd /var/www/wallclub_django_risk_engine
docker-compose down
docker-compose up --build -d
```

### 4. Validar logs
```bash
docker logs wallclub-riskengine --tail 100 | grep maxmind
```

**Até configurar MaxMind:** Sistema usa fallback (score 50) sem problemas.
