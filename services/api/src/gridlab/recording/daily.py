"""One recording per day, decided and validated rather than merely attempted.

    make record-daily

This is the whole of the recording capability, and it deliberately knows nothing about how
it was invoked. :func:`run_daily` takes a client factory and an archive and returns a
receipt. Cron, GitHub Actions, Task Scheduler and a person typing `make` are all the same
caller as far as this module is concerned — which is the property ADR 0014 is about, and the
reason moving to a different scheduler will not touch this file.

The sequence, and why each step is where it is:

1. **Decide.** If the archive already holds a *valid* recording for the day, stop. Zero
   requests, exit 0. This is what makes a twice-daily schedule cost nothing and a retry
   safe: running it again is not an error, it is a no-op.
2. **Record**, retrying only what retrying can fix. A dropped connection is worth another
   attempt in thirty seconds; a 401 is not, and hammering an API with a token it has
   already refused is how a key gets rate-limited before a hackathon.
3. **Judge.** A thin recording is a failure, not a small success. This is the step that
   stops a bad night from replacing a good yesterday.
4. **Write**, atomically, and only if step 3 passed.
5. **Log the attempt either way.** A failure that leaves no trace is a day that looks like
   it was never scheduled.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, date, datetime
from enum import StrEnum
from pathlib import Path

import structlog
from pydantic import BaseModel, ConfigDict

from gridlab.emaps import errors
from gridlab.emaps.client import EMapsClient
from gridlab.recording.archive import RunEntry, ScenarioArchive
from gridlab.recording.completeness import Completeness, assess
from gridlab.scripts.record_scenario import record
from gridlab.store.scenario import RecordingMeta, Scenario

log = structlog.get_logger(__name__)

#: Failures worth trying again.
#:
#: Transport, upstream 5xx and rate limiting are conditions of the moment. Everything else —
#: a bad token, a signal outside the plan, a zone that does not exist — is a condition of the
#: configuration, and will still be true in thirty seconds.
TRANSIENT: tuple[type[Exception], ...] = (
    errors.TransportError,
    errors.UpstreamError,
    errors.RateLimitError,
)

DEFAULT_ATTEMPTS = 3
DEFAULT_BACKOFF = 20.0
"""Seconds before the second attempt, doubling. Nobody is waiting on this run."""


class Outcome(StrEnum):
    """What a run did. The exit code is derived from this and nothing else."""

    RECORDED = "recorded"
    ALREADY_PRESENT = "already_present"
    INCOMPLETE = "incomplete"
    FAILED = "failed"
    MISCONFIGURED = "misconfigured"

    @property
    def exit_code(self) -> int:
        """0 for the two outcomes that mean "the archive holds today"."""
        if self in (Outcome.RECORDED, Outcome.ALREADY_PRESENT):
            return 0
        if self is Outcome.MISCONFIGURED:
            return 2
        return 1


class RunReceipt(BaseModel):
    """What happened, in enough detail to diagnose it without the logs."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    outcome: Outcome
    day: str
    scenario_id: str
    started_at: datetime
    finished_at: datetime
    attempts: int = 0
    path: Path | None = None
    completeness: Completeness | None = None
    error: str | None = None
    """Exception class name. Never the message — messages quote URLs and parameters."""

    message: str = ""

    @property
    def exit_code(self) -> int:
        return self.outcome.exit_code


