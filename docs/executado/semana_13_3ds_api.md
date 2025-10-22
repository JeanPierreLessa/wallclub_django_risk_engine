# SEMANA 13: 3D SECURE E API REST

**Status:** ✅ CONCLUÍDA  
**Data:** 16/10/2025

---

## OBJETIVO

Implementar autenticação 3D Secure 2.0 e padronizar APIs REST para integração externa.

---

## ENTREGAS

### 1. Auth3DSService ✅

**Arquivo:** `antifraude/services_3ds.py` (439 linhas)

**Funcionalidades:**
- `verificar_elegibilidade(bin_cartao, valor)` - Verifica se cartão está inscrito no 3DS
- `iniciar_autenticacao(...)` - Inicia processo de autenticação com banco emissor
- `validar_autenticacao(auth_id)` - Valida resultado após cliente completar desafio
- `recomendar_3ds(score, valor, bin)` - Recomenda uso baseado em regras

**Regras de Recomendação 3DS:**
- Score > 60: **Sempre usa 3DS**
- Valor > R$ 500: **Sempre usa 3DS**
- Score 40-60 + Valor > R$ 200: **Usa 3DS**
- Score < 40 + Valor < R$ 200: **Não usa 3DS**

**Fluxo 3DS:**
```
1. Verificar elegibilidade → 2. Iniciar autenticação → 
3. Cliente completa desafio → 4. Validar resultado → 
5. Usar CAVV/ECI na transação
```

---

### 2. API REST Pública ✅

**Arquivo:** `antifraude/views_api.py` (340 linhas)

#### Endpoints Implementados:

