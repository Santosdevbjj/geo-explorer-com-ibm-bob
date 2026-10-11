# Model monitoring: data drift, concept drift e saúde operacional

## Três perguntas diferentes

1. **O serviço está disponível?** `/health` responde se a API está operacional.
2. **O artefato de modelo está carregado?** `/model-info` informa se o modo é `rules+model` ou `rules-only`.
3. **O modelo continua útil?** Isso exige avaliação com resultados rotulados posteriores; não pode ser inferido apenas por saúde HTTP ou drift.

## Data drift

Data drift é uma mudança na distribuição de entradas ou features entre a referência e uma janela atual. O Sentinel calcula PSI para um conjunto definido de features. A referência é versionada como artefato gerado pelo pipeline de treino e armazenada em `data/processed/reference_distribution.json`.

Limitações:
- PSI depende da escolha de bins, amostra, features e qualidade da referência.
- Janelas pequenas ou dados ausentes podem tornar a estimativa instável.
- O limiar é um gatilho de investigação, não uma decisão automática de retreino.
- Comparações só fazem sentido se o esquema e a semântica das features forem compatíveis entre versões.

## Concept drift

Concept drift é a mudança na relação entre as entradas \(X\) e o resultado-alvo \(Y\). Em geral, exige rótulos ou resultados posteriores. Uma distribuição de features pode permanecer estável enquanto a relação com o alvo muda; e pode mudar sem que o desempenho piore.

**Regra de interpretação:** data drift não prova perda de acurácia. Para medir degradação, compare métricas em janelas rotuladas com baseline, intervalos de incerteza e segmentos relevantes.

## Procedimento de monitoramento

1. Registrar versão do modelo, versão da referência, janela temporal e tamanho da amostra.
2. Validar schema, valores ausentes, infinitos e duplicatas antes de comparar.
3. Calcular PSI por feature monitorada e guardar o resultado agregado sem payloads brutos.
4. Investigar alertas de drift com contexto operacional e mudanças conhecidas de coleta.
5. Quando os rótulos estiverem disponíveis, medir precision, recall, F1, PR-AUC e taxa de falsos positivos, conforme o caso de uso.
6. Abrir decisão documentada para manter, recalibrar ou retreinar; não retreinar automaticamente apenas pelo PSI.
7. Após mudança de modelo, comparar com baseline em holdout temporal e manter rollback do artefato anterior.

## Estados que não devem ser confundidos

| Estado | Interpretação correta |
|---|---|
| API saudável, modelo ausente | Serviço atende; inferência ML está indisponível e o sistema pode operar em modo somente regras |
| Modelo carregado, sem drift observado | Não há evidência de drift nas features monitoradas; não é prova de boa acurácia |
| Drift detectado | Distribuição observada mudou; investigar, não concluir degradação |
| Métricas degradadas em dados rotulados | Evidência de piora na métrica medida; investigar causas e impacto |

## Privacidade e retenção

Persistir agregados necessários à análise, evitar logs de eventos brutos, aplicar controle de acesso e retenção explícita. Usar apenas dados sintéticos ou dados autorizados. Não colocar dados pessoais ou segredos em fixtures, relatórios ou exemplos.
