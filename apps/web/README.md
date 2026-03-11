# VozJusta Web

SPA pública do chat RAG do VozJusta construída com:

- React + Vite + TypeScript
- motion
- axios
- @tanstack/react-query
- shadcn/ui + Tailwind CSS

## Rodando localmente

```bash
npm install
npm run dev
```

Acesse `http://localhost:5173`.

## Variáveis de ambiente

Crie `.env` com base em `.env.example`:

```bash
cp .env.example .env
```

- `VITE_API_BASE_URL` (default: `http://localhost:8000`)
- `VITE_API_TIMEOUT_MS` (default: `180000`)

## Qualidade

```bash
npm run typecheck
npm run build
```
