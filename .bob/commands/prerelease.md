# /prerelease — Revisão independente antes da release

Atue como Staff Engineer revisor independente. Não faça commit, push, deploy, publicação de release ou alterações automáticas.

1. Leia `README.md`, `CHANGELOG.md`, `docs/release-readiness.md`, `docs/security-review.md`, ADRs e arquivos alterados.
2. Execute ou peça execução dos testes e scanners disponíveis; registre o comando e o resultado real. Se não puder executar, marque como não verificado.
3. Revise API, limites, autenticação, saúde do serviço versus disponibilidade do modelo, armazenamento em memória, dependências e configuração.
4. Revise dados sintéticos, vazamento de alvo, versionamento de artefatos, data drift versus concept drift e afirmações de métricas.
5. Inspecione permissões CI, exposição de segredos, MCP somente leitura e compatibilidade do ambiente de deploy.
6. Entregue findings ordenados por severidade, evidência, consequência, correção mínima e status.
7. Termine com uma decisão explícita: aprovado, aprovado com ressalvas ou bloqueado. Não marque como aprovado sem evidências.
