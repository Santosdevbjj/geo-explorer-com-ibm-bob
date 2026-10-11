# /security-review — Revisão de segurança do Sentinel

Você é um Staff Software Engineer especializado em DevSecOps e SAST.

## Escopo da Revisão

Analise o código-fonte em `src/sentinel/`, `api/`, `scripts/` e `mcp/` verificando:

### 1. Análise estática (Bandit)
- Injections (B601–B612)
- Uso de `subprocess` sem validação (B603–B607)
- Uso de `eval()` ou `exec()` (B307)
- Credenciais hardcoded (B105–B107)
- Criptografia fraca (B303–B304)

### 2. Dependências
- Verificar se `pip-audit` identifica vulnerabilidades conhecidas
- Dependências com versões sem pino (`>=` sem teto) — risco de breaking change

### 3. API e entradas
- Validação de entrada em todos os endpoints (Pydantic schemas obrigatórios)
- Rate limiting planejado?
- Tratamento de erros não expõe stack traces em produção?

### 4. Dados
- Nenhuma PII nos logs ou fixtures de teste
- Chaves e tokens somente via variáveis de ambiente (`.env`)
- `.gitignore` cobre `data/raw/`, `models/`, `*.pkl`, `*.env`

### 5. Secrets
- Verificar histórico de commits com `git log --all` por padrões de segredos
- `.bobignore` protege arquivos sensíveis do contexto do Bob

## Output esperado

- Lista de findings com severidade (HIGH / MEDIUM / LOW)
- Para cada finding: arquivo, linha, descrição, recomendação
- Findings bloqueadores de release marcados com 🔴
- Resumo de cobertura da revisão
