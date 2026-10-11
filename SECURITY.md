# Política de Segurança

## Versões Suportadas

| Versão | Suporte de segurança |
|--------|----------------------|
| `main` | ✅ Sim               |

## Reportando uma Vulnerabilidade

**Não abra uma issue pública** para relatar vulnerabilidades de segurança.

Envie um e-mail para **santossergiorealbjj@outlook.com** com:

1. Descrição da vulnerabilidade
2. Passos para reproduzir
3. Impacto potencial estimado
4. Sugestão de correção (opcional)

**Prazo de resposta:** Confirmação em até 72 horas. Correção publicada em até 14 dias para issues críticas.

Após a correção, o relator será creditado no `CHANGELOG.md` (se desejar).

## Práticas de Segurança deste Projeto

- Análise estática com **Bandit** em cada PR
- Auditoria de dependências com **pip-audit** no CI
- Varredura de segredos com **Gitleaks** no CI
- Nenhum segredo no repositório — variáveis via `.env` (ver `.env.example`)
- Dados sensíveis e modelos serializados em `.gitignore`
