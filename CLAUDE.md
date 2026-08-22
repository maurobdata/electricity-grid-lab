# CLAUDE.md — working rules for this repository

## What this is

**Grid Lab** — a local-first, containerized foundation for experimenting with real
Electricity Maps data, built ahead of **Hack on the Grid**, Copenhagen, **Friday 11
September 2026**, 09:00-18:00.

**This is not the product.** The product is undecided. See `docs/adr/0007-defer-product-decision.md`.

Read before making architectural decisions:
1. `docs/PROJECT_CONTEXT.md` — the canonical brief
2. `docs/adr/` — decisions already made, and what would reverse them
3. `docs/electricity-maps-api.md` — the verified API surface
4. `docs/research/` — four contradictory research passes. Hypotheses, not requirements.

## Hard rules

1. **Never invent an Electricity Maps endpoint.** Every path must exist in
   `docs/electricity-maps-api.md` with a source, and in the `SUPPORTED` matrix in
   `services/api/src/gridlab/emaps/signals.py`. Add it to the doc first.
2. **Never commit a secret.** Tokens live in `.env`, which is gitignored. `.env.example`
   documents the shape and holds no values.
3. **Never call Electricity Maps from browser code.** Server-side only, cached. Rate limits
   are undocumented; assume they are tight.
4. **`emaps/normalize.py` is the only module allowed to know an Electricity Maps field
   name.** Everything above it uses our domain models.
5. **Never let synthetic data look measured.** Every value carries `provenance`
   (`live` | `recorded` | `synthetic`) and it must reach the UI.
6. **The agent gets explicit tools only.** No shell, no filesystem, no arbitrary HTTP, no
   database handle. A new tool that mutates anything needs an ADR.
7. **The repo must run offline with no API key.** `make up` defaults to replay mode. If a
   change breaks that, the change is wrong.

## Preferences

- Distinguish fact, hypothesis and decision explicitly. The research documents do this well;
  match it.
- Prefer small reversible changes. Prefer a working vertical slice over abstract infrastructure.
- Tests around the domain and the adapter. Not around glue.
- Document meaningful decisions as ADRs. Do not edit accepted ADRs; supersede them.
- **UX > architecture. Product > technology. Real data > simulated numbers.**
  Do not optimise technical sophistication at the expense of the experience.

## Things deliberately not built

Auth, accounts, multi-user, CI/CD, Kubernetes, a world map, RAG, calendar feeds, scoring
engines, optimizers, SLO engines. Each belongs to a product that has not been chosen.
See the deferred list in `README.md`.

## Commands

    make up       # everything, replay mode, no key needed
    make test     # offline pytest
    make probe    # ask a real token what it can actually reach
    make record   # record raw API responses into fixtures/
    make demo     # play a scenario at speed
    make eval     # agent evaluations
