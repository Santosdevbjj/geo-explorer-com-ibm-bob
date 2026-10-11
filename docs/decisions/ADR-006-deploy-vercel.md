# ADR-006 — Deploy na Vercel com Python Serverless

**Status:** Aceito  
**Data:** 2025-01  
**Contexto:** Deploy do Sentinel como projeto de portfólio público

---

## Contexto

O Sentinel precisa de um ambiente de deploy público para demonstração. Vercel é a plataforma escolhida por integrar nativamente com GitHub, suportar Python via `@vercel/python` e não exigir infra adicional.

## Decisão

Usar **Vercel Serverless Functions** para a API Python e **Vercel Static** para o frontend Next.js no mesmo repositório.

Configuração: [`vercel.json`](../../vercel.json) com `@vercel/python` apontando para `api/index.py`.

## Limitações Conhecidas e Aceitas

| Limitação | Impacto | Mitigação |
|---|---|---|
| **Sem persistência entre invocações** | Alertas em memória perdidos ao reiniciar a função | Documentar explicitamente no README e em `GET /alerts` |
| **Cold start ~500–1500ms** | Primeira requisição após inatividade é lenta | Documentar latência esperada; health check para "aquecimento" |
| **Modelo ML não persistido** | `AnomalyDetector` precisa ser treinado previamente e não pode ser salvo na Vercel | API opera em modo rules-only no deploy Vercel até ter artefato bundlado |
| **Limite de tamanho de função** | Vercel Free: 50MB por função | pandas + scikit-learn podem aproximar esse limite |
| **Sem subprocessos de longa duração** | `train_model.py` não pode rodar na Vercel | Treino é sempre local/CI |

## Alternativas Consideradas

| Alternativa | Motivo da rejeição |
|---|---|
| Render / Railway | Mais infra para gerenciar; adequado para produção real |
| Fly.io | Requer Docker e configuração de volumes |
| AWS Lambda | Mais complexo para portfólio |
| Vercel com banco externo (PlanetScale/Neon) | Adicionaria dependência externa desnecessária para portfólio |

## Consequências

- `requirements.txt` mantido separado do `pyproject.toml` para uso pelo Vercel
- API funciona em modo rules-only em produção (sem modelo ML)
- README documenta URL de produção e as limitações

## Decisão sobre Python 3.14 em Vercel

🟡 **Hipótese:** o runtime `@vercel/python` pode não suportar Python 3.14 imediatamente.  
🟢 O deploy usará Python 3.12 (versão atual do projeto) até suporte oficial do Vercel para 3.14.
