# Revisão de segurança — Sentinel

**Status:** checklist inicial; não equivale a pentest, auditoria independente ou aprovação para produção.  
**Data da revisão registrada:** a preencher na execução real.  
**Responsável/revisor:** a preencher.

## Escopo

`src/sentinel/`, `api/`, `scripts/`, `mcp/`, dependências, GitHub Actions, configuração e documentação de deploy.

## Findings e evidências

| ID | Área | Severidade | Estado | Evidência a coletar / critério |
|---|---|---|---|---|
| SEC-001 | Segredo padrão da API | Alta em produção | Mitigação no código; validar configuração | Confirmar que `SENTINEL_ENV=production` rejeita `API_SECRET_KEY=change-me-in-production`; testar sem chave e com chave incorreta |
| SEC-002 | Limites de entrada | Média | Verificação contínua | Testar payload grande, lote acima do limite, JSON inválido e tipos inesperados |
| SEC-003 | Serialização do modelo | Alta se artefato não confiável | Pendente de política operacional | Artefatos `joblib`/pickle só devem vir de pipeline confiável e com hash/verificação de origem; nunca carregar upload de usuário |
| SEC-004 | Dependências | Média | Executar no CI | Registrar resultado de `pip-audit`; corrigir ou justificar vulnerabilidades |
| SEC-005 | Segredos no histórico | Alta | Executar no CI e no histórico | Gitleaks sem achados não justificados; revogar imediatamente credenciais reais expostas |
| SEC-006 | MCP | Média | Revisar a cada alteração | Apenas quatro ferramentas permitidas; sem shell, caminhos fornecidos pelo cliente, escrita ou deploy; respostas sem payload bruto |
| SEC-007 | CORS e exposição de docs | Média conforme deploy | Configuração por ambiente | Restringir origens; decidir explicitamente se `/docs` e `/redoc` ficam públicos em produção |
| SEC-008 | Dependências e permissões CI | Média | Revisão de workflow | `permissions: contents: read`, sem `pull_request_target` privilegiado e sem publicar releases automaticamente |
| SEC-009 | Dados de exemplo | Alta se dados reais forem incluídos | Verificar antes do release | Confirmar que fixtures e relatórios contêm apenas dados sintéticos ou devidamente autorizados |
| SEC-010 | Frontend / cadeia npm | Média | Pendente | O ZIP recebido não contém `frontend/package-lock.json`; sem lockfile, instalação não é totalmente reproduzível. Gerar lockfile, revisar versão de Next.js e executar `npm audit`/build antes de release |

## Comandos locais

```bash
ruff check .
ruff format --check .
mypy src/sentinel/ api/
pytest --cov=src/sentinel --cov-report=term-missing
bandit -r src/ api/ scripts/ -c pyproject.toml
pip-audit
```

Para Gitleaks, use a ação de CI ou a versão oficial instalada no ambiente. Examine o histórico de commits; verificar apenas a árvore atual não detecta segredos já removidos.

## Regra para findings

Cada finding real deve registrar: identificador, severidade, ativo afetado, evidência reproduzível, impacto, correção, responsável e status. Não marque como aprovado com base apenas na existência de configuração ou de um workflow.

## Critério de encerramento

Esta revisão só pode ser marcada como concluída após executar os comandos no commit candidato, anexar os resultados e resolver ou aceitar formalmente os riscos residuais. Não afirmar “sem vulnerabilidades” com base apenas em ferramentas estáticas.
