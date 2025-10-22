# Semana 8: Coleta e Normalização de Dados

**Status:** ✅ Concluída  
**Data:** 16/10/2025

## Objetivo

Implementar sistema de coleta e normalização de dados de transações vindas de diferentes origens (POS, App Mobile, Checkout Web) em formato único para análise de risco.

---

## Entregas

### 1. ColetaDadosService (`antifraude/services_coleta.py`)

**Funcionalidades:**
- Extração automática de BIN (6 primeiros dígitos do cartão)
- Normalização de origem (POS, APP, WEB)
- Normalização de modalidade (PIX, CREDITO, DEBITO, etc)
- Normalização específica por origem
- Detecção automática de origem
- Validação de dados mínimos

**Métodos principais:**

#### `extrair_bin_cartao(numero_cartao: str) -> str`
- Remove caracteres não numéricos
- Retorna primeiros 6 dígitos
- Suporta formatos: `4111111111111111`, `4111 1111 1111 1111`, `4111-1111-1111-1111`

#### `normalizar_dados_pos(dados: dict) -> dict`
Normaliza dados de Terminal POS:
- `nsu` → `transacao_id`
- `terminal` → `device_fingerprint`
- CPF sem pontuação
- Sem IP (POS não tem IP do cliente)

#### `normalizar_dados_app(dados: dict) -> dict`
Normaliza dados de App Mobile:
- `transaction_id` ou `order_id` → `transacao_id`
- Inclui IP, device_fingerprint, user_agent
- Detecta dispositivo móvel

#### `normalizar_dados_web(dados: dict) -> dict`
Normaliza dados de Checkout Web:
- `order_id` ou `token` → `transacao_id`
- Inclui IP, user_agent
- Browser fingerprint

#### `normalizar_dados(dados: dict, origem: str = None) -> dict`
**Método unificado** que detecta origem automaticamente:
- Se tem `nsu` + `terminal` → POS
- Se tem `device_fingerprint` + `mobile` no user_agent → APP
- Se tem `token` ou outros → WEB

#### `validar_dados_minimos(dados: dict) -> (bool, str)`
Valida campos obrigatórios:
- `transacao_id` presente
- `cpf` válido (11 dígitos)
- `valor` numérico e > 0
- `modalidade` presente

---

### 2. Atualização de Views (`antifraude/views.py`)

**Endpoint `/api/antifraude/analisar/`** refatorado:
- Remove dependência de campo `origem` obrigatório
- Detecta origem automaticamente
- Valida dados antes de criar registro
- Tratamento de erros específico
- Formato de resposta padronizado: `{"sucesso": bool, ...}`

**Campos mínimos obrigatórios:**
- `cpf`
- `valor`
- `modalidade`

**Campos detectados automaticamente:**
- `origem` (POS/APP/WEB)
- `bin_cartao` (extraído de `numero_cartao`)
- `transacao_id` (nsu, order_id, token)

---

### 3. Endpoints de Teste (`antifraude/views_teste.py`)

#### `POST /api/antifraude/teste/normalizar/`
Valida normalização de dados sem criar registro:
```json
{
  "sucesso": true,
  "entrada": {...},
  "saida_normalizada": {...},
  "validacao": {
    "valido": true,
    "erro": null
  },
  "detalhes": {
    "origem_detectada": "POS",
    "bin_extraido": "411111",
    "cpf_normalizado": "12345678900",
    "modalidade_normalizada": "PIX"
  }
}
```

#### `POST /api/antifraude/teste/bin/`
Testa extração de BIN de múltiplos formatos:
```json
{
  "numeros_cartao": [
    "4111111111111111",
    "4111 1111 1111 1111",
    "4111-1111-1111-1111"
  ]
}
```

