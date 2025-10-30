# 🛡️ WALLCLUB RISK ENGINE - MOTOR ANTIFRAUDE

**Versão:** 1.2  
**Data:** 30/10/2025  
**Container:** Separado (porta 8004)

**Atualizações Recentes:**
- **30/10:** `transaction_id` usa `checkout_transactions.id` (era token de 64 chars)
- **23/10:** Campo `transacao_id` aceito diretamente na normalização WEB
- **23/10:** OAuth 2.0 entre containers validado
- **22/10:** Integração completa com Checkout Web (Link de Pagamento)

---

## 📋 VISÃO GERAL

O **Risk Engine** é um sistema independente que analisa transações em tempo real e decide se devem ser aprovadas, reprovadas ou enviadas para revisão manual.

### Fluxo Básico:

```
App Principal (8003)  →  Risk Engine (8004)  →  Decisão
                              ↓
                      Análise de Regras
                              ↓
                    ┌─────────┴─────────┐
                    │                   │
              APROVADO            REPROVADO
                    │                   │
              (Processa)           (Bloqueia)
                    
                    REVISAO
                      ↓
              ┌───────┴───────┐
              │ Notificação   │
              ├─ Email        │
              └─ Slack        │
                      ↓
              Dashboard Admin
                      ↓
        ┌─────────────┴─────────────┐
    Aprovar                     Reprovar
        │                           │
    Callback                    Callback
        ↓                           ↓
App processa                 App cancela
```

---

## 🎯 COMO FUNCIONAM AS REGRAS

### 1. Estrutura de Uma Regra

Cada regra tem:

| Campo | Descrição | Exemplo |
|-------|-----------|---------|
| **Nome** | Identificação única | "Velocidade Alta - Múltiplas Transações" |
| **Tipo** | Categoria da regra | VELOCIDADE, VALOR, DISPOSITIVO, HORARIO, LOCALIZACAO |
| **Parâmetros** | Configuração em JSON | `{"max_transacoes": 3, "janela_minutos": 10}` |
| **Peso** | Impacto no score (1-10) | 8 |
| **Ação** | O que fazer se disparar | APROVAR, REPROVAR, REVISAR, ALERTAR |
| **Prioridade** | Ordem de execução (1-100) | 10 (executa primeiro) |

### 2. Cálculo do Score de Risco

```python
# Para cada regra que dispara:
score_total += peso_da_regra * 10

# Exemplos:
Regra com peso 8 → +80 pontos
Regra com peso 5 → +50 pontos
Regra com peso 3 → +30 pontos

# Score máximo: 100 pontos
```

### 3. Decisão Final

```
Score < 50      → APROVADO (baixo risco)
Score 50-80     → REVISAO (risco médio)
Score > 80      → REPROVADO (alto risco)

MAS: Se alguma regra tem ação=REPROVAR → REPROVADO (independente do score)
```

---

## 📊 REGRAS IMPLEMENTADAS (5 básicas)

### **Regra 1: Velocidade Alta**
```json
{
  "nome": "Velocidade Alta - Múltiplas Transações",
  "tipo": "VELOCIDADE",
  "parametros": {
    "max_transacoes": 3,
    "janela_minutos": 10
  },
  "peso": 8,
  "acao": "REVISAR",
  "prioridade": 10
}
```

**Lógica:**
- Conta transações do mesmo CPF nos últimos 10 minutos
- Se > 3 transações → Dispara (score +80)
- **Exemplo real:** Cliente faz 4 compras em 8 minutos = SUSPEITO

---

### **Regra 2: Valor Suspeito**
```json
{
  "nome": "Valor Suspeito - Acima do Normal",
  "tipo": "VALOR",
  "parametros": {
    "multiplicador_media": 3
  },
  "peso": 7,
  "acao": "REVISAR",
  "prioridade": 20
}
```

**Lógica:**
- Calcula média das transações do cliente (últimos 30 dias)
- Se valor_atual > (média * 3) → Dispara (score +70)
- **Exemplo real:** Cliente costuma gastar R$ 50, faz compra de R$ 200 = SUSPEITO

---

