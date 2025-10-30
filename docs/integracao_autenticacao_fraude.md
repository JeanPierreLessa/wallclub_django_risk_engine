# Integração: Autenticação Cliente ↔ Engine de Fraude

## Visão Geral

Integração entre `wallclub_django` (autenticação de clientes) e `wallclub-riskengine` (análise antifraude) para enriquecer a análise de risco com dados comportamentais de autenticação.

## Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                     wallclub-riskengine                         │
│                                                                 │
│  ┌────────────────────────────────────────────────────────┐   │
│  │  AnaliseRiscoService.analisar_transacao()              │   │
│  │                                                         │   │
│  │  1. Score MaxMind (base)                              │   │
│  │  2. Score Whitelist (desconto)                        │   │
│  │  3. Score Autenticação (novo) ◄─────────────┐        │   │
│  │  4. Regras internas                          │        │   │
│  │  5. Decisão final                            │        │   │
│  └──────────────────────────────────────────────┼────────┘   │
│                                                  │            │
│  ┌──────────────────────────────────────────────┼────────┐   │
│  │  ClienteAutenticacaoService                  │        │   │
│  │                                               │        │   │
│  │  consultar_historico_autenticacao() ─────────┘        │   │
│  │  calcular_score_autenticacao()                        │   │
│  └───────────────────────────────┬───────────────────────┘   │
│                                   │                           │
│                                   │ OAuth 2.0                 │
│                                   │ GET /api/v1/...           │
└───────────────────────────────────┼───────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                      wallclub_django                            │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  ClienteAutenticacaoAnaliseView                         │   │
│  │  GET /cliente/api/v1/autenticacao/analise/<cpf>/       │   │
│  │                                                         │   │
│  │  @require_oauth_riskengine  (OAuth exclusivo)         │   │
│  └─────────────────────────┬───────────────────────────────┘   │
│                             │                                   │
│  ┌──────────────────────────▼──────────────────────────────┐   │
│  │  ClienteAutenticacaoAnaliseService                      │   │
│  │                                                         │   │
│  │  analisar_historico_cliente() ────────┐                │   │
│  │    ├─ TentativaLogin                  │                │   │
│  │    ├─ ClienteAutenticacao             │                │   │
│  │    ├─ Bloqueio                        │                │   │
│  │    └─ ClienteJWTToken                 │                │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Fluxo de Dados

### 1. Requisição de Análise
```python
# wallclub-riskengine: AnaliseRiscoService
transacao = TransacaoRisco.objects.create(
    cpf='12345678900',
    valor=1000.00,
    ip_address='192.168.1.1',
    device_fingerprint='abc123',
    # ...
)

decisao = AnaliseRiscoService.analisar_transacao(transacao)
```

### 2. Consulta de Autenticação (Automática)
```python
# wallclub-riskengine: ClienteAutenticacaoService
dados_auth = ClienteAutenticacaoService.consultar_historico_autenticacao(
    cpf='12345678900',
    canal_id=1
)
```

### 3. Resposta do Django
```json
{
  "encontrado": true,
  "cpf": "12345678900",
  "cliente_id": 123,
  "status_autenticacao": {
    "bloqueado": false,
    "tentativas_15min": 0,
    "tentativas_1h": 1,
    "ultimo_ip": "192.168.1.1"
  },
  "historico_recente": {
    "total_tentativas": 10,
    "tentativas_falhas": 2,
    "taxa_falha": 0.2,
    "ips_distintos": 2,
    "devices_distintos": 1
  },
  "dispositivos_conhecidos": [
    {
      "device_fingerprint": "abc123",
      "total_logins": 50,
      "confiavel": true
    }
  ],
  "bloqueios_historico": [],
  "flags_risco": [
    "ip_novo"
  ]
}
```

### 4. Cálculo de Score
```python
# wallclub-riskengine: ClienteAutenticacaoService
score_auth = ClienteAutenticacaoService.calcular_score_autenticacao(dados_auth)
# Retorna: 10 (IP novo)

# Adicionado ao score total
score_total += score_auth  # MaxMind + Whitelist + Autenticação + Regras
```

## Flags de Risco

| Flag | Descrição | Score |
|------|-----------|-------|
| `conta_bloqueada` | Conta bloqueada agora | +30 |
| `bloqueio_recente` | Bloqueio nos últimos 7 dias | +20 |
| `multiplos_bloqueios` | 2+ bloqueios em 30 dias | +15 |
| `alta_taxa_falha` | Taxa de falha >= 30% | +15 |
| `multiplas_tentativas_falhas` | 5+ falhas em 24h | +10 |
| `multiplos_ips_recentes` | 3+ IPs distintos em 24h | +10 |
| `multiplos_devices_recentes` | 2+ devices em 24h | +10 |
| `todos_devices_novos` | Todos devices com < 7 dias | +10 |
| `nenhum_device_confiavel` | Nenhum device com 10+ logins | +5 |

**Score máximo de autenticação: 50 pontos**

## Novas Regras Antifraude

### Regra 1: Dispositivo Novo - Alto Valor
```json
{
  "nome": "Dispositivo Novo - Alto Valor",
  "tipo": "DISPOSITIVO",
  "parametros": {
    "device_age_days": 7,
    "valor_minimo": 500.00
  },
  "peso": 7,
  "acao": "REVISAR"
}
```

