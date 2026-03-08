#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

log() {
  printf '[vozjusta-start] %s\n' "$*"
}

fail() {
  printf '[vozjusta-start] ERRO: %s\n' "$*" >&2
  exit 1
}

to_lower() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]'
}

is_true() {
  case "$(to_lower "$1")" in
    1|true|yes|on) return 0 ;;
    *) return 1 ;;
  esac
}

wait_http() {
  local url="$1"
  local label="$2"
  local timeout_seconds="${3:-180}"
  local deadline=$((SECONDS + timeout_seconds))

  while [ "$SECONDS" -lt "$deadline" ]; do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done

  fail "Timeout aguardando ${label} em ${url}."
}

ensure_env_file_and_load() {
  if [ ! -f "$ROOT_DIR/.env" ]; then
    cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
    log "Arquivo .env criado automaticamente a partir de .env.example"
  fi

  local original_vozjusta_env
  original_vozjusta_env="$(env | grep '^VOZJUSTA_' || true)"

  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a

  if [ -n "$original_vozjusta_env" ]; then
    while IFS= read -r line; do
      [ -z "$line" ] && continue
      case "$line" in
        VOZJUSTA_*=*)
          export "$line"
          ;;
      esac
    done <<EOF
$original_vozjusta_env
EOF
  fi

  : "${VOZJUSTA_DATABASE_URL:=postgresql+psycopg://vozjusta:vozjusta@localhost:5432/vozjusta}"
  : "${VOZJUSTA_HOST:=0.0.0.0}"
  : "${VOZJUSTA_PORT:=8000}"
  : "${VOZJUSTA_OLLAMA_BASE_URL:=http://localhost:11434}"
  : "${VOZJUSTA_OLLAMA_CHAT_MODEL:=llama3.1:8b}"
  : "${VOZJUSTA_OLLAMA_EMBEDDING_MODEL:=nomic-embed-text}"
  : "${VOZJUSTA_OLLAMA_DATA_DIR:=${ROOT_DIR}/.docker-data/ollama}"
  : "${VOZJUSTA_PROMETHEUS_DATA_DIR:=${ROOT_DIR}/.docker-data/prometheus}"
  : "${VOZJUSTA_GRAFANA_DATA_DIR:=${ROOT_DIR}/.docker-data/grafana}"
  : "${VOZJUSTA_GRAFANA_ADMIN_USER:=admin}"
  : "${VOZJUSTA_GRAFANA_ADMIN_PASSWORD:=admin}"
  : "${VOZJUSTA_INGEST_PATH:=knowledge_base/raw}"
  : "${VOZJUSTA_BOOTSTRAP_MODELS:=true}"
  : "${VOZJUSTA_AUTO_INGEST_ON_START:=true}"

  local default_use_host_ollama="false"
  if [ "$(uname -s)" = "Darwin" ]; then
    default_use_host_ollama="true"
  fi
  : "${VOZJUSTA_USE_HOST_OLLAMA:=${default_use_host_ollama}}"

  export \
    VOZJUSTA_DATABASE_URL \
    VOZJUSTA_HOST \
    VOZJUSTA_PORT \
    VOZJUSTA_OLLAMA_BASE_URL \
    VOZJUSTA_OLLAMA_CHAT_MODEL \
    VOZJUSTA_OLLAMA_EMBEDDING_MODEL \
    VOZJUSTA_OLLAMA_DATA_DIR \
    VOZJUSTA_PROMETHEUS_DATA_DIR \
    VOZJUSTA_GRAFANA_DATA_DIR \
    VOZJUSTA_GRAFANA_ADMIN_USER \
    VOZJUSTA_GRAFANA_ADMIN_PASSWORD \
    VOZJUSTA_INGEST_PATH \
    VOZJUSTA_BOOTSTRAP_MODELS \
    VOZJUSTA_AUTO_INGEST_ON_START \
    VOZJUSTA_USE_HOST_OLLAMA
}

ensure_runtime_tools() {
  if [ ! -x "$ROOT_DIR/.venv/bin/vozjusta-api" ] || [ ! -x "$ROOT_DIR/.venv/bin/vozjusta-ingest" ] || [ ! -x "$ROOT_DIR/.venv/bin/alembic" ]; then
    if command -v uv >/dev/null 2>&1; then
      log "Instalando dependências com uv..."
      uv sync --all-packages --dev
    else
      fail "Dependências não encontradas na .venv e 'uv' não está no PATH. Execute: uv sync --all-packages --dev"
    fi
  fi
}

