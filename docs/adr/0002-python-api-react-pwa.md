# 2. Python API + React PWA, in containers

Date: 2026-08-22 · Status: Accepted

## Context

The foundation needs to (a) do time-series work over grid data, (b) run an LLM agent whose
reference material — *A Common-Sense Guide to AI Engineering* — is entirely Python, and
(c) produce a polished front end fast, at an event co-hosted by Lovable.

The host machine has Docker and `uv`, but **no Node and no npm**.

## Decision

- **Backend:** Python 3.12, FastAPI, httpx, Pydantic, DuckDB.
- **Frontend:** React + TypeScript + Vite + Tailwind + shadcn/ui, with `vite-plugin-pwa`.
- **Everything runs in Docker.** The web toolchain never touches the host.

## Consequences

- Lovable emits React + Vite + Tailwind + shadcn/ui. Anything generated there on the day
  drops into `services/web/src` without a rewrite. This was the deciding argument.
- Two languages means two toolchains. Accepted: the alternative (TypeScript everywhere)
  would have put the agent and the time-series work in the weaker language for both.
- No Node on the host means dependency installation must run in the container. `make up`
  handles it; running Vite outside Docker is not supported.

## Reverse this if

The front end stops being the point — e.g. if the chosen product is a calendar feed or a
CLI, in which case the PWA is dead weight and a single Python service would do.
