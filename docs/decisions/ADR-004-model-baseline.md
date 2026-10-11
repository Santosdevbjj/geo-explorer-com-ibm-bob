# ADR-004 — Modelo de baseline para anomalias

- **Status:** Aceito como experimento de portfólio.
- **Contexto:** o Sentinel precisa demonstrar integração de ML sem alegar desempenho operacional com dados não representativos.
- **Decisão:** usar IsolationForest sobre features determinísticas e documentadas como baseline opcional. Regras explícitas continuam disponíveis quando o artefato não está carregado.
- **Alternativas:** regras somente; modelo supervisionado com dados rotulados autorizados; ensemble com calibração.
- **Consequências:** permite exercitar treino, versionamento, avaliação e monitoramento; score de anomalia não é probabilidade calibrada; métricas em dados sintéticos não sustentam alegações sobre ataques reais.
- **Critério para evoluir:** conjunto rotulado representativo, baseline competitivo, análise de custo de falsos positivos/falsos negativos, avaliação temporal e governança de artefatos.
