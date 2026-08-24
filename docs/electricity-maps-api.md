# Electricity Maps API v4 — verified reference

**Status.** Everything below was verified **against the live API on 22 August 2026** with a
free-tier token, unless marked otherwise. Raw responses are committed in [`fixtures/`](../fixtures/)
and `tests/test_fixtures.py` parses every one of them, so this document and the code cannot
drift apart silently.

The rule this project follows: *never invent an endpoint*.
[`emaps/signals.py`](../services/api/src/gridlab/emaps/signals.py) encodes the table below as
a capability matrix, and `tests/test_signals.py` asserts the two stay in sync. If you need
something that is not here, verify it against the live API, record the evidence here, and
only then add it to the matrix.

> ### What the first pass got wrong
>
> This document originally separated "verified" endpoint paths from "unverified" response
> schemas, and the unverified half turned out to contain four real errors. They are listed
> here rather than quietly corrected, because the pattern is worth remembering: **the paths
> were guessable from the docs; the parameter *values* and field names were not.**
>
> | Guessed | Actually |
> |---|---|
> | `renewable-level`, `carbon-free-level` | `renewable-percentage-level`, `carbon-free-percentage-level` |
> | `breakdownType=production` / `consumption` | `breakdownType=normal` / `flow-traced` |
> | mix under `powerConsumptionBreakdown` | mix under `mix` (that name belongs to a *different* endpoint) |
> | flows under `powerImportBreakdown` / `powerExportBreakdown` | flows under `import` / `export` |
>
> Every one would have produced a 400 or a silently wrong chart on the first live call.

---

## Base URL and auth

```
https://api.electricitymaps.com/v4
```

Every request except `/zones` requires:

```
auth-token: <your token>
```

Basic Auth is also supported.

### `/v4/zones` is the capability list, not just a zone list

Called **without** a token it returns all 350 zones with descriptive metadata. Called **with**
a token, each zone gains an `access` array — a list of exact `signal/temporality` strings the
plan permits:

```json
"DK-DK2": {
  "zoneName": "East Denmark", "countryName": "Denmark", "zoneKey": "DK-DK2",
  "countryCode": "DK", "zoneParentKey": "DK", "subZoneKeys": [],
  "isCommerciallyAvailable": true, "tier": "TIER_A",
  "access": ["carbon-intensity/latest", "carbon-intensity/history", ...]
}
```

This is why `make probe` costs **one** request rather than forty: the answer is published.

Two wrinkles found by using it:

- The `access` list names per-source generation as `electricity-source-wind`, but the **URL**
  is `electricity-source/wind`. Requesting the capability key as a path returns 400.
- It over-promises: it advertises `carbon-intensity-level/history`, which returns
  `400 "Expected one of latest, past, past-range"`. The API is the authority over its own
  capability listing.

### Geolocation

`zone=<key>`, or `lat=`/`lon=`, or `GET /v4/zone` to resolve coordinates up front. There is
also an offline coordinate→zone repo (`electricitymaps/zone-finder`).

> **Silent fallback.** With no zone resolved, the API geolocates *the caller's IP*. A request
> that meant to ask about Spain then returns Danish data, and the response looks perfectly
> valid. Grid Lab always sends `disableCallerLookup=true`.

---

## Endpoints

Paths are a regular product of **signal × temporality**: `/v4/{signal}/{temporality}`.

| Signal | Path segment | Notes |
|---|---|---|
| Carbon intensity | `carbon-intensity` | gCO₂eq/kWh |
| Fossil-only carbon intensity | `carbon-intensity-fossil-only` | residual-mix proxy |
| Renewable percentage | `renewable-energy` | `value` with `unit: "%"` |
| Carbon-free percentage | `carbon-free-energy` | |
| Electricity mix | `electricity-mix` | breakdown under `mix` |
| Single-source generation | `electricity-source/<sourceType>` | `solar`, `wind`, `hydro`, `nuclear`, `gas`, `coal`, `oil`, `biomass`, `geothermal`, `unknown`, `battery`, `hydro-discharge`, `battery-discharge` |
| Cross-border flows | `electricity-flows` | `import` / `export` maps |
| Power breakdown | `power-breakdown` | the v3-style shape; `powerConsumptionBreakdown` |
| Day-ahead price | `price-day-ahead` | Europe + a few zones |
| Day-ahead LMP | `locational-marginal-price-day-ahead` | **needs `node`, not `zone`** |
| Total load | `total-load` | EM-calculated |
| Total reported load | `total-reported-load` | as TSOs report it |
| Net load | `net-load` | load minus wind and solar — the duck curve |
| Carbon intensity level | `carbon-intensity-level` | beta, `low`/`moderate`/`high` |
| Renewable level | `renewable-percentage-level` | beta |
| Carbon-free level | `carbon-free-percentage-level` | beta |

