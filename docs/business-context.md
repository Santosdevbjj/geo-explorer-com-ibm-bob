# Contexto de negócio — Intelligent DevSecOps Sentinel

## Problema que o projeto explora

Equipes de segurança recebem eventos de autenticação, HTTP e rede em volume elevado. Alertas sem contexto podem gerar ruído, aumentar o tempo de triagem e dificultar a explicação de por que uma atividade foi priorizada.

O Sentinel é um projeto de portfólio que demonstra um pipeline reproduzível para validar eventos sintéticos, aplicar regras transparentes e produzir sinais explicáveis. Ele **não é um SIEM de produção nem comprova detecção de ataques reais**.

## Usuários e decisões apoiadas

- Analista de segurança: decidir quais eventos exigem investigação inicial.
- Engenheiro de dados/ML: verificar qualidade de entrada, consistência de features e disponibilidade de artefatos.
- Revisor técnico: rastrear regra, versão, limitações e evidências usadas para uma decisão.

## Escopo atual

- Validação de schema e qualidade de lotes.
- Regras heurísticas para força bruta, pico de tráfego e padrões de injeção.
- Modelo IsolationForest opcional, treinado com dados sintéticos.
- Resumo de avaliação e monitoramento de data drift.
- API local e ferramentas MCP somente leitura.

## Fora do escopo

- Bloqueio automático de IPs, resposta ativa ou contenção de incidentes.
- Atribuição de intenção maliciosa a pessoas.
- Garantia de precisão operacional, SLA, redução de incidentes ou economia financeira.
- Uso de dados pessoais, telemetria corporativa ou logs de terceiros sem autorização formal.

## Critérios de valor a medir em uma futura validação

Antes de afirmar impacto, definir dataset autorizado e rotulado, baseline comparável, custo de falsos positivos e falsos negativos, latência p95, throughput, estabilidade por segmento e protocolo de revisão humana. Os resultados precisam ser reproduzíveis e acompanhados de limitações.

## Hipóteses e riscos

| Hipótese | Como validar | Risco se estiver errada |
|---|---|---|
| Regras transparentes ajudam a triagem | Revisão cega por analistas com amostra rotulada | Ruído e confiança excessiva |
| Features capturam mudanças úteis | Análise por janela e ablação | Sinais sem valor operacional |
| Data drift é um alerta de investigação | Comparar drift com rótulos e métricas posteriores | Alarmes desnecessários ou falsa tranquilidade |
| MCP reduz atrito de consulta | Teste com tarefas representativas e limites de acesso | Exposição excessiva ou resultados mal interpretados |

## Princípio de comunicação

Todo resultado precisa distinguir **fato medido**, **hipótese** e **limitação**. Dados sintéticos demonstram comportamento técnico, não desempenho no mundo real.
