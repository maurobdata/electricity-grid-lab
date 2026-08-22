# 8. The free-tier constraint is history, not breadth

Date: 2026-08-22 · Status: Accepted · Amends the assumptions behind ADR 0004 and 0007

## Context

Every research pass in `docs/research/` expected participant API access to be limited by
**breadth**. The Green Web Foundation reported free access narrowed to a single region, and
all four documents treated "you may only get one zone" as the highest-leverage unknown —
the thing that would kill comparison, flow stories and anything league-shaped.

A free-tier token was obtained and probed on 22 August 2026. The expectation was wrong in
both directions:

- **350 zones are accessible.** 189 Tier A, 2 Tier B, 146 Tier C. The `access` list is
  identical for every one of them, so access is plan-level, not zone-level.
- **`past` and `past-range` return 401 for every signal.** `history` returns only the
  trailing ~24 hours. `daily` granularity is rejected.

So the constraint is **depth**, not breadth.

## Decision

1. **Build multi-zone freely.** Comparison, cross-border flows and cross-zone simultaneity
   are all available today and need no special handling.
2. **Treat arbitrary history as unavailable until a deeper key exists.** Anything that
   needs a real historical window — scoring a forecast against its outcome, replaying a
   named storm, backtesting a strategy — cannot be demonstrated on this key.
3. **`LiveSource.history()` falls back from `past-range` to `history`** when the former is
   refused, and clips the result to the requested window. 24 hours is much less than asked
   for, but it is the only history this key has, and leaving it unreachable would be worse.
4. **Record scenarios from the rolling window now, and re-record later.** `make record` and
   `scenarios/` exist for exactly this. What is reachable today is gone tomorrow.

## Consequences

- ADR 0004 said replay exists because a demo should not depend on the live grid. It now has
  a second and stronger reason: **replay is the only way to show a historical event at all**
  on this plan.
- The `SUPPORTED` matrix keeps `past` and `past-range`, because the *API* offers them. What
  a plan grants is a separate axis, answered by `capabilities.py` from the published
  `access` list. Conflating "the API has it" with "we can call it" would make the matrix
  wrong the moment a better key arrives.
- Re-run `make probe` the day a trial or event key is issued. If `past-range` appears, the
  forecast-error and event-replay directions reopen, and that reopening should be an
  explicit, dated decision rather than something noticed by accident.

## Reverse this if

A trial or event key grants `past`/`past-range`. Verify with `make probe` rather than
assuming — and record the new result here, because the difference changes which of the four
candidate products are buildable.
