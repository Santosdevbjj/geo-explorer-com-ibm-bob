# Integração MCP — Sentinel

Servidor local de ferramentas para clientes MCP compatíveis, incluindo IBM Bob quando configurado para usar servidores MCP locais.

## Instalação e execução

Na raiz do repositório:

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Linux/macOS:
# source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev,mcp]"
python mcp/server.py
```

O servidor usa o SDK oficial `mcp` e transporte `stdio`. Configure o cliente para iniciar
`python mcp/server.py` com o diretório de trabalho na raiz do projeto.

## Ferramentas disponíveis

| Ferramenta | Uso |
|---|---|
| `get_model_info` | Versão, disponibilidade e modo de inferência |
| `analyze_event` | Valida e analisa um evento individual |
| `get_metrics_summary` | Resumo de métricas de avaliação previamente persistidas |
| `get_drift_summary` | Resumo de drift previamente persistido |

## Limites de segurança

- Não existem ferramentas para executar shell, escrever arquivos, treinar, implantar ou alterar configuração.
- As ferramentas não aceitam caminhos de arquivo do cliente.
- `analyze_event` valida o evento com Pydantic e limita o payload a 16 KiB.
- A resposta não ecoa o evento bruto; logs não devem conter payloads.
- Relatórios são lidos de caminhos fixos dentro de `reports/` e apenas campos permitidos são retornados.
- Scores não são probabilidades calibradas. Data drift não prova, por si só, perda de acurácia.
- Use somente dados sintéticos ou dados para os quais você tenha autorização.

O servidor é local e não fornece autenticação de rede porque usa `stdio`. Não o exponha por um wrapper de rede sem uma revisão de segurança separada.
