.PHONY: help up down build rebuild logs logs-api logs-worker logs-db \
        restart restart-api restart-worker psql shell-api shell-worker \
        reset ps eval curl-health

help:
	@echo "Available commands:"
	@echo "  make build          - Build all images"
	@echo "  make up             - Start db, api, worker (in order)"
	@echo "  make down           - Stop everything"
	@echo "  make restart        - Restart api and worker (use after code changes)"
	@echo "  make restart-api    - Restart only api"
	@echo "  make restart-worker - Restart only worker (needed after harness/skill changes)"
	@echo "  make logs           - Tail all logs"
	@echo "  make logs-api       - Tail api logs only"
	@echo "  make logs-worker    - Tail worker logs only"
	@echo "  make logs-db        - Tail db logs only"
	@echo "  make ps             - Show running containers"
	@echo "  make psql           - Open a psql shell into the database"
	@echo "  make shell-api      - Open a bash shell inside the api container"
	@echo "  make shell-worker   - Open a bash shell inside the worker container"
	@echo "  make eval           - Run the evaluation suite"
	@echo "  make reset          - Full reset: wipes DB volume, rebuilds, restarts everything"
	@echo "  make curl-health    - Quick health check against the running api"

build:
	docker compose build

up:
	docker compose up -d db
	sleep 2
	docker compose up -d api worker
	@echo "Started. API at http://localhost:8000 — viewer at http://localhost:8000/static/viewer.html"

down:
	docker compose down

restart: restart-api restart-worker

restart-api:
	docker compose stop api
	docker compose up -d api

restart-worker:
	docker compose stop worker
	docker compose up -d worker

logs:
	docker compose logs -f

logs-api:
	docker compose logs -f api

logs-worker:
	docker compose logs -f worker

logs-db:
	docker compose logs -f db

ps:
	docker compose ps

psql:
	docker compose exec db psql -U bidharness -d bidharness

shell-api:
	docker compose exec api bash

shell-worker:
	docker compose exec worker bash

eval:
	docker compose run --rm api python -m app.eval.runner

reset:
	docker compose down -v
	docker compose build
	docker compose up -d db
	sleep 2
	docker compose up -d api worker
	@echo "Full reset complete."

curl-health:
	curl -s http://localhost:8000/health