async def _record_with_retry(
    client_factory: Callable[[], EMapsClient],
    zones: Sequence[str],
    *,
    scenario_id: str,
    granularity: str,
    day: date,
    attempts: int,
    backoff: float,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> tuple[Scenario | None, int, str | None]:
    """Record, retrying transient failures. Returns the scenario, attempts used, error name.

    A fresh client per attempt: a connection pool that has just failed is not the one to try
    again with, and the cost of building another is nothing next to the requests.
    """
    error: str | None = None
    for attempt in range(1, attempts + 1):
        try:
            async with client_factory() as client:
                scenario = await record(
                    client,
                    list(zones),
                    scenario_id=scenario_id,
                    granularity=granularity,
                    day=day,
                )
            return scenario, attempt, None
        except TRANSIENT as exc:
            error = type(exc).__name__
            log.warning(
                "gridlab.recording.transient",
                attempt=attempt,
                of=attempts,
                error=error,
            )
            if attempt < attempts:
                await sleep(backoff * (2 ** (attempt - 1)))
        except errors.ElectricityMapsError as exc:
            # A configuration failure. Retrying spends requests to be told the same thing.
            log.error("gridlab.recording.permanent", error=type(exc).__name__)
            return None, attempt, type(exc).__name__
        except RuntimeError as exc:
            # `record` raises this when no zone yielded actuals — usually a plan without
            # `history`. Not transient, and writing nothing is the correct response.
            log.error("gridlab.recording.no_window", error=str(exc)[:200])
            return None, attempt, "RuntimeError"

    return None, attempts, error


def _with_completeness(scenario: Scenario, verdict: Completeness) -> Scenario:
    """Stamp the verdict into the artifact.

    So that a file can be judged without re-deriving the judgement, and so that a later
    change to the thresholds cannot silently reinterpret what was already accepted.
    """
    if scenario.recording is None:
        return scenario
    meta = scenario.recording.model_copy(
        update={
            "complete": verdict.complete,
            "completeness_checks": dict(verdict.checks),
            "completeness_reasons": verdict.reasons,
        }
    )
    return scenario.model_copy(update={"recording": meta})


async def run_daily(
    *,
    client_factory: Callable[[], EMapsClient],
    archive: ScenarioArchive,
    zones: Sequence[str],
    granularity: str = "hourly",
    day: date | None = None,
    force: bool = False,
    attempts: int = DEFAULT_ATTEMPTS,
    backoff: float = DEFAULT_BACKOFF,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> RunReceipt:
    """Ensure the archive holds a complete recording for ``day``.

    Args:
        client_factory: Called once per attempt. A factory rather than a client so a retry
            gets a clean connection pool, and so tests can inject a transport that fails.
        archive: Where recordings live. The only thing this function writes to.
        force: Record even when a valid recording already exists. For re-recording a day
            that succeeded but was thin in a way the checks did not catch.
        sleep: Injected so tests do not wait through the backoff.

    Never raises for an operational failure. The receipt carries the outcome, because a
    scheduler needs an exit code rather than a traceback.
    """
    day = day or datetime.now(UTC).date()
    started = datetime.now(UTC)
    scenario_id = archive.scenario_id(list(zones), day)
    day_key = f"{day:%Y-%m-%d}"

    def receipt(
        outcome: Outcome,
        *,
        used: int = 0,
        path: Path | None = None,
        verdict: Completeness | None = None,
        error: str | None = None,
        message: str = "",
    ) -> RunReceipt:
        return RunReceipt(
            outcome=outcome,
            day=day_key,
            scenario_id=scenario_id,
            started_at=started,
            finished_at=datetime.now(UTC),
            attempts=used,
            path=path,
            completeness=verdict,
            error=error,
            message=message,
        )

    def remember(entry: RunReceipt, scenario: Scenario | None) -> None:
        meta: RecordingMeta | None = scenario.recording if scenario else None
        best = (
            max((len(z.carbon_intensity) for z in scenario.zones.values()), default=0)
            if scenario
            else None
        )
        endpoints = list(meta.endpoints) if meta else []
        archive.append_run(
            RunEntry(
                day=entry.day,
                scenario_id=entry.scenario_id,
                outcome=entry.outcome.value,
                started_at=entry.started_at,
                finished_at=entry.finished_at,
                attempts=entry.attempts,
                zones=tuple(zones),
                granularity=granularity,
                points=best,
                complete=entry.completeness.complete if entry.completeness else None,
                reasons=entry.completeness.reasons if entry.completeness else (),
                error=entry.error,
                endpoints_ok=sum(1 for e in endpoints if e.outcome == "ok") or None,
                endpoints_skipped=sum(1 for e in endpoints if e.outcome == "skipped") or None,
            )
        )

    # -- 1. decide -----------------------------------------------------------
    if not force and archive.has_valid_for(scenario_id):
        out = receipt(
            Outcome.ALREADY_PRESENT,
            path=archive.path_for(scenario_id),
            message=f"{scenario_id} is already recorded and complete. Nothing to do.",
        )
        log.info("gridlab.recording.already_present", scenario=scenario_id)
        remember(out, None)
        return out

    # -- 2. record -----------------------------------------------------------
    log.info("gridlab.recording.start", scenario=scenario_id, zones=list(zones))
    scenario, used, error = await _record_with_retry(
        client_factory,
        zones,
        scenario_id=scenario_id,
        granularity=granularity,
        day=day,
        attempts=attempts,
        backoff=backoff,
        sleep=sleep,
    )

    if scenario is None:
        out = receipt(
            Outcome.FAILED,
            used=used,
            error=error,
            message=(
                f"Recording {scenario_id} failed after {used} attempt(s) ({error}). "
                f"Nothing was written; any previous recording is untouched."
            ),
        )
        log.error("gridlab.recording.failed", scenario=scenario_id, error=error, attempts=used)
        remember(out, None)
        return out

    # -- 3. judge ------------------------------------------------------------
    verdict = assess(scenario)
    scenario = _with_completeness(scenario, verdict)

    if not verdict.complete:
        out = receipt(
            Outcome.INCOMPLETE,
            used=used,
            verdict=verdict,
            message=(
                f"{scenario_id} came back incomplete and was not written: "
                f"{'; '.join(verdict.reasons)}"
            ),
        )
        log.error(
            "gridlab.recording.incomplete", scenario=scenario_id, reasons=list(verdict.reasons)
        )
        remember(out, scenario)
        return out

    # -- 4. write ------------------------------------------------------------
    try:
        path = archive.write(scenario)
    except (OSError, ValueError) as exc:
        out = receipt(
            Outcome.FAILED,
            used=used,
            verdict=verdict,
            error=type(exc).__name__,
            message=(
                f"{scenario_id} was recorded but could not be written ({type(exc).__name__}). "
                f"Any previous recording is untouched."
            ),
        )
        log.error("gridlab.recording.write_failed", scenario=scenario_id, error=type(exc).__name__)
        remember(out, scenario)
        return out

    out = receipt(
        Outcome.RECORDED,
        used=used,
        path=path,
        verdict=verdict,
        message=f"Recorded {scenario_id} to {path}.",
    )
    log.info("gridlab.recording.recorded", scenario=scenario_id, path=str(path), attempts=used)
    remember(out, scenario)
    return out
