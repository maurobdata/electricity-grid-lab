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

The archive in use is **`maurobdata/electricity-grid-lab-recordings`** (private).

**1. Create the private archive repository.** It must be **private** — that is the whole
point. Any name works; the one above is what these docs assume.

**2. Point this checkout at it.**

If the archive already has commits, clone it:

```bash
make archive-init ARCHIVE=git@github.com:maurobdata/electricity-grid-lab-recordings.git
```

If it is **empty**, or you already have recordings on disk, `git clone` will not help —
initialise in place instead, because `recordings/` is where the data already is:

```bash
cd recordings
git init -b main
git remote add origin git@github.com:maurobdata/electricity-grid-lab-recordings.git
git add -A && git commit -m "Recordings archive"
git push -u origin main
```

**3. Add the token to the *archive* repository**, not to this one:
Settings → Secrets and variables → Actions → New repository secret, named
`ELECTRICITY_MAPS_API_TOKEN`.

**4. Allow the workflow to commit.** Settings → Actions → General → Workflow permissions →
**Read and write permissions**. The workflow asks for `contents: write`, but a repository
whose default is read-only caps it there and the push fails with a 403.

**5. Install the workflow in the archive repository:**

```bash
mkdir -p recordings/.github/workflows
cp ops/daily-recording.yml recordings/.github/workflows/
cd recordings && git add .github && git commit -m "Daily recording workflow" && git push
```

Then run it once by hand from the Actions tab — see the dispatch procedure below — and
leave it.

### An empty archive cannot be checked out

`actions/checkout` fails on a repository with no commits: there is no default branch to
resolve. Step 2 or step 5 gives it its first commit, so do one of them before the first
workflow run.

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

## Testing it by hand

The dispatch procedure, in order. Run it once after setup and after any change to the
workflow.

**1.** Archive repo → **Actions** → **daily-recording** → **Run workflow**.
Leave *"Re-record even if today is already present"* unticked. Branch `main`. Run.

**2.** Watch the run. Expected, in order:

| Step | Expected |
|---|---|
| Check out the archive | succeeds — fails here if the repo has no commits yet |
| Check out the lab | succeeds, no token used |
| Record today | `outcome  recorded`, five `ok` completeness lines, and `Recorded dk-dk2-<today>` |
| Commit the recording | `Recording <today>` pushed — or `Nothing new to commit.` if today was already in the archive |
| Report the archive | a summary naming the latest valid recording and any missing days |

**3.** Confirm the artifact landed: the archive repo should show a new commit containing
`dk-dk2-<today>.json` and an updated `index.json`.

**4.** Run it a second time, again unticked. This is the important one — it proves
idempotency in the real environment:

- **Record today** must print `outcome  already_present` and **no `emaps.request` lines at
  all**;
- **Commit the recording** must print `Nothing new to commit.`;
- the run must still be green.

**5.** Check the log for the token. Search the raw log for `auth-token` and for any 35-character
key-shaped string; GitHub masks secrets, but confirm the recorder is not printing one
anyway. `params=` lines show the query string only — zone, granularity, horizon — and
never a header.

If step 4 makes API calls, idempotency is broken and the schedule is spending the key twice
a day for nothing. Stop and investigate before leaving it running.

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
