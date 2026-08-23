# 9. Derived values are first-class, and carry provenance

Date: 2026-08-23 · Status: Accepted · Extends [ADR 0004](0004-live-vs-replay-clock.md)

## Context

Grid Lab has served *measured* values since Phase 1, and ADR 0004 made one rule load-bearing
for all of them: every value carries a `provenance` — `live`, `recorded` or `synthetic` — and
that label reaches the UI. Synthetic data must never be mistakable for measured data.

The next thing the lab needs is values it **computes**: where the cheapest window sits, how
far apart cheap and clean are, whether today is unusual for this zone, what is worth looking
at right now. Three pressures make this necessary rather than optional.

1. **A dashboard waits to be interrogated.** It shows everything, ranks nothing, and leaves
   the reader to notice the negative price at 03:00 — which they will not, because noticing
   is work and the panel gives no reason to start.
2. **Numbers must not come from a language model.** A model asked for the cheapest window
   usually gets it right and occasionally does not, and the two answers look identical. An
   audience that suspects a model produced a number discounts every number beside it.
3. **Finding things is cheaper than being asked.** A detector runs on every poll for
   nothing. Asking a model to notice the same thing costs a request and a wait, per
   question, forever.

But a computed value is *more* dangerous than a measured one under the ADR 0004 rule, not
less. Arithmetic launders provenance: mix a recorded series with a synthetic one and the
result looks exactly like a number, with nothing on its face to say which half it came from.
And a derived number carries assumptions a measured one does not — a resampling policy, a
baseline window, a threshold — each of which changes what the number means.

## Decision

**1. A new package, `gridlab/analysis/`, holding pure functions over the domain models.**
No network, no clock, no cache, no model. Same series in, same answer out, in milliseconds,
pinnable against a committed fixture. The analysis layer may not reach past the source
interface, so every number it produces is checkable against a request a human could make
against `/api/v1/grid` themselves.

**2. Provenance propagates, taking the weakest input.** `weakest()` in `domain/models.py`
applies the same pessimism `Series.provenance` already applies to a run of points: one
generated input makes the whole result generated, however much measured data it was mixed
with.

**3. Every derived value carries a `Derived` record** — the method *and its parameters*
(`align.step_hold(cadence=3600s, max_hold=2 steps)`, not `"aligned"`), the `InputRef`s it
consumed, the resulting provenance, and `caveats`: what the number is **not**. Caveats are
written at the point of calculation, because that is the only place the limitation is
actually known. The marginal-versus-average caveat on any price/carbon comparison is the
canonical example, and it ships with the number rather than living in a footnote.

**4. `Finding` and `ViewIntent` are domain types.** A finding is something worth looking at,
detected deterministically, carrying its evidence and a stable `id`. It also carries a
`ViewIntent` — the view that would show it — which is what turns a list of observations into
navigation. `ViewIntent` is defined once here and mirrored in TypeScript, and it is the same
contract the agent will use to *propose* a view (ADR 0010).

**5. Refusing to answer is a supported outcome.** A percentile over four samples looks
exactly as authoritative as one over four hundred. A correlation over a flat series is
undefined, not zero. A window that would span a gap is a schedule nobody could run. In each
case the function returns nothing and says why, rather than returning a confident shape.

## Consequences

- The UI can say *where to look* before the user knows what to ask, with no model in the
  loop and no per-question cost.
- The agent's role narrows usefully: it explains what the analysis layer found instead of
  computing. Its answers become checkable against a deterministic result rather than against
  nothing.
- The one place the two mixes, price, flows and load can be joined honestly is now a single
  tested module rather than a chart's private opinion — `align.py`, whose policy is
  step-hold onto the coarser cadence with a bounded hold, disclosed on every result.
- Cost: another layer, and a discipline. Every new derived value has to decide its method
  string and its caveats, which is slower than returning a float. That slowness is the
  feature.

## Reverse this if

Nothing here is a good candidate for reversal wholesale, but two parts are:

- **The alignment policy.** Step-hold onto the coarser cadence is a choice among wrong
  answers. If forward price turns out to be quarter-hourly and carbon stays hourly, the cost
  of downsampling price becomes real, and interpolating carbon — with the result labelled as
  interpolated — may become the better wrong answer. Change the policy in `align.py`, change
  the method string with it, and never change one without the other.
- **`frontier.py` and anything that scores a trade-off.** Deliberately kept separate and
  flagged, because it is the most product-specific thing in the package and the product is
  still undecided ([ADR 0007](0007-defer-product-decision.md)).
