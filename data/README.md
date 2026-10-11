# Dados do Sentinel

Este diretório contém os dados utilizados pelo pipeline analítico.

## Estrutura

```
data/
├── raw/          ← dados brutos ingeridos (gitignored, exceto .gitkeep)
├── processed/    ← dados validados e transformados (gitignored)
└── synthetic/    ← logs sintéticos gerados por scripts/generate_synthetic_data.py
```

## Geração de dados sintéticos

```bash
python scripts/generate_synthetic_data.py
# Saída: data/synthetic/events_<timestamp>.jsonl
```

## Política de dados

- **Dados brutos (`raw/`):** nunca commitados. Devem ser obtidos localmente conforme `docs/data-governance.md`.
- **Dados processados (`processed/`):** nunca commitados. Gerados via `scripts/validate_data.py`.
- **Dados sintéticos (`synthetic/`):** gerados por script com seed fixo — reproduzíveis, sem dados reais.
- Nenhum arquivo desta pasta deve conter PII ou dados sensíveis reais.

## Dicionário de dados

Ver [`docs/data-dictionary.md`](../docs/data-dictionary.md).