### Regra 2: IP Novo + Histórico de Bloqueios
```json
{
  "nome": "IP Novo + Histórico de Bloqueios",
  "tipo": "LOCALIZACAO",
  "parametros": {
    "ip_age_days": 3,
    "bloqueios_ultimos_30_dias": 2
  },
  "peso": 8,
  "acao": "REVISAR"
}
```

### Regra 3: Múltiplas Tentativas Falhas Recentes
```json
{
  "nome": "Múltiplas Tentativas Falhas Recentes",
  "tipo": "CUSTOM",
  "parametros": {
    "tentativas_falhas_24h": 5,
    "taxa_falha_minima": 0.3
  },
  "peso": 6,
  "acao": "REVISAR"
}
```

### Regra 4: Cliente com Bloqueio Recente
```json
{
  "nome": "Cliente com Bloqueio Recente",
  "tipo": "CUSTOM",
  "parametros": {
    "dias_desde_ultimo_bloqueio": 7
  },
  "peso": 9,
  "acao": "REVISAR"
}
```

## Configurações Centralizadas

Todos os parâmetros são configuráveis via `ConfiguracaoAntifraude`:

### Autenticação
- `AUTH_MAX_TENTATIVAS_FALHAS_24H`: 5
- `AUTH_TAXA_FALHA_SUSPEITA`: 0.3
- `AUTH_DIAS_ULTIMO_BLOQUEIO`: 7
- `AUTH_MAX_BLOQUEIOS_30_DIAS`: 2
- `AUTH_MAX_IPS_DISTINTOS_24H`: 3
- `AUTH_MAX_DEVICES_DISTINTOS_24H`: 2

### Dispositivo
- `DISPOSITIVO_NOVO_DIAS`: 7
- `DISPOSITIVO_MIN_TRANSACOES_CONFIAVEL`: 10

### Localização
- `IP_NOVO_DIAS`: 3

### Geral
- `CONSULTA_AUTH_TIMEOUT_SEGUNDOS`: 2

## Segurança

### OAuth 2.0
- Cliente: `wallclub-riskengine`
- Endpoint protegido: `@require_oauth_riskengine`
- Validação exclusiva: apenas riskengine pode acessar

### LGPD
- CPF mascarado nos logs: `123***`
- Dados mínimos necessários
- Auditoria de todas consultas

### Resiliência
```python
# Fail-safe: se consulta falhar, continua análise sem dados de auth
if dados_auth.get('falha_consulta'):
    score_auth = 0  # Score neutro, não penaliza
```

## Setup

### 1. Popular Configurações
```bash
# Container riskengine
python manage.py shell < scripts/seed_configuracoes_antifraude.py
```

### 2. Criar Regras
```bash
# Container riskengine
python manage.py shell < scripts/seed_regras_autenticacao.py
```

### 3. Registrar Cliente OAuth (se não existir)
```sql
-- wallclub_django
INSERT INTO comum_oauth_client (
    client_id, 
    client_secret, 
    name, 
    allowed_contexts, 
    is_active
) VALUES (
    'wallclub-riskengine',
    'SECRET_KEY_AQUI',
    'WallClub Risk Engine',
    'riskengine',
    true
);
```

## Monitoramento

### Logs
```python
# Consulta bem-sucedida
registrar_log(
    'antifraude.cliente_auth',
    "Consulta OK: CPF 123*** - Encontrado: True - Tempo: 45ms"
)

# Score calculado
registrar_log(
    'antifraude.cliente_auth',
    "Score autenticação: +15 - Flags: 2"
)
```

### Métricas Importantes
- Taxa de timeout nas consultas
- Tempo médio de resposta
- % de clientes com flags de risco
- Score médio de autenticação

## Troubleshooting

### Consulta sempre retorna falha_consulta=true

**Causa**: OAuth token inválido ou expirado

**Solução**:
```python
# Verificar token OAuth
from comum.oauth.services import OAuthService
token = OAuthService.get_oauth_token()
print(token)  # Deve retornar token válido
```

### Score de autenticação sempre 0

**Causa**: Cliente não encontrado ou sem histórico

**Verificar**:
```python
# wallclub_django
from apps.cliente.models import Cliente
Cliente.objects.filter(cpf='12345678900').exists()
```

### Timeout nas consultas

**Ajustar**:
```python
# Aumentar timeout em ConfiguracaoAntifraude
ConfiguracaoAntifraude.objects.filter(
    chave='CONSULTA_AUTH_TIMEOUT_SEGUNDOS'
).update(valor_texto='5')  # 2 → 5 segundos
```

## Performance

### Tempos Esperados
- Consulta OAuth: ~50ms
- Processamento Django: ~30ms
- Cálculo score: ~5ms
- **Total: ~85ms** (< 100ms)

### Otimizações Aplicadas
- Cache de token OAuth (evita renovação a cada chamada)
- Queries otimizadas com `select_related`
- Índices nas tabelas de autenticação
- Timeout configurável
- Fail-fast em caso de erro

## Próximos Passos

1. ✅ Integração básica implementada
2. ✅ Configurações centralizadas
3. ✅ 4 regras de autenticação criadas
4. ⏳ Testes de carga
5. ⏳ Dashboard de monitoramento
6. ⏳ Alertas para comportamentos suspeitos
