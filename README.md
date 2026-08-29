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
make up    # API + agent
make web   # add the PWA
```

- **PWA** — <http://localhost:5173>
- **API** — <http://localhost:8000/docs>
- **Agent** — <http://localhost:8001/docs>

The PWA sits behind a Compose profile, so `make up` stays the lean pair when you are only
working on the backend.

**`make web` is the dev server, and it deliberately registers no service worker** — one
would fight hot reload, so `vite-plugin-pwa` is configured with `devOptions: { enabled:
false }`. To see the installed-app behaviour, build it:

```bash
make preview   # builds and serves the real PWA on :4173, service worker active
```

The build is verified: 8 precache entries, a `standalone` manifest, and the `NetworkFirst`
rule for `/api/v1/`. Service-worker *activation* has only been checked in an embedded
browser that refuses to register one, so confirm the offline behaviour in a real Chrome or
Safari before relying on it.

**No API key and no network are required.** The lab starts in *replay* mode, playing a
recorded window of grid time against a virtual clock. That is the default on purpose: the
14-day Electricity Maps trial should not be started until early September, a hackathon demo
must not depend on the live grid doing something interesting at 17:00, and venue wifi is
not a dependency worth taking.

```bash
make atlas    # cheap-vs-clean across 41 European zones -> data/atlas.json
make test     # offline test suite: no network, no key (test-api / test-web to split)
make lint     # ruff + mypy --strict (lint-api / lint-web to split)
make probe    # ask a real token what it can actually reach
make record   # record raw API responses into recordings/fixtures/
make scenario # regenerate the bundled (synthetic) scenarios
make record-daily   # record today (idempotent) -> recordings/
make recordings     # what the archive holds, and what is missing
make demo     # walk the current scenario and narrate it
make eval ARGS=--offline   # check the eval checkers, no key needed
make down
```

Requirements: Docker with Compose. Nothing else — Python and Node both live in containers.

### What CI checks

Every pull request, and every push to `main`, runs three jobs in parallel
([`.github/workflows/ci.yml`](.github/workflows/ci.yml)):

| Job | |
|---|---|
| `backend` | `make lint-api` + `make test-api` — ruff, `ruff format --check`, `mypy --strict`, pytest |
| `frontend` | `make lint-web` + `make test-web` + a real `vite build` |
| `smoke` | Boots the stack from a clean checkout and asserts it is in replay mode, holds no token, and reports `synthetic` provenance |

They call the repository's own `make` targets rather than re-spelling the commands, so CI
and a laptop cannot drift apart. **No secrets are used and none are needed** — the suite is
offline and replay-based, so a pull request from a fork runs exactly the same checks.

The smoke job is the interesting one: it turns CLAUDE.md rule 7 — *the repo must run offline
with no API key* — from a claim into a check, and it fails loudly if Electricity Maps data
ever reaches this repository, because a clean checkout would then stop reading `synthetic`.

The daily recording deliberately does **not** run here; it lives in the private archive
repository ([ADR 0014](docs/adr/0014-daily-recording-scheduler-outside-the-lab.md)).

---

## Getting real data in

1. Get a token at <https://portal.electricitymaps.com/>. **Timing matters:** a 14-day trial
   started today expires before 11 September. Start it 5–8 September.
2. Put it in `.env` as `ELECTRICITY_MAPS_API_TOKEN`. `.env` is gitignored; `.env.example`
   documents the shape and holds no values.
3. **Run `make probe` first.** `/v4/zones` publishes an `access` list of exactly the
   `signal/temporality` pairs your plan permits, so this costs one request and is
   authoritative. It writes `data/capabilities.json`, which the api container mounts and
   `GET /api/v1/capabilities` serves.
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
trial or event key.

So the rolling window has to be captured before it rolls away:

```bash
make record-daily                                   # DK-DK2 + DE, hourly
make record-daily ZONES=DK-DK2,DE,PL,FR,NO-NO2     # more zones
make record-daily GRAN=15_minutes                  # 96 points instead of 24
```

That writes `recordings/<zone>-<date>.json` with `provenance: recorded` — roughly 24 hours
of actuals plus the forecast **as issued at the moment of recording**, which reaches 72
hours past the end of the window.

One recording cannot show forecast-versus-outcome, because the hours a forecast covers have
not happened yet. **Record daily** and today's forecast lands on top of tomorrow's actuals —
which is the only way to get that comparison out of a key with no `past-range`.

### That happens by itself now

Relying on somebody remembering did not work. The archive records 22, 23 and 24 August and
then stops: **25 August is permanently lost**, because the API cannot be asked for a day
that has rolled out of the trailing window.

```bash
make record-daily    # record today, if today is not already recorded
make recordings      # what the archive holds, what is missing, how the last run went
```

`make record-daily` is the command a schedule runs twice a day, and the same one you run by
hand. It is idempotent: a day already recorded and complete costs **zero API calls** and
exits 0, so the second daily run is a free retry for a morning when something was down.

A run that fails, or comes back too thin to be worth keeping, **writes nothing** — the
previous recording is never at risk. Exit 1 turns the scheduled run red and GitHub emails
the owner; every attempt is appended to a ledger with its reasons.

The scheduler holds no logic at all: its whole body is `make record-daily`. Moving it
elsewhere is deleting one YAML file
([ADR 0014](docs/adr/0014-daily-recording-scheduler-outside-the-lab.md)).

**Runbook:** [`docs/RECORDING.md`](docs/RECORDING.md). **Setup:** [`ops/README.md`](ops/README.md).

### Where recordings live, and why not here

Not in this repository. Electricity Maps' terms prohibit reproducing or publishing their
Data to any third party, and the day-ahead prices carry a further restriction from Nord Pool
and EPEX — and this repository is public.

So recordings and raw fixtures live in a separate **private** archive, cloned into
`./recordings` and gitignored here ([ADR 0013](docs/adr/0013-recorded-data-is-not-published.md)).

```bash
make archive-init ARCHIVE=git@github.com:maurobdata/electricity-grid-lab-recordings.git
```

Without it the lab still runs, on the two committed synthetic scenarios, offline and with no
key. That was already the rule; it is now the default path for anyone cloning this.

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
| [`docs/DEMO.md`](docs/DEMO.md) | The runbook: what to record on the morning, what to show, and what breaks |
| [`docs/RECORDING.md`](docs/RECORDING.md) | The daily archive: how it is triggered, where it writes, how it fails, how to recover |
| [`ops/README.md`](ops/README.md) | Setting up the private archive and its schedule |
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
A series takes the weakest provenance of its points. `scenarios/dk-dk2-*.json` is
**recorded** — real API responses; the two named scenarios are **synthetic** — plausibly
shaped, entirely made up — and a test fails if a synthetic one stops saying so.

**3. It must run offline.** Replay is the default path, not a fallback, so it is always
exercised and always works. The whole test suite is offline and deterministic.

---

## The lab

One zone in focus, plus a comparison across several. A workbench, not a design — the
product that eventually grows out of this will not have this shape.

| Panel | |
|---|---|
| **Mode bar** | Live or replay, which scenario, transport controls and a scrubber. Always on screen, so nobody has to wonder whether they are looking at the grid or a recording. |
| **Now** | Carbon intensity, renewable and carbon-free share, day-ahead price, load. Signals the plan cannot reach are shown as explicitly missing rather than omitted. |
| **Mix** | Production versus flow-traced, as a toggle — and the panel computes the gap between them, because that gap is the point. |
| **Flows** | Net exchange per neighbour, diverging from a centre line. Deliberately not a map. |
| **Forecast vs actual** | History solid, forecast dashed, a divider at the clock, and the mean absolute error across any overlap. |
| **Compare** | One signal, one instant, several zones — with the caveat that raw rankings are frozen and a real league needs baseline-relative scoring. |
| **Agent** | Ask about the grid in plain language. Tool calls and results render inline. |
| **Capability** | What the token can actually reach, from the last `make probe`. |

The front end is React + Vite + Tailwind with shadcn/ui conventions (`@/` alias, `cn()`,
the standard CSS variables), so a component generated by Lovable on the day drops in
without a rewrite. Charts are hand-rolled SVG rather than a chart library: the shapes are
simple, and the forecast overlay and the synthetic hatch want exact control.

---

## Status

| Phase | |
|---|---|
| 0 · Repo, docs, ADRs, containers | done |
| 1 · Electricity Maps adapter + domain model | done |
| 2 · Clock, sources, DuckDB cache, HTTP API | done |
| 2b · Live mode verified against the real API; schema corrected | done |
| 2c · `make scenario-live` — real, replayable, provenance-preserving recordings | done |
| 3 · PWA — zone picker, now panel, mix, forecast, flows, compare | done |
| 4 · Agent sandbox — seven read-only tools, visible tool trace | done |
| 5 · Evals, OpenTelemetry tracing, demo walkthrough | done |
| 6 · Forward price, deterministic analysis layer, findings | done |
| 7 · View-state contract, agent proposes views, panel shell | done |
| 8 · Cross-zone atlas, cached narration | done |
| 9 · Daily recording: reusable recorder, private archive, scheduled off-machine | done |
| 10 · CI gate: backend, frontend and an offline smoke check on every PR | done |

515 tests, offline and deterministic. `ruff` and `mypy --strict` clean.

**A clone without the private archive runs about 440 of them.** Three modules —
`test_fixtures`, `test_live`, `test_record_scenario` — assert against real API responses and
skip themselves when those are not mounted. That is not a gap that appeared here: those
guards were written before the licence question was, and they turned out to be exactly the
right shape.

23 real API responses live in `recordings/fixtures/` and every one of them is parsed by the
test suite, so the adapter is pinned to what the API actually sends rather than to what the
documentation implies. They are Electricity Maps data, so they are kept in the private
archive rather than published here
([ADR 0013](docs/adr/0013-recorded-data-is-not-published.md)).

---

## The agent

Seven read-only tools — `get_current_grid`, `get_forecast`, `get_mix`, `get_price`,
`get_flows`, `query_history`, `compare_zones` — and nothing else. `GET :8001/api/v1/tools`
publishes the whole surface, because the declared tool list **is** the security boundary.

Its working is shown. Every tool call and result renders inline in the UI, so an answer can
be checked rather than trusted: each number it quotes corresponds to a request you could
make yourself against the API on port 8000.

The sandbox, verified rather than asserted — from inside the running container:

| | |
|---|---|
| Runs as | uid 10001, non-root, all capabilities dropped |
| Can reach | `api:8000` |
| Cannot reach | `web:5173` — not even DNS-resolvable, it is on another network |
| Filesystem | read-only everywhere except a 16 MB tmpfs at `/tmp` |
| Volume mounts | none |

What this does **not** guarantee is network egress: the container must reach
`api.anthropic.com`, and Docker cannot restrict egress by domain. The agent is
tool-constrained and filesystem-isolated, not network-isolated — see
[ADR 0005](docs/adr/0005-agent-sandbox-container.md), which says so plainly rather than
overclaiming.

Guardrails that are code rather than prompt: zones are allowlisted before any request,
history windows are bounded, series are downsampled to a hard cap before reaching the model
— preserving the minimum, maximum and both endpoints, because a dropped price spike is
exactly what somebody was asking about. The prompt handles what code cannot check:
disclosing provenance, refusing to rank on raw values, admitting when a tool came back
empty. Phase 5 measures whether it actually does.

Without an `ANTHROPIC_API_KEY` the service still runs and still publishes its tools; only
the model call is unavailable.

---

## Evaluating the agent

```bash
make eval                  # run the cases against the live agent, then check
make eval ARGS=--offline   # re-check committed transcripts, no key needed
make eval ARGS=--judge     # add an LLM judge for what code cannot check
make eval ARGS=--align     # score the judge itself, TPR/TNR
```

Capturing a transcript costs model calls; checking one costs nothing. So capture is a
separate step, transcripts are written to disk, and every later run of the checkers is free
— improving a checker never means paying for the answers again.

**The most important check is deterministic.** The agent's first rule is *never state a
number you did not get from a tool*, and that is mechanically decidable: pull every number
out of the answer and look for it in the tool traffic. No judge, no cost, no flakiness. It
allows rounding (`75.2318` → `75%`) and fraction-to-percent (`0.08` → `8%`), and it is
honest about its limit — arithmetic on grounded numbers is reported as unverified rather
than silently passed, because this check is precise about invention and imprecise about
derivation.

The LLM judge covers only what code cannot: did the answer explain the difference between
the two mixes, did it treat a forecast as a prediction, did it avoid a league table. **And
the judge is itself scored** against hand-labelled examples, reported as true positive and
true negative rates separately — a judge that passes everything scores 100% TPR and 0% TNR,
which a single accuracy figure would hide completely.

`evals/examples/` holds hand-written transcripts, each built to break one checker, with a
human verdict attached. They are what the checkers are unit-tested against: *a checker that
has stopped catching anything looks exactly like a checker with nothing to catch.*

---

## Tracing

```bash
docker compose --profile tracing up phoenix   # then GRIDLAB_TRACING_ENABLED=true
```

Three spans, which are the three questions asked when something looks wrong: what did
Electricity Maps say, which tools did the agent run, how long did a turn take. Off by
default and behind a profile, so instrumentation that costs a service to run gets turned on
when you want it. When disabled, `span()` is a no-op context manager — no branching
anywhere else in the codebase.

---

## Deliberately not built

Auth, accounts, multi-user, deployment, Kubernetes, a world map, RAG, calendar generation,
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
