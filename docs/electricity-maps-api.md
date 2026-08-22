# Electricity Maps API v4 — verified reference

**Status of this document.** Everything under "Verified" was read from Electricity Maps'
own documentation on 22 August 2026. Everything under "Unverified" could not be confirmed
from public sources and **must be checked against a live token before it is relied on**.

The rule this project follows: *never invent an endpoint*. `services/api/src/gridlab/emaps/signals.py`
encodes the table below as a capability matrix, and `tests/test_signals.py` asserts the two
stay in sync. If you need an endpoint that is not here, add it here first, with a source.

---

## Verified

### Base URL and auth

```
https://api.electricitymaps.com/v4
```

Every request except `/zones` requires a header:

```
auth-token: <your token>
```

Basic Auth is also supported. `GET /v4/zones` works with **no** token (returns all zones)
and with a token (returns the zones *your plan can reach*) — which makes it the capability
probe. See `scripts/probe_capabilities.py`.

### Geolocation

Three ways to identify a zone:

1. `zone=<zone-key>` — keys come from `/v4/zones`.
2. `lat=` and `lon=`.
3. `GET /v4/zone` to resolve coordinates to a zone up front.

There is also an offline coordinate-to-zone repo (`electricitymaps/zone-finder`) if you
must not send coordinates at all.

> **Silent fallback.** If no zone is resolved, the API falls back to geolocating *the
> caller's IP*. That will silently return Danish data for a request that meant to ask
> about Spain. Grid Lab always sends `disableCallerLookup=true`.

### Endpoint grammar

Paths are a regular product of **signal × temporality**:

```
/v4/{signal}/{temporality}
```

| Signal | Path segment | Notes |
|---|---|---|
| Carbon intensity | `carbon-intensity` | gCO₂eq/kWh |
| Fossil-only carbon intensity | `carbon-intensity-fossil-only` | residual-mix proxy |
| Renewable percentage | `renewable-energy` | |
| Carbon-free percentage | `carbon-free-energy` | |
| Electricity mix | `electricity-mix` | per-source breakdown incl. storage discharge |
| Single-source generation | `electricity-source/<sourceType>` | `solar`, `wind`, `hydro`, `nuclear`, `gas`, `coal`, `oil`, `biomass`, `geothermal`, `hydro-discharge`, `battery-discharge` |
| Cross-border flows | `electricity-flows` | imports/exports per neighbour |
| Day-ahead price | `price-day-ahead` | **Europe + a few zones only** |
| Day-ahead LMP | `locational-marginal-price-day-ahead` | preview, node-level, USD/MWh |
| Total load | `total-load` | EM-calculated |
| Total reported load | `total-reported-load` | as TSOs report it |
| Net load | `net-load` | load minus wind and solar |
| Carbon intensity level | `carbon-intensity-level` | **beta**, bucketed low/moderate/high |
| Renewable level | `renewable-level` | beta |
| Carbon-free level | `carbon-free-level` | beta |

Temporalities:

| Temporality | Required params | Meaning |
|---|---|---|
| `latest` | `zone` | most recent value |
| `past` | `zone`, `datetime` | value at one instant |
| `past-range` | `zone`, `start`, `end` | series over a window |
| `history` | `zone` | recent trailing history |
| `forecast` | `zone` | forward-looking series |

`price-day-ahead` additionally has `combined`, `actual` and `forecast`. `combined` returns
published prices where they exist and Electricity Maps' modelled prices where they do not,
in one call — a shape no other provider offers.

**`locational-marginal-price-day-ahead` has no `forecast` variant. Calling it returns 400.**

### Parameters

| Parameter | Values |
|---|---|
| `temporalGranularity` | `5_minutes`, `15_minutes`, `hourly` (default), and `daily` / `monthly` / `quarterly` / `yearly` for past data only |
| `emissionFactorType` | `lifecycle` (default), `direct` |
| `flowTraced` / `breakdownType` | consumption (flow-traced) vs production mix. Carbon intensity defaults to flow-traced. |
| `disableEstimations` | `true` suppresses estimated values |
| `disableCallerLookup` | `true` stops the IP-geolocation fallback |
| `horizonHours` | `6`, `24`, `48`, `72` — **availability depends on plan** |
| `dataCenterProvider` / `dataCenterRegion` | query by e.g. `gcp` / `europe-west1` instead of resolving a zone |
| `lat` / `lon` | coordinate lookup |
| `datetime`, `start`, `end` | ISO 8601, e.g. `2026-08-09T06:15:00Z` |

### Limits

- **`past-range` is capped at 10 days at hourly granularity and 100 days at daily.**
  Longer ranges must be fetched as a loop of chunks. `EMapsClient` does this.
- Historical data goes back to 2017. Forecasts run to 72 hours ahead.
- Zones are tiered **A** (measured hourly), **B** (partial), **C** (monthly/yearly estimates
  only). Only Tier A zones are suitable for anything that compares zones or scores a
  prediction.
- Responses carry `isEstimated` and `estimationMethod`.

---

## Unverified — confirm before relying on

1. **Exact JSON field names for every signal.** The full reference is behind an
   authenticated single-page app and could not be read without a token. The only publicly
   evidenced shape is carbon intensity:

   ```json
   {
     "zone": "DE",
     "carbonIntensity": 302,
     "datetime": "2026-04-25T18:07:00.350Z",
     "updatedAt": "2026-04-25T18:07:01.000Z",
     "emissionFactorType": "lifecycle",
     "isEstimated": true,
     "estimationMethod": "TIME_SLICER_AVERAGE"
   }
   ```

   Range endpoints wrap rows as `{"data": [ ... ]}`.

   **How this project handles the gap:** `emaps/normalize.py` maps raw responses into our
   own domain models and nothing outside that module knows an EM field name. Run
   `scripts/record_fixtures.py` the moment a token exists; the recorded fixtures become the
   normalizer's test inputs. A schema surprise is then a one-file change.

2. **Rate limits.** No public number found. Assume they exist and are not generous:
   server-side calls only, DuckDB read-through cache, and **never** call Electricity Maps
   from browser code.

3. **Free-tier scope.** Reported to be roughly one zone and a limited signal set. If true,
   every multi-zone feature in this lab degrades to single-zone. `GET /v4/zones` with the
   token answers this in one call — run `make probe` first, before designing anything.

4. **Which zones have day-ahead price.** Europe is fine; verify per zone.

5. **Post-hackathon licensing** for anything published from event-issued tokens. Governed
   by the ToS; ask the organisers rather than assuming.

---

## Related, and deliberately not used

- `electricitymaps/electricitymaps-contrib` — the parser collection. **AGPL-3.0** since
  v1.5.0. Its `geo/` directory holds tempting zone geometries; pulling that GeoJSON into a
  hosted app is arguably AGPL network-copyleft territory. If this project ever needs
  boundaries, use Natural Earth (public domain). See ADR 0006.
- The Electricity Maps web app cannot be embedded — see ADR 0006 for the CSP evidence.

## Sources

- <https://app.electricitymaps.com/api/docs/reference>
- <https://app.electricitymaps.com/api/docs/concepts-and-parameters>
- <https://app.electricitymaps.com/developer-hub/api/getting-started>
- <https://app.electricitymaps.com/api/docs/quick-start>
- <https://help.electricitymaps.com/en/articles/13168690-understanding-and-using-the-electricity-maps-api>
- <https://github.com/electricitymaps/if-electricitymaps> — response shape for `past-range`
