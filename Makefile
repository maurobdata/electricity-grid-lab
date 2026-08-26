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

.PHONY: help up down logs restart build web pwa preview test lint fmt probe record scenario scenario-live record-daily recordings archive-init atlas demo eval shell clean

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

# The dev server deliberately does not register a service worker -- it would fight hot
# reload -- so `make web` cannot show you the installed-app behaviour. This builds the PWA
# and serves it the way a browser would really receive it.
preview:  ## Build the PWA and serve it like production (service worker active), :4173
> $(COMPOSE) --profile web run --rm --no-deps -p 4173:4173 web sh -c "npm run build && npx vite preview --host 0.0.0.0 --port 4173"

test:  ## Run the offline test suite (no network, no key) -- API and web
> $(API) pytest -q
> $(COMPOSE) --profile web run --rm --no-deps -T web npm test

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

# Into the archive, not the repository: raw API responses are Electricity Maps data and
# their terms do not permit publishing it (ADR 0013). The container still sees them at
# /app/fixtures, so nothing above this line changed.
record: .env  ## Record raw Electricity Maps responses into recordings/fixtures/
> $(NOCONV) $(COMPOSE) run --rm --no-deps -T \
>   --volume "$(CURDIR)/recordings/fixtures":/out api \
>   python -m gridlab.scripts.record_fixtures --out /out

scenario:  ## Regenerate the bundled (synthetic) replay scenarios
> $(NOCONV) $(COMPOSE) run --rm --no-deps -T \
>   --volume "$(CURDIR)/scenarios":/out api \
>   python -m gridlab.scripts.make_scenario --out /out

# ZONES and GRAN are overridable: `make scenario-live ZONES=DK-DK2,DE,PL GRAN=15_minutes`
ZONES ?= DK-DK2,DE
GRAN  ?= hourly

# Writes into data/, which the api container mounts, so /api/v1/atlas can serve it. A live
# sweep with no replay equivalent: one zone's numbers can be replayed, a picture of every
# grid cannot. ARGS passes through -- `make atlas ARGS=--all` sweeps every reachable zone.
atlas: .env  ## Cheap-vs-clean across many zones -> data/atlas.json (live, throttled)
> $(NOCONV) $(COMPOSE) run --rm --no-deps -T --volume "$(CURDIR)/data":/out api python -m gridlab.scripts.build_atlas --out /out $(ARGS)

scenario-live: .env  ## Record a REAL scenario once, ad hoc, into recordings/
> $(NOCONV) $(COMPOSE) run --rm --no-deps -T \
>   --volume "$(CURDIR)/recordings":/out api \
>   python -m gridlab.scripts.make_scenario --from-live --out /out \
>     --zones "$(ZONES)" --granularity "$(GRAN)"

# The command a scheduler runs, and the same one you run by hand. Idempotent: if today is
# already recorded and complete it makes no API calls at all, so running it twice costs
# nothing. Exit 0 recorded or already present, 1 failed or incomplete, 2 no token.
# See docs/RECORDING.md and ops/README.md.
record-daily: .env  ## Record today into recordings/ if it is not already there (idempotent)
> $(NOCONV) $(COMPOSE) run --rm --no-deps -T \
>   --volume "$(CURDIR)/recordings":/out api \
>   python -m gridlab.scripts.record_daily --out /out \
>     --zones "$(ZONES)" --granularity "$(GRAN)" $(ARGS)

recordings:  ## What the archive holds, what is missing, and how the last run went
> $(NOCONV) $(COMPOSE) run --rm --no-deps -T \
>   --volume "$(CURDIR)/recordings":/out api \
>   python -m gridlab.scripts.record_daily --out /out --status

# Recordings are Electricity Maps data and must not be published (ADR 0013), so the archive
# is a separate private repository cloned into ./recordings, which is gitignored here.
archive-init:  ## Clone the private recordings archive into ./recordings
> @test -n "$(ARCHIVE)" || (echo "Usage: make archive-init ARCHIVE=git@github.com:you/your-data-repo.git"; exit 2)
> @test ! -d recordings/.git || (echo "recordings/ is already a clone."; exit 0)
> git clone "$(ARCHIVE)" recordings

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
