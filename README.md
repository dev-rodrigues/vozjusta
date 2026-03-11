# VozJusta Monorepo (V1)

Monorepo Python para um RAG jurídico local com FastAPI + PostgreSQL/pgvector + Ollama.

## Links do Projeto

- Repositorio da aplicacao: https://github.com/dev-rodrigues/vozjusta
- Pull Request principal: https://github.com/dev-rodrigues/vozjusta/pull/1
- Capturas do dashboard Grafana: [img.png](docs/img.png)
## Estrutura

- `apps/api`: API FastAPI
- `apps/ingest`: CLI de ingestão (`vozjusta-ingest run`)
- `apps/eval`: avaliação com perguntas de aceitação
- `apps/web`: SPA pública de chat (React + Vite + motion + React Query + shadcn/ui)
- `packages/rag_core`: utilitários de chunking, prompt e guardrails
- `packages/legal_kb`: ingestão, modelos e persistência da base jurídica
- `infra/docker`: ambiente Docker (Postgres + Ollama + Prometheus + Grafana)
- `infra/monitoring`: configurações de scrape, provisioning e dashboard Grafana
- `knowledge_base/raw`: documentos jurídicos curados

## Requisitos

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Node.js 20+ e npm
- Docker + Docker Compose

## Inicialização Em Um Comando

Rode:

```bash
make start
```

Esse comando faz bootstrap automático:

- cria `.env` (a partir de `.env.example`) se ainda não existir;
- sobe infraestrutura necessária (`postgres`, `prometheus`, `grafana`);
- usa Ollama nativo no macOS por padrão (`VOZJUSTA_USE_HOST_OLLAMA=true`) para aproveitar GPU/Metal;
- garante modelos no Ollama (`llama3.1:8b` e `nomic-embed-text`);
- aplica migrações;
- executa ingestão inicial apenas se a base estiver vazia;
- inicia a API já pronta em `http://localhost:8000/swagger`;
- inicia também o frontend React em `http://localhost:5173` (logs em `logs/web-dev.log`).

Use `Ctrl+C` no terminal do `make start` para encerrar API e frontend juntos.

Para parar containers depois, use:

```bash
make down
```

## Subir infraestrutura

```bash
make up
```

Depois de subir, confirme/baixe os modelos:

```bash
make pull-models
make list-models
```

Por padrão, os modelos do Ollama ficam em `VOZJUSTA_OLLAMA_DATA_DIR`:

- `/Volumes/bucket/dev-rodrigues/vozjusta/.docker-data/ollama`

Você pode trocar o caminho (ainda dentro de `/Volumes/bucket`) assim:

```bash
VOZJUSTA_OLLAMA_DATA_DIR=/Volumes/bucket/seu-diretorio/ollama-models make up
```

No `make up`, os dados de monitoramento também ficam em bind mounts no bucket:

- `VOZJUSTA_PROMETHEUS_DATA_DIR` (default: `/Volumes/bucket/dev-rodrigues/vozjusta/.docker-data/prometheus`)
- `VOZJUSTA_GRAFANA_DATA_DIR` (default: `/Volumes/bucket/dev-rodrigues/vozjusta/.docker-data/grafana`)

## Variáveis de ambiente

A API e a CLI de ingestão carregam automaticamente variáveis da raiz do projeto nesta ordem:

1. `.env` (se existir)
2. `.env.example` (fallback automático)

1. Copie o exemplo:

```bash
cp .env.example .env
```

2. Edite os valores no `.env`.

Use prefixo `VOZJUSTA_` para configurar:

