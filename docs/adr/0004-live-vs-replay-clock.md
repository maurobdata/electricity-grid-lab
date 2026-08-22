# 4. Live and replay are the same code path, separated by a Clock

Date: 2026-08-22 · Status: Accepted

## Context

Three constraints point the same way:

1. A 14-day Electricity Maps trial started now expires before 11 September, so the
   foundation must be fully buildable and testable **with no live key at all**.
2. A hackathon demo must not depend on the live grid doing something interesting at 17:00,
   or on the venue wifi working.
3. Tests over a live API are slow and non-deterministic.

## Decision

Introduce a `Clock` protocol with two implementations: `LiveClock` (wall time) and
`ReplayClock` (starts at a scenario `t0`, advances at a speed multiplier). Every read goes
through a `GridSource` that takes the clock's `now()`; `LiveSource` and `ReplaySource`
satisfy the same interface, so nothing above them knows which is running.

Recorded scenarios live in `scenarios/` and are committed.

Every value carries a `provenance` field — `live`, `recorded`, or `synthetic` — that is
propagated all the way to a badge in the UI.

## Consequences

- Replay is not a fallback bolted on late; it is the default mode, and therefore always
  works.
- The test suite is deterministic and offline.
- Historical replay doubles as a feature: forecast-versus-actual divergence is only visible
  when you can wind a real day forward.
- The `provenance` field is load-bearing, not decorative. Synthetic data must never be able
  to be mistaken for measured data — on stage or in a screenshot.