### **Regra 3: Dispositivo Novo**
```json
{
  "nome": "Dispositivo Novo",
  "tipo": "DISPOSITIVO",
  "parametros": {
    "permitir_primeiro_uso": true
  },
  "peso": 5,
  "acao": "ALERTAR",
  "prioridade": 30
}
```

**Lógica:**
- Verifica se `device_fingerprint` já foi usado pelo cliente
- Se nunca usou → Dispara (score +50)
- **Exemplo real:** Cliente sempre usa iPhone, agora aparece Android = ALERTA

---

### **Regra 4: Horário Incomum**
```json
{
  "nome": "Horário Incomum",
  "tipo": "HORARIO",
  "parametros": {
    "hora_inicio": 0,
    "hora_fim": 5
  },
  "peso": 4,
  "acao": "ALERTAR",
  "prioridade": 40
}
```

**Lógica:**
- Verifica hora da transação
- Se entre 00h-05h → Dispara (score +40)
- **Exemplo real:** Compra às 3h da manhã = ALERTA

---

### **Regra 5: IP Suspeito**
```json
{
  "nome": "IP Suspeito - Múltiplos CPFs",
  "tipo": "LOCALIZACAO",
  "parametros": {
    "max_cpfs_por_ip": 5,
    "janela_horas": 24
  },
  "peso": 9,
  "acao": "REVISAR",
  "prioridade": 15
}
```

**Lógica:**
- Conta CPFs diferentes usando mesmo IP nas últimas 24h
- Se > 5 CPFs → Dispara (score +90)
- **Exemplo real:** 10 CPFs diferentes em 1 IP = FRAUDADOR usando proxy

---

## 🔄 TRATAMENTO DE PEDIDOS SUSPEITOS

### Cenário 1: Cliente Novo (CPF nunca visto)

```
1. Cliente novo faz 1ª transação R$ 150
2. Risk Engine analisa:
   ├─ Regra "Dispositivo Novo" → Dispara (+50 pontos)
   └─ Score = 50 → REVISAO

3. Sistema notifica:
   ├─ Email: admin@wallclub.com.br
   └─ Slack: #antifraude

4. Analista vê no dashboard:
   GET /api/antifraude/revisao/pendentes/
   
   {
     "transacao_id": "NSU123456",
     "cpf": "12345678900",
     "valor": 150.00,
     "score_risco": 50,
     "motivo": "Dispositivo Novo: Primeiro uso deste dispositivo"
   }

5. Analista DECIDE:
   
   OPÇÃO A - APROVAR:
   POST /api/antifraude/revisao/1/aprovar/
   {
     "usuario_id": 123,
     "observacao": "CPF validado, cliente verificado por telefone"
   }
   → Callback para app principal
   → App libera a compra
   
   OPÇÃO B - REPROVAR:
   POST /api/antifraude/revisao/1/reprovar/
   {
     "usuario_id": 123,
     "observacao": "CPF em blacklist do Serasa"
   }
   → Callback para app principal
   → App cancela e bloqueia CPF
```

---

### Cenário 2: Múltiplas Transações Rápidas

```
1. Cliente faz 4 compras em 8 minutos:
   - 08:00 → R$ 50
   - 08:03 → R$ 75
   - 08:05 → R$ 100
   - 08:08 → R$ 120

2. Na 4ª transação, Risk Engine analisa:
   ├─ Regra "Velocidade Alta" → Dispara (+80 pontos)
   └─ Score = 80 → REVISAO

3. Sistema notifica automaticamente

4. Analista investiga:
   - Verifica histórico do cliente
   - Liga para cliente
   - Cliente confirma: "Fiz compras para família"

5. Analista APROVA com observação:
   "Cliente confirmou por telefone, é um presente de aniversário"
   
6. App libera todas as 4 transações
```

---

### Cenário 3: IP Suspeito (Fraude Real)

```
1. 10 CPFs diferentes fazem transações do mesmo IP em 2 horas

2. Na 10ª transação, Risk Engine analisa:
   ├─ Regra "IP Suspeito" → Dispara (+90 pontos)
   └─ Score = 90 → REPROVADO (automático)

3. Transação BLOQUEADA imediatamente
   (Não vai para revisão, reprovação automática)

4. Sistema registra no banco:
   decisao = 'REPROVADO'
   motivo = '10 CPFs diferentes no IP 192.168.1.1'

5. App principal recebe resposta:
   {
     "decisao": "REPROVADO",
     "score_risco": 90,
     "motivo": "IP Suspeito..."
   }
   
6. App bloqueia transação e notifica cliente
```

