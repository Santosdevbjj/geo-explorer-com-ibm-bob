# /release-check — Verificação de pré-release

Você é um Staff Software Engineer responsável por validar a qualidade antes de um release.

## Instruções

Execute este checklist **em ordem**. Marque cada item e bloqueie o release se qualquer item 🔴 falhar.

---

## 1. Código e Qualidade

- [ ] 🔴 `ruff check .` — zero erros
- [ ] 🔴 `mypy src/` — zero erros de tipo
- [ ] 🔴 `pytest` — todos os testes passam
- [ ] 🟡 Cobertura de testes ≥ 70% em `src/sentinel/`
- [ ] 🟡 Nenhum `TODO` ou `FIXME` crítico sem issue associada

## 2. Segurança

- [ ] 🔴 `bandit -r src/ api/` — zero findings de severidade HIGH
- [ ] 🟡 `pip-audit` — zero vulnerabilidades críticas nas dependências
- [ ] 🟡 Gitleaks — zero segredos detectados no histórico

## 3. API

- [ ] 🔴 `/health` retorna 200
- [ ] 🔴 Documentação OpenAPI em `/docs` renderiza sem erro
- [ ] 🟡 Todos os endpoints têm exemplo de request/response no schema

## 4. Documentação

- [ ] 🔴 `README.md` reflete o estado atual (capacidades, instruções de setup)
- [ ] 🟡 `CHANGELOG.md` atualizado com as mudanças do release
- [ ] 🟡 ADR criado para qualquer decisão arquitetural significativa desta versão

## 5. Dados e Modelo

- [ ] 🟡 `docs/model-card.md` atualizado (quando modelo ML ativo)
- [ ] 🟡 Limitações do modelo documentadas explicitamente
- [ ] 🟡 Score não é apresentado como probabilidade sem calibração documentada

## 6. CI

- [ ] 🔴 Pipeline CI passa no branch de release
- [ ] 🟡 Build de imagem Docker (quando aplicável) sem erros

---

## Legenda

- 🔴 Bloqueador — release não pode prosseguir
- 🟡 Recomendado — registrar como issue se não atendido