Temporalities:

| Temporality | Required params | Meaning |
|---|---|---|
| `latest` | `zone` | most recent value |
| `past` | `zone`, `datetime` | value at one instant |
| `past-range` | `zone`, `start`, `end` | series over a window |
| `history` | `zone` | recent trailing history |
| `forecast` | `zone` | forward-looking series |

`price-day-ahead` additionally has `combined`, `actual` and `forecast`. **`combined` is the
one to reach for**: it blends published auction prices with Electricity Maps' modelled ones
in a single call, needs only a zone, and labels each row with its `source`.

`locational-marginal-price-day-ahead` has no `forecast` variant, and a zone-only request
returns `400 "Missing arguments \"node\""`.

Level signals reject `history` despite advertising it: `latest`, `past`, `past-range` only.

### `combined` is where forward price lives — verified

`price-day-ahead/combined` **reaches into the future**, and it is the only forward price
this plan can get. Measured from the committed fixture
[`price-day-ahead__combined.json`](../fixtures/price-day-ahead__combined.json), recorded
22 August 2026 at 20:03 UTC for DK-DK2:

| | |
|---|---|
| Rows | 25, hourly |
| Span | `2026-08-22T20:00Z` .. `2026-08-23T20:00Z` — **+24 h from the moment of recording** |
| `source` | `nordpool.com` on every row |
| `createdAt` / `updatedAt` | `2026-08-21T11:30Z` on the first two rows, `2026-08-22T11:29Z` from 22:00Z onward |

That `createdAt` step is the **auction clearing**, visible in the data. SDAC clears at 12:00
CET for the following delivery day, so a response fetched after lunch carries the rows that
cleared at lunch. This is why forward price is reachable on a key with no `past-range`:
tomorrow's prices are not a prediction that has to be modelled, they are **a settled auction
result published ahead of delivery**.

Consequences, all of which the code now encodes:

- Use `combined`, **not** `forecast`. `price-day-ahead/forecast` rejects `horizonHours`
  outright — `400 "Missing or invalid date parameter \"start\""` — and demands a window you
  would have to guess. `FORECAST_NEEDS_WINDOW` in `emaps/signals.py` already refuses it
  locally.
- **How far forward you get depends on when you ask.** The fixture was captured at 20:03Z
  and reached +24 h. Immediately after the 11:29Z clearing the window should reach further,
  to the end of tomorrow. Not yet measured — see the validation list below.
- Split the response at your clock. It reaches backwards as well as forwards, and the
  backward half is what `history` already returns.
- Keep `source` per row. `combined` interleaves cleared prices with modelled ones, and it is
  the only field that tells them apart once the envelope is gone.

> #### The window where price and carbon are both known is about a day
>
> Carbon intensity forecasts reach **72 hours**. Mix, flows and every load signal reach
> **24 hours only**. Forward price reaches to the end of the delivery day the auction
> covered.
>
> So any analysis joining price with carbon — or either with flows — is bounded by the
> shortest of these, which is roughly **24 hours**, not 72. Design cross-signal work to a
> day. Discovering this on stage would be worse.

#### Still unmeasured about forward price

Re-check these the moment a trial or event key exists; each changes what is buildable.

1. `combined` with `temporalGranularity=15_minutes`. The fixture is **hourly**. European
   day-ahead has cleared in 15-minute MTUs since 1 October 2025, so tomorrow may have 96
   points rather than 24 — but that is not verified on this signal, and no code should
   assume it.
2. `price-day-ahead/forecast` with an explicit `start`/`end`. Never called once. It may give
   a longer or cleaner window than `combined` — and given the finding below, it is now the
   only candidate for reaching further than a day.
3. Day-ahead price coverage across the 350 zones — documented as Europe plus a few, never
   enumerated.

#### Measured since: `combined` is a rolling +24 h window

The open question was whether `combined` reaches past +24 h when called shortly after the
noon clearing. **It does not.** Two live recordings, at opposite ends of the day:

| Recorded at | Rows | Span | Auction cleared |
|---|---|---|---|
| 2026-08-23 19:00Z | 25 | `08-23 19:00Z` → `08-24 19:00Z` | `08-23 11:24Z` |
| 2026-08-24 08:13Z | 25 | `08-24 08:00Z` → `08-25 08:00Z` | `08-24 07:32Z` |

