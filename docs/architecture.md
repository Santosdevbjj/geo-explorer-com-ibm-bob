# Arquitetura do Sentinel

## Visão geral

O Sentinel é um projeto de portfólio para explorar validação de eventos, detecção baseada em regras, avaliação de uma baseline de ML e controles básicos de API. O dataset padrão é sintético.

```text
data/synthetic/events.jsonl
        |
        v
scripts/validate_data.py / scripts/train_model.py
        |
        v
src/sentinel/
  data/validation.py       schema, ausentes e duplicatas
  features/engineering.py features agregadas
  detection/rules.py      regras explícitas
  detection/model.py      IsolationForest experimental
  detection/scoring.py    score e explicabilidade baseados em regras
  evaluation/metrics.py   métricas experimentais
  monitoring/drift.py     PSI de distribuição de features
        |
        v
api/index.py (FastAPI)
  /health /model-info /ingest /detect /analyze /analyze/batch
  /alerts /metrics
        |
        +---- frontend/ (Next.js)
        |
        +---- mcp/server.py (SDK oficial; stdio; somente leitura)
```

## Limites de responsabilidade

- `src/sentinel/` contém contratos e lógica analítica; `api/` é a camada HTTP.
- `/health` informa disponibilidade da API; `/model-info` informa estado do artefato. Esses estados não são equivalentes.
- O score final dos alertas usa as regras explícitas. O modelo IsolationForest é uma baseline experimental e ainda não está integrado ao scoring final.
- O modelo pode estar ausente sem tornar a API indisponível; nesse caso, o pipeline de regras continua disponível.
- O score de anomalia não é uma probabilidade calibrada.
- A API mantém alertas em memória; isso não fornece durabilidade ou auditoria de produção.
- O servidor MCP usa o SDK oficial com transporte `stdio` e quatro ferramentas restritas. Não oferece shell, escrita, deploy ou acesso a caminhos escolhidos pelo cliente.

## Endpoints

| Método | Rota | Responsabilidade |
|---|---|---|
| GET | `/health` | Saúde do serviço |
| GET | `/model-info` | Disponibilidade do artefato e modo atual de análise |
| POST | `/ingest` | Validar lote de eventos |
| POST | `/detect` | Aplicar regras e gerar alertas |
| POST | `/analyze` | Alias tipado para análise de evento único |
| POST | `/analyze/batch` | Analisar lote com limites |
| GET | `/alerts`, `/alerts/{alert_id}` | Consultar alertas da memória do processo |
| GET | `/metrics` | Ler relatório de avaliação previamente gerado |

## Segurança e dados

- Schemas Pydantic validam eventos antes de processá-los.
- Lotes e tamanho de evento têm limites.
- A chave padrão não pode ser usada em `SENTINEL_ENV=production`.
- Não registrar payloads brutos nem colocar segredos em fixtures.
- Carregar artefatos serializados apenas de fonte confiável.
- A configuração CORS, exposição de OpenAPI e estratégia de autenticação devem ser revistas para cada ambiente.

## Drift e avaliação

A referência padrão para drift fica em `data/processed/reference_distribution.json`. O PSI sinaliza mudanças nas distribuições monitoradas, mas não prova queda de desempenho. Avaliar degradação exige rótulos/resultados posteriores e métricas em janelas comparáveis.

## Decisões

As decisões arquiteturais e seus trade-offs estão documentados em [`decisions/`](decisions/). Uma decisão aceita para portfólio não é automaticamente adequada para produção.
