# Aplicação do complemento

1. Faça backup e verifique `git status` no clone atual.
2. Extraia este ZIP na raiz do repositório, revisando sobrescritas locais.
3. Exclua manualmente `mcp/__init__.py`: ele conflita com o pacote do SDK MCP oficial.
4. O diretório `src/sentinel.egg-info/` é gerado pelo build e não deve ser versionado.
5. Reinstale dependências e execute os testes conforme `MIGRATION_NOTES.md`.

Arquivos alterados: 22
Arquivos novos: 10
Arquivos a remover: mcp/__init__.py
