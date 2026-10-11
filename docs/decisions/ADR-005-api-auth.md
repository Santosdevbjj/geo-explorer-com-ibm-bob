# ADR-005 — Autenticação da API via API Key

**Status:** Aceito  
**Data:** 2025-01  
**Contexto:** Hardening da API Sentinel para deploy

---

## Contexto

A API Sentinel expõe endpoints de ingestão e detecção que processam dados de segurança. Sem autenticação, qualquer agente pode enviar dados maliciosos ou causar DoS via batches grandes.

## Decisão

Implementar **API Key via header `X-Api-Key`** para endpoints de escrita:
- `POST /ingest` — requer chave
- `POST /detect` — requer chave
- `GET /health`, `GET /alerts`, `GET /metrics` — públicos

A chave é lida de `API_SECRET_KEY` no `.env`. Em desenvolvimento (`change-me-in-production`), qualquer valor é aceito para não bloquear o desenvolvimento local.

## Alternativas Consideradas

| Alternativa | Motivo da rejeição |
|---|---|
| OAuth2 / JWT | Overhead excessivo para portfólio sem múltiplos usuários |
| Sem autenticação | Endpoint de ingestão aberto é risco inaceitável em produção |
| mTLS | Requer PKI — inadequado para portfólio simples |

## Consequências

- Desenvolvedor local precisa passar `X-Api-Key: change-me-in-production` ou qualquer valor
- Em produção, `API_SECRET_KEY` deve ser rotacionado via segredos do ambiente (Vercel env vars)
- Testes de integração passam o header explicitamente

## Limitações

- API Key não é por usuário — todos os clientes compartilham a mesma chave
- Não substitui OAuth2 para ambientes multi-tenant
- Não provê rastreabilidade por usuário individual
