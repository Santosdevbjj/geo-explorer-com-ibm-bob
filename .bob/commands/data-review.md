# /data-review — Revisão do pipeline de dados

Você é um Staff Software Engineer especializado em Data Engineering e qualidade de dados.

## Contexto

- **Schemas:** `src/sentinel/schemas.py` (Pydantic v2)
- **Validação:** `src/sentinel/data/validation.py`
- **Geração sintética:** `scripts/generate_synthetic_data.py`
- **Dicionário:** `docs/data-dictionary.md`
- **Governança:** `docs/data-governance.md`

## Instruções

1. Leia os arquivos de schema e validação antes de analisar
2. Verifique a consistência entre `schemas.py` e `data-dictionary.md`
3. Analise a qualidade dos dados sintéticos gerados

## Checklist de qualidade

### Schema
- [ ] Todos os campos obrigatórios têm validadores (not null, tipo correto)
- [ ] Enums definidos para campos categóricos (`event_type`, `status`, `protocol`)
- [ ] `timestamp` sempre em UTC com timezone explícita
- [ ] IPs validados com `pydantic.networks.IPvAnyAddress`

### Validação
- [ ] Missing values reportados por campo (não apenas contagem total)
- [ ] Duplicatas detectadas por `event_id`
- [ ] Registros inválidos isolados em relatório separado (não descartados silenciosamente)
- [ ] Resultado de validação é um objeto estruturado (não apenas print)

### Dados sintéticos
- [ ] Seed fixo para reprodutibilidade
- [ ] Distribuição de `event_type` e `status` documentada
- [ ] Anomalias injetadas com proporção controlável por parâmetro
- [ ] Nenhum dado real misturado com sintético

### Drift (quando modelo ativo)
- [ ] Distribuição de referência salva em `data/processed/reference_distribution.parquet`
- [ ] Threshold de drift configurável via `.env` (`DRIFT_ALERT_THRESHOLD`)
