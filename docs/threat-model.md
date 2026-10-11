# Threat Model — Sentinel

**Status:** avaliação inicial de ameaças; não é pentest nem aprovação de produção.  
**Escopo:** FastAPI, pipeline Python, artefatos ML, relatórios e servidor MCP local.  
**Método:** STRIDE simplificado.

## Ativos

- Disponibilidade e integridade da API.
- Integridade de eventos e relatórios de avaliação.
- Chaves de API e configurações de ambiente.
- Artefatos serializados do modelo.
- Dados e metadados dos eventos.
- Ferramentas e limites de acesso MCP.

## Ameaças e controles

| Ameaça | Vetor | Controles presentes | Risco residual / ação |
|---|---|---|---|
| Spoofing | Chamada de endpoint protegido sem chave | Header `X-Api-Key` quando configurado | Definir gerenciamento/rotação de chaves antes de deploy compartilhado |
| Segredo padrão | Deploy com placeholder | Placeholder rejeitado em `SENTINEL_ENV=production` | Testar configuração do ambiente de deploy |
| DoS | Lotes grandes ou evento muito grande | `MAX_BATCH_SIZE` e limite de 64 KiB por evento nos endpoints de ingestão/detecção | Rate limiting por IP e limites de proxy ainda precisam de decisão |
| Tampering | Campos malformados ou tipos inesperados | Schemas Pydantic e validação do pipeline | Rever campos de metadata e validações específicas do domínio |
| Information disclosure | Erros e logs revelam payload | Mensagens de erro controladas; logging sem payload bruto nos fluxos revistos | Revisar todos os logs e o comportamento do servidor ASGI no deploy |
| Model poisoning / unsafe deserialization | Artefato `joblib` adulterado | Artefatos fora do repositório e gerados localmente | Nunca carregar artefatos de upload ou origem não confiável; registrar hash/origem |
| Secret leakage | `.env` ou token em commit | `.gitignore`, `.bobignore` e Gitleaks no CI | Executar Gitleaks também sobre o histórico |
| Abuso de MCP | Ferramenta invocada com argumentos maliciosos | SDK oficial; quatro ferramentas de escopo limitado; sem shell, escrita ou caminho fornecido pelo cliente | Revisar qualquer nova ferramenta e limitar dados devolvidos |
| Supply chain | Dependência vulnerável ou adulterada | `pip-audit` e revisão de dependências no CI | Dependências não estão todas fixadas por hash; manter lock/constraints quando necessário |
| Exposição frontend | Dependências npm antigas ou sem lockfile | Revisão ainda pendente | Gerar `package-lock.json`, revisar versões e executar `npm audit`/build |

## Configurações relevantes

- `API_SECRET_KEY` deve ser fornecida por secret manager ou variável segura no ambiente.
- Em produção, nunca usar `change-me-in-production`.
- Restringir `CORS_ORIGINS` ao conjunto necessário; evitar wildcard em ambientes com exposição pública.
- Decidir se `/docs` e `/redoc` devem permanecer acessíveis no ambiente de produção.
- Alertas são mantidos em memória e não fornecem persistência durável nem trilha de auditoria.

## Fora do escopo atual

Rate limiting por IP, autenticação por usuário (OAuth2/JWT), persistência durável, audit log completo, criptografia em repouso e pentest formal.

## Conclusão

Os controles listados são medidas de redução de risco, não prova de ausência de vulnerabilidades. Antes de release, executar os scanners, revisar o commit e preencher `docs/security-review.md` e `docs/release-readiness.md` com evidências.
