"""The recordings on disk, and the log of every attempt to make one.

One directory holds one file per recorded day, named as ``make scenario-live`` has always
named them — ``<zone>-<YYYY-MM-DD>.json`` — plus ``index.json``, the ledger. The naming
convention is load-bearing: it is how "have we already recorded today?" is answered without
opening every file, and changing it would orphan every existing recording.

Two properties matter more than anything else here.

**A write either lands whole or does not land.** The new file is written beside the target,
read back, and re-validated as a :class:`Scenario` before it replaces anything. A recording
that parses in memory and not on disk is exactly the failure that would be discovered weeks
later, by the analysis that needed it.

**A failure never destroys a success.** Nothing is deleted, nothing is truncated, and the
canonical filename is only ever reached by an artifact that has already been judged
complete. A run that fails leaves yesterday's archive exactly as it was.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import structlog
from pydantic import BaseModel, ConfigDict, Field

from gridlab.domain.models import Provenance
from gridlab.recording.completeness import Completeness, assess
from gridlab.store.atomic import write_atomic
from gridlab.store.scenario import Scenario

log = structlog.get_logger(__name__)

LEDGER_NAME = "index.json"

#: How many run entries the ledger keeps.
#:
#: One entry per attempt, two attempts a day: a year is about 730. The cap exists so the
#: file cannot grow without bound if something schedules it every minute by accident.
MAX_RUNS = 2000


class RunEntry(BaseModel):
    """One attempt to record a day, successful or not."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    day: str
    scenario_id: str
    outcome: str
    """``recorded`` | ``already_present`` | ``incomplete`` | ``failed`` | ``misconfigured``."""

    started_at: datetime
    finished_at: datetime
    attempts: int = 1
    zones: tuple[str, ...] = ()
    granularity: str = "hourly"
    points: int | None = None
    """Carbon-intensity points in the best zone. The quickest read on whether a day is thin."""

    complete: bool | None = None
    reasons: tuple[str, ...] = ()
    error: str | None = None
    """The exception *class name*. Never the message — messages quote URLs and parameters."""

    endpoints_ok: int | None = None
    endpoints_skipped: int | None = None


class Ledger(BaseModel):
    """Every attempt, newest last, plus the derived per-day view."""

    model_config = ConfigDict(extra="forbid")

    updated_at: datetime | None = None
    runs: list[RunEntry] = Field(default_factory=list)

    def latest_run(self) -> RunEntry | None:
        return self.runs[-1] if self.runs else None

    def by_day(self) -> dict[str, RunEntry]:
        """The last outcome for each day. A later success supersedes an earlier failure."""
        seen: dict[str, RunEntry] = {}
        for run in self.runs:
            previous = seen.get(run.day)
            if previous is None or run.finished_at >= previous.finished_at:
                seen[run.day] = run
        return seen


