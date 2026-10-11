# Changelog

Todas as mudanças notáveis neste projeto estão documentadas aqui.  
Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/).  
Este projeto adota [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Unreleased]

### Added
- Endpoints `/model-info`, `/analyze` e `/analyze/batch`, com limites explícitos de lote e tamanho de evento.
- Documentação de contexto de negócio, monitoramento, revisão de segurança e prontidão para release.
- Comandos IBM Bob para revisão de qualidade/vazamento e pré-release.
- Integração MCP com o SDK oficial e quatro ferramentas somente leitura.

### Changed
- Referência padrão de drift em JSON, evitando dependência obrigatória de engine Parquet.
- Configuração da API rejeita o segredo placeholder em ambiente de produção.
- Testes da API, de segurança e de ferramentas MCP atualizados.

### Validation
- Na execução de validação local deste pacote: `357 passed` com cobertura de `97%` em `src/sentinel/`.
- Ruff, mypy, Bandit, pip-audit, SDK MCP e build frontend não foram executados neste ambiente; verificar no ambiente do projeto antes de release.

---

## [Não lançado]

### Adicionado
- Estrutura inicial do repositório Sentinel
- `pyproject.toml` com metadados, dependências e configuração de Ruff, mypy, pytest e Bandit
- `.python-version` fixando Python 3.12
- `README.md` com descrição, arquitetura e instruções de setup
- `SECURITY.md` com política de divulgação responsável
- `CONTRIBUTING.md` com guia de contribuição
- `.env.example` com todas as variáveis de ambiente documentadas
- `docs/decisions/ADR-001-architecture.md` — decisão de arquitetura Python modular
- Estrutura de diretórios: `src/sentinel/`, `tests/`, `data/`, `docs/`, `scripts/`, `mcp/`
- Comandos IBM Bob em `.bob/commands/`
