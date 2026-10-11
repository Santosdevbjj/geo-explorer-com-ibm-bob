# Plano Técnico — Intelligent DevSecOps Sentinel

**Status:** plano de trabalho; itens devem ser verificados no commit local antes de serem marcados como concluídos.  
**Escopo:** completar a base de portfólio com controles testáveis e documentação honesta.  
**Regra:** não registrar comandos como aprovados sem executá-los e guardar a saída.

## Estado observado na revisão do ZIP recebido

- Existem módulos para validação, engenharia de features, regras, scoring, modelo, métricas e drift.
- A API já possui `/health`, `/ingest`, `/detect`, `/alerts` e `/metrics`; o plano adiciona aliases de análise e `/model-info`.
- Existe uma suíte considerável de testes, mas a execução inicial neste ambiente teve falhas. Veja os resultados reais no registro de trabalho; não os trate como aprovação.
- O MCP original usava implementação JSON-RPC própria e ferramentas diferentes da especificação desejada. O servidor foi ajustado para usar o SDK oficial e ferramentas somente leitura.
- A distribuição de referência de drift foi ajustada para JSON para remover a dependência implícita de um engine Parquet no caminho padrão. Arquivos Parquet legados continuam sendo aceitos se o engine estiver instalado.
- A revisão de segurança e a prontidão de release são checklists a preencher com evidências, não certificações.

## Fase 1 — Contratos de API e limites

- [ ] Executar testes de `/health` e `/model-info`.
- [ ] Testar `/analyze` e `/analyze/batch` com entradas válidas e inválidas.
- [ ] Confirmar limite de lote e limite por evento.
- [ ] Confirmar que o segredo placeholder é rejeitado em produção.
- [ ] Verificar que respostas de erro não ecoam payloads.

**Aceite:** testes reproduzíveis e sem regressão nos endpoints anteriores.

## Fase 2 — Qualidade do pipeline de dados e ML

- [ ] Executar validação do dataset sintético com seed fixa.
- [ ] Verificar split temporal e ausência de vazamento de alvo.
- [ ] Registrar métricas reais do holdout sintético, com aviso explícito.
- [ ] Verificar comportamento sem artefato de modelo.
- [ ] Validar JSON de referência, tamanho de amostra e limiar de drift.
- [ ] Diferenciar data drift de concept drift em relatório e documentação.

**Aceite:** relatório reprodutível, versão de dados/modelo identificada e limitações documentadas.

## Fase 3 — Segurança e cadeia de dependências

- [ ] Executar Ruff, mypy, pytest, Bandit e pip-audit.
- [ ] Executar Gitleaks sobre a árvore e o histórico.
- [ ] Revisar permissões de GitHub Actions e configuração de CORS/docs.
- [ ] Confirmar que artefatos joblib vêm apenas de fonte confiável.
- [ ] Atualizar `docs/security-review.md` com findings e evidências.

**Aceite:** findings bloqueadores resolvidos ou aceitos formalmente; nenhum resultado inventado.

## Fase 4 — MCP oficial e somente leitura

- [ ] Instalar `.[mcp]` e verificar import do SDK oficial.
- [ ] Confirmar as quatro ferramentas permitidas.
- [ ] Testar argumentos inválidos, evento grande e relatórios ausentes.
- [ ] Verificar ausência de ferramentas de shell, escrita, deploy ou caminhos arbitrários.
- [ ] Testar configuração local no cliente MCP utilizado.

**Aceite:** servidor inicializa localmente e só expõe ferramentas documentadas.

## Fase 5 — Documentação e pré-release

- [ ] Revisar README, arquitetura, dicionário, governança, model card e ADRs.
- [ ] Revisar frontend contra o contrato atual da API.
- [ ] Executar build frontend se as dependências estiverem disponíveis.
- [ ] Preencher `docs/release-readiness.md` com o commit e saídas reais.
- [ ] Não publicar ou implantar automaticamente.

**Aceite:** decisão de release explícita, com evidências anexadas e riscos residuais registrados.

## Próxima ação recomendada

Executar localmente a suíte e corrigir falhas antes de ampliar funcionalidades. Uma pipeline verde prova que os checks configurados passaram; não prova, sozinha, que o modelo é útil ou que o sistema está pronto para produção.
