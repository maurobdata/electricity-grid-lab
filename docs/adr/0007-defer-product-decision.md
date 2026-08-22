# 7. The product decision is deferred, and the foundation must not presume it

Date: 2026-08-22 · Status: Accepted

## Context

Four independent research passes exist in `docs/research/`. They recommend four different
products and argue against each other:

- **BROWNOUT** — a status page and on-call system for the grid (SRE framing).
- **CHARGE** — a daily battery-scheduling puzzle scored against a computed optimum.
- **Windfall** — the grid delivered as a subscribable calendar feed.
- **THE REVEAL / WATTFOLIO** — daily prediction, and fantasy-league drafting of zones.

The design doc calls the SRE framing a trap. The strategy doc scores games below its
threshold. The foundation doc says both lose to the calendar. The idea atlas kills several
of the others outright. `PROJECT_CONTEXT.md` section 22 lists the final product as
explicitly undecided.

That is not a failure of research. Four capable analyses reaching four conclusions is
evidence that the question is genuinely open.

## Decision

Build an **Electricity Lab**, not a product. The foundation provides: a verified adapter, a
provider-neutral domain model, live/replay symmetry, a visualization shell, and a
tool-based agent. It contains **nothing** specific to any of the four candidates — no
calendar generation, no scoring or optimizer, no SLO engine, no draft mechanics.

Each candidate must be reachable from this foundation in hours. That is the acceptance test
for the architecture, and the only one that matters here.

## Consequences

- Some work will be thrown away. That is the price of not guessing, and it is cheaper than
  building the wrong thing well.
- The one thing the foundation *does* commit to is that real Electricity Maps data, both
  historical and forecast, is worth building on. Every one of the four agrees on that.
- When a product is chosen, that choice gets its own ADR superseding this one, stating what
  it was chosen over and why.

## Reverse this if

Evidence from prototyping — not from further analysis — makes one candidate clearly best.
Analysis has now been run four times and has not converged; more of it will not help.
