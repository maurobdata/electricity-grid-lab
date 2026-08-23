# 12. Forward day-ahead price comes from `combined`, and is not a forecast

Date: 2026-08-23 · Status: Accepted

## Context

Anything that relates price to carbon needs both signals pointing **forward**. Carbon
intensity forecasts reach 72 hours on this plan ([ADR 0008](0008-history-not-breadth-is-the-constraint.md)).
Price appeared not to, and the most recent product research treats forward price as its
single critical risk — the thing that, if absent, removes the market half of every concept
built on the price/carbon relationship.

It is not absent. Three facts, all measured rather than assumed:

1. **The token already has it.** `data/capabilities.json`, written by `make probe` on
   22 August 2026, lists `price-day-ahead` access as `actual, combined, forecast, history,
   latest`.
2. **`combined` reaches into the future.** The committed fixture
   `fixtures/price-day-ahead__combined.json`, recorded at 20:03 UTC, holds 25 hourly rows
   spanning `2026-08-22T20:00Z` .. `2026-08-23T20:00Z` — a full day beyond the moment of
   recording — every one labelled `source: nordpool.com`.
3. **The auction clearing is visible in the rows.** `createdAt` reads `2026-08-21T11:30Z`
   for the first two rows and `2026-08-22T11:29Z` from 22:00Z onward. SDAC clears at 12:00
   CET for the following delivery day; that step is the clearing, in the data.

Meanwhile `price-day-ahead/forecast` is the wrong door. It rejects `horizonHours` —
`400 "Missing or invalid date parameter \"start\""` — and `emaps/signals.py` has refused it
locally, via `FORECAST_NEEDS_WINDOW`, since the matrix was written.

So the gap was never access. It was plumbing: `scripts/record_scenario.py` carried the
comment *"`combined` is the better forward view and is left for a later pass"*, and nothing
above the client had a way to ask for it.

## Decision

**1. Forward price is served from `price-day-ahead/combined`.** `GridSource` gains
`price_forward(zone)`, implemented by both sources and exposed as
`GET /api/v1/grid/{zone}/price/forward`.

**2. It is a separate method, not `forecast(signal="price")`, and a separate path, not a
`signal` parameter on `/forecast`.** A day-ahead price is an **auction result published
ahead of delivery**, not a prediction of one. Filing it among forecasts invites every
consumer above this layer to treat it as a model output and to score it against an outcome
it already is. The API agrees, by refusing the horizon-shaped call.

**3. The response is split at the clock; only the forward half is returned.** `combined`
reaches backwards as well as forwards, and the backward half is what `history` already
answers. Serving it under two names lets a chart overlaying them draw one hour twice.

**4. `source` is preserved to the UI, and into recordings.** `combined` interleaves cleared
auction prices with Electricity Maps' modelled ones, and `source` is the only field that
distinguishes them once the envelope is gone. Scenarios gain a `PricePoint` that carries it.

**5. `issued_at` is the newest `updatedAt` among the forward rows** — when the auction that
set them was published — not the wall clock. Prices for one period can be re-published, and
*when was this known* is a different question from *when does it apply*.

**6. Generated prices carry neither.** A synthetic scenario has no exchange and no clearing
time, so both fields are null and a test enforces it. These two fields are what survives
being quoted out of the UI, and forging them would forge the only evidence that a real
market spoke.

## Consequences

- The forward window in which price **and** carbon are both known is bounded by price, at
  roughly **24 hours** — not the 72 that carbon alone offers. Mix, flows and load forecasts
  are 24 hours only, so any cross-signal forward analysis is a one-day object. This is now
  documented in `docs/electricity-maps-api.md` rather than discovered later.
- Recordings made from today carry forward price. **`scenarios/dk-dk2-2026-08-22.json` does
  not** — it predates this — so replaying it returns 404 for forward price, with a message
  saying so and naming the fix. Re-record with `make scenario-live`.
- The synthetic scenarios offer their own price series as the forward view, clipped at the
  replay clock, so the path is exercised on a fresh clone with no key.
- One less reason to want a deeper key. Forward price was assumed to need one; it does not.

## Reverse this if

`price-day-ahead/forecast` with an explicit `start`/`end` turns out to give a **longer or
cleaner** window than `combined` — it has never been called once — or if `combined` proves
not to extend past +24 h when fetched shortly after the noon clearing. Both are on the
validation list in `docs/electricity-maps-api.md` and cost one request each.

Note also that the fixture is **hourly**. European day-ahead has cleared in 15-minute market
time units since 1 October 2025, so `temporalGranularity=15_minutes` may return 96 points
for tomorrow instead of 24. That is unverified on this signal, and nothing here assumes it.