**a) POST /api/antifraude/analyze/**
- Endpoint principal de análise de risco
- Normalização automática de dados (POS/APP/WEB)
- Integração com 3DS (verifica elegibilidade e inicia se necessário)
- Retorna decisão + score + regras acionadas + dados 3DS (se aplicável)

**Payload:**
```json
{
    "transaction_id": "TRX-123",
    "cpf": "12345678900",
    "valor": 150.00,
    "modalidade": "CREDITO",
    "numero_cartao": "5111111111111111",
    "loja_id": 1,
    "requer_3ds": false
}
```

**Response:**
```json
{
    "sucesso": true,
    "transacao_id": "TRX-123",
    "decisao": "APROVADO",
    "score_risco": 35,
    "motivo": "Transação normal",
    "regras_acionadas": [...],
    "tempo_analise_ms": 125,
    "requer_3ds": false,
    "dados_3ds": null
}
```

**b) GET /api/antifraude/decision/<transacao_id>/**
- Consulta decisão de transação específica
- Retorna dados completos da análise
- CPF mascarado (123.***.**-00)

**c) POST /api/antifraude/validate-3ds/**
- Valida resultado da autenticação 3DS
- Atualiza decisão baseado no resultado (Y/N/A/U)
- Retorna ECI, CAVV, XID para transação final

**d) GET /api/antifraude/health/**
- Health check do serviço
- Verifica status: MaxMind, 3DS, Redis
- Status: `healthy` ou `degraded`

---

### 3. Configurações ✅

**Arquivo:** `riskengine/settings.py`

```python
# 3D Secure 2.0
THREEDS_ENABLED = os.environ.get('THREEDS_ENABLED', 'False') == 'True'
THREEDS_GATEWAY_URL = os.environ.get('THREEDS_GATEWAY_URL', None)
THREEDS_MERCHANT_ID = os.environ.get('THREEDS_MERCHANT_ID', None)
THREEDS_MERCHANT_KEY = os.environ.get('THREEDS_MERCHANT_KEY', None)
THREEDS_TIMEOUT = int(os.environ.get('THREEDS_TIMEOUT', '30'))
```

**Variáveis de Ambiente (.env):**
```bash
# 3D Secure
THREEDS_ENABLED=True
THREEDS_GATEWAY_URL=https://gateway.3ds-provider.com
THREEDS_MERCHANT_ID=merchant_123
THREEDS_MERCHANT_KEY=secret_key_here
THREEDS_TIMEOUT=30
```

---

### 4. Rotas Atualizadas ✅

**Arquivo:** `antifraude/urls.py`

```python
# API REST Pública (Semana 13)
path('analyze/', views_api.analyze, name='antifraude_analyze'),
path('decision/<str:transacao_id>/', views_api.decision, name='antifraude_decision'),
path('validate-3ds/', views_api.validate_3ds, name='antifraude_validate_3ds'),
path('health/', views_api.health, name='antifraude_health'),

# Legado (manter compatibilidade)
path('analisar/', views.analisar_transacao, name='antifraude_analisar'),
path('decisao/<str:transacao_id>/', views.consultar_decisao, name='antifraude_decisao'),
```

---

## DECISÕES 3DS

### Status de Decisão:

- **APROVADO**: Score baixo, sem necessidade de 3DS
- **REPROVADO**: Score alto ou blacklist, bloqueio imediato
- **REVISAO**: Score médio, revisão manual necessária
- **REQUER_3DS**: Score/valor requer autenticação 3DS (novo status)

### Códigos de Status 3DS:

- **Y** (Yes): Autenticação bem-sucedida → APROVADO
- **A** (Attempt): Tentativa de autenticação → APROVADO
- **N** (No): Autenticação falhou → REPROVADO
- **U** (Unavailable): Sistema indisponível → Continua sem 3DS
- **R** (Reject): Autenticação rejeitada → REPROVADO
- **C** (Challenge): Desafio necessário → Aguarda cliente

---

## FLUXO DE INTEGRAÇÃO

### Para POSP2/Apps/Checkout:

```python
# 1. Chamar análise
response = requests.post('/api/antifraude/analyze/', {
    'cpf': '12345678900',
    'valor': 250.00,
    'modalidade': 'CREDITO',
    'numero_cartao': '5111111111111111'
})

# 2. Verificar se requer 3DS
if response['requer_3ds']:
    # Redirecionar cliente para URL de autenticação
    redirect_url = response['dados_3ds']['redirect_url']
    auth_id = response['dados_3ds']['auth_id']
    
    # Cliente completa desafio...
    
    # 3. Validar resultado 3DS
    validacao = requests.post('/api/antifraude/validate-3ds/', {
        'auth_id': auth_id,
        'transacao_id': response['transacao_id']
    })
    
    # 4. Usar CAVV/ECI na transação Pinbank
    if validacao['autenticado']:
        eci = validacao['eci']
        cavv = validacao['cavv']
        # Processar transação com dados 3DS
```

---

## SEGURANÇA

### Autenticação:
- Todos endpoints requerem OAuth token
- Header: `Authorization: Bearer <token>`

### Assinatura de Requisições:
- Requisições 3DS assinadas com HMAC SHA256
- Evita man-in-the-middle e replay attacks

### Timeout:
- Padrão: 30 segundos
- Configurável via `THREEDS_TIMEOUT`

---

## PRÓXIMOS PASSOS

### Semana 14: Integração e Testes

1. **Integrar POSP2** - Interceptar transações antes de processar
2. **Integrar Apps Mobile** - Análise em operações críticas
3. **Integrar Checkout Web** - Análise no pagamento
4. **Testes E2E** - Validar todos os fluxos
5. **Deploy Staging** - Ambiente de homologação

---

## TESTES

### Testar 3DS:

```bash
# 1. Verificar health
curl http://localhost:8004/api/antifraude/health/ \
  -H "Authorization: Bearer <token>"

# 2. Análise com 3DS
curl -X POST http://localhost:8004/api/antifraude/analyze/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "cpf": "12345678900",
    "valor": 600.00,
    "modalidade": "CREDITO",
    "numero_cartao": "5111111111111111",
    "loja_id": 1
  }'

# 3. Validar 3DS
curl -X POST http://localhost:8004/api/antifraude/validate-3ds/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "auth_id": "3DS-AUTH-123",
    "transacao_id": "TRX-123"
  }'
```

---

## MÉTRICAS DE SUCESSO

- ✅ Service 3DS implementado (439 linhas)
- ✅ 4 endpoints REST públicos criados
- ✅ Integração 3DS no fluxo de análise
- ✅ Configurações e documentação completas
- ✅ Compatibilidade mantida com endpoints legados

**Tempo de desenvolvimento:** 1 dia  
**Linhas de código:** ~800 linhas

---

## REFERÊNCIAS

- **3D Secure 2.0 Spec:** https://www.emvco.com/emv-technologies/3d-secure/
- **EMVCo:** https://www.emvco.com/
- **PCI DSS:** https://www.pcisecuritystandards.org/

---

**Fase 2 - Semana 13 CONCLUÍDA** ✅
