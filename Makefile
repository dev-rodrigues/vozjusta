.PHONY: start up down monitor-up monitor-down monitor-check synthetic-up synthetic-down synthetic-check backfill-90h backfill-history sync migrate ingest api test eval pull-models list-models web-install web-dev web-build

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
HOURS ?= 90
STEP_MINUTES ?= 5

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
	@curl -fsS -u "$(GRAFANA_ADMIN_USER):$(GRAFANA_ADMIN_PASSWORD)" "http://localhost:3000/api/dashboards/uid/vozjusta-business-v1" | jq -e '.dashboard.uid == "vozjusta-business-v1"' >/dev/null && echo "Grafana dashboard provisioning: OK" || (echo "Grafana dashboard provisioning: FAIL" && exit 1)

synthetic-up:
	@mkdir -p logs .docker-data
	@pkill -f "scripts/synthetic_metrics_exporter.py" >/dev/null 2>&1 || true
	@for i in $$(seq 1 20); do lsof -nP -iTCP:9201 -sTCP:LISTEN >/dev/null 2>&1 || break; sleep 0.2; done
	@nohup ./.venv/bin/python ./scripts/synthetic_metrics_exporter.py --host 0.0.0.0 --port 9201 --interval-seconds 5 > logs/synthetic_metrics_exporter.out 2>&1 & echo $$! > .docker-data/synthetic_metrics_exporter.pid
	@sleep 1
	@curl -fsS http://localhost:9201/metrics >/dev/null || (echo "Falha ao subir synthetic exporter. Veja logs/synthetic_metrics_exporter.out" && tail -n 40 logs/synthetic_metrics_exporter.out && exit 1)
	@echo "Synthetic exporter PID: $$(cat .docker-data/synthetic_metrics_exporter.pid)"
	@cd infra/docker && docker compose restart prometheus >/dev/null
	@echo "Prometheus reiniciado para aplicar target synthetic."

synthetic-down:
	@pkill -f "scripts/synthetic_metrics_exporter.py" >/dev/null 2>&1 || true
	@if [ -f .docker-data/synthetic_metrics_exporter.pid ]; then rm -f .docker-data/synthetic_metrics_exporter.pid; fi
	@echo "Synthetic exporter parado."

synthetic-check:
	@curl -fsS http://localhost:9201/metrics | grep -q "vozjusta_business_questions_total" && echo "Synthetic exporter: OK" || (echo "Synthetic exporter: FAIL" && exit 1)
	@ok=0; \
	for i in $$(seq 1 12); do \
		health=$$(curl -fsS http://localhost:9090/api/v1/targets | jq -r '.data.activeTargets[] | select(.labels.job=="vozjusta-synthetic") | .health' | head -n 1); \
		if [ "$$health" = "up" ]; then ok=1; break; fi; \
		sleep 5; \
	done; \
	if [ $$ok -eq 1 ]; then \
		echo "Prometheus target vozjusta-synthetic: UP"; \
	else \
		echo "Prometheus target vozjusta-synthetic: DOWN"; \
		exit 1; \
	fi

backfill-90h:
	python3 scripts/backfill_prometheus_business_history.py --hours 90 --step-minutes 5 --output-file logs/vozjusta_backfill_90h.openmetrics

backfill-history:
	python3 scripts/backfill_prometheus_business_history.py --hours "$(HOURS)" --step-minutes "$(STEP_MINUTES)" --output-file "logs/vozjusta_backfill_$(HOURS)h.openmetrics"

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

web-install:
	cd apps/web && npm install

web-dev:
	cd apps/web && npm run dev

web-build:
	cd apps/web && npm run build
