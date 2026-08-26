# Operations — the daily recording

One command, run twice a day by something that is not your laptop.

```bash
make record-daily      # record today, if today is not already recorded
make recordings        # what the archive holds, what is missing, how the last run went
```

Everything else on this page is setup you do once.

---

## Why the archive is a separate repository

Electricity Maps' terms list among prohibited activities:

> Reproduce, publish, resell, or otherwise make available Data or Unmodified Data to any
> third party […]

and day-ahead prices carry a second restriction: Nord Pool and EPEX data may not be
disclosed or displayed externally without a redistribution licence from those providers.

`electricity-grid-lab` is public. So the code is here and the data is not — recordings and
raw fixtures live in a **private** repository mounted at `./recordings`, which is gitignored
here. See [ADR 0013](../docs/adr/0013-recorded-data-is-not-published.md).

---

## One-time setup

**1. Create the private archive repository.** Any name; `electricity-grid-lab-data` is the
one the docs assume. It must be **private**.

**2. Point this checkout at it.**

```bash
make archive-init ARCHIVE=git@github.com:maurobdata/electricity-grid-lab-data.git
```

That clones it into `./recordings`. If you already have recordings locally, move them in
and push — the archive is just a directory of JSON files.

**3. Add the token to the *archive* repository**, not to this one:
Settings → Secrets and variables → Actions → New repository secret,
named `ELECTRICITY_MAPS_API_TOKEN`.

**4. Copy the workflow into the archive repository:**

```bash
mkdir -p ../electricity-grid-lab-data/.github/workflows
cp ops/daily-recording.yml ../electricity-grid-lab-data/.github/workflows/
```

Commit and push it. Run it once by hand from the Actions tab to confirm, then leave it.

### Why the workflow lives in the archive repo and not here

Three reasons, and each one removes a failure mode:

- **No cross-repo token.** A workflow pushing to a *different* repository needs a personal
  access token stored as a secret. One that pushes to its own needs only the built-in
  `GITHUB_TOKEN`, which expires when the job ends.
- **The schedule cannot go stale.** GitHub disables scheduled workflows after 60 days
  without repository activity. The archive gets a commit every day it records, so it is
  never idle. This repository could easily be quiet for two months after the hackathon.
- **The token is in the private repository only.** The public one holds no secrets at all.

The cost is that the workflow is copied rather than referenced. It is versioned here so it
is reviewed with the recorder, and it is 90 lines that change roughly never.

---

## What it does

```
schedule (05:17 and 15:17 UTC)
   ↓
make record-daily
   ↓
gridlab.recording.daily.run_daily()
   ↓
recordings/<zone>-<date>.json  +  recordings/index.json
   ↓
committed to the private archive
```

Twice a day on purpose. The recorder is idempotent, so if the morning run worked the
afternoon one makes no API calls and exits 0 — which makes the second slot a free retry for
a morning when Electricity Maps or the network was unwell.

## When it fails

The run goes red and GitHub emails the repository owner, which is the whole alerting
mechanism and is deliberately not more than that. The step summary carries `make recordings`
output, so the failure and the state of the archive are on the same page.

| Exit | Meaning | What to do |
|---|---|---|
| 0 | Recorded, or already recorded | Nothing |
| 1 | Failed, or the result was incomplete | Read the reasons. Nothing was written; the previous recording is intact |
| 2 | No API token | Fix the secret, not the run |

A failure never destroys a good recording, so the safe response to any red run is to look
before acting. `make record-daily` by hand will re-attempt the same day.

## Moving to another scheduler

Delete the workflow and have anything else run `make record-daily` daily. Task Scheduler,
cron, a NAS, a CI system, a person. The recorder holds every decision — see
[ADR 0014](../docs/adr/0014-daily-recording-scheduler-outside-the-lab.md) — so nothing about
the recording changes when the trigger does.