run_compose_infra() {
  mkdir -p "$VOZJUSTA_OLLAMA_DATA_DIR" "$VOZJUSTA_PROMETHEUS_DATA_DIR" "$VOZJUSTA_GRAFANA_DATA_DIR"

  log "Subindo infraestrutura Docker (postgres, prometheus, grafana)..."
  (
    cd "$ROOT_DIR/infra/docker"
    if is_true "$VOZJUSTA_USE_HOST_OLLAMA"; then
      docker compose stop ollama ollama-init >/dev/null 2>&1 || true
      VOZJUSTA_OLLAMA_DATA_DIR="$VOZJUSTA_OLLAMA_DATA_DIR" \
      VOZJUSTA_PROMETHEUS_DATA_DIR="$VOZJUSTA_PROMETHEUS_DATA_DIR" \
      VOZJUSTA_GRAFANA_DATA_DIR="$VOZJUSTA_GRAFANA_DATA_DIR" \
      VOZJUSTA_GRAFANA_ADMIN_USER="$VOZJUSTA_GRAFANA_ADMIN_USER" \
      VOZJUSTA_GRAFANA_ADMIN_PASSWORD="$VOZJUSTA_GRAFANA_ADMIN_PASSWORD" \
      docker compose up -d postgres prometheus grafana
    else
      VOZJUSTA_OLLAMA_DATA_DIR="$VOZJUSTA_OLLAMA_DATA_DIR" \
      VOZJUSTA_PROMETHEUS_DATA_DIR="$VOZJUSTA_PROMETHEUS_DATA_DIR" \
      VOZJUSTA_GRAFANA_DATA_DIR="$VOZJUSTA_GRAFANA_DATA_DIR" \
      VOZJUSTA_GRAFANA_ADMIN_USER="$VOZJUSTA_GRAFANA_ADMIN_USER" \
      VOZJUSTA_GRAFANA_ADMIN_PASSWORD="$VOZJUSTA_GRAFANA_ADMIN_PASSWORD" \
      docker compose up -d postgres ollama ollama-init prometheus grafana
    fi
  )
}

wait_postgres() {
  log "Aguardando PostgreSQL ficar pronto..."
  local deadline=$((SECONDS + 120))
  while [ "$SECONDS" -lt "$deadline" ]; do
    if docker exec vozjusta-postgres pg_isready -U vozjusta -d vozjusta >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  fail "PostgreSQL não ficou pronto a tempo."
}

start_docker_ollama() {
  log "Subindo Ollama em Docker (fallback CPU)..."
  (
    cd "$ROOT_DIR/infra/docker"
    VOZJUSTA_OLLAMA_DATA_DIR="$VOZJUSTA_OLLAMA_DATA_DIR" \
    VOZJUSTA_PROMETHEUS_DATA_DIR="$VOZJUSTA_PROMETHEUS_DATA_DIR" \
    VOZJUSTA_GRAFANA_DATA_DIR="$VOZJUSTA_GRAFANA_DATA_DIR" \
    VOZJUSTA_GRAFANA_ADMIN_USER="$VOZJUSTA_GRAFANA_ADMIN_USER" \
    VOZJUSTA_GRAFANA_ADMIN_PASSWORD="$VOZJUSTA_GRAFANA_ADMIN_PASSWORD" \
    docker compose up -d ollama ollama-init
  )
}

resolve_ollama_bin() {
  if command -v ollama >/dev/null 2>&1; then
    command -v ollama
    return 0
  fi

  if [ -x "/Applications/Ollama.app/Contents/Resources/ollama" ]; then
    printf '/Applications/Ollama.app/Contents/Resources/ollama\n'
    return 0
  fi

  return 1
}

ensure_ollama_up() {
  local tags_url="${VOZJUSTA_OLLAMA_BASE_URL%/}/api/tags"

  if curl -fsS "$tags_url" >/dev/null 2>&1; then
    log "Ollama disponível em ${VOZJUSTA_OLLAMA_BASE_URL}"
    return 0
  fi

  if is_true "$VOZJUSTA_USE_HOST_OLLAMA"; then
    case "$VOZJUSTA_OLLAMA_BASE_URL" in
      http://localhost:*|http://127.0.0.1:*|https://localhost:*|https://127.0.0.1:*) ;;
      *) fail "VOZJUSTA_USE_HOST_OLLAMA=true exige VOZJUSTA_OLLAMA_BASE_URL local (localhost/127.0.0.1)." ;;
    esac

    local ollama_bin
    if ! ollama_bin="$(resolve_ollama_bin)"; then
      log "Ollama local não encontrado. Usando fallback para Docker (CPU)."
      start_docker_ollama
      wait_http "$tags_url" "Ollama (Docker fallback)" 180
      VOZJUSTA_USE_HOST_OLLAMA="false"
      export VOZJUSTA_USE_HOST_OLLAMA
      return 0
    fi

    log "Iniciando Ollama nativo (${ollama_bin})..."
    nohup "$ollama_bin" serve >/tmp/vozjusta-ollama.log 2>&1 &
    wait_http "$tags_url" "Ollama nativo" 180
    return 0
  fi

  wait_http "$tags_url" "Ollama (Docker)" 180
}

