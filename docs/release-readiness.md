# Release readiness — Sentinel

**Status inicial:** não aprovado para release até que as evidências abaixo sejam coletadas no commit candidato.  
**Commit avaliado:** a preencher.  
**Data:** a preencher.  
**Responsável:** a preencher.

## Bloqueadores

- [ ] `ruff check .` concluído sem erros.
- [ ] `ruff format --check .` concluído.
- [ ] `mypy src/sentinel/ api/` concluído sem erros ou exceções documentadas.
- [ ] `pytest --cov=src/sentinel --cov-report=term-missing` executado; falhas corrigidas e cobertura observada registrada.
- [ ] Testes de API validam `/health`, `/model-info`, `/analyze`, `/analyze/batch`, autenticação e limite de lote.
- [ ] `bandit` e `pip-audit` executados; findings tratados ou aceitos com justificativa.
- [ ] Gitleaks executado sobre a árvore e o histórico.
- [ ] Segredo padrão rejeitado em `SENTINEL_ENV=production`.
- [ ] Dependências e artefatos de modelo têm origem e versões documentadas.
- [ ] README e model card não apresentam métricas sintéticas como desempenho real.
- [ ] Revisão de `docs/security-review.md` atualizada com evidências.

## Métricas e modelo

- [ ] Dados de avaliação e metodologia documentados.
- [ ] Holdout temporal separado do treino.
- [ ] Métricas relevantes e baseline registrados, sem claims sem evidência.
- [ ] Scores de anomalia identificados como não calibrados.
- [ ] Comportamento quando o artefato está ausente é testado e documentado.
- [ ] Referência de drift tem versão, data, schema e tamanho de amostra.
- [ ] Nenhuma conclusão de concept drift é feita sem rótulos/resultados posteriores.

## Deploy e operação

- [ ] Ambiente, Python e dependências compatíveis com a plataforma alvo.
- [ ] CORS, autenticação, rate limiting, exposição de docs e limites de payload revisados.
- [ ] Confirmado que o armazenamento em memória não é persistência de produção.
- [ ] Plano de rollback e retenção definido, se houver implantação real.
- [ ] MCP testado em modo local; nenhuma ferramenta de mutação ou execução arbitrária.

## Decisão

- [ ] **Aprovado** — todos os bloqueadores atendidos e evidências anexadas.
- [ ] **Aprovado com ressalvas** — somente se houver aceitação formal de riscos não bloqueadores.
- [ ] **Bloqueado** — existe bloqueador não resolvido.

**Decisão e justificativa:** a preencher após execução. Este arquivo é um checklist, não evidência de que a release passou.