Retorna:
```json
{
  "sucesso": true,
  "total_testado": 3,
  "resultados": [
    {"entrada": "4111111111111111", "bin": "411111", "valido": true},
    {"entrada": "4111 1111 1111 1111", "bin": "411111", "valido": true},
    {"entrada": "4111-1111-1111-1111", "bin": "411111", "valido": true}
  ]
}
```

#### `GET /api/antifraude/teste/exemplos/`
Retorna payloads de exemplo para cada origem (POS, APP, WEB).

---

## Exemplos de Payloads

### POS (Terminal)
```json
{
  "nsu": "148482386",
  "cpf": "12345678900",
  "cliente_id": 123,
  "valor": 150.00,
  "modalidade": "PIX",
  "parcelas": 1,
  "numero_cartao": "4111111111111111",
  "bandeira": "VISA",
  "terminal": "POS001",
  "loja_id": 1,
  "canal_id": 6
}
```

### APP (Mobile)
```json
{
  "transaction_id": "TXN-2025-001",
  "cpf": "12345678900",
  "cliente_id": 123,
  "valor": 250.00,
  "modalidade": "CREDITO",
  "parcelas": 3,
  "numero_cartao": "5111111111111111",
  "bandeira": "MASTERCARD",
  "ip_address": "192.168.1.100",
  "device_fingerprint": "abc123xyz",
  "user_agent": "WallClub/1.0 (iPhone; iOS 15.0)",
  "loja_id": 1,
  "canal_id": 6
}
```

### WEB (Checkout)
```json
{
  "order_id": "ORD-2025-001",
  "token": "tok_abc123",
  "cpf": "12345678900",
  "cliente_id": 123,
  "valor": 500.00,
  "modalidade": "PARCELADO",
  "parcelas": 6,
  "numero_cartao": "4111 1111 1111 1111",
  "bandeira": "VISA",
  "ip_address": "201.10.20.30",
  "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
  "loja_id": 1,
  "canal_id": 6
}
```

---

## Índices de Busca

**Já implementados no Model TransacaoRisco:**
```python
indexes = [
    models.Index(fields=['cpf', 'data_transacao']),
    models.Index(fields=['ip_address', 'data_transacao']),
    models.Index(fields=['device_fingerprint', 'data_transacao']),
    models.Index(fields=['bin_cartao', 'data_transacao']),
]
```

**Campos indexados individualmente:**
- `transacao_id`
- `origem`
- `cliente_id`
- `cpf`
- `ip_address`
- `device_fingerprint`
- `bin_cartao`
- `loja_id`
- `canal_id`
- `data_transacao`

---

## Testes de Validação

### 1. Testar Normalização POS
```bash
curl -X POST http://localhost:8004/api/antifraude/teste/normalizar/ \
  -H "Content-Type: application/json" \
  -d '{
    "nsu": "123456",
    "cpf": "123.456.789-00",
    "valor": 150,
    "modalidade": "pix",
    "terminal": "POS001"
  }'
```

### 2. Testar Extração BIN
```bash
curl -X POST http://localhost:8004/api/antifraude/teste/bin/ \
  -H "Content-Type: application/json" \
  -d '{
    "numeros_cartao": [
      "4111111111111111",
      "4111 1111 1111 1111",
      "4111-1111-1111-1111"
    ]
  }'
```

### 3. Ver Exemplos
```bash
curl http://localhost:8004/api/antifraude/teste/exemplos/
```

---

## Próxima Fase

**Semana 9: Integração MaxMind**
- Integrar MaxMind minFraud para score externo
- Cache Redis (1 hora)
- Fallback para score neutro (50)
- Logs de consultas

---

## Arquivos Criados

1. `antifraude/services_coleta.py` - 330 linhas
2. `antifraude/views_teste.py` - 150 linhas
3. `docs/semana_8_coleta_dados.md` - Este arquivo

## Arquivos Modificados

1. `antifraude/views.py` - Refatorado endpoint analisar_transacao
2. `antifraude/urls.py` - Adicionadas rotas de teste
