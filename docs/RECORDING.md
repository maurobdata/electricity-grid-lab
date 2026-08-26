# Recording, daily

Written for whoever has to work out, under time pressure, whether yesterday was captured.

**The problem this solves:** the key reaches back about 24 hours and `past-range` is 401
([ADR 0008](adr/0008-history-not-breadth-is-the-constraint.md)). A day nobody records is a
day nobody can ever record. 25 August 2026 is missing from the archive for exactly that
reason — someone forgot.

---

## The two commands

```bash
make record-daily    # record today, if today is not already recorded
make recordings      # what the archive holds, what is missing, how the last run went
```

`make record-daily` is safe to run at any time, as often as you like. If today is already
recorded and complete it makes **no API calls at all** and exits 0.

## How it is triggered

A GitHub Actions schedule in the private archive repository, at 05:17 and 15:17 UTC. Its
entire body is `make record-daily` — see [`ops/README.md`](../ops/README.md) for the setup
and [ADR 0014](adr/0014-daily-recording-scheduler-outside-the-lab.md) for why it lives
there rather than here.

Twice daily on purpose: the recorder is idempotent, so the afternoon run costs nothing when
the morning one worked, and is a free retry when it did not.

## Where the data goes

```
recordings/
├── dk-dk2-2026-08-26.json    one file per recorded day
├── dk-dk2-2026-08-24.json
└── index.json                the run ledger: every attempt, successful or not
```

`recordings/` is a clone of a **private** repository and is gitignored here. Recordings are
Electricity Maps data and their terms do not permit publishing it
([ADR 0013](adr/0013-recorded-data-is-not-published.md)). The api container mounts the
directory read-only, so the lab reads recordings exactly as it always read scenarios.

Raw API fixtures live in `recordings/fixtures/` for the same reason.

## How it decides a recording is missing

By looking at the artifact, not at the ledger — the file is the truth and the ledger only
describes attempts.

A day counts as recorded when `recordings/<zone>-<date>.json` exists **and** passes the
completeness check: recorded provenance, at least one zone, at least 12 carbon-intensity
points, a window of at least 12 hours, and at least one forecast with points.

The forecast requirement is not incidental. Actuals alone can be compared with nothing;
`issued_at` is what lets today's prediction be scored against tomorrow's measurement, which
is the entire reason for keeping an archive.

**A present-but-incomplete recording does not block a new one.** A thin file from a bad
night is replaced by today's good run rather than mistaken for success.

## How the app finds the latest valid scenario

`GRIDLAB_SCENARIO` names one explicitly. Left blank — which is the recommended setting — the
lab picks the newest **complete recording**, preferring a recording over a generated
scenario, and says which one it chose in the log:

```
gridlab.scenario_fallback  requested= using=dk-dk2-2026-08-26 provenance=recorded
```

It uses the same completeness judgement the recorder does, so the app and the archive cannot
disagree about what "usable" means. With no archive at all it falls back to the bundled
synthetic scenarios and still starts.

`GET /api/v1/recordings` reports the same thing over HTTP, including which days are missing.

## How failures are surfaced

The exit code, which turns the scheduled run red, and GitHub emails the repository owner.

| Exit | Outcome | Meaning |
|---|---|---|
| 0 | `recorded` | A new recording was written |
| 0 | `already_present` | Today was already recorded and complete. No requests were made |
| 1 | `incomplete` | The data came back too thin to keep. **Nothing was written** |
| 1 | `failed` | The requests or the write failed. **Nothing was written** |
| 2 | `misconfigured` | No API token. Fix the environment, not the run |

Every attempt is appended to `recordings/index.json` with its outcome, the reasons, how many
endpoints answered and how many were refused. Failures record the exception **class name**
only — messages quote URLs and parameters, and this file is committed.

The token never appears in an artifact, in the ledger, or in the output. A test asserts it.

## Recovering safely

**A failed run needs no cleanup.** Nothing was written, the previous recording is intact,
and no temporary file is left behind. Re-run `make record-daily`.

**A day was recorded badly.** `make record-daily ARGS=--force` re-records today over it.

**A day is missing.** If it has rolled out of the trailing 24-hour window it is gone; the
API cannot be asked for it. This is the failure the whole milestone exists to prevent, and
`make recordings` names those days so the loss is visible rather than silent.

**The archive is unreachable.** The lab runs without it, on the bundled synthetic scenarios,
with the badge reading `synthetic`. Never demo from that state without saying so.

**A corrupt ledger.** It reads as empty and the recording proceeds. Delete it if it offends;
it is diagnostic, not authoritative.

## Running it somewhere else

Have anything call `make record-daily` once a day. The recorder holds every decision, so
nothing about the recording changes when the trigger does — a test drives `run_daily`
directly with no CLI, no environment and no container to prove it.
