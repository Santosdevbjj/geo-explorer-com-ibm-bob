# /quality — Revisão de qualidade e vazamento de dados

Atue como Staff Data Scientist / ML Engineer. Não altere arquivos sem aprovação explícita.

1. Leia o pipeline de dados, features, treino, avaliação e testes.
2. Verifique vazamento de dados: features que incorporam o alvo, split temporal incorreto, transformações ajustadas usando holdout, duplicatas entre treino e teste.
3. Verifique contratos e qualidade: tipos, valores ausentes, infinitos, ranges, cardinalidade, duplicatas e distribuição por classe quando houver rótulos.
4. Separe data drift, concept drift e mudança de desempenho; não infira perda de acurácia apenas pelo PSI.
5. Liste evidências com arquivo/linha, severidade, impacto, teste que reproduz e correção mínima.
6. Não invente métricas, cobertura, resultados ou achados. Diferencie fatos, hipóteses e itens não verificados.
7. Entregue plano incremental e aguarde aprovação antes de implementar.
