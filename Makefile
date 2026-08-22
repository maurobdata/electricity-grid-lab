# Grid Lab
# `make up` is the one command. Everything else is optional.

SHELL := /bin/sh
COMPOSE := docker compose
API := $(COMPOSE) run --rm --no-deps -T api

.DEFAULT_GOAL := help

.PHONY: help up down logs restart build test lint fmt probe record demo eval shell clean

help:  ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-10s\033[0m %s\n",$$1,$$2}'

up: .env  ## Start everything (replay mode, no API key needed)
	$(COMPOSE) up --build -d
	@echo ""
	@echo "  PWA    http://localhost:5173"
	@echo "  API    http://localhost:8000/docs"
	@echo "  Agent  http://localhost:8001/docs"
	@echo ""

down:  ## Stop everything
	$(COMPOSE) down

logs:  ## Tail logs
	$(COMPOSE) logs -f --tail=100

restart: down up  ## Restart

build:  ## Rebuild images
	$(COMPOSE) build

test:  ## Run the offline test suite (no network, no key)
	$(API) pytest -q

lint:  ## Ruff check + mypy
	$(API) ruff check src tests
	$(API) mypy src

fmt:  ## Format
	$(API) ruff format src tests
	$(API) ruff check --fix src tests

probe: .env  ## Ask a real token what it can actually reach -> capabilities.json
	$(COMPOSE) run --rm --no-deps -T -v "$(CURDIR)":/out api \
		python -m gridlab.scripts.probe_capabilities --out /out/capabilities.json

record: .env  ## Record raw Electricity Maps responses into fixtures/
	$(COMPOSE) run --rm --no-deps -T -v "$(CURDIR)/fixtures":/out api \
		python -m gridlab.scripts.record_fixtures --out /out

demo:  ## Play the default scenario at speed
	$(COMPOSE) exec api python -m gridlab.scripts.demo

eval:  ## Run agent evaluations
	$(COMPOSE) run --rm -T agent python -m gridlab.agent.evals.run

shell:  ## Shell into the api container
	$(COMPOSE) run --rm --no-deps api /bin/bash

clean:  ## Remove containers, volumes and local caches
	$(COMPOSE) down -v --remove-orphans
	find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true

.env:
	@test -f .env || (cp .env.example .env && echo "Created .env from .env.example")
