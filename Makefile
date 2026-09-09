.PHONY: up down build logs logs-api logs-worker restart-worker restart-api psql shell-api reset test-skill

# Build all images
build:
	docker compose build

# Start everything in the background, in the right order
up:
	docker compose up -d db
	sleep 2
	docker compose up -d api worker

# Stop everything
down:
	docker compose down

# Full reset — wipes the database volume too (careful: destroys all data)
reset:
	docker compose down -v
	docker compose build
	docker compose up -d db
	sleep 2
	docker compose up -d api worker

# Tail logs from everything
logs:
	docker compose logs -f

# Tail just the api
logs-api:
	docker compose logs -f api

# Tail just the worker
logs-worker:
	docker compose logs -f worker

# Restart worker only (needed after code changes, since it has no auto-reload)
restart-worker:
	docker compose stop worker
	docker compose up -d worker

# Restart api only (usually unnecessary — it auto-reloads — but here for symmetry)
restart-api:
	docker compose stop api
	docker compose up -d api

# Open a psql shell into the database
psql:
	docker compose exec db psql -U bidharness -d bidharness

# Open a shell inside the api container
shell-api:
	docker compose exec api bash

## Running the evaluation suite
run:
	docker compose run --rm api python -m app.eval.runner