Both are exactly 25 hourly rows anchored on the current hour, **regardless of proximity to
the clearing** — the second was fetched 41 minutes after its auction cleared and still
stopped at +24 h. So `combined` is a rolling window, not a view of the delivery day: it
truncates the published auction result rather than serving all of it.

Consequences:

- The forward price horizon is **a flat 24 hours from whenever you ask**, and it does not
  grow after lunch. Anything planning around "tomorrow's whole delivery day" is planning
  around a window this endpoint does not give.
- Recording in the morning and recording in the evening yield the same *depth*, so the
  daily recording can run at any hour without losing forward price.
- If a longer forward window is ever needed, item 2 above is the only remaining candidate.

---

## Forecast horizons are per signal, not per plan

This contradicts the documentation, which says 6/24/48/72 with availability "depending on
your plan". Swept against the live API:

| Signal | `horizonHours` accepted |
|---|---|
| `carbon-intensity` | 6, 24, 48, 72 |
| `carbon-intensity-fossil-only` | 6, 24, 48, 72 |
| `renewable-energy` | 6, 24, 48, 72 |
| `carbon-free-energy` | 6, 24, 48, 72 |
| `electricity-mix` | **24 only** |
| `electricity-source/<type>` | **24 only** |
| `electricity-flows` | **24 only** |
| `power-breakdown` | **24 only** |
| `total-load`, `total-reported-load`, `net-load` | **24 only** |
| `price-day-ahead` | **none** — requires `start` and `end` |

6, 48 and 72 return 400 on the "24 only" signals. `price-day-ahead/forecast` with
`horizonHours` returns `400 "Missing or invalid date parameter \"start\""`.

`carbon-intensity/forecast?horizonHours=72` returns **73 rows** — hourly, inclusive of now.

---

## Parameters

| Parameter | Values | Notes |
|---|---|---|
| `temporalGranularity` | `5_minutes`, `15_minutes`, `hourly` (default) | On `history`: 288 / 96 / 24 rows. `daily` returns 400 on `history`; the coarse values are past-only. |
| `emissionFactorType` | `lifecycle` (default), `direct` | **Not a rounding difference.** The same DK-DK2 instant read 75 gCO₂eq/kWh lifecycle and **20** direct. |
| `breakdownType` | `normal`, `flow-traced` | On `electricity-mix`. Anything else: `400 "Valid breakdown types are: normal, flow-traced"`. Flow-tracing changed wind from 1008 MW to 944 MW in the sample. |
| `flowTraced` | `true` / `false` | Works on `carbon-intensity` (75 → 60 when false). **Has no effect on `electricity-mix`** — use `breakdownType` there. |
| `disableEstimations` | `true` | Suppresses modelled values. |
| `disableCallerLookup` | `true` | Stops the IP-geolocation fallback. Always send it. |
| `horizonHours` | see table above | |
| `dataCenterProvider` / `dataCenterRegion` | e.g. `gcp` / `europe-west1` | Not exercised here. |
| `datetime`, `start`, `end` | ISO 8601 | e.g. `2026-08-09T06:15:00Z` |

---

## Response shapes

Three envelope shapes are in use. `normalize.rows()` handles all three.

**Bare object** — `carbon-intensity/latest`, `power-breakdown/latest`:

```json
{ "zone": "DK-DK2", "carbonIntensity": 75, "datetime": "2026-08-22T17:00:00.000Z",
  "updatedAt": "...", "createdAt": "...", "emissionFactorType": "lifecycle",
  "flowTraced": true, "isEstimated": true, "estimationMethod": "FORECASTS_HIERARCHY",
  "temporalGranularity": "hourly" }
```

**`{"data": [...]}`** — most endpoints, including all `history` and most `forecast`.

**`{"forecast": [...]}`** — `carbon-intensity/forecast`. Its rows are minimal:
`{"carbonIntensity": 77, "datetime": "..."}` — no `isEstimated`, no `updatedAt`. Every field
except `datetime` must therefore be optional in a parser.

### Per-signal rows

| Signal | Value field | Notes |
|---|---|---|
| `carbon-intensity` | `carbonIntensity` | plus `emissionFactorType`, `flowTraced` |
| `renewable-energy`, `carbon-free-energy` | `value` | with `unit: "%"` |
| `total-load`, `net-load`, `electricity-source/*` | `value` | with `unit: "MW"` |
| `price-day-ahead` | `value` | with `unit: "EUR/MWh"` and `source: "nordpool.com"` |
| `carbon-intensity-level` etc. | `level` | `low` / `moderate` / `high` |