---

## 🔗 INTEGRAÇÃO COM APP PRINCIPAL

### 1. App Principal Chama Risk Engine

```python
# No app principal (wallclub_django)
import requests

def processar_transacao_posp2(nsu, cliente_id, valor, ...):
    # 1. Enviar para análise
    response = requests.post(
        'http://wallclub-riskengine:8004/api/antifraude/analisar/',
        json={
            'origem': 'POS',
            'transacao_id': nsu,
            'cliente_id': cliente_id,
            'cpf': cpf,
            'valor': valor,
            'modalidade': 'PIX',
            'terminal': terminal,
            'loja_id': loja_id,
            'canal_id': canal_id
        },
        timeout=5
    )
    
    decisao = response.json()
    
    # 2. Tratar decisão
    if decisao['decisao'] == 'APROVADO':
        # Processar normalmente
        return processar_pagamento()
    
    elif decisao['decisao'] == 'REPROVADO':
        # Bloquear
        return {'erro': 'Transação bloqueada por segurança'}
    
    elif decisao['decisao'] == 'REVISAO':
        # Marcar como pendente
        return {
            'status': 'PENDENTE_REVISAO',
            'mensagem': 'Transação em análise, aguarde aprovação'
        }
```

---

### 2. Risk Engine Faz Callback Após Revisão

```python
# No app principal, criar endpoint callback
@api_view(['POST'])
def callback_antifraude(request):
    """
    Recebe callback do Risk Engine após revisão manual
    
    POST /api/antifraude/callback/
    {
        "transacao_id": "NSU123456",
        "decisao_final": "APROVADO",
        "revisado_por": 123,
        "observacao": "Cliente verificado"
    }
    """
    transacao_id = request.data['transacao_id']
    decisao_final = request.data['decisao_final']
    
    # Buscar transação pendente
    transacao = Transacao.objects.get(nsu=transacao_id, status='PENDENTE_REVISAO')
    
    if decisao_final == 'APROVADO':
        # Liberar transação
        transacao.status = 'APROVADO'
        transacao.save()
        processar_pagamento(transacao)
        
    else:  # REPROVADO
        # Cancelar transação
        transacao.status = 'CANCELADO'
        transacao.save()
        estornar_se_necessario(transacao)
    
    return Response({'ok': True})
```

---

### 3. Integração Checkout Web - Link de Pagamento (✅ 22/10/2025)

```python
# No checkout/link_pagamento_web/services.py
from checkout.services_antifraude import CheckoutAntifraudeService

def processar_checkout_link_pagamento(
    token: str,
    dados_cartao: Dict[str, Any],
    dados_sessao: Dict[str, Any],
    ip_address: str,
    user_agent: str
) -> Dict[str, Any]:
    # ... validações iniciais ...
    
    # ========================================
    # ANÁLISE ANTIFRAUDE (RISK ENGINE)
    # ========================================
    permitir, resultado_antifraude = CheckoutAntifraudeService.analisar_transacao(
        cpf=session.cpf,
        valor=valor_final,
        modalidade=session.tipo_pagamento,
        parcelas=session.parcelas,
        loja_id=token_obj.loja_id,
        canal_id=token_obj.canal_id,
        numero_cartao=numero_cartao,
        bandeira=dados_cartao.get('bandeira'),
        ip_address=ip_address,
        user_agent=user_agent,
        device_fingerprint=dados_sessao.get('device_fingerprint'),
        cliente_nome=session.nome,
        transaction_id=f"CHECKOUT-{token}"
    )
    
    # Salvar resultado na transação
    transacao.score_risco = resultado_antifraude.get('score_risco', 0)
    transacao.decisao_antifraude = resultado_antifraude.get('decisao', 'APROVADO')
    transacao.motivo_bloqueio = resultado_antifraude.get('motivo', '')
    transacao.antifraude_response = resultado_antifraude
    
    # Tratar REPROVADO
    if not permitir or resultado_antifraude.get('decisao') == 'REPROVADO':
        transacao.status = 'BLOQUEADA_ANTIFRAUDE'
        transacao.save()
        
        return {
            'sucesso': False,
            'mensagem': 'Transação bloqueada por segurança. Entre em contato com o vendedor.'
        }
    
    # Tratar REVISAR (processar mas marcar)
    if resultado_antifraude.get('decisao') == 'REVISAR':
        transacao.status = 'PENDENTE_REVISAO'
    
    # Continuar processamento no Pinbank
    resultado_transacao = transacoes_service.efetuar_transacao_cartao(dados_transacao)
    # ...
```

