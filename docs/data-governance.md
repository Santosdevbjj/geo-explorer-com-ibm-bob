# Governança de Dados

## Princípios

1. **Nenhum dado real em repositório:** dados brutos e processados são gitignored.
2. **Dados sintéticos reproduzíveis:** gerados com seed fixo; qualquer pessoa pode recriar.
3. **Sem PII:** eventos não contêm informações pessoais identificáveis. `user_id` é anonimizado.
4. **Rastreabilidade:** todo dataset processado registra sua origem e versão do script gerador.

## Fontes Autorizadas

| Fonte | Tipo | Uso |
|---|---|---|
| `scripts/generate_synthetic_data.py` | Sintético | Desenvolvimento, testes, CI |
| [CICIDS2017](https://www.unb.ca/cic/datasets/ids-2017.html) | Público autorizado | Pesquisa / treinamento (não commitado) |
| [NSL-KDD](https://www.unb.ca/cic/datasets/nsl.html) | Público autorizado | Pesquisa / avaliação (não commitado) |

## Procedimento para Adicionar uma Nova Fonte

1. Verificar licença de uso — apenas datasets com licença explícita para pesquisa/educação
2. Documentar a fonte neste arquivo com URL, licença e data de acesso
3. Adicionar o nome do arquivo ao `.gitignore` antes de baixar
4. Registrar o schema em `docs/data-dictionary.md`
5. Nunca commitar os dados brutos

## Retenção e Limpeza

- Dados em `data/processed/` podem ser regenerados a qualquer momento via scripts
- Dados em `data/synthetic/` são descartáveis — recriados com `generate_synthetic_data.py`
- Modelos em `models/` são versionados por nome de arquivo; versões antigas devem ser removidas manualmente