### `electricity-mix` — three traps

```json
{ "datetime": "...", "updatedAt": "...", "isEstimated": true,
  "estimationMethod": "ESTIMATED_FORECASTS_HIERARCHY", "breakdownType": "normal",
  "mix": { "nuclear": null, "biomass": 229.05, "wind": 1008.25, "solar": 71.06,
           "gas": 14.76, "oil": 4.32, "coal": null, "hydro": null, "unknown": null,
           "hydro storage":   {"charge": 0, "discharge": null},
           "battery storage": {"charge": 0, "discharge": null},
           "flows": {"exports": 489, "imports": 450} } }
```

1. **Nulls are normal.** Plotting them as zero invents generation that did not happen.
2. **Storage is two-directional.** `{"charge", "discharge"}`; only discharge is generation.
   Counting charge would double-count it — it is demand.
3. **`flows` is nested inside `mix` but is not a source.** Left in, it appears as several
   hundred MW of generation called "flows" and every percentage in the breakdown is wrong.

The row declares its own `breakdownType`, so a chart never has to remember what was asked.

### `electricity-flows`

```json
{ "datetime": "...", "import": {"DE": 36}, "export": {"DK-DK1": 450, "SE-SE4": 453} }
```

Two unsigned maps. A neighbour can appear in both at once, so they are netted into one
signed figure per neighbour (positive = export).

---

## Free-tier reality, 22 August 2026

Measured, not assumed. **This is the section to re-check the moment a trial or event key is
issued** — `make probe` rewrites `data/capabilities.json` in one request.

| | |
|---|---|
| **Zones** | **350** — not one. Tier A 189, Tier B 2, Tier C 146, untiered 13. |
| **Access entries** | 79, **identical across all 350 zones** — so access is plan-level, not zone-level. |
| **`latest`** | yes, all signals |
| **`history`** | yes — but **only the trailing ~24 hours** |
| **`forecast`** | yes, horizons as tabled above |
| **`past` / `past-range`** | **no.** 401 for every signal. |
| **`price-day-ahead`** | yes, including `combined` and `actual` |
| **Level signals** | yes, `latest` only |

> ### The constraint that actually matters
>
> Every research pass expected the free tier to be limited by **breadth** — one zone — and
> designed around that. It is limited by **depth** instead. 350 zones are open; arbitrary
> history is not.
>
> So multi-zone comparison, cross-border flow stories and simultaneity are all available
> today. What is *not* available is anything that needs a real historical window: scoring a
> forecast against its outcome, replaying a named storm, backtesting a strategy. Those need
> a trial or event key.
>
> Practical consequence: **record scenarios from the rolling 24 hours now**, and re-record
> once a deeper key exists. That is what `make record` and `scenarios/` are for.

### Rate limits

Still no published number, and none hit during ~120 requests in a single session. Assume one
exists and is not generous: server-side calls only, cached in DuckDB, and **never** call
Electricity Maps from browser code.

### Documented limits not exercisable on this plan

- `past-range` is capped at **10 days hourly / 100 days daily**. The client chunks around it
  and the chunking is unit-tested, but it could not be verified live without `past-range`
  access.
- History is documented back to 2017.

---

## Errors

`from_status` maps these to typed errors. One correction came from real responses:

**Electricity Maps returns 401 for *authorization* failures, not only authentication.**

```json
{"error": "Request unauthorized for zoneKey=DK-DK2,requestType=past,dataType=carbon-intensity.",
 "message": "You do not have access to this specific endpoint for this specific zone."}
```

A valid token asking for a signal outside its plan gets 401, not 403. Reporting that as
"check your token" sends you to debug the wrong thing entirely, so the body is inspected and
these map to `AccessDeniedError`.

---

## Related, and deliberately not used

- `electricitymaps/electricitymaps-contrib` — the parser collection, **AGPL-3.0** since
  v1.5.0. Its `geo/` directory holds tempting zone geometries; pulling that GeoJSON into a
  hosted app is arguably network-copyleft territory. Use Natural Earth (public domain) if
  boundaries are ever needed. See ADR 0006.
- The Electricity Maps web app **cannot be embedded** — its
  `Content-Security-Policy: frame-ancestors` does not include our origin. See ADR 0006.

## Sources

- Live API, 22 August 2026, free-tier token — see [`fixtures/`](../fixtures/)
- <https://app.electricitymaps.com/api/docs/reference>
- <https://app.electricitymaps.com/api/docs/concepts-and-parameters>
- <https://app.electricitymaps.com/developer-hub/api/getting-started>