**Campos Adicionados no Model (checkout_transactions):**
```python
class CheckoutTransaction(models.Model):
    # ... campos existentes ...
    
    # Antifraude (Risk Engine)
    score_risco = models.IntegerField(null=True, blank=True)  # 0-100
    decisao_antifraude = models.CharField(max_length=20, null=True)  # APROVADO/REPROVADO/REVISAR
    motivo_bloqueio = models.TextField(null=True, blank=True)
    antifraude_response = models.JSONField(null=True, blank=True)
    revisado_por = models.BigIntegerField(null=True, blank=True)
    revisado_em = models.DateTimeField(null=True, blank=True)
    observacao_revisao = models.TextField(null=True, blank=True)
    
    # Status
    STATUS_CHOICES = [
        # ... status existentes ...
        ('BLOQUEADA_ANTIFRAUDE', 'Bloqueada pelo Antifraude'),
        ('PENDENTE_REVISAO', 'Pendente de Revisão Manual'),
    ]
```

**SQL Migration:**
```sql
-- scripts/sql/adicionar_campos_antifraude_checkout.sql
ALTER TABLE checkout_transactions 
MODIFY COLUMN status VARCHAR(30) NOT NULL DEFAULT 'PENDENTE';

ALTER TABLE checkout_transactions
ADD COLUMN score_risco INT NULL,
ADD COLUMN decisao_antifraude VARCHAR(20) NULL,
ADD COLUMN motivo_bloqueio TEXT NULL,
ADD COLUMN antifraude_response JSON NULL,
ADD COLUMN revisado_por BIGINT NULL,
ADD COLUMN revisado_em DATETIME NULL,
ADD COLUMN observacao_revisao TEXT NULL;

CREATE INDEX idx_score_risco ON checkout_transactions(score_risco);
CREATE INDEX idx_decisao_antifraude ON checkout_transactions(decisao_antifraude);
```

**Fluxo Completo:**
```
Cliente → Link Pagamento → Preenche Cartão → Envia
                                              ↓
                                    Risk Engine Analisa
                                              ↓
                            ┌─────────┬─────────┐
                            │           │           │
                        APROVADO    REVISAR    REPROVADO
                            │           │           │
                      Processa  Processa+  Bloqueia
                       Pinbank   Notifica   Imediato
                            │    Analista      │
                        APROVADA PENDENTE_ BLOQUEADA_
                                 REVISAO   ANTIFRAUDE
```

---

## 📊 EXEMPLO COMPLETO PASSO A PASSO

### Situação: CPF Novo com Valor Alto

