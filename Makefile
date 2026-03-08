.PHONY: start up down monitor-up monitor-down monitor-check sync migrate ingest api test eval pull-models list-models

ENV_FILE := $(if $(wildcard .env),.env,.env.example)
ifneq ("$(wildcard $(ENV_FILE))","")
include $(ENV_FILE)
export
endif

OLLAMA_DATA_DIR ?= $(or $(VOZJUSTA_OLLAMA_DATA_DIR),/Volumes/bucket/dev-rodrigues/vozjusta/.docker-data/ollama)
PROMETHEUS_DATA_DIR ?= $(or $(VOZJUSTA_PROMETHEUS_DATA_DIR),/Volumes/bucket/dev-rodrigues/vozjusta/.docker-data/prometheus)
GRAFANA_DATA_DIR ?= $(or $(VOZJUSTA_GRAFANA_DATA_DIR),/Volumes/bucket/dev-rodrigues/vozjusta/.docker-data/grafana)
GRAFANA_ADMIN_USER ?= $(or $(VOZJUSTA_GRAFANA_ADMIN_USER),admin)
GRAFANA_ADMIN_PASSWORD ?= $(or $(VOZJUSTA_GRAFANA_ADMIN_PASSWORD),admin)

start:
	./scripts/dev_start.sh

up:
	mkdir -p "$(OLLAMA_DATA_DIR)" "$(PROMETHEUS_DATA_DIR)" "$(GRAFANA_DATA_DIR)"
	cd infra/docker && VOZJUSTA_OLLAMA_DATA_DIR="$(OLLAMA_DATA_DIR)" VOZJUSTA_PROMETHEUS_DATA_DIR="$(PROMETHEUS_DATA_DIR)" VOZJUSTA_GRAFANA_DATA_DIR="$(GRAFANA_DATA_DIR)" VOZJUSTA_GRAFANA_ADMIN_USER="$(GRAFANA_ADMIN_USER)" VOZJUSTA_GRAFANA_ADMIN_PASSWORD="$(GRAFANA_ADMIN_PASSWORD)" docker compose up -d

down:
	cd infra/docker && docker compose down

monitor-up:
	mkdir -p "$(PROMETHEUS_DATA_DIR)" "$(GRAFANA_DATA_DIR)"
	cd infra/docker && VOZJUSTA_PROMETHEUS_DATA_DIR="$(PROMETHEUS_DATA_DIR)" VOZJUSTA_GRAFANA_DATA_DIR="$(GRAFANA_DATA_DIR)" VOZJUSTA_GRAFANA_ADMIN_USER="$(GRAFANA_ADMIN_USER)" VOZJUSTA_GRAFANA_ADMIN_PASSWORD="$(GRAFANA_ADMIN_PASSWORD)" docker compose up -d prometheus grafana

monitor-down:
	cd infra/docker && docker compose stop prometheus grafana

monitor-check:
	@curl -fsS http://localhost:8000/metrics | grep -q "vozjusta_business_kb_last_success_unixtime" && echo "API metrics: OK" || (echo "API metrics: FAIL" && exit 1)
	@curl -fsS http://localhost:9090/-/ready >/dev/null && echo "Prometheus ready: OK" || (echo "Prometheus ready: FAIL" && exit 1)
	@curl -fsS http://localhost:9090/api/v1/targets | python3 -c 'import json,sys; data=json.load(sys.stdin); targets=[t for t in data.get("data",{}).get("activeTargets",[]) if t.get("labels",{}).get("job")=="vozjusta-api"]; ok=any(t.get("health")=="up" for t in targets); print("Prometheus target vozjusta-api: UP" if ok else "Prometheus target vozjusta-api: DOWN"); raise SystemExit(0 if ok else 1)'
	@curl -fsS http://localhost:3000/api/health >/dev/null && echo "Grafana health: OK" || (echo "Grafana health: FAIL" && exit 1)
	@curl -fsS -u "$(GRAFANA_ADMIN_USER):$(GRAFANA_ADMIN_PASSWORD)" "http://localhost:3000/api/search?query=vozjusta-business-v1" | grep -q "vozjusta-business-v1" && echo "Grafana dashboard provisioning: OK" || (echo "Grafana dashboard provisioning: FAIL" && exit 1)

sync:
	uv sync --all-packages --dev

migrate:
	uv run --package vozjusta-api alembic -c apps/api/alembic.ini upgrade head

ingest:
	uv run --package vozjusta-ingest vozjusta-ingest run --path knowledge_base/raw

api:
	uv run --package vozjusta-api vozjusta-api

test:
	uv run pytest

eval:
	uv run --package vozjusta-eval vozjusta-eval run

pull-models:
	@if [ "$(VOZJUSTA_USE_HOST_OLLAMA)" = "true" ]; then \
		if command -v ollama >/dev/null 2>&1; then \
			ollama pull llama3.1:8b && ollama pull nomic-embed-text; \
		elif [ -x "/Applications/Ollama.app/Contents/Resources/ollama" ]; then \
			/Applications/Ollama.app/Contents/Resources/ollama pull llama3.1:8b && /Applications/Ollama.app/Contents/Resources/ollama pull nomic-embed-text; \
		else \
			echo "Ollama local não encontrado. Instale o app Ollama."; \
			exit 1; \
		fi \
	else \
		docker exec vozjusta-ollama ollama pull llama3.1:8b && docker exec vozjusta-ollama ollama pull nomic-embed-text; \
	fi

list-models:
	@if [ "$(VOZJUSTA_USE_HOST_OLLAMA)" = "true" ]; then \
		if command -v ollama >/dev/null 2>&1; then \
			ollama list; \
		elif [ -x "/Applications/Ollama.app/Contents/Resources/ollama" ]; then \
			/Applications/Ollama.app/Contents/Resources/ollama list; \
		else \
			echo "Ollama local não encontrado. Instale o app Ollama."; \
			exit 1; \
		fi \
	else \
		docker exec vozjusta-ollama ollama list; \
	fi