model_exists() {
  local model="$1"
  python3 - "$VOZJUSTA_OLLAMA_BASE_URL" "$model" <<'PY'
import json
import sys
import urllib.error
import urllib.request

base_url = sys.argv[1].rstrip('/')
requested_model = sys.argv[2]

try:
    with urllib.request.urlopen(f"{base_url}/api/tags", timeout=20) as response:
        payload = json.load(response)
except Exception:
    print("0")
    raise SystemExit(0)

models = payload.get("models", [])
model_names = [item.get("name", "") for item in models if isinstance(item, dict)]
has_tag = ":" in requested_model

found = False
for name in model_names:
    if not isinstance(name, str):
        continue
    if name == requested_model:
        found = True
        break
    if not has_tag and name.startswith(requested_model + ":"):
        found = True
        break

print("1" if found else "0")
PY
}

pull_model_if_missing() {
  local model="$1"

  if [ "$(model_exists "$model")" = "1" ]; then
    log "Modelo já disponível: ${model}"
    return 0
  fi

  log "Baixando modelo Ollama: ${model}"
  curl -fsS "${VOZJUSTA_OLLAMA_BASE_URL%/}/api/pull" \
    -H "Content-Type: application/json" \
    -d "{\"model\":\"${model}\",\"stream\":false}" >/dev/null
}

ensure_models() {
  if ! is_true "$VOZJUSTA_BOOTSTRAP_MODELS"; then
    log "Bootstrap de modelos desativado (VOZJUSTA_BOOTSTRAP_MODELS=false)"
    return 0
  fi

  pull_model_if_missing "$VOZJUSTA_OLLAMA_CHAT_MODEL"
  pull_model_if_missing "$VOZJUSTA_OLLAMA_EMBEDDING_MODEL"
}

run_migrations() {
  log "Aplicando migrações Alembic..."
  "$ROOT_DIR/.venv/bin/alembic" -c "$ROOT_DIR/apps/api/alembic.ini" upgrade head
}

count_sources() {
  "$ROOT_DIR/.venv/bin/python" - <<'PY'
import os
from sqlalchemy import create_engine, text

database_url = os.environ["VOZJUSTA_DATABASE_URL"]
engine = create_engine(database_url)

try:
    with engine.connect() as connection:
        count = connection.execute(text("SELECT COUNT(1) FROM sources")).scalar_one()
except Exception:
    count = 0

print(int(count or 0))
PY
}

run_ingestion_if_needed() {
  if ! is_true "$VOZJUSTA_AUTO_INGEST_ON_START"; then
    log "Ingestão automática desativada (VOZJUSTA_AUTO_INGEST_ON_START=false)"
    return 0
  fi

  local sources_count
  sources_count="$(count_sources)"

  if [ "$sources_count" -gt 0 ]; then
    log "Base jurídica já populada (${sources_count} fontes). Pulando ingestão inicial."
    return 0
  fi

  log "Executando ingestão inicial em ${VOZJUSTA_INGEST_PATH}..."
  "$ROOT_DIR/.venv/bin/vozjusta-ingest" run --path "$VOZJUSTA_INGEST_PATH"
}

print_summary() {
  log "Stack pronta. URLs:"
  log "- API/Swagger: http://localhost:${VOZJUSTA_PORT}/swagger"
  log "- Prometheus: http://localhost:9090"
  log "- Grafana: http://localhost:3000 (admin/admin por padrão)"
}

start_api() {
  print_summary
  log "Iniciando API (Ctrl+C para parar a API)..."
  exec "$ROOT_DIR/.venv/bin/vozjusta-api"
}

main() {
  ensure_env_file_and_load
  ensure_runtime_tools
  run_compose_infra
  wait_postgres
  ensure_ollama_up
  ensure_models
  run_migrations
  run_ingestion_if_needed
  start_api
}

main "$@"
