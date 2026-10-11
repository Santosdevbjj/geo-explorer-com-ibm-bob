# ADR-001 — Arquitetura Python Modular com FastAPI

**Status:** Aceito  
**Data:** 2025-01  
**Autores:** Sergio Santos  
**Contexto:** Intelligent DevSecOps Sentinel v0.1

---

## Contexto

O projeto parte do desafio Geo-Explorer com IBM Bob e precisa evoluir para um produto analítico de segurança com cinco capacidades: ingestão de dados, detecção, priorização, avaliação de modelos e engenharia de software.

A decisão de arquitetura deve equilibrar:
- **Clareza educacional** — o código deve ser legível e auditável por recrutadores e pares
- **Separação de responsabilidades** — pipeline de dados independente da API e da interface
- **Testabilidade** — cada módulo isolável para testes unitários sem dependências externas
- **Extensibilidade** — adição de novos detectores e modelos sem reescrita
- **Segurança por padrão** — análise estática, auditoria de dependências e CI desde o início

---

## Decisão

Adotar **arquitetura Python modular** com os seguintes componentes:

```
src/sentinel/          ← biblioteca principal (importável, testável)
├── config.py          ← configuração centralizada via pydantic-settings
├── schemas.py         ← contratos de dados (Pydantic v2)
├── data/              ← ingestão e validação
├── features/          ← engenharia de atributos
├── detection/         ← regras + modelo + scoring
├── evaluation/        ← métricas e comparação de baseline
└── monitoring/        ← drift e degradação de modelo

api/index.py           ← FastAPI (camada de transporte — não contém lógica analítica)
scripts/               ← pipeline offline (treino, avaliação, geração de dados)
mcp/                   ← servidor MCP (exposição opcional para IBM Bob)
frontend/              ← Next.js (interface desacoplada — consome a API)
```

**Separação explícita:** a lógica analítica (`src/sentinel/`) nunca importa de `api/` ou `frontend/`. A API é apenas um adaptador HTTP sobre a biblioteca.

---

## Alternativas Consideradas

| Alternativa | Por que foi rejeitada |
|---|---|
| Monolito Flask com tudo em um arquivo | Dificulta testes unitários e leitura do pipeline |
| Jupyter Notebook como produto principal | Não é deployável; dificulta CI e revisão de código |
| Microserviços desde o início | Prematura para v0.1; overhead de infra desnecessário |
| Django | Overhead de ORM e admin; inadequado para API analítica pura |

---

## Consequências

**Positivas:**
- `src/sentinel/` pode ser instalado como pacote (`pip install -e .`) e importado em notebooks e scripts
- A API pode ser trocada por outro framework sem alterar a lógica de detecção
- Testes unitários rodam sem levantar servidor HTTP
- Facilita separação de responsabilidades no CI (lint por módulo, cobertura por pacote)

**Negativas / trade-offs:**
- Mais boilerplate inicial comparado a um único arquivo
- Desenvolvedor precisa entender a separação `src/sentinel/` vs `api/` vs `scripts/`

---

## Decisão sobre Python 3.14

O alvo de longo prazo é **Python 3.14.8** (estável previsto para outubro de 2026). A versão fixada em `.python-version` é **3.12** porque as dependências críticas (`pandas`, `scikit-learn`, `numpy`) ainda não publicaram wheels estáveis para 3.14.x.

**Critério de migração:** quando `pandas >= 2.x`, `scikit-learn >= 1.5.x` e `numpy >= 2.x` publicarem wheels para Python 3.14 no PyPI sem sinalizadores `pre-release`, abriremos um PR de atualização com ADR de migração separado.

---

## Referências

- [FastAPI — Design Principles](https://fastapi.tiangolo.com/features/)
- [Pydantic v2 — Performance and Strict Mode](https://docs.pydantic.dev/latest/)
- [Python Packaging — src layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/)
- [Python 3.14 Release Schedule — PEP 745](https://peps.python.org/pep-0745/)
