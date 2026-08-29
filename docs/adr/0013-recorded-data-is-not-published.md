# 13. Recorded Electricity Maps data is not published

Date: 2026-08-26 · Status: Accepted

## Context

This repository is public. Until this decision it committed three recorded scenarios and
twenty-three raw API responses, and the recordings carried day-ahead price rows stamped
`"source": "nordpool.com"`.

The Electricity Maps Terms of Service list among **prohibited** activities:

> Reproduce, publish, resell, or otherwise make available Data or Unmodified Data to any
> third party, or use the Data as part of any data aggregation service, ETL pipeline, data
> connector, or similar product.

and separately, on third-party licensed data:

> the Client may not disclose, display, redistribute, or otherwise make Third-Party Licensed
> Data available externally (including through graphs, dashboards, or reports) without first
> obtaining a redistribution license directly from the relevant third-party provider

where the named providers are Nord Pool and EPEX — precisely the source of the measured
day-ahead prices in `price` and `price_forward`.

Sources, retrieved 26 August 2026:
[Terms of Service](https://help.electricitymaps.com/en/articles/11750446-terms-of-service),
[API access and restrictions](https://help.electricitymaps.com/en/articles/13335550-how-can-i-access-the-electricity-maps-api-and-are-there-any-restrictions).

This surfaced while designing the daily recorder, and it invalidated the obvious design.
"Commit the recording next to the code" is the cheapest possible preservation mechanism and
the one the licence does not permit.

## Decision

**Code is public. Electricity Maps data is private.**

- Recordings and raw fixtures live in a separate **private** repository, cloned into
  `./recordings`, which is gitignored here.
- `.gitignore` refuses `/recordings/`, `/fixtures/` and `scenarios/*.json`, with the two
  generated scenarios explicitly re-included: `dk2-wind-lull` and `es-solar-surplus` are
  ours, synthetic, and contain no measured value.
- The container mount points are unchanged — `/app/fixtures`, `/app/scenarios` — so nothing
  above the filesystem knows the difference.
- The already-published blobs are removed from history and the branch force-pushed. Removing
  them from the tip alone would leave them one `git log` away.

## Consequences

- **A public clone has no recordings and no fixtures.** It still runs: replay falls back to
  the bundled synthetic scenarios, which is the behaviour CLAUDE.md rule 7 already required
  and which is now exercised by default rather than in theory.
- **Three test modules skip themselves** — `test_fixtures`, `test_live`,
  `test_record_scenario` — because they assert against real API responses. They already
  guarded on the mount being present; that guard was written for a different reason and
  turns out to be the right one.
- The archive is a plain git repository, so history, diffing and recovery are unchanged. It
  is also where the daily workflow lives (ADR 0014).
- Cost: two repositories, and one setup step on a new machine (`make archive-init`).

## What this does *not* settle

**Showing day-ahead prices to an audience.** The Nord Pool / EPEX clause restricts external
*display*, including "graphs, dashboards, or reports", and the lab draws price charts — the
cheap-versus-clean comparison is built on them, and the demo leads with it. A hackathon run
by Electricity Maps is a setting where that is plausibly expected and permitted, but that is
an assumption, not a reading of the licence.

**Ask the organisers before 11 September.** The fallback, if the answer is no, is to show
carbon and mix and to describe the price relationship without plotting the prices, which
costs one panel rather than the demo.

## Reverse this if

A licence permitting redistribution is obtained — an event key, an academic grant, or
written permission — in which case the archive can be merged back and this whole split
disappears. Note that a redistribution licence from Electricity Maps still would not cover
the Nord Pool and EPEX rows, which are theirs to license.