```
┌─────────────────────────────────────────────────────────────┐
│ 1. CLIENTE FAZ COMPRA                                       │
├─────────────────────────────────────────────────────────────┤
│ CPF: 123.456.789-00 (NUNCA COMPROU ANTES)                   │
│ Valor: R$ 500,00                                            │
│ Dispositivo: iPhone 15 (nunca usado por ele)                │
│ Horário: 14:30 (normal)                                     │
│ IP: 192.168.1.50                                            │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. APP PRINCIPAL ENVIA PARA RISK ENGINE                     │
├─────────────────────────────────────────────────────────────┤
│ POST http://wallclub-riskengine:8004/api/antifraude/analisar/ │
│ {                                                           │
│   "origem": "APP",                                          │
│   "transacao_id": "ORD789",                                 │
│   "cliente_id": 1,                                          │
│   "cpf": "12345678900",                                     │
│   "valor": 500.00,                                          │
│   "modalidade": "PIX"                                       │
│ }                                                           │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. RISK ENGINE EXECUTA REGRAS (prioridade crescente)        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ ✅ Regra "Velocidade Alta" (prior. 10)                      │
│    └─ Apenas 1 transação em 10min → NÃO dispara            │
│                                                             │
│ ✅ Regra "IP Suspeito" (prior. 15)                          │
│    └─ Apenas 1 CPF neste IP → NÃO dispara                  │
│                                                             │
│ ✅ Regra "Valor Suspeito" (prior. 20)                       │
│    └─ Sem histórico para comparar → NÃO dispara            │
│                                                             │
│ 🔴 Regra "Dispositivo Novo" (prior. 30)                     │
│    └─ Primeiro uso do device → DISPARA!                    │
│        Score: +50 pontos                                    │
│        Ação: ALERTAR                                        │
│                                                             │
│ ✅ Regra "Horário Incomum" (prior. 40)                      │
│    └─ 14:30 é horário normal → NÃO dispara                 │
│                                                             │
│ SCORE FINAL: 50 pontos                                     │
│ DECISÃO: REVISAO (score 50-80)                             │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. RISK ENGINE SALVA DECISÃO NO BANCO                       │
├─────────────────────────────────────────────────────────────┤
│ INSERT INTO antifraude_decisao (                           │
│   transacao_id=123,                                         │
│   score_risco=50,                                           │
│   decisao='REVISAO',                                        │
│   motivo='Dispositivo Novo: Primeiro uso...',              │
│   tempo_analise_ms=125                                      │
│ )                                                           │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. RISK ENGINE NOTIFICA EQUIPE                              │
├─────────────────────────────────────────────────────────────┤
│ 📧 Email para: admin@wallclub.com.br                        │
│    Assunto: [ANTIFRAUDE] Revisão Manual Necessária         │
│    Corpo: Transação ORD789 - Score 50 - R$ 500             │
│                                                             │
│ 💬 Slack: #antifraude                                       │
│    🔴 REVISÃO MANUAL NECESSÁRIA                             │
│    Transação: ORD789                                        │
│    Score: 50/100                                            │
│    Motivo: Dispositivo Novo                                 │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 6. RISK ENGINE RESPONDE PARA APP PRINCIPAL                  │
├─────────────────────────────────────────────────────────────┤
│ Response (125ms):                                           │
│ {                                                           │
│   "decisao": "REVISAO",                                     │
│   "score_risco": 50,                                        │
│   "motivo": "Dispositivo Novo: Primeiro uso...",           │
│   "regras_acionadas": [                                     │
│     {                                                       │
│       "nome": "Dispositivo Novo",                           │
│       "tipo": "DISPOSITIVO",                                │
│       "peso": 5,                                            │
│       "acao": "ALERTAR"                                     │
│     }                                                       │
│   ]                                                         │
│ }                                                           │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 7. APP PRINCIPAL MARCA COMO PENDENTE                        │
├─────────────────────────────────────────────────────────────┤
│ UPDATE transacoes                                           │
│ SET status = 'PENDENTE_REVISAO'                             │
│ WHERE id = 789                                              │
│                                                             │
│ Response para cliente:                                      │
│ {                                                           │
│   "status": "PENDENTE",                                     │
│   "mensagem": "Pedido em análise, você será notificado"    │
│ }                                                           │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 8. ANALISTA ACESSA DASHBOARD (10 minutos depois)            │
├─────────────────────────────────────────────────────────────┤
│ GET /api/antifraude/revisao/pendentes/                      │
│                                                             │
│ Response:                                                   │
│ {                                                           │
│   "total": 1,                                               │
│   "pendentes": [                                            │
│     {                                                       │
│       "id": 456,                                            │
│       "transacao_id": "ORD789",                             │
│       "cpf": "12345678900",                                 │
│       "valor": "500.00",                                    │
│       "score_risco": 50,                                    │
│       "motivo": "Dispositivo Novo..."                       │
│     }                                                       │
│   ]                                                         │
│ }                                                           │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 9. ANALISTA INVESTIGA                                       │
├─────────────────────────────────────────────────────────────┤
│ - Verifica CPF no Serasa: APROVADO ✅                       │
│ - Liga para cliente: Confirma compra ✅                     │
│ - Decisão: APROVAR                                          │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 10. ANALISTA APROVA NO SISTEMA                              │
├─────────────────────────────────────────────────────────────┤
│ POST /api/antifraude/revisao/456/aprovar/                   │
│ {                                                           │
│   "usuario_id": 123,                                        │
│   "observacao": "CPF ok, cliente confirmou por telefone"    │
│ }                                                           │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 11. RISK ENGINE ATUALIZA DECISÃO                            │
├─────────────────────────────────────────────────────────────┤
│ UPDATE antifraude_decisao SET                               │
│   decisao = 'APROVADO',                                     │
│   revisado_por = 123,                                       │
│   revisado_em = NOW(),                                      │
│   observacao_revisao = 'CPF ok, cliente confirmou...'       │
│ WHERE id = 456                                              │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 12. RISK ENGINE FAZ CALLBACK PARA APP PRINCIPAL             │
├─────────────────────────────────────────────────────────────┤
│ POST http://wallclub-prod:8000/api/antifraude/callback/     │
│ {                                                           │
│   "transacao_id": "ORD789",                                 │
│   "decisao_final": "APROVADO",                              │
│   "score_risco": 50,                                        │
│   "revisado_por": 123,                                      │
│   "observacao": "CPF ok, cliente confirmou..."              │
│ }                                                           │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 13. APP PRINCIPAL LIBERA TRANSAÇÃO                          │
├─────────────────────────────────────────────────────────────┤
│ UPDATE transacoes                                           │
│ SET status = 'APROVADO'                                     │
│ WHERE id = 789                                              │
│                                                             │
│ # Processar pagamento                                       │
│ processar_pix(transacao)                                    │
│                                                             │
│ # Notificar cliente                                         │
│ enviar_email(cliente, "Pedido aprovado!")                   │
└─────────────────────────────────────────────────────────────┘
                          ↓
                      ✅ CONCLUÍDO
```