- `VOZJUSTA_DATABASE_URL` (default: `postgresql+psycopg://vozjusta:vozjusta@localhost:5432/vozjusta`)
- `VOZJUSTA_OLLAMA_BASE_URL` (default: `http://localhost:11434`)
- `VOZJUSTA_OLLAMA_CHAT_MODEL` (default: `llama3.1:8b`)
- `VOZJUSTA_OLLAMA_EMBEDDING_MODEL` (default: `nomic-embed-text`)
- `VOZJUSTA_OLLAMA_TIMEOUT_SECONDS` (default: `300`)
- `VOZJUSTA_OLLAMA_NUM_PREDICT` (default: `96`)
- `VOZJUSTA_OLLAMA_NUM_CTX` (default: `1024`)
- `VOZJUSTA_OLLAMA_KEEP_ALIVE` (default: `30m`)
- `VOZJUSTA_USE_HOST_OLLAMA` (default: `true` no macOS, `false` fora do macOS)
- `VOZJUSTA_BOOTSTRAP_MODELS` (default: `true`)
- `VOZJUSTA_OLLAMA_DATA_DIR` (default: `/Volumes/bucket/dev-rodrigues/vozjusta/.docker-data/ollama`)
- `VOZJUSTA_PROMETHEUS_DATA_DIR` (default: `/Volumes/bucket/dev-rodrigues/vozjusta/.docker-data/prometheus`)
- `VOZJUSTA_GRAFANA_DATA_DIR` (default: `/Volumes/bucket/dev-rodrigues/vozjusta/.docker-data/grafana`)
- `VOZJUSTA_GRAFANA_ADMIN_USER` (default: `admin`)
- `VOZJUSTA_GRAFANA_ADMIN_PASSWORD` (default: `admin`)
- `VOZJUSTA_ADMIN_TOKEN` (default: `trocar-token-admin`)
- `VOZJUSTA_RAG_RETRIEVE_TOP_K` (default: `4`)
- `VOZJUSTA_RAG_CONTEXT_TOP_K` (default: `1`)
- `VOZJUSTA_RAG_CONTEXT_EXCERPT_MAX_CHARS` (default: `320`)
- `VOZJUSTA_ASK_CACHE_TTL_SECONDS` (default: `600`)
- `VOZJUSTA_ASK_CACHE_MAX_ITEMS` (default: `256`)
- `VOZJUSTA_CORS_ALLOWED_ORIGINS` (default: `http://localhost:5173`, aceita lista separada por vírgula)
- `VOZJUSTA_AUTO_INGEST_ON_START` (default: `true`)
- `VOZJUSTA_INGEST_PATH` (default: `knowledge_base/raw`)

## Instalação

```bash
cd /path/to/vozjusta
uv sync --all-packages --dev
```

Se houver erro de execução de script (ex.: `Failed to spawn`), rode `uv sync --all-packages --dev` novamente para recriar os entrypoints do workspace.

## Migrações

```bash
uv run --package vozjusta-api alembic -c apps/api/alembic.ini upgrade head
```

## Ingestão de documentos

```bash
uv run --package vozjusta-ingest vozjusta-ingest run --path knowledge_base/raw
```

Se aparecer erro de modelo não encontrado no Ollama, rode:

```bash
make pull-models
```

## API

```bash
uv run --package vozjusta-api vozjusta-api
```

## SPA Web (Chat Público)

A aplicação web está em `apps/web` e consome `POST /api/v1/ask`.

1. Instale dependências:

```bash
make web-install
```

2. Suba a API (terminal 1):

```bash
make api
```

3. Suba a SPA (terminal 2):

```bash
make web-dev
```

4. Abra `http://localhost:5173`.

Build de produção:

```bash
make web-build
```

Variável de ambiente do frontend (`apps/web/.env.example`):

- `VITE_API_BASE_URL` (default: `http://localhost:8000`)
- `VITE_API_TIMEOUT_MS` (default: `180000`)

### Endpoints principais

- `POST /api/v1/ask`
- `POST /api/v1/admin/ingest/run` (header `X-Admin-Token`)
- `GET /api/v1/sources`
- `GET /api/v1/health`
- `GET /metrics`

## Monitoramento (Prometheus + Grafana)

Com a API rodando no host (`uv run --package vozjusta-api vozjusta-api`), suba o monitoramento:

```bash
make monitor-up
```

URLs locais:

- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000` (default `admin/admin`)
- Dashboard provisionado: `VozJusta - Negócio V1`

Validação rápida:

```bash
make monitor-check
```

Retenção de histórico:

- Prometheus configurado com retenção explícita de `240h` (10 dias), cobrindo com folga a necessidade de `50h`.
- O TSDB fica persistido em `.docker-data/prometheus` (bind mount no bucket).
- Evite comandos destrutivos como `docker compose down -v`, pois removem volumes/dados.
- Você pode ajustar a retenção pelo `.env` via `VOZJUSTA_PROMETHEUS_RETENTION_TIME` (ex.: `240h`, `336h`).
- No dashboard de negócio, os painéis de distribuição/cobertura usam janela fixa de `50h`, então mesmo se a URL abrir com outro range (ex.: `from=now-3h`) eles continuam mostrando o histórico das últimas 50 horas.

Para desligar apenas monitoramento:

```bash
make monitor-down
```

### Documentação Swagger

- Swagger UI: `GET /swagger`
- ReDoc: `GET /redoc`
- OpenAPI JSON: `GET /openapi.json`

Exemplo rápido:

```bash
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"O que fazer em caso de discriminação racial no trabalho?"}'
```

## Testes

```bash
uv run pytest
```

Para testes de integração com banco real, use um banco dedicado:

```bash
export VOZJUSTA_TEST_DATABASE_URL='postgresql+psycopg://vozjusta:vozjusta@localhost:5432/vozjusta_test'
uv run pytest -m integration
```
