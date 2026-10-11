# Notas para aplicar a versão complementada

Este arquivo é um pacote de código-fonte limpo para comparação e aplicação ao repositório `Santosdevbjj/geo-explorer-com-ibm-bob`.

## Antes de copiar

1. Faça backup da pasta atual e verifique `git status`.
2. Compare os arquivos antes de sobrescrever mudanças locais não commitadas.
3. Copie o conteúdo deste pacote para a raiz do clone local, preservando a pasta `.git` que já existe.
4. Remova `mcp/__init__.py` se ele ainda existir no clone antigo. O nome `mcp` colide com o pacote do SDK oficial; o diretório local é mantido sem `__init__.py` deliberadamente.
5. Não copie uma pasta `.venv` do pacote antigo. Recrie ou atualize o ambiente local com os comandos abaixo.

## Ambiente Windows PowerShell

```powershell
py -3.12 -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev,mcp]"
pytest --cov=src/sentinel --cov-report=term-missing
```

Para apenas API/testes sem a integração MCP opcional, use `python -m pip install -e ".[dev]"`.

## O que foi validado nesta preparação

- Sintaxe Python compilada com `compileall`.
- Suíte de testes executada no ambiente de preparação: **357 passaram**, cobertura total de **97% em `src/sentinel/`**.
- O ambiente de preparação não tinha Ruff, mypy ou SDK MCP oficial instalados; esses checks não são declarados como aprovados. O workflow tem um job separado para instalar e verificar o SDK MCP.
- O build do frontend, `pip-audit`, Bandit e Gitleaks não foram executados nesta preparação.
- O ZIP original não continha `frontend/package-lock.json`; o workflow foi ajustado para não exigir esse arquivo na etapa de setup, mas gerar e revisar um lockfile continua recomendado antes de release.

## Limitações importantes

- O score final dos alertas continua baseado em regras explícitas. O modelo IsolationForest é uma baseline experimental e ainda não compõe o score final.
- O dataset padrão é sintético; as métricas não representam desempenho real.
- Alertas são armazenados em memória.
- A documentação de segurança e pré-release é um checklist a ser preenchido com evidências, não uma certificação.
