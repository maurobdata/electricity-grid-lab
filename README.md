# Grid Lab

**An Electricity Lab** — a local-first, containerized foundation for experimenting with real
[Electricity Maps](https://www.electricitymaps.com/) data, built ahead of
**[Hack on the Grid](https://luma.com/hki2v950)**, Copenhagen, **Friday 11 September 2026**.

> **This is not the product.**
>
> Four independent research passes (in [`docs/research/`](docs/research/)) recommend four
> different products and argue against each other: a grid status page, a battery-scheduling
> puzzle, a calendar feed, and a prediction league. That disagreement is evidence the
> question is genuinely open, so the product decision is deliberately deferred —
> [ADR 0007](docs/adr/0007-defer-product-decision.md).
>
> What this repository provides is everything all four would need: a verified API adapter,
> a provider-neutral domain model, live/replay symmetry, a visualization shell, and a
> sandboxed agent with explicit tools. The test of the architecture is whether any of them
> can be reached from here in hours.

---

## Run it

```bash
make up
```

- **PWA** — <http://localhost:5173>
- **API** — <http://localhost:8000/docs>
- **Agent** — <http://localhost:8001/docs>

**No API key and no network are required.** The lab starts in *replay* mode, playing a
recorded window of grid time against a virtual clock. That is the default on purpose: the
14-day Electricity Maps trial should not be started until early September, a hackathon demo
must not depend on the live grid doing something interesting at 17:00, and venue wifi is
not a dependency worth taking.

```bash
make test     # offline test suite: no network, no key
make lint     # ruff + mypy --strict
make probe    # ask a real token what it can actually reach
make record   # record raw API responses into fixtures/
make scenario # regenerate the bundled (synthetic) scenarios
make down
```

Requirements: Docker with Compose. Nothing else — Python and Node both live in containers.

---

## Getting real data in

1. Get a token at <https://portal.electricitymaps.com/>. **Timing matters:** a 14-day trial
   started today expires before 11 September. Start it 5–8 September.
2. Put it in `.env` as `ELECTRICITY_MAPS_API_TOKEN`. `.env` is gitignored; `.env.example`
   documents the shape and holds no values.
3. **Run `make probe` first.** `/v4/zones` publishes an `access` list of exactly the
   `signal/temporality` pairs your plan permits, so this costs one request and is
   authoritative. It writes `capabilities.json`, which the UI then reads.
4. Set `GRIDLAB_MODE=live` and `make restart`.

If the token is missing, live mode falls back to replay with a warning rather than failing.

### What a free-tier key actually gives you

Measured on 22 August 2026, and **the opposite of what the research predicted**
([ADR 0008](docs/adr/0008-history-not-breadth-is-the-constraint.md)):

| | |
|---|---|
| Zones | **350** — not one. Comparison and cross-border flows are fully available. |
| `latest`, `forecast` | yes, all signals |
| `history` | yes — but **only the trailing ~24 hours** |
| `past` / `past-range` | **no.** 401 for every signal. |

The constraint is **depth, not breadth**. Anything needing a real historical window —
scoring a forecast against its outcome, replaying a named storm, backtesting — needs a
trial or event key. So: **record scenarios from the rolling window now**, and re-record
when a deeper key exists. What is reachable today is gone tomorrow.

---

## Architecture

Three containers, two images.

```
Electricity Maps v4 ──► EMapsClient      auth-token, chunking, retry, typed errors
                          │
                          ▼
                        Normalizer       the only module that knows their field names
                          │
                          ▼
                     domain models       provider-neutral, provenance on every value
                          │
                     ┌────┴────┐
                LiveSource   ReplaySource      one interface, one Clock protocol
                     └────┬────┘
                          ▼
                   FastAPI :8000 ──┬──► web   PWA          :5173
                                   └──► agent sandbox      :8001
```

The agent runs from the **same image** as the API with a different command, on a network
that reaches only `api`, read-only, no volumes, no capabilities. It can act only through
declared tools. [ADR 0005](docs/adr/0005-agent-sandbox-container.md) states precisely what
that does and does not guarantee.

**Key documents**

| | |
|---|---|
| [`docs/PROJECT_CONTEXT.md`](docs/PROJECT_CONTEXT.md) | The canonical brief |
| [`docs/electricity-maps-api.md`](docs/electricity-maps-api.md) | The API surface, verified against the live API — including four things the first pass guessed wrong |
| [`docs/adr/`](docs/adr/) | Decisions, and what would reverse them |
| [`docs/research/`](docs/research/) | Four contradictory research passes. Hypotheses, not requirements. |
| [`CLAUDE.md`](CLAUDE.md) | Working rules for this repository |

---

## Three things this foundation insists on

**1. Never invent an endpoint.** `emaps/signals.py` encodes the v4 surface as a
signal × temporality capability matrix; a pair the matrix does not admit cannot produce a
URL. A test asserts the matrix and `docs/electricity-maps-api.md` agree in both directions.
Documented exceptions are encoded rather than discovered — day-ahead LMP has no forecast
variant, so asking for one fails locally instead of returning a 400 in Copenhagen.

**2. Never let generated data look measured.** Every value carries `provenance`
(`live` | `recorded` | `synthetic`) and `is_estimated`, and both reach the UI as a badge.
A series takes the weakest provenance of its points. The scenarios bundled in this repo are
**synthetic** — plausibly shaped, entirely made up — and say so in every response.

**3. It must run offline.** Replay is the default path, not a fallback, so it is always
exercised and always works. The whole test suite is offline and deterministic.

---

## Status

| Phase | |
|---|---|
| 0 · Repo, docs, ADRs, containers | done |
| 1 · Electricity Maps adapter + domain model | done |
| 2 · Clock, sources, DuckDB cache, HTTP API | done |
| 2b · Live mode verified against the real API; schema corrected | done |
| 3 · PWA — zone picker, now panel, mix, forecast, flows, compare | next |
| 4 · Agent sandbox — seven tools, tracing | not started |
| 5 · Evals, observability, demo scenarios | not started |

202 tests, offline and deterministic. `ruff` and `mypy --strict` clean.

21 real API responses are committed in [`fixtures/`](fixtures/) and every one of them is
parsed by the test suite, so the adapter is pinned to what the API actually sends rather
than to what the documentation implies.

---

## Deliberately not built

Auth, accounts, multi-user, CI/CD, Kubernetes, a world map, RAG, calendar generation,
scoring engines, optimizers, SLO engines, game mechanics.

Each of those belongs to a product that has not been chosen. A world map in particular is
tempting and wrong: it competes directly with Electricity Maps' own flagship, on their home
turf, and loses — all four research passes say so independently.

The Electricity Maps web app is also **not** embedded. Its
`Content-Security-Policy: frame-ancestors` does not include our origin, so an iframe would
fail silently in the console; the integration point is deep links plus our own rendering.
See [ADR 0006](docs/adr/0006-no-iframe-of-electricity-maps.md).

---

## Licensing note

`electricitymaps-contrib` — which holds the tempting zone geometries — is **AGPL-3.0**.
Pulling that GeoJSON into a hosted web app is arguably network-copyleft territory. If this
project ever needs boundaries, use Natural Earth (public domain).
