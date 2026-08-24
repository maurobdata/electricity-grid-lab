# 11. Precomputed artifacts on disk, and no job queue

Date: 2026-08-24 · Status: Accepted

## Context

Some things the lab wants to show cannot be computed while somebody is waiting.

The cross-zone atlas is the concrete case. Forty-one European zones is eighty-two requests
against an API with **no published rate limit** ([ADR 0008](0008-history-not-breadth-is-the-constraint.md)),
taking about half a minute with a deliberate pause between zones. Doing that on a page load
would be slow, would hammer a key that has to survive until 11 September, and would put a
long uncached round trip in the middle of a demo. The same shape applies to anything else
that sweeps breadth rather than depth.

The reflex answer is a task queue — Celery, RQ, a worker container, a broker. That is a
service to run, a second failure mode, and a thing to explain, in a repository whose whole
premise is `make up` and nothing else. `README.md` lists exactly this under "deliberately
not built".

There is also already a working precedent in the repository, arrived at for a different
reason: `make probe` writes `data/capabilities.json`, the api container mounts `data/`
read-only, and `GET /api/v1/capabilities` serves whatever the last probe produced. That has
been in place since Phase 2 and has needed no maintenance.

## Decision

**Expensive derived data is produced by a script, written to a dated file in `data/`, and
served by a read-only endpoint.** No queue, no broker, no worker.

Concretely, for the atlas:

- `make atlas` runs `gridlab.scripts.build_atlas` against the live API.
- It writes `data/atlas-YYYY-MM-DD.json` **and** `data/atlas.json`. The dated file is the
  archive; the stable name is what the endpoint reads, so serving it needs no globbing.
- `GET /api/v1/atlas` reads that file and sorts it. It never computes and never fetches.
- Scheduling, if it is ever wanted, is the operating system's job — Task Scheduler or cron
  running the same command. The lab does not grow a scheduler.

Three properties are required of any such script, because they are what make a file an
acceptable substitute for a job system:

1. **Throttled**, with the pause configurable. The rate limit is undocumented, so the
   default is unhurried.
2. **Resumable.** `--resume` takes a previous artifact and skips zones already recorded.
   The expensive part is the requests; losing forty zones to a dropped connection at zone
   forty-one must not mean starting over.
3. **Honest about failure.** A zone that could not be scored is recorded with the reason
   rather than omitted, because "no day-ahead market here" is a result. The atlas cannot
   know in advance which zones those are — `has_day_ahead_price` from the capability probe
   is derived from the plan-level access list, which is identical for all 350 zones and so
   is `true` everywhere.

## Consequences

- Nothing new to run. `make up` is still the whole story, and the atlas endpoint degrades
  to a 404 that explains how to populate it.
- The artifact is inspectable, diffable and committable. A sweep can be read, argued with,
  and compared against yesterday's without a database.
- **The atlas has no replay equivalent, and this is worth saying plainly.** One zone's
  numbers can be recorded and replayed; a picture of every grid cannot, because the
  scenario format holds zones rather than sweeps. Without a token, the endpoint 404s.
- Staleness is visible rather than managed: `computed_at` is in the payload, and a reader
  can see the sweep is from yesterday. There is no cache invalidation because there is no
  cache — only a file somebody last wrote at a time it states.
- Cost: the data is as fresh as the last run, and nothing reminds you to run it. For a
  batch view of tomorrow's auction that is the right trade; for anything that must be
  current it would not be, which is the trigger below.

## Reverse this if

An artifact must refresh faster than a person can run a command — a live leaderboard, or
anything a second user's action should update for the first. At that point a file is the
wrong shape and a queue becomes the honest answer. Until then it is machinery serving a
requirement nobody has.

Also reconsider if a sweep grows past what fits comfortably in one file. Forty-one zones is
about 40 kB; all 350 would be roughly ten times that, still trivial. A year of daily sweeps
retained for comparison would not be.
