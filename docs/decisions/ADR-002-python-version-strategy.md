# ADR-002 — Estratégia de Compatibilidade com Python 3.14

**Status:** Aceito  
**Data:** 2025-01  
**Autores:** Sergio Santos  
**Relacionado:** ADR-001 (arquitetura), `.python-version`, `pyproject.toml`, `ci.yml`

---

## Contexto

O objetivo declarado do projeto é Python 3.15.0 (previsto para outubro de 2026).  
Durante a implementação das Fases 0–2, **Python 3.14 foi confirmado como instalado localmente** — evidência: `tests/__pycache__/conftest.cpython-314-pytest-9.1.1.pyc`.

No entanto, o CI no GitHub Actions não tem imagem estável para Python 3.14 ainda, e algumas dependências (`pandas`, `scikit-learn`, `numpy`) podem não ter wheels para 3.14 no PyPI em todas as plataformas de CI.

---

## Decisão

Adotar uma **estratégia em três camadas**:

| Camada                    | Versão                                                 | Onde                     | Propósito                                        |
| ------------------------- | ------------------------------------------------------ | ------------------------ | ------------------------------------------------ |
| **Desenvolvimento local** | Python 3.15 (`.python-version`)                        | Máquina do desenvolvedor | Alvo declarado — detecta incompatibilidades cedo |
| **CI principal**          | Python 3.15 (pinado no `ci.yml`)                       | GitHub Actions           | Estabilidade e reprodutibilidade de CI           |
| **Smoke test**            | Python 3.15 (`py313-smoke`, `continue-on-error: true`) | GitHub Actions           | Monitor de compatibilidade intermediária         |

### Critério de migração do CI para 3.15

O CI principal será migrado para Python 3.15 quando **todas** as condições forem atendidas:

1. `setup-python@v5` publicar imagem oficial para 3.14 no GitHub Actions
2. `pandas >= 2.x` publicar wheel para Python 3.15 no PyPI
3. `scikit-learn >= 1.5.x` publicar wheel para Python 3.14
4. `numpy >= 2.x` publicar wheel para Python 3.15
5. O job `py313-smoke` passar sem erros por pelo menos 2 semanas

---

## Consequências

**Positivas:**

- Desenvolvimento local já usa 3.15 — incompatibilidades de API são detectadas cedo
- CI estável em 3.12 não bloqueia PRs por problemas de imagem
- Smoke test em 3.13 detecta problemas antes de migrar

**Negativas / trade-offs:**

- Divergência entre versão local (3.15) e CI (3.12) pode mascarar incompatibilidades sutis
- `.python-version` fixado em 3.15 pode causar problemas em ambientes sem 3.14 instalado

## Configuração atual

```
.python-version    → 3.15  (local e ferramentas que leem este arquivo)
pyproject.toml     → requires-python = ">=3.15"  (permite 3.12, 3.13, 3.14, 3.15)
ci.yml lint/test   → python-version: "3.15"  (pinado para estabilidade)
ci.yml smoke       → python-version: "3.15"  (continue-on-error: true)
```

---

## Referências

- [Python 3.14 Release Schedule — PEP 745](https://peps.python.org/pep-0745/)
- [GitHub Actions — setup-python available versions](https://github.com/actions/setup-python/blob/main/docs/advanced-usage.md)
- [ADR-001 — Arquitetura Python Modular](ADR-001-architecture.md)
