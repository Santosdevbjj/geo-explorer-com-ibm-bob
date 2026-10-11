# Intelligent DevSecOps Sentinel

[![CI](https://github.com/Santosdevbjj/geo-explorer-com-ibm-bob/actions/workflows/ci.yml/badge.svg)](https://github.com/Santosdevbjj/geo-explorer-com-ibm-bob/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.14%20%7C%203.12-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

> Como transformar grandes volumes de eventos de segurança em alertas priorizados, explicáveis e mensuráveis — sem tratar toda anomalia como um ataque confirmado?

O **Sentinel** é um projeto de portfólio de análise defensiva construído com Python, FastAPI e Scikit-learn. Ele combina **regras transparentes** com um modelo de baseline opcional para explorar validação de eventos, geração de alertas explicáveis e monitoramento. O comportamento é demonstrado com dados sintéticos; não representa um SIEM de produção nem comprova desempenho em ataques reais.

Desenvolvido a partir do desafio **Geo-Explorer com IBM Bob** como projeto de portfólio em DevSecOps e Security Data Science.

---

## Capacidades

| #   | Capacidade                                         | Status                                                                 |
| --- | -------------------------------------------------- | ---------------------------------------------------------------------- |
| 1   | Ingestão e qualidade dos dados                     | ✅ Implementado                                                        |
| 2   | Detecção de comportamentos suspeitos (regras + ML) | ✅ Implementado                                                        |
| 3   | Priorização e explicabilidade de alertas           | ✅ Implementado                                                        |
| 4   | Avaliação e monitoramento experimental de modelos  | Implementação de baseline; validar resultados no ambiente local        |
| 5   | API, CI e integração MCP somente leitura           | Implementação em revisão; executar os checks antes de qualquer release |

---

## Arquitetura

```
logs / eventos
      │
      ▼
┌─────────────────────────────────────────────────────────┐
│  src/sentinel/                                          │
│  ├── data/validation.py    ← schema, missing, dupes     │
│  ├── features/engineering.py ← atributos temporais      │
│  ├── detection/                                         │
│  │   ├── rules.py          ← regras explícitas          │
│  │   ├── model.py          ← modelo ML (baseline)       │
│  │   └── scoring.py        ← score + explicabilidade    │
│  ├── evaluation/metrics.py ← precision/recall/F1/drift  │
│  └── monitoring/drift.py   ← detecção de data drift     │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
         api/index.py (FastAPI)
         GET /health · GET /model-info
         POST /ingest · POST /detect · POST /analyze[/batch]
         GET /alerts · GET /metrics
                 │
          ┌──────┴──────┐
          ▼             ▼
      Dashboard      MCP Server
      (Next.js)    (IBM Bob tools)
```

---

## Início Rápido

### Pré-requisitos

- **Python 3.14** recomendado (alvo do projeto — confirmado localmente)
  Python 3.12+ aceito para CI e ambientes sem 3.14 disponível
  Ver [`.python-version`](.python-version) e [`ADR-002`](docs/decisions/ADR-002-python-version-strategy.md)
- `pip` ou `uv`

### Instalação

```bash
# Clone
git clone https://github.com/Santosdevbjj/geo-explorer-com-ibm-bob.git
cd geo-explorer-com-ibm-bob

# Ambiente virtual
python -m venv .venv
source .venv/bin/activate      # Linux/macOS
.venv\Scripts\activate         # Windows

# Dependências
pip install -e ".[dev]"
# Opcional: servidor MCP oficial
# pip install -e ".[dev,mcp]"

# Variáveis de ambiente
cp .env.example .env
```

### Rodar a API

```bash
uvicorn api.index:app --reload
# → http://localhost:8000/docs
```

### Gerar dados sintéticos

```bash
python scripts/generate_synthetic_data.py
```

### Testes

```bash
pytest                  # todos os testes + cobertura
pytest tests/unit/      # apenas unitários
pytest tests/integration/  # apenas integração
```

### Qualidade estática

```bash
ruff check .            # lint
mypy src/sentinel/ api/ # tipagem
bandit -r src/ api/ scripts/ -c pyproject.toml
pip-audit               # auditoria de dependências
```

---

## Endpoints principais

| Método | Rota                             | Finalidade                                              |
| ------ | -------------------------------- | ------------------------------------------------------- |
| GET    | `/health`                        | Saúde da API; não garante que o modelo esteja carregado |
| GET    | `/model-info`                    | Versão, disponibilidade do modelo e modo de inferência  |
| POST   | `/ingest`                        | Validação de lote                                       |
| POST   | `/detect`                        | Pipeline existente de detecção                          |
| POST   | `/analyze`                       | Análise de um evento tipado                             |
| POST   | `/analyze/batch`                 | Análise de lote com limite configurável                 |
| GET    | `/alerts` e `/alerts/{alert_id}` | Consulta de alertas em memória                          |
| GET    | `/metrics`                       | Relatório de avaliação previamente gerado               |

Configure `API_SECRET_KEY` fora do código em ambientes compartilhados. O valor placeholder é permitido apenas fora de produção; em `SENTINEL_ENV=production`, ele deve causar falha fechada. Alertas ainda são armazenados em memória e não têm garantia de persistência.

Consulte [`docs/model-monitoring.md`](docs/model-monitoring.md), [`docs/threat-model.md`](docs/threat-model.md), [`docs/security-review.md`](docs/security-review.md) e [`docs/release-readiness.md`](docs/release-readiness.md) para limites e critérios de validação.

---

## Estrutura do Projeto

```
geo-explorer-com-ibm-bob/
├── .bob/           ← comandos e configuração do IBM Bob
├── .github/        ← GitHub Actions CI
├── api/            ← FastAPI (entry point para deploy)
├── data/           ← dados raw, processed e synthetic
├── docs/           ← arquitetura, ADRs, model-card
├── mcp/            ← servidor MCP (integração IBM Bob)
├── models/         ← modelos treinados (gitignored)
├── notebooks/      ← análise exploratória
├── reports/        ← relatórios de avaliação
├── scripts/        ← pipeline de dados e treinamento
├── src/sentinel/   ← código-fonte principal
└── tests/          ← unit, integration, security
```

---

## Decisões de Design

As decisões arquiteturais estão documentadas em [`docs/decisions/`](docs/decisions/):

| ADR                                                          | Decisão                                    |
| ------------------------------------------------------------ | ------------------------------------------ |
| [ADR-001](docs/decisions/ADR-001-architecture.md)            | Arquitetura Python modular com FastAPI     |
| [ADR-002](docs/decisions/ADR-002-python-version-strategy.md) | Estratégia Python 3.14 (local) / 3.12 (CI) |
| [ADR-003](docs/decisions/ADR-003-persistence.md)             | Limites do armazenamento em memória        |
| [ADR-004](docs/decisions/ADR-004-model-baseline.md)          | Modelo de baseline e limitações            |
| [ADR-005](docs/decisions/ADR-005-api-auth.md)                | Autenticação API Key                       |
| [ADR-006](docs/decisions/ADR-006-deploy-vercel.md)           | Deploy na Vercel                           |
| [ADR-007](docs/decisions/ADR-007-mcp-readonly.md)            | MCP somente leitura                        |

**Python 3.14:** confirmado como instalado localmente (`__pycache__/cpython-314`).
CI usa 3.12 (imagem Actions estável). Detalhes em [`ADR-002`](docs/decisions/ADR-002-python-version-strategy.md).

---

## Segurança

Veja [`SECURITY.md`](SECURITY.md) para a política de divulgação responsável.  
Este projeto executa análise estática com Bandit, auditoria de dependências com pip-audit e varredura de segredos com Gitleaks no CI.

---

## Licença

MIT — veja [`LICENSE`](LICENSE).

---

**Autor:** Sérgio Santos — Cientista de Dados | Ambientes Críticos e Governança de Dados

[![Portfólio Sérgio Santos](https://img.shields.io/badge/Portfólio-Sérgio_Santos-111827?style=for-the-badge&logo=githubpages&logoColor=00eaff)](https://portfoliosantossergio.vercel.app)
[![LinkedIn Sérgio Santos](https://img.shields.io/badge/LinkedIn-Sérgio_Santos-0A66C2?style=for-the-badge&logo=linkedin&logoColor=white)](https://linkedin.com/in/santossergioluiz)
