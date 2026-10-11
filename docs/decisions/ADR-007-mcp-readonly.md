# ADR-007 — Servidor MCP oficial, local e somente leitura

- **Status:** Aceito para a integração de portfólio
- **Transporte:** `stdio`
- **SDK:** pacote Python oficial `mcp` (instalado via extra opcional `.[mcp]`)

## Contexto

A integração permite que um cliente MCP compatível consulte o estado do Sentinel e faça análise limitada de um evento autorizado, sem fornecer acesso genérico ao sistema operacional, arquivos ou implantação.

## Ferramentas permitidas

| Ferramenta | Capacidade | Limite |
|---|---|---|
| `get_model_info` | Estado e versão do modelo | Não expõe caminhos de artefatos |
| `analyze_event` | Validar e analisar um evento | Um evento, limite de payload, sem persistência e sem eco do evento bruto |
| `get_metrics_summary` | Resumo de métricas existentes | Lê relatório de caminho fixo e devolve apenas campos permitidos |
| `get_drift_summary` | Resumo de drift existente | Não aceita caminho do cliente; explica limitações de interpretação |

## Proibições

Não existem ferramentas para shell, execução de código, escrita de arquivos, treinamento, deploy, alteração de configuração ou acesso a caminhos arbitrários. Ferramentas MCP não devem registrar payloads brutos ou dados sensíveis.

## Consequências e limitações

- O servidor usa `stdio`, não um endpoint de rede; a configuração do cliente define quem pode iniciá-lo.
- `analyze_event` é uma operação analítica, mas não modifica estado persistente.
- Relatórios ausentes retornam `available: false`; isso não é falha do serviço.
- Scores de anomalia não são probabilidades calibradas.
- Data drift não comprova, por si só, perda de acurácia.
- A revisão de segurança precisa ser repetida após alterações nas ferramentas, no SDK ou no fluxo de dados.
