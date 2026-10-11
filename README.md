# Intelligent DevSecOps Sentinel

[![CI](https://github.com/Santosdevbjj/geo-explorer-com-ibm-bob/actions/workflows/ci.yml/badge.svg)](https://github.com/Santosdevbjj/geo-explorer-com-ibm-bob/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.14%20%7C%203.12-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

> **Como transformar um volume alto de eventos de segurança em alertas priorizados, explicáveis e mensuráveis, sem tratar toda anomalia como ataque confirmado?**

---

## Visão geral

O **Sentinel** é um pipeline analítico de segurança defensiva. Ele recebe eventos de autenticação, HTTP e rede, valida a qualidade dos dados, aplica **regras transparentes** de detecção e entrega alertas com **score, prioridade e os sinais exatos que os geraram**. Um modelo de ML (IsolationForest) roda ao lado como baseline experimental.

Quem se beneficia: o analista que precisa decidir o que investigar primeiro, o engenheiro de dados que precisa confiar na entrada, e o revisor técnico que precisa rastrear *por que* um alerta existe.

**Importante:** o projeto roda sobre **dados sintéticos**. Ele demonstra engenharia, método e governança. Ele **não** é um SIEM de produção e **não** comprova detecção de ataques reais.

Desenvolvido a partir do desafio **Geo-Explorer com IBM Bob**, usando o IBM Bob como assistente de desenvolvimento (comandos em [`.bob/commands/`](.bob/commands/)).

## Objetivo do projeto

Eu criei este projeto para praticar, ponta a ponta, o trabalho de **Security Data Science**: sair do dado bruto, passar por validação, regras, modelo, avaliação e monitoramento, e chegar a uma API e um dashboard que outra pessoa consegue usar e auditar.

Três decisões guiaram tudo:

1. **Explicar antes de impressionar.** Todo alerta carrega seus sinais, limiares e limitações.
2. **Não afirmar o que não foi medido.** Cada resultado é separado em *fato medido*, *hipótese* e *limitação*.
3. **Resolver o problema do analista, não exibir uma ferramenta.** O foco é reduzir ruído na triagem; o scikit-learn é um meio.

---

## 1. Problema de negócio

Equipes de segurança recebem eventos de autenticação, HTTP e rede em volume elevado. Alertas sem contexto geram ruído, aumentam o tempo de triagem e dificultam explicar por que uma atividade foi priorizada. O risco é duplo: **perder um ataque real** no meio do ruído, ou **tratar comportamento legítimo como ataque**.

A pergunta de negócio deste projeto:

> Como priorizar eventos suspeitos de forma que o analista saiba **o que investigar primeiro e por quê**?

## 2. Contexto

| Item | Descrição |
|---|---|
| **Quem decide** | Analista de segurança (o que investigar), engenheiro de dados/ML (qualidade da entrada), revisor técnico (rastreabilidade) |
| **Dados de entrada** | Eventos `auth_attempt`, `http_request`, `dns_query` e `network_flow` (schema em [`docs/data-dictionary.md`](docs/data-dictionary.md)) |
| **Ameaças cobertas** | Força bruta, pico de tráfego e padrões de injeção (SQL, XSS, path traversal) |
| **Fora do escopo** | Bloqueio automático de IPs, resposta a incidentes, atribuição de intenção a pessoas, garantia de precisão ou de economia financeira |

Detalhes em [`docs/business-context.md`](docs/business-context.md).

## 3. Premissas

- Os eventos são **sintéticos**, gerados com seed fixo por `scripts/generate_synthetic_data.py`. Nenhum dado real, pessoal ou segredo é usado.
- O campo `metadata.label` existe só para avaliação e **nunca** entra como feature (sem vazamento de alvo).
- O score de alerta **não é probabilidade calibrada**.
- As análises identificam **padrões**, não causalidade.
- **Data drift não prova perda de acurácia.** Medir degradação exige rótulos posteriores.
- Um alerta é um **sinal para investigação**, não confirmação de ataque. Ações que afetam sistemas ou usuários exigem revisão humana.

## 4. Baseline

Um projeto de dados só prova valor quando supera uma referência. Aqui há duas camadas:

| Camada | O que é | Papel |
|---|---|---|
| **Status quo (referência de negócio)** | Triagem sem priorização: todo evento anômalo recebe o mesmo peso | O que o Sentinel precisa superar em organização e explicabilidade |
| **Baseline técnica** | Regras explícitas (`BruteForceRule`, `TrafficSpikeRule`, `InjectionRule`) | Referência determinística contra a qual o IsolationForest é comparado |

O módulo [`evaluation/metrics.py`](src/sentinel/evaluation/metrics.py) calcula a comparação com a baseline e **registra o resultado mesmo quando o modelo não a supera**. Os números não são publicados neste README porque dependem do dataset, do hash e do split de cada execução (veja [Performance](#9-performance-do-modelo)).

## 5. Planejamento da solução

```
logs / eventos
      │
      ▼
┌──────────────────────────────────────────────────────────┐
│  src/sentinel/                                           │
│  ├── data/validation.py      ← schema, ausentes, duplicatas
│  ├── features/engineering.py ← features por IP e janela  │
│  ├── detection/                                          │
│  │   ├── rules.py            ← regras explícitas         │
│  │   ├── model.py            ← IsolationForest (baseline)│
│  │   └── scoring.py          ← score, prioridade, sinais │
│  ├── evaluation/metrics.py   ← precision/recall/F1/PR-AUC│
│  └── monitoring/drift.py     ← data drift (PSI)          │
└────────────────┬─────────────────────────────────────────┘
                 ▼
         api/index.py (FastAPI)
                 │
          ┌──────┴──────┐
          ▼             ▼
      Dashboard      Servidor MCP
      (Next.js)   (somente leitura)
```

| Etapa | Ferramenta |
|---|---|
| Contratos de dados e configuração | Pydantic v2, pydantic-settings |
| Processamento e features | Pandas, NumPy |
| Modelo | Scikit-learn (IsolationForest + StandardScaler), Joblib |
| API | FastAPI, Uvicorn |
| Dashboard | Next.js 14, TypeScript, Tailwind CSS |
| Integração com IA | Servidor MCP (SDK oficial, transporte `stdio`) |
| Qualidade e segurança | Pytest, Ruff, mypy, Bandit, pip-audit, Gitleaks |
| Deploy | GitHub Actions (CI), Vercel |

## 6. Limpeza e validação dos dados

A entrada passa por [`data/validation.py`](src/sentinel/data/validation.py) antes de qualquer análise:

- validação de schema com Pydantic (tipos, enums, faixas, ex.: porta 1–65535);
- detecção de campos ausentes e de `event_id` duplicado;
- **registros inválidos são injetados de propósito** no gerador (`--include-invalid`) para provar que a validação funciona;
- limites de segurança: tamanho máximo de lote (`MAX_BATCH_SIZE`) e de evento (64 KiB).

Resultado observado no notebook de exploração (2.008 registros no arquivo): 8 inválidos intencionais foram separados, restando 2.000 para análise, e 1.993 passaram na validação Pydantic. Os 7 que falharam têm campos opcionais ausentes ou tipos errados, comportamento esperado nos casos "benignos parecidos" do gerador.

## 7. Análise exploratória (EDA)

O notebook [`01_exploratory_analysis.ipynb`](notebooks/01_exploratory_analysis.ipynb) trata cada observação como **hipótese a validar**, nunca como causa.

| Observação (fato medido no dataset sintético) | Interpretação cuidadosa |
|---|---|
| 2.000 eventos em ~1 hora, 1.916 IPs únicos | O gerador cria IPs aleatórios para tráfego normal. Em dados reais haveria IPs recorrentes; features baseadas em histórico de IP perdem poder aqui. |
| `request_path` e `user_agent` ausentes em 52,4% | Estrutural: só eventos HTTP têm esses campos. Não é dado corrompido. |
| Mix de eventos: 47,6% HTTP, 28,9% auth, 13,7% DNS, 9,8% fluxo de rede | Reflete os pesos configurados no gerador. |
| Status: 78,1% sucesso, 13,4% falha, 5,6% bloqueado, 3,0% timeout | Idem. Não assumimos que representa tráfego real. |
| Taxa de erro parecida entre tipos de evento (16% a 20%) | Tráfego normal usa os mesmos pesos de status; o sinal de ataque não aparece na média, aparece **por IP e janela**. |
| Janelas de 5 min suavizam picos que ocorrem em sub-segundos | Limitação identificada. Motivou a feature `inter_event_min_ms`. |

## 8. Preparação de dados e features

[`features/engineering.py`](src/sentinel/features/engineering.py) calcula, por `source_ip` e janela deslizante (padrão 300 s), **16 colunas**: duas de identificação (`source_ip`, `window_start`) e 14 features.

| Grupo | Features |
|---|---|
| Autenticação | `auth_failure_rate`, `auth_failure_count` |
| HTTP | `request_count`, `unique_paths`, `req_per_second`, `scan_path_hits` |
| Falhas | `failure_ratio`, `error_count`, `timeout_ratio` |
| Payload | `payload_size_mean`, `payload_size_std` |
| Temporal | `inter_event_mean_ms`, `inter_event_min_ms` |
| User-agent | `scanner_agent_ratio` |

Princípios aplicados: nenhuma feature usa `metadata.label`; todas são computáveis em inferência; a saída é determinística. O `StandardScaler` é ajustado **somente no treino** e reutilizado na inferência.

## 9. Treinamento e justificativa do algoritmo

| Escolha | Justificativa | Alternativa considerada |
|---|---|---|
| **IsolationForest** | Não supervisionado: não existe conjunto rotulado e autorizado. Rápido, sem exigir distribuição específica. | Modelo supervisionado, que exigiria rótulos reais |
| **Divisão temporal** (`test_split=0.20`) | Evita olhar o futuro durante o treino, ao contrário de um split aleatório | Split aleatório |
| `contamination=0.05`, `n_estimators=100`, `random_state=42` | Parâmetros documentados e reproduzíveis | Ajuste por busca, sem dados reais que o justifiquem |

[`scripts/train_model.py`](scripts/train_model.py) registra seed, hash SHA-256 do dataset, features, configuração e metadados em `models/metadata_<versão>.json`. Binários de modelo **não são versionados**.

## 10. Performance do modelo

Métricas calculadas em `numpy` puro por [`evaluation/metrics.py`](src/sentinel/evaluation/metrics.py): precision, recall, F1, macro-F1, PR-AUC, matriz de confusão e taxa de falsos positivos. A *accuracy* não é usada isoladamente, e métricas com denominador zero retornam `None` em vez de um número inventado.

```bash
python scripts/train_model.py
python scripts/evaluate_model.py   # gera o relatório; a API o expõe em GET /metrics
```

**Fato medido sobre a qualidade do código** (execução de validação registrada em [`CHANGELOG.md`](CHANGELOG.md) e [`MIGRATION_NOTES.md`](MIGRATION_NOTES.md)): `357 passed`, cobertura de `97%` em `src/sentinel/`.

**O que ainda não foi medido:** Ruff, mypy, Bandit, pip-audit e o build do frontend não foram executados nesse ambiente de validação. Rode-os antes de qualquer release.

**Por que não há números de precision/recall aqui:** métricas em dados sintéticos só descrevem o comportamento *desse experimento*. Publicá-las sem dataset, hash, split e baseline seria uma alegação sem evidência.

## 11. Business performance

O passo que converte o erro do modelo em impacto para o negócio. Sem dados reais, **não existe valor honesto em R$**, mas o modelo de custo já está definido:

```
custo_mensal_residual = (FN × custo_de_um_incidente_não_detectado)
                      + (FP × custo_de_triagem_de_um_falso_alerta)
```

| Parâmetro | Quem fornece | Status |
|---|---|---|
| `FN` e `FP` por período | Avaliação em dataset autorizado e rotulado | Pendente |
| Custo de um incidente não detectado | Gestão de risco / segurança | Pendente |
| Custo de triagem de um falso alerta | Tempo médio do analista × custo-hora | Pendente |

Critérios para afirmar valor no futuro (de [`docs/business-context.md`](docs/business-context.md)): dataset autorizado, baseline comparável, custo de FP e FN, latência p95, throughput, estabilidade por segmento e protocolo de revisão humana.

## 12. Modelo e API em produção

A API é um adaptador HTTP fino: a lógica analítica vive em `src/sentinel/` e nunca importa de `api/`.

| Método | Rota | Auth | Finalidade |
|---|---|---|---|
| GET | `/health` | Pública | Saúde do serviço (não garante modelo carregado) |
| GET | `/model-info` | Pública | Versão, disponibilidade do modelo, modo de inferência |
| POST | `/ingest` | `X-Api-Key` | Validação de lote |
| POST | `/detect` | `X-Api-Key` | Regras e geração de alertas |
| POST | `/analyze` | `X-Api-Key` | Análise de um evento tipado |
| POST | `/analyze/batch` | `X-Api-Key` | Análise de lote com limite configurável |
| GET | `/alerts`, `/alerts/{id}` | Pública | Alertas da memória do processo |
| GET | `/metrics` | Pública | Relatório de avaliação previamente gerado |

**Estados que não se confundem:** API saudável não implica modelo carregado, e modelo carregado não implica modelo útil. Se o artefato estiver ausente, a API continua em modo `rules-only`.

**Segurança embutida:** o segredo padrão da API é **rejeitado** em `SENTINEL_ENV=production`; schemas Pydantic validam a entrada; lotes e eventos têm limites; Gitleaks, Bandit e pip-audit rodam no CI. Veja [`docs/threat-model.md`](docs/threat-model.md) e [`docs/security-review.md`](docs/security-review.md).

**Servidor MCP (IBM Bob):** quatro ferramentas somente leitura (`get_model_info`, `analyze_event`, `get_metrics_summary`, `get_drift_summary`). Sem shell, sem escrita, sem deploy, sem caminhos escolhidos pelo cliente. Decisão em [`ADR-007`](docs/decisions/ADR-007-mcp-readonly.md).

**Monitoramento:** o PSI compara a distribuição atual das features com a referência (`DRIFT_ALERT_THRESHOLD=0.1`). Drift é gatilho de **investigação**, não de retreino automático ([`docs/model-monitoring.md`](docs/model-monitoring.md)).

## 13. Storytelling: do evento ao alerta

Exemplo ilustrativo, derivado das regras do código: um IP gera 18 falhas de autenticação em menos de 5 minutos.

```json
{
  "category": "brute_force",
  "priority": "critical",
  "score": 1.0,
  "signals": [
    {
      "name": "repeated_auth_failures",
      "source": "rule",
      "value": 18.0,
      "threshold": 5.0,
      "contribution": 1.0
    }
  ],
  "limitations": "Score calculado a partir de regras heurísticas com limiares fixos. Sem calibração estatística: o valor numérico não representa uma probabilidade. Falsos positivos são esperados. Revise os sinais antes de tomar ação.",
  "model_version": "rules-only"
}
```

O analista lê: **o que** aconteceu (força bruta), **quanto** (18 falhas contra limiar 5), **quão grave** (crítico) e **o que não pode concluir** (o score não é probabilidade).

Sinais fracos não viram alerta por padrão: com `ALERT_SCORE_THRESHOLD=0.6`, uma rajada precisa de pelo menos 9 falhas para passar o corte. O dashboard Next.js (`/`, `/alerts/[id]`, `/metrics`) apresenta esses alertas, seus sinais e as limitações.

---

## Decisões técnicas

Cada decisão está registrada como ADR em [`docs/decisions/`](docs/decisions/), com alternativas e trade-offs.

| ADR | Decisão | Alternativa rejeitada e por quê |
|---|---|---|
| [001](docs/decisions/ADR-001-architecture.md) | Python modular (`src/sentinel/`) + FastAPI | Monolito Flask e notebook como produto: dificultam teste e CI. Microserviços: prematuros para a v0.1. |
| [002](docs/decisions/ADR-002-python-version-strategy.md) | Python 3.14 local, 3.12 no CI, 3.13 como smoke test | Fixar só 3.14: wheels e imagens de CI ainda podem faltar. Trade-off aceito: divergência entre local e CI. |
| [003](docs/decisions/ADR-003-persistence.md) | Alertas em memória | SQLite em plataforma de disco efêmero seria falsa persistência. Revisar quando houver réplicas, auditoria ou SLA. |
| [004](docs/decisions/ADR-004-model-baseline.md) | IsolationForest como baseline opcional | Só regras (sem ML), supervisionado (sem rótulos) ou ensemble (sem calibração). |
| [005](docs/decisions/ADR-005-api-auth.md) | API Key via `X-Api-Key` nos endpoints de escrita | OAuth2/JWT e mTLS: custo alto para um portfólio sem múltiplos usuários. |
| [006](docs/decisions/ADR-006-deploy-vercel.md) | Vercel (API serverless + Next.js) | Render, Fly.io e AWS Lambda: mais infraestrutura para um portfólio. |
| [007](docs/decisions/ADR-007-mcp-readonly.md) | MCP local, `stdio`, somente leitura | Ferramentas genéricas de shell/arquivos: superfície de risco inaceitável. |

## Tecnologias utilizadas

- **Python 3.12+ (alvo 3.14)**, FastAPI, Pydantic v2
- **Pandas, NumPy, Scikit-learn** (IsolationForest)
- **Next.js 14, TypeScript, Tailwind CSS** (dashboard)
- **MCP** (SDK oficial) para integração com o IBM Bob
- **Pytest, Ruff, mypy, Bandit, pip-audit, Gitleaks** e **GitHub Actions**
- **Vercel** para deploy

## Como executar o projeto

**Pré-requisitos:** Python 3.12 ou superior (3.14 recomendado, veja [`.python-version`](.python-version)), `pip` ou `uv`. Para o dashboard, Node.js 20.

```bash
# 1. Clonar
git clone https://github.com/Santosdevbjj/geo-explorer-com-ibm-bob.git
cd geo-explorer-com-ibm-bob

# 2. Ambiente virtual
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
.venv\Scripts\activate           # Windows

# 3. Dependências
pip install -e ".[dev]"
# Opcional, para o servidor MCP: pip install -e ".[dev,mcp]"

# 4. Variáveis de ambiente
cp .env.example .env

# 5. Gerar dados sintéticos, validar e treinar
python scripts/generate_synthetic_data.py
python scripts/validate_data.py --input data/synthetic/events.jsonl
python scripts/train_model.py

# 6. Subir a API
uvicorn api.index:app --reload
# → http://localhost:8000/docs
```

**Dashboard (opcional):**

```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

**Testes e qualidade:**

```bash
pytest                      # todos os testes com cobertura
pytest tests/unit/          # unitários
pytest tests/integration/   # integração (API e MCP)
ruff check .                # lint
mypy src/sentinel/ api/     # tipagem
bandit -r src/ api/ scripts/ -c pyproject.toml
pip-audit                   # vulnerabilidades em dependências
```

**Estrutura:**

```
geo-explorer-com-ibm-bob/
├── .bob/           ← comandos e configuração do IBM Bob
├── .github/        ← CI (GitHub Actions)
├── api/            ← FastAPI
├── data/           ← raw, processed e synthetic
├── docs/           ← arquitetura, ADRs, model card, threat model
├── frontend/       ← dashboard Next.js
├── mcp/            ← servidor MCP
├── models/         ← artefatos treinados (não versionados)
├── notebooks/      ← análise exploratória
├── scripts/        ← geração de dados, validação, treino, avaliação
├── src/sentinel/   ← biblioteca principal
└── tests/          ← unit, integration, security
```

## Aprendizados

- **Honestidade técnica é um recurso de design.** Escrever `limitations` dentro de cada alerta e um model card que proíbe "ensemble híbrido" enquanto o ML não compõe o score me forçou a separar o que o código faz do que eu gostaria que ele fizesse.
- **Dado sintético ensina engenharia, não eficácia.** O notebook mostrou onde o gerador distorce a realidade (IPs quase todos únicos, janelas largas demais para picos de milissegundos). Esse tipo de achado só aparece quando se desconfia do próprio dado.
- **Estado de saúde tem camadas.** Separar `/health`, `/model-info` e a utilidade do modelo evitou o erro de tratar "API no ar" como "modelo funcionando".
- **Segurança desde o primeiro commit** (Gitleaks, Bandit, pip-audit, segredo padrão rejeitado em produção) custa pouco no início e muito depois.
- **O que faria diferente:** definir o contrato de score por evento antes de escrever o modelo, e gerar o `package-lock.json` do frontend desde o começo.
- **Ferramenta de IA como parceira, não como autora.** O IBM Bob acelerou a revisão e a documentação; as decisões e a validação continuam sendo minhas.

## Limitações assumidas

1. Dados sintéticos não reproduzem a variedade de tráfego e ataques reais.
2. O IsolationForest **ainda não compõe o score final dos alertas**: o score vem das regras explícitas.
3. Alertas ficam em memória; reiniciar o processo os apaga.
4. No deploy serverless, o modelo não é persistido e a API opera em modo `rules-only`.
5. `docs/security-review.md` e `docs/release-readiness.md` são **checklists a preencher com evidências**, não certificações.


## Próximos passos

- [ ] Obter um dataset **autorizado e rotulado** e repetir a avaliação com baseline comparável
- [ ] Definir o contrato de score por evento e **integrar o IsolationForest ao scoring** com calibração e limiares
- [ ] Preencher o modelo de custo FP/FN (seção *Business performance*) com dados reais
- [ ] Persistência durável de alertas e trilha de auditoria (gatilho do ADR-003)
- [ ] Rate limiting por IP e autenticação por usuário
- [ ] Gerar `package-lock.json` e executar `npm audit`
- [ ] Migrar o CI para Python 3.14 quando os critérios do ADR-002 forem atendidos
- [ ] Executar e registrar Ruff, mypy, Bandit, pip-audit e Gitleaks no commit candidato a release

## Contribuição e segurança

Veja [`CONTRIBUTING.md`](CONTRIBUTING.md) e [`SECURITY.md`](SECURITY.md) (política de divulgação responsável).

## Licença

MIT. Veja [`LICENSE`](LICENSE).

---

**Autor:** Sérgio Santos, Cientista de Dados | Ambientes Críticos e Governança de Dados

[![Portfólio Sérgio Santos](https://img.shields.io/badge/Portfólio-Sérgio_Santos-111827?style=for-the-badge&logo=githubpages&logoColor=00eaff)](https://portfoliosantossergio.vercel.app)
[![LinkedIn Sérgio Santos](https://img.shields.io/badge/LinkedIn-Sérgio_Santos-0A66C2?style=for-the-badge&logo=linkedin&logoColor=white)](https://linkedin.com/in/santossergioluiz)