---

## 🔧 CONFIGURAÇÕES

### Variáveis de Ambiente

```env
# Risk Engine (.env)
SECRET_KEY=django-secret-key
DEBUG=False

# Banco compartilhado
DB_NAME=wallclub
DB_USER=root
DB_PASSWORD=senha
DB_HOST=mysql

# Cache compartilhado
REDIS_HOST=redis
REDIS_PORT=6379

# Callback
CALLBACK_URL_PRINCIPAL=http://wallclub-prod-release300:8000

# Notificações
NOTIFICACAO_EMAIL=admin@wallclub.com.br,fraude@wallclub.com.br
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T00000/B00000/XXXX
```

---

## 📈 MÉTRICAS E MONITORAMENTO

### Dashboards Sugeridos

1. **Taxa de Aprovação**
   - Total analisado vs Aprovado/Reprovado/Revisão
   - Meta: >90% aprovação automática

2. **Score Médio**
   - Score médio por origem (POS, APP, WEB)
   - Score médio por horário

3. **Tempo de Análise**
   - Média: <200ms
   - P95: <500ms

4. **Taxa de Fraude Real**
   - Transações reprovadas que eram fraude real
   - Falsos positivos (bloqueou transação legítima)

5. **Tempo de Revisão Manual**
   - Tempo médio entre notificação e decisão
   - Meta: <15 minutos

---

## 🚀 PRÓXIMAS EVOLUÇÕES

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

4. **Integração Externa**
   - MaxMind minFraud
   - Consulta de CPF em bureaus
   - Verificação de BIN de cartão

---

## 📝 RESUMO EXECUTIVO

**O que faz:** Analisa transações em tempo real e decide se aprova, reprova ou envia para revisão manual.

**Como funciona:** Executa 5 regras configuráveis, cada uma soma pontos no score de risco (0-100).

**Decisões:**
- Score <50 = APROVADO (automático)
- Score 50-80 = REVISAO (equipe analisa)
- Score >80 = REPROVADO (automático)

**Tratamento de Suspeitos:**
1. Sistema notifica equipe (email + Slack)
2. Analista revisa no dashboard
3. Aprova ou reprova manualmente
4. Callback para app principal
5. App processa ou cancela

**Tempo médio:** 125ms de análise + 10min de revisão manual (quando necessário)