class ScenarioArchive:
    """A directory of daily recordings.

    Deliberately not a database. The archive is a handful of JSON files a person can read,
    diff and copy — which is the same reasoning ADR 0011 applied to the atlas, and the
    reason nothing here needs a service to be running.
    """

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    # --- naming -------------------------------------------------------------

    @staticmethod
    def scenario_id(zones: tuple[str, ...] | list[str], day: date) -> str:
        """``<first zone, lowercased>-<YYYY-MM-DD>``.

        Unchanged from what ``record_scenario`` has always generated, so an archive written
        before the daily runner existed is still an archive it understands.
        """
        return f"{zones[0].lower()}-{day:%Y-%m-%d}"

    def path_for(self, scenario_id: str) -> Path:
        return self.directory / f"{scenario_id}.json"

    # --- reading ------------------------------------------------------------

    def paths(self) -> Iterator[Path]:
        if not self.directory.is_dir():
            return
        for path in sorted(self.directory.glob("*.json")):
            if path.name != LEDGER_NAME:
                yield path

    def load(self, scenario_id: str) -> Scenario | None:
        """One recording, or ``None`` if it is absent or unreadable.

        Unreadable counts as absent on purpose: a corrupt file should let today's run
        replace it, not stop the run with a parse error.
        """
        path = self.path_for(scenario_id)
        if not path.is_file():
            return None
        try:
            return Scenario.model_validate_json(path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            log.warning("gridlab.recording.unreadable", path=str(path), error=type(exc).__name__)
            return None

    def all(self) -> list[Scenario]:
        scenarios: list[Scenario] = []
        for path in self.paths():
            try:
                scenarios.append(Scenario.model_validate_json(path.read_text(encoding="utf-8")))
            except (ValueError, OSError) as exc:
                log.warning(
                    "gridlab.recording.unreadable", path=str(path), error=type(exc).__name__
                )
        return scenarios

    def has_valid_for(self, scenario_id: str) -> bool:
        """Is there already a recording for this day that is good enough to keep?

        The whole of idempotency rests on this one question. Answering it from the artifact
        rather than from the ledger is deliberate: the file is the truth, the ledger is a
        record of attempts, and a ledger that disagreed with the directory must never be
        able to cause a good recording to be overwritten.
        """
        scenario = self.load(scenario_id)
        return scenario is not None and assess(scenario).complete

    def latest_valid(self) -> Scenario | None:
        """The newest complete recording in the archive.

        Ordering is by the window's end, matching ``LabState._fallback``, so a recording
        whose id does not follow the convention still lands in the right place.
        """
        valid = [s for s in self.all() if assess(s).complete]
        if not valid:
            return None
        return max(valid, key=lambda s: s.end)

    def days(self) -> list[str]:
        """Every day the archive holds a recording for, oldest first."""
        seen = set()
        for scenario in self.all():
            if scenario.recording is not None:
                seen.add(scenario.recording.day)
            else:
                # Recorded before `recording` existed: fall back to the window's end, which
                # is what the filename was derived from anyway.
                seen.add(f"{scenario.end:%Y-%m-%d}")
        return sorted(seen)

    def missing_days(self, since: date, until: date) -> list[str]:
        """Days in ``[since, until]`` with no recording. The gaps, stated plainly."""
        have = set(self.days())
        out: list[str] = []
        cursor = since
        while cursor <= until:
            key = f"{cursor:%Y-%m-%d}"
            if key not in have:
                out.append(key)
            cursor = date.fromordinal(cursor.toordinal() + 1)
        return out

    # --- writing ------------------------------------------------------------

    def write(self, scenario: Scenario) -> Path:
        """Write a recording so that a reader sees either the old one or the new one.

        Raises:
            ValueError: if what landed on disk does not read back as the same scenario.
                Raised *before* the rename, so the previous recording is untouched.
        """
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.path_for(scenario.id)
        payload = scenario.model_dump_json(indent=2) + "\n"

        # Round-trip through the serialized form before anything is replaced. A model that
        # serializes but does not deserialize is rare and catastrophic: it would be found
        # by the next boot of the API, or by an analysis in October.
        try:
            restored = Scenario.model_validate_json(payload)
        except ValueError as exc:
            raise ValueError(f"{scenario.id} does not survive serialization: {exc}") from exc
        if restored.id != scenario.id or restored.end != scenario.end:
            raise ValueError(f"{scenario.id} changed identity on serialization")

        write_atomic(path, payload)
        return path

    # --- the ledger ---------------------------------------------------------

    @property
    def ledger_path(self) -> Path:
        return self.directory / LEDGER_NAME

    def ledger(self) -> Ledger:
        """The run log. A corrupt or absent ledger reads as empty rather than raising.

        The ledger is diagnostic, not authoritative. Letting a damaged one stop a recording
        would trade the thing that matters for the thing that describes it.
        """
        path = self.ledger_path
        if not path.is_file():
            return Ledger()
        try:
            return Ledger.model_validate_json(path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            log.warning("gridlab.ledger.unreadable", path=str(path), error=type(exc).__name__)
            return Ledger()

    def append_run(self, entry: RunEntry) -> None:
        ledger = self.ledger()
        ledger.runs.append(entry)
        if len(ledger.runs) > MAX_RUNS:
            del ledger.runs[: len(ledger.runs) - MAX_RUNS]
        ledger.updated_at = datetime.now(UTC)
        self.directory.mkdir(parents=True, exist_ok=True)
        write_atomic(self.ledger_path, ledger.model_dump_json(indent=2) + "\n")

    # --- reporting ----------------------------------------------------------

    def status(self, *, today: date | None = None) -> dict[str, Any]:
        """What an operator wants to know: what is here, what is missing, what last happened."""
        today = today or datetime.now(UTC).date()
        ledger = self.ledger()
        latest = self.latest_valid()
        days = self.days()
        since = date.fromisoformat(days[0]) if days else today

        return {
            "directory": str(self.directory),
            "exists": self.directory.is_dir(),
            "recordings": len(days),
            "days": days,
            "missing_days": self.missing_days(since, today),
            "latest_valid": (
                {
                    "id": latest.id,
                    "start": latest.start.isoformat(),
                    "end": latest.end.isoformat(),
                    "provenance": latest.provenance.value,
                    "recorded_at": (
                        latest.recording.recorded_at.isoformat() if latest.recording else None
                    ),
                    "zones": list(latest.zone_keys),
                }
                if latest
                else None
            ),
            "last_run": (
                ledger.latest_run().model_dump(mode="json") if ledger.latest_run() else None
            ),
            "runs": len(ledger.runs),
        }


def is_recorded(scenario: Scenario) -> bool:
    """Convenience for callers that only care whether a scenario is measured data."""
    return scenario.provenance is Provenance.RECORDED


def completeness_of(scenario: Scenario) -> Completeness:
    """Re-exported so callers need one import rather than two."""
    return assess(scenario)
