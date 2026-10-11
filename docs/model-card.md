# Model Card — Sentinel AnomalyDetector baseline

**Status:** baseline experimental; não aprovado para decisões operacionais  
**Algoritmo:** IsolationForest + StandardScaler (`scikit-learn`)  
**Artefatos:** gerados localmente por `scripts/train_model.py`; não versionar binários  
**Última revisão documental:** 2026-10

## Finalidade pretendida

Demonstrar um ciclo reproduzível de preparação de features, treinamento, avaliação e monitoramento para detecção não supervisionada de anomalias em eventos sintéticos de segurança.

O componente não substitui um SIEM, analista humano ou investigação de incidentes. Não afirmar que detecta ataques reais sem validação com dados autorizados e representativos.

## Dados

- Fonte padrão: `data/synthetic/events.jsonl`, gerado por `scripts/generate_synthetic_data.py`.
- O script de treino usa divisão temporal com holdout final definido por `--test-split` (padrão 20%).
- O treino é não supervisionado; rótulos sintéticos não devem ser usados inadvertidamente como feature.
- A quantidade efetiva depende do dataset e dos parâmetros usados. Registre hash, versão e tamanho do arquivo em cada execução.
- Não incluir logs reais, dados pessoais ou segredos em exemplos ou artefatos sem autorização e controles de governança.

## Features

As features usadas pelo modelo estão definidas em `src/sentinel/detection/model.py` e devem permanecer alinhadas com `src/sentinel/features/engineering.py`. Entre elas estão taxas de falha, contagem de requisições, caminhos únicos, proporção de falhas, tamanho de payload e intervalos entre eventos.

O scaler é ajustado no treino e reutilizado na inferência. Mudanças no schema ou nas definições de features exigem nova versão da referência e reavaliação.

## Parâmetros

| Parâmetro | Padrão | Observação |
|---|---:|---|
| `contamination` | `0.05` | Estimativa de proporção de anomalias usada pelo IsolationForest |
| `n_estimators` | `100` | Quantidade de árvores |
| `random_state` | `42` | Reprodutibilidade |
| `test_split` | `0.20` | Proporção temporal reservada para avaliação |

Parâmetros podem ser alterados por argumentos do script e/ou variáveis de ambiente documentadas em `.env.example`.

## Saída e interpretação

O método `predict` retorna um score normalizado relativo ao conjunto avaliado. **Esse valor não é uma probabilidade calibrada de ataque.** A normalização por lote pode afetar a comparação entre lotes diferentes.

## Integração atual com a API

O modelo é uma baseline experimental e pode ser carregado por `get_detector()`. Nesta versão, o score do modelo **não compõe o score final dos alertas**: a geração de alertas usa regras explícitas (`BruteForceRule`, `TrafficSpikeRule` e `InjectionRule`). `/model-info` diferencia disponibilidade do artefato de integração efetiva ao scoring. Não descrever o pipeline atual como ensemble híbrido.

A próxima etapa, se houver necessidade comprovada, deve definir um contrato de score por evento, uma estratégia estável de comparação entre janelas, calibração/limiares e avaliação com rótulos antes de integrar o score de ML aos alertas.

## Avaliação

`python scripts/evaluate_model.py` gera o relatório da versão treinada. Métricas calculadas em dados sintéticos são evidência apenas do comportamento nesse experimento; não demonstram desempenho no mundo real. Não publicar números sem registrar a execução, dataset/hash, split e baseline de comparação.

## Monitoramento

A referência padrão é `data/processed/reference_distribution.json`. O monitoramento usa PSI para comparar distribuições de features e sinalizar mudanças que merecem investigação. O limiar padrão é `DRIFT_ALERT_THRESHOLD=0.1`.

Data drift não é sinônimo de concept drift e não prova queda de acurácia. Para avaliar concept drift ou degradação, são necessários rótulos/resultados posteriores e métricas por janela.

## Limitações e riscos

1. Dados sintéticos não reproduzem toda a variedade de tráfego e ataques reais.
2. IsolationForest não fornece probabilidade calibrada.
3. Um score relativo ao lote não deve ser comparado ingenuamente entre lotes.
4. Features agregadas podem esconder ataques distribuídos ou comportamentos raros.
5. Drift pode gerar falso alarme; ausência de drift nas features monitoradas não prova que o modelo continua útil.
6. Artefatos serializados (`joblib`/pickle) devem ser carregados somente se produzidos por pipeline confiável. Nunca carregar artefato fornecido por usuário.
7. O modelo ainda não influencia o score final dos alertas da API.

## Uso responsável

- Tratar alertas como sinais para investigação, não como confirmação de ataque.
- Exigir revisão humana antes de ações que afetem sistemas ou usuários.
- Guardar apenas agregados necessários, evitando logs de payloads brutos.
- Versionar dados de referência, código, parâmetros e artefatos de maneira rastreável.
