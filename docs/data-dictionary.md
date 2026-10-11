# Dicionário de Dados

## Evento de Log (`LogEvent`)

Schema de entrada do Sentinel. Todos os campos marcados com `*` são obrigatórios.

| Campo | Tipo | Descrição | Exemplo |
|---|---|---|---|
| `event_id` * | `str` (UUID) | Identificador único do evento | `"a1b2c3d4-..."` |
| `timestamp` * | `datetime` (ISO 8601) | Momento do evento em UTC | `"2025-01-15T14:23:00Z"` |
| `source_ip` * | `str` (IPv4/IPv6) | IP de origem da requisição | `"192.168.1.10"` |
| `dest_ip` | `str` (IPv4/IPv6) | IP de destino | `"10.0.0.1"` |
| `dest_port` | `int` (1–65535) | Porta de destino | `443` |
| `protocol` | `str` (enum) | Protocolo: `TCP`, `UDP`, `ICMP`, `HTTP`, `HTTPS` | `"HTTPS"` |
| `event_type` * | `str` (enum) | Tipo: `auth_attempt`, `http_request`, `dns_query`, `network_flow` | `"auth_attempt"` |
| `status` * | `str` (enum) | Resultado: `success`, `failure`, `blocked`, `timeout` | `"failure"` |
| `user_id` | `str` | Identificador do usuário (anonimizado) | `"user_42"` |
| `payload_size_bytes` | `int` (≥ 0) | Tamanho do payload em bytes | `1024` |
| `user_agent` | `str` | User-agent HTTP (quando aplicável) | `"Mozilla/5.0..."` |
| `request_path` | `str` | Caminho da requisição HTTP | `"/api/v1/login"` |
| `metadata` | `dict` | Campos adicionais sem schema fixo | `{"region": "br-east"}` |

## Alerta (`Alert`)

Saída do pipeline de detecção.

| Campo | Tipo | Descrição |
|---|---|---|
| `alert_id` | `str` (UUID) | Identificador único do alerta |
| `created_at` | `datetime` | Timestamp de geração do alerta |
| `category` | `str` (enum) | `brute_force`, `traffic_spike`, `injection_attempt`, `anomaly`, `unknown` |
| `priority` | `str` (enum) | `low`, `medium`, `high`, `critical` |
| `score` | `float` (0–1) | Score composto — **não é probabilidade calibrada** |
| `signals` | `list[Signal]` | Lista de sinais que contribuíram para o alerta |
| `source_event_ids` | `list[str]` | IDs dos eventos de origem |
| `limitations` | `str` | Texto explícito sobre as limitações da avaliação |
| `model_version` | `str` | Versão do modelo utilizado |

## Sinal (`Signal`)

Componente de explicabilidade do alerta.

| Campo | Tipo | Descrição |
|---|---|---|
| `name` | `str` | Nome do sinal (ex: `repeated_auth_failures`) |
| `source` | `str` (enum) | `rule` ou `model` |
| `value` | `float` | Valor numérico observado |
| `threshold` | `float` | Limiar que ativou o sinal |
| `contribution` | `float` (0–1) | Contribuição relativa para o score final |

## Tipos de Eventos Gerados Sinteticamente

| Tipo | Frequência base | Descrição |
|---|---|---|
| `auth_attempt` | Alta | Tentativas de autenticação (sucesso e falha) |
| `http_request` | Muito alta | Requisições HTTP/HTTPS comuns |
| `dns_query` | Alta | Consultas DNS |
| `network_flow` | Média | Fluxos de rede entre hosts |

## Categorias de Alertas Detectados

| Categoria | Regras associadas | Modelo ML |
|---|---|---|
| `brute_force` | ≥ N falhas de auth em janela T | IsolationForest |
| `traffic_spike` | Volume de requisições > P95 da baseline | IsolationForest |
| `injection_attempt` | Padrões SQL/XSS/path traversal no payload | — (somente regras) |
| `anomaly` | Comportamento incomum detectado pelo modelo | IsolationForest |
