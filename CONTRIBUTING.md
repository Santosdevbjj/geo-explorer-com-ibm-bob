# Guia de Contribuição

Obrigado pelo interesse em contribuir com o Sentinel!

## Pré-requisitos

- Python 3.15
- Git configurado com e-mail e nome
- Familiaridade com FastAPI, Pydantic e pytest

## Configuração do Ambiente

```bash
git clone https://github.com/Santosdevbjj/geo-explorer-com-ibm-bob.git
cd geo-explorer-com-ibm-bob
python -m venv .venv
source .venv/bin/activate      # Linux/macOS
.venv\Scripts\activate         # Windows
pip install -e ".[dev]"
cp .env.example .env
```

## Fluxo de Trabalho

1. Crie um branch a partir de `main`:

   ```bash
   git checkout -b feat/nome-da-funcionalidade
   ```

2. Faça as alterações seguindo as [convenções de código](#convenções-de-código).

3. Rode as verificações localmente **antes** de abrir o PR:

   ```bash
   ruff check .
   mypy src/
   pytest
   bandit -r src/ api/
   ```

4. Abra um Pull Request com:
   - Descrição clara do que foi alterado e por quê
   - Referência à issue relacionada (se houver)
   - Evidência de que os testes passam

## Convenções de Código

- **Formatação:** Ruff (line-length 88)
- **Tipagem:** mypy strict — todo código novo deve ter type hints
- **Testes:** pytest — novas funcionalidades exigem testes; coverage não deve cair
- **Commits:** mensagens em inglês, no formato `tipo: descrição curta`
  - `feat:` nova funcionalidade
  - `fix:` correção de bug
  - `docs:` apenas documentação
  - `test:` adição ou correção de testes
  - `chore:` manutenção (deps, CI, config)
  - `refactor:` refatoração sem mudança de comportamento

## Decisões Arquiteturais

Mudanças significativas de arquitetura devem ser acompanhadas de um novo ADR em `docs/decisions/`.  
Veja [`ADR-001`](docs/decisions/ADR-001-architecture.md) como referência de formato.

## Segurança

Não inclua segredos, tokens ou dados sensíveis nos commits.  
Vulnerabilidades devem ser reportadas conforme [`SECURITY.md`](SECURITY.md).

## Dúvidas

Abra uma issue com a label `question`.
