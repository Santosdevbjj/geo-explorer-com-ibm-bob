# Frontend — Dashboard Sentinel

Interface web do Sentinel construída com **Next.js 14**, **TypeScript** e **Tailwind CSS**, hospedada na Vercel.

## Páginas

| Rota           | Componente                 | Descrição                                    |
| -------------- | -------------------------- | -------------------------------------------- |
| `/`            | `app/page.tsx`             | Lista de alertas da sessão atual             |
| `/alerts/[id]` | `app/alerts/[id]/page.tsx` | Detalhe do alerta: sinais, score, limitações |
| `/metrics`     | `app/metrics/page.tsx`     | Relatório de avaliação do modelo             |

## Estrutura

```
frontend/
├── app/
│   ├── layout.tsx              ← layout global (header, footer)
│   ├── globals.css             ← Tailwind base
│   ├── page.tsx                ← lista de alertas
│   ├── not-found.tsx           ← 404 personalizado
│   ├── alerts/[id]/page.tsx    ← detalhe do alerta
│   └── metrics/page.tsx        ← métricas do modelo
├── components/
│   ├── AlertCard.tsx           ← card de alerta na lista
│   ├── CategoryBadge.tsx       ← badge de categoria
│   ├── PriorityBadge.tsx       ← badge de prioridade
│   ├── SignalBar.tsx           ← barra de contribuição de sinal
│   └── StatusBadge.tsx         ← indicador API online/offline
├── lib/
│   ├── api.ts                  ← funções fetch tipadas para a API Sentinel
│   └── types.ts                ← tipos TypeScript espelhando schemas Pydantic
├── package.json
├── tsconfig.json
├── tailwind.config.js
├── next.config.js
└── postcss.config.js
```

## Desenvolvimento local

### Pré-requisitos

- Node.js 20+
- API Sentinel rodando em `http://localhost:8000`

### Instalação

```bash
cd frontend
npm install

# Configure a URL da API
# Crie um arquivo .env.local com:
# NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Iniciar

```bash
# 1. Inicie a API Python (na raiz do projeto)
uvicorn api.index:app --reload

# 2. Inicie o frontend (em frontend/)
npm run dev
# → http://localhost:3000
```

### Build de produção

```bash
npm run build
npm run start
```

### Verificações

```bash
npm run type-check   # TypeScript sem erros
npm run lint         # ESLint
npm run build        # build completo
```

## Variáveis de ambiente

| Variável              | Padrão                  | Descrição                                                |
| --------------------- | ----------------------- | -------------------------------------------------------- |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | URL base da API Sentinel                                 |
| `NEXT_PUBLIC_API_KEY` | `""`                    | Chave de API para endpoints protegidos (opcional em dev) |

Crie `.env.local` na pasta `frontend/` com os valores reais. **Nunca comite `.env.local`.**

## Deploy na Vercel

O deploy é configurado pelo [`vercel.json`](../vercel.json) na raiz do projeto.
O frontend é servido como app Next.js e a API Python como Serverless Function.

**Limitação importante:** alertas não persistem entre reinicializações da API Serverless.
Ver [`docs/decisions/ADR-006-deploy-vercel.md`](../docs/decisions/ADR-006-deploy-vercel.md).
