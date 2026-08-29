# 14. The recorder is a library; the scheduler is somebody else's problem

Date: 2026-08-26 · Status: Accepted

## Context

The free tier reaches back roughly 24 hours and `past` / `past-range` are 401
([ADR 0008](0008-history-not-breadth-is-the-constraint.md)). Whatever is reachable today is
gone tomorrow, and forecast-versus-outcome — the next product capability — cannot exist
without consecutive days of recordings that nobody can go back and collect.

Until now the trigger was a developer remembering to run `make scenario-live`. The archive
shows what that is worth: 22, 23 and 24 August recorded, then nothing. **25 August is
permanently lost**, and no amount of engineering will get it back.

[ADR 0011](0011-precomputed-artifacts-no-job-queue.md) already said scheduling "is the
operating system's job — Task Scheduler or cron running the same command. The lab does not
grow a scheduler." That was right and incomplete: it named a category, not a host, and every
host it implied is a laptop that is sometimes closed.

## Decision

**The recording capability is a function. The scheduler is a caller, and interchangeable.**

```
scheduler  →  make record-daily  →  run_daily(client_factory, archive, zones)  →  artifact
```

`gridlab.recording.daily.run_daily` takes a client factory and an archive and returns a
receipt. It knows nothing about cron, Docker, GitHub or argparse. Everything that could be
called a decision lives inside it:

- **whether to record at all** — a day already recorded *and complete* is skipped, with zero
  requests. This is what makes running it twice free.
- **whether to retry** — only failures that retrying can fix. A dropped connection gets
  another attempt; a 401 does not, and spending a hackathon key to be refused three times is
  worse than failing once.
- **whether the result is worth keeping** — completeness is judged separately from whether
  the requests succeeded, because a run can make twenty successful requests and produce
  something useless.
- **what to write, and when** — atomically, after re-reading it, and never over a good file.

The scheduler contains none of that. In the chosen deployment it is 90 lines of YAML whose
body is one `make` invocation.

**The chosen scheduler is GitHub Actions, hosted in the private archive repository**
(ADR 0013), twice daily. That placement is operational rather than architectural: it needs
no cross-repo token, its daily commit keeps the schedule from being auto-disabled after 60
idle days, and the API token then exists only in the private repository. See
[`ops/README.md`](../../ops/README.md).

### What was rejected

- **A queue, a broker, a worker container.** Same reasoning as ADR 0011: a service to run, a
  failure mode to explain, in a repository whose premise is `make up` and nothing else. The
  work is one command a day.
- **A scheduling sidecar in the compose stack.** It only runs when the stack runs, which
  means when the laptop is open. That is the problem, not the solution.
- **Task Scheduler on the workstation.** Same objection, and it also cannot be reviewed,
  version-controlled, or handed to anyone.

## Consequences

- Recording no longer depends on a person or a particular machine. A gap in the archive
  becomes visible — `make recordings` names the missing days — rather than being discovered
  months later by the analysis that needed them.
- Idempotency is load-bearing rather than incidental: the second daily run is a free retry,
  a manual run during the day is harmless, and re-running after a failure is the obvious
  correct action.
- Moving to another scheduler is deleting one YAML file. Nothing about the recording
  changes, and a test asserts the recorder runs with no CLI, no environment and no container.
- Cost: a workflow copied into another repository rather than referenced from this one, and
  one manual setup step.

## Reverse this if

The recording needs to happen more often than daily, or needs to react to something rather
than to a clock — at which point a schedule is the wrong shape and this becomes a service
rather than a cron line. Nothing currently wants that.

Also revisit if the archive stops being a git repository. Everything here assumes the
artifact is a file, committed, that a person can read and diff.
