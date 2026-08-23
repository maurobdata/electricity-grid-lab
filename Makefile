# Grid Lab
#
# `make up` is the one command. Everything else is optional.
#
# Recipes use `>` instead of a leading tab (.RECIPEPREFIX). Tabs in Makefiles are a
# well-known source of invisible breakage, and this repo is edited from Windows.

.RECIPEPREFIX = >
SHELL := /bin/sh
COMPOSE := docker compose
API := $(COMPOSE) run --rm --no-deps -T api

# Git Bash on Windows rewrites container-side absolute paths ("/out" becomes
# "C:/Program Files/Git/out") unless path conversion is switched off.
NOCONV := MSYS_NO_PATHCONV=1

.DEFAULT_GOAL := help

.PHONY: help up down logs restart build web pwa test lint fmt probe record scenario scenario-live demo eval shell clean

help:  ## Show this help
> @grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
>   | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-10s\033[0m %s\n",$$1,$$2}'

up: .env  ## Start everything (replay mode -- no API key or network needed)
> $(COMPOSE) up --build -d
> @echo ""
> @echo "  API    http://localhost:8000/docs"
> @echo "  Agent  http://localhost:8001/docs"
> @echo ""

down:  ## Stop everything
> $(COMPOSE) down

logs:  ## Tail logs
> $(COMPOSE) logs -f --tail=100

restart: down up  ## Restart

build:  ## Rebuild images
> $(COMPOSE) build

web: .env  ## Start the PWA as well (API + agent must be up)
> $(COMPOSE) --profile web up --build -d web
> @echo ""
> @echo "  PWA    http://localhost:5173"
> @echo "  API    http://localhost:8000/docs"
> @echo ""

pwa: web  ## Alias for web

test:  ## Run the offline test suite (no network, no key)
> $(API) pytest -q

lint:  ## Ruff check + mypy --strict, and the web typecheck
> $(API) sh -c "ruff check src tests && ruff format --check src tests && mypy src"
> $(COMPOSE) --profile web run --rm --no-deps -T web npx tsc -b

fmt:  ## Format and auto-fix
> $(API) sh -c "ruff check --fix src tests; ruff format src tests"

# Writes into data/, which the api container mounts, so /api/v1/capabilities can serve the
# result. Writing it to the repository root left the endpoint permanently reporting that no
# probe had been run.
probe: .env  ## Ask a real token what it can actually reach -> data/capabilities.json
> $(NOCONV) $(COMPOSE) run --rm --no-deps -T \
>   --volume "$(CURDIR)/data":/out api \
>   python -m gridlab.scripts.probe_capabilities --out /out/capabilities.json

record: .env  ## Record raw Electricity Maps responses into fixtures/
> $(NOCONV) $(COMPOSE) run --rm --no-deps -T \
>   --volume "$(CURDIR)/fixtures":/out api \
>   python -m gridlab.scripts.record_fixtures --out /out

scenario:  ## Regenerate the bundled (synthetic) replay scenarios
> $(NOCONV) $(COMPOSE) run --rm --no-deps -T \
>   --volume "$(CURDIR)/scenarios":/out api \
>   python -m gridlab.scripts.make_scenario --out /out

# ZONES and GRAN are overridable: `make scenario-live ZONES=DK-DK2,DE,PL GRAN=15_minutes`
ZONES ?= DK-DK2,DE
GRAN  ?= hourly

scenario-live: .env  ## Record a REAL scenario from the live API into scenarios/
> $(NOCONV) $(COMPOSE) run --rm --no-deps -T \
>   --volume "$(CURDIR)/scenarios":/out api \
>   python -m gridlab.scripts.make_scenario --from-live --out /out \
>     --zones "$(ZONES)" --granularity "$(GRAN)"

demo:  ## Walk the current scenario and narrate it in the terminal
> $(COMPOSE) exec -T api python -m gridlab.scripts.demo $(ARGS)

# ARGS passes through: `make eval ARGS=--offline` checks the committed examples with no
# key; `make eval ARGS="--judge"` adds the LLM judge; `make eval ARGS=--align` scores the
# judge itself against the hand-labelled set.
eval:  ## Run agent evaluations (ARGS=--offline for the no-key path)
> $(COMPOSE) run --rm --no-deps -T api python -m gridlab.agent.evals.run $(ARGS)

shell:  ## Shell into the api container
> $(COMPOSE) run --rm --no-deps api /bin/bash

clean:  ## Remove containers, volumes and local caches
> $(COMPOSE) down -v --remove-orphans
> find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true

.env:
> @test -f .env || (cp .env.example .env && echo "Created .env from .env.example")
