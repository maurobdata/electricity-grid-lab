"""The daily recorder: idempotency, partial writes, failure, and what it preserves.

Every test here is offline and deterministic. The recorder is driven through a mock
transport, and the two properties that matter most are asserted directly rather than
implied:

* a run that fails or comes back thin **never** replaces a good recording;
* a day already recorded costs **zero** requests, so a schedule can be as eager as it likes.

The upstream here is hand-written rather than the committed fixtures, because the fixtures
now live in a private archive (ADR 0013) and a public clone has none. Tests that need the
real API shapes still live in ``test_record_scenario.py`` and skip when it is not mounted.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from gridlab.domain.models import Provenance
from gridlab.emaps.client import EMapsClient
from gridlab.recording.archive import ScenarioArchive
from gridlab.recording.completeness import assess
from gridlab.recording.daily import Outcome, run_daily
from gridlab.store.scenario import Scenario

ZONE = "DK-DK2"
TOKEN = "secret-token-do-not-leak"
DAY = date(2026, 8, 26)


# --- a synthetic upstream ---------------------------------------------------


def _rows(count: int) -> list[dict[str, Any]]:
    """One row shape every normalizer can read.

    ``value`` serves carbon intensity, both percentages, load and price, because each of
    those normalizers falls back to it; the breakdowns and the unit serve mix, flows and
    price. Values stay in the twenties so the same number is a plausible percentage as well
    as a plausible price.
    """
    base = datetime(2026, 8, 25, 12, tzinfo=UTC)
    return [
        {
            "zone": ZONE,
            "datetime": (base + timedelta(hours=h)).isoformat(),
            "updatedAt": base.isoformat(),
            "isEstimated": False,
            "value": 20.0 + h,
            "unit": "EUR/MWh",
            "source": "nordpool.com",
            "powerConsumptionBreakdown": {"wind": 900.0, "gas": 100.0},
            "powerProductionBreakdown": {"wind": 1400.0, "gas": 100.0},
            "powerExportBreakdown": {"DE": 250.0, "SE-SE4": 120.0},
            "powerImportBreakdown": {"DE": 500.0, "SE-SE4": 0.0},
        }
        for h in range(count)
    ]


def _handler(
    *,
    history: int = 24,
    forecast: int = 24,
    fail: type[Exception] | None = None,
    status: int = 200,
) -> Callable[[httpx.Request], httpx.Response]:
    """A stand-in for the API, parameterised by the failure being simulated."""

    def handle(request: httpx.Request) -> httpx.Response:
        if fail is not None:
            raise fail("simulated")
        if status != 200:
            return httpx.Response(status, json={"error": "simulated"})

        path = request.url.path
        if "forecast" in path:
            return httpx.Response(200, json={"zone": ZONE, "forecast": _rows(forecast)})
        if "history" in path:
            return httpx.Response(200, json={"zone": ZONE, "history": _rows(history)})
        return httpx.Response(200, json={"zone": ZONE, "data": _rows(24)})

    return handle


def _client_factory(**kwargs: Any) -> Callable[[], EMapsClient]:
    def make() -> EMapsClient:
        return EMapsClient(
            token=TOKEN, transport=httpx.MockTransport(_handler(**kwargs)), retries=0
        )

    return make


def _exploding_factory(seen: list[int]) -> Callable[[], EMapsClient]:
    """A client that fails the test if it is ever asked for anything."""

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(1)
        raise AssertionError(f"a request was made that should have been skipped: {request.url}")

    def make() -> EMapsClient:
        return EMapsClient(token=TOKEN, transport=httpx.MockTransport(handle), retries=0)

    return make


async def _noop_sleep(_seconds: float) -> None:
    """Backoff without the waiting."""


def _thin_file(archive: ScenarioArchive, scenario_id: str, day: str) -> Path:
    """A recording that is real, parseable, and not worth keeping."""
    archive.directory.mkdir(parents=True, exist_ok=True)
    path = archive.path_for(scenario_id)
    path.write_text(
        json.dumps(
            {
                "id": scenario_id,
                "title": "thin",
                "provenance": "recorded",
                "start": f"{day}T00:00:00+00:00",
                "end": f"{day}T02:00:00+00:00",
                "zones": {
                    ZONE: {"carbon_intensity": [{"at": f"{day}T00:00:00+00:00", "value": 100.0}]}
                },
                "notes": "RECORDED but barely",
            }
        ),
        encoding="utf-8",
    )
    return path


@pytest.fixture
def archive(tmp_path: Path) -> ScenarioArchive:
    return ScenarioArchive(tmp_path / "recordings")


# --- the happy path ---------------------------------------------------------


async def test_records_a_complete_day(archive: ScenarioArchive) -> None:
    receipt = await run_daily(
        client_factory=_client_factory(),
        archive=archive,
        zones=[ZONE],
        day=DAY,
        sleep=_noop_sleep,
    )

    assert receipt.outcome is Outcome.RECORDED
    assert receipt.exit_code == 0
    assert receipt.scenario_id == "dk-dk2-2026-08-26"
    assert receipt.path is not None and receipt.path.is_file()

    scenario = archive.load("dk-dk2-2026-08-26")
    assert scenario is not None
    assert scenario.provenance is Provenance.RECORDED
    assert assess(scenario).complete


async def test_the_artifact_says_which_day_when_and_from_where(archive: ScenarioArchive) -> None:
    """The questions a later analysis will ask of a file it did not write."""
    await run_daily(
        client_factory=_client_factory(), archive=archive, zones=[ZONE], day=DAY, sleep=_noop_sleep
    )
    scenario = archive.load("dk-dk2-2026-08-26")

    assert scenario is not None and scenario.recording is not None
    meta = scenario.recording
    assert meta.day == "2026-08-26"
    assert meta.recorded_at.tzinfo is not None
    assert meta.api_base_url.startswith("https://")
    assert meta.zones == (ZONE,)
    assert meta.complete is True

    # Which endpoints were used, not merely which data survived.
    used = {(e.signal, e.temporality) for e in meta.endpoints if e.outcome == "ok"}
    assert ("carbon-intensity", "history") in used
    assert ("carbon-intensity", "forecast") in used


async def test_the_forecast_is_kept_with_its_issue_time(archive: ScenarioArchive) -> None:
    """The single field that makes forecast-versus-outcome possible later. Without it a
    stored forecast is just a second, wrong actuals series."""
    await run_daily(
        client_factory=_client_factory(), archive=archive, zones=[ZONE], day=DAY, sleep=_noop_sleep
    )
    scenario = archive.load("dk-dk2-2026-08-26")

    assert scenario is not None
    forecasts = scenario.zones[ZONE].forecasts
    assert forecasts
    for forecast in forecasts.values():
        assert forecast.issued_at is not None
        assert forecast.horizon_hours > 0


# --- idempotency ------------------------------------------------------------


async def test_a_recorded_day_costs_no_requests(archive: ScenarioArchive) -> None:
    """The property the whole schedule rests on: running it again is a no-op, not an error.

    Asserted by handing the second run a transport that raises if it is touched at all.
    """
    first = await run_daily(
        client_factory=_client_factory(), archive=archive, zones=[ZONE], day=DAY, sleep=_noop_sleep
    )
    assert first.outcome is Outcome.RECORDED

    seen: list[int] = []
    second = await run_daily(
        client_factory=_exploding_factory(seen),
        archive=archive,
        zones=[ZONE],
        day=DAY,
        sleep=_noop_sleep,
    )

    assert second.outcome is Outcome.ALREADY_PRESENT
    assert second.exit_code == 0
    assert seen == [], "a request was made for a day already recorded"


async def test_recording_twice_does_not_change_the_file(archive: ScenarioArchive) -> None:
    await run_daily(
        client_factory=_client_factory(), archive=archive, zones=[ZONE], day=DAY, sleep=_noop_sleep
    )
    path = archive.path_for("dk-dk2-2026-08-26")
    before = path.read_bytes()

    await run_daily(
        client_factory=_client_factory(), archive=archive, zones=[ZONE], day=DAY, sleep=_noop_sleep
    )

    assert path.read_bytes() == before


async def test_force_re_records_a_present_day(archive: ScenarioArchive) -> None:
    """The escape hatch. Idempotency has to be overridable, or a day that passed the checks
    while still being wrong is stuck forever."""
    await run_daily(
        client_factory=_client_factory(), archive=archive, zones=[ZONE], day=DAY, sleep=_noop_sleep
    )
    receipt = await run_daily(
        client_factory=_client_factory(),
        archive=archive,
        zones=[ZONE],
        day=DAY,
        force=True,
        sleep=_noop_sleep,
    )

    assert receipt.outcome is Outcome.RECORDED


async def test_an_invalid_existing_recording_is_replaced(archive: ScenarioArchive) -> None:
    """Duplicate detection keys on *valid*, not on *present*. A thin file from a bad night
    must not block today's good recording."""
    path = _thin_file(archive, "dk-dk2-2026-08-26", "2026-08-26")
    assert not assess(Scenario.model_validate_json(path.read_text(encoding="utf-8"))).complete

    receipt = await run_daily(
        client_factory=_client_factory(), archive=archive, zones=[ZONE], day=DAY, sleep=_noop_sleep
    )

    assert receipt.outcome is Outcome.RECORDED
    replaced = archive.load("dk-dk2-2026-08-26")
    assert replaced is not None and assess(replaced).complete


# --- failure ----------------------------------------------------------------


async def test_a_transport_failure_is_retried_then_reported(archive: ScenarioArchive) -> None:
    waits: list[float] = []

    async def spy(seconds: float) -> None:
        waits.append(seconds)

    receipt = await run_daily(
        client_factory=_client_factory(fail=httpx.ConnectError),
        archive=archive,
        zones=[ZONE],
        day=DAY,
        attempts=3,
        backoff=10.0,
        sleep=spy,
    )

    assert receipt.outcome is Outcome.FAILED
    assert receipt.exit_code == 1
    assert receipt.attempts == 3
    assert waits == [10.0, 20.0], "backoff should widen, and not sleep after the last attempt"


async def test_an_auth_failure_is_not_retried(archive: ScenarioArchive) -> None:
    """A 401 will still be a 401 in thirty seconds. Retrying spends requests from a key that
    has to last until 11 September, to be told the same thing three times."""
    waits: list[float] = []

    async def spy(seconds: float) -> None:
        waits.append(seconds)

    receipt = await run_daily(
        client_factory=_client_factory(status=401),
        archive=archive,
        zones=[ZONE],
        day=DAY,
        attempts=3,
        sleep=spy,
    )

    assert receipt.outcome is Outcome.FAILED
    assert receipt.attempts == 1
    assert waits == []


async def test_a_failed_run_leaves_yesterdays_recording_untouched(
    archive: ScenarioArchive,
) -> None:
    """The requirement stated as a test: a failure must never destroy a success."""
    await run_daily(
        client_factory=_client_factory(),
        archive=archive,
        zones=[ZONE],
        day=date(2026, 8, 25),
        sleep=_noop_sleep,
    )
    yesterday = archive.path_for("dk-dk2-2026-08-25")
    before = yesterday.read_bytes()

    receipt = await run_daily(
        client_factory=_client_factory(status=500),
        archive=archive,
        zones=[ZONE],
        day=DAY,
        attempts=1,
        sleep=_noop_sleep,
    )

    assert receipt.outcome is Outcome.FAILED
    assert yesterday.read_bytes() == before
    assert not archive.path_for("dk-dk2-2026-08-26").exists()


async def test_an_empty_upstream_writes_nothing(archive: ScenarioArchive) -> None:
    """Every signal refused: `record` raises rather than writing a window-less file, and the
    runner turns that into an exit code instead of a traceback."""
    receipt = await run_daily(
        client_factory=_client_factory(status=401),
        archive=archive,
        zones=[ZONE],
        day=DAY,
        attempts=1,
        sleep=_noop_sleep,
    )

    assert receipt.outcome is Outcome.FAILED
    assert list(archive.paths()) == []


async def test_a_thin_recording_is_rejected_with_reasons(archive: ScenarioArchive) -> None:
    """Three hours of data is a successful set of requests and a useless artifact."""
    receipt = await run_daily(
        client_factory=_client_factory(history=3, forecast=0),
        archive=archive,
        zones=[ZONE],
        day=DAY,
        sleep=_noop_sleep,
    )

    assert receipt.outcome is Outcome.INCOMPLETE
    assert receipt.exit_code == 1
    assert receipt.completeness is not None and not receipt.completeness.complete
    assert receipt.completeness.reasons
    assert not archive.path_for("dk-dk2-2026-08-26").exists(), "an incomplete run wrote a file"


# --- partial writes ---------------------------------------------------------


async def test_a_write_that_dies_partway_leaves_the_previous_file_intact(
    archive: ScenarioArchive,
) -> None:
    await run_daily(
        client_factory=_client_factory(),
        archive=archive,
        zones=[ZONE],
        day=date(2026, 8, 25),
        sleep=_noop_sleep,
    )
    path = archive.path_for("dk-dk2-2026-08-25")
    before = path.read_bytes()

    def explode(_src: Any, _dst: Any) -> None:
        raise OSError("killed during rename")

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(os, "replace", explode)
        receipt = await run_daily(
            client_factory=_client_factory(),
            archive=archive,
            zones=[ZONE],
            day=date(2026, 8, 25),
            force=True,
            sleep=_noop_sleep,
        )

    assert receipt.outcome is Outcome.FAILED
    assert path.read_bytes() == before
    assert not list(archive.directory.glob(".*.tmp")), "temporary debris left behind"


async def test_the_archive_never_shows_a_half_written_file(archive: ScenarioArchive) -> None:
    """Stated directly: during a write the canonical path holds the old file or the new one,
    never a prefix of either."""
    await run_daily(
        client_factory=_client_factory(), archive=archive, zones=[ZONE], day=DAY, sleep=_noop_sleep
    )
    path = archive.path_for("dk-dk2-2026-08-26")
    observed: list[str] = []
    real = os.replace

    def watch(src: Any, dst: Any) -> None:
        # The ledger is written through the same helper; only the recording is under test.
        if Path(dst).name == path.name:
            observed.append(Scenario.model_validate_json(Path(dst).read_text(encoding="utf-8")).id)
        real(src, dst)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(os, "replace", watch)
        await run_daily(
            client_factory=_client_factory(),
            archive=archive,
            zones=[ZONE],
            day=DAY,
            force=True,
            sleep=_noop_sleep,
        )

    assert observed == ["dk-dk2-2026-08-26"]
    assert path.is_file()


# --- discovery --------------------------------------------------------------


async def test_latest_valid_prefers_complete_over_merely_newer(archive: ScenarioArchive) -> None:
    await run_daily(
        client_factory=_client_factory(),
        archive=archive,
        zones=[ZONE],
        day=date(2026, 8, 24),
        sleep=_noop_sleep,
    )
    _thin_file(archive, "dk-dk2-2026-08-27", "2026-08-27")

    latest = archive.latest_valid()
    assert latest is not None and latest.id == "dk-dk2-2026-08-24"


async def test_missing_days_are_reported(archive: ScenarioArchive) -> None:
    """Every gap is permanent: the API cannot be asked for a day that has rolled out of the
    trailing window, so naming them is the only remedy available."""
    for day in (date(2026, 8, 24), date(2026, 8, 26)):
        await run_daily(
            client_factory=_client_factory(),
            archive=archive,
            zones=[ZONE],
            day=day,
            sleep=_noop_sleep,
        )

    assert archive.missing_days(date(2026, 8, 24), date(2026, 8, 26)) == ["2026-08-25"]


# --- the ledger -------------------------------------------------------------


async def test_every_outcome_reaches_the_ledger(archive: ScenarioArchive) -> None:
    await run_daily(
        client_factory=_client_factory(), archive=archive, zones=[ZONE], day=DAY, sleep=_noop_sleep
    )
    await run_daily(
        client_factory=_client_factory(status=500),
        archive=archive,
        zones=[ZONE],
        day=date(2026, 8, 27),
        attempts=1,
        sleep=_noop_sleep,
    )

    ledger = archive.ledger()
    assert [run.outcome for run in ledger.runs] == ["recorded", "failed"]
    assert ledger.by_day()["2026-08-27"].error


async def test_a_corrupt_ledger_does_not_stop_a_recording(archive: ScenarioArchive) -> None:
    """The ledger describes the archive; it is not the archive. A damaged one must never
    cost a day."""
    archive.directory.mkdir(parents=True)
    archive.ledger_path.write_text("{ this is not json", encoding="utf-8")

    receipt = await run_daily(
        client_factory=_client_factory(), archive=archive, zones=[ZONE], day=DAY, sleep=_noop_sleep
    )

    assert receipt.outcome is Outcome.RECORDED


# --- credentials ------------------------------------------------------------


async def test_the_token_reaches_neither_the_artifact_nor_the_ledger(
    archive: ScenarioArchive, capsys: pytest.CaptureFixture[str]
) -> None:
    """Artifacts are pushed to an archive and logs get pasted into issues. Neither may ever
    carry the key."""
    await run_daily(
        client_factory=_client_factory(), archive=archive, zones=[ZONE], day=DAY, sleep=_noop_sleep
    )
    await run_daily(
        client_factory=_client_factory(status=401),
        archive=archive,
        zones=[ZONE],
        day=date(2026, 8, 27),
        attempts=1,
        sleep=_noop_sleep,
    )

    for path in [*archive.paths(), archive.ledger_path]:
        assert TOKEN not in path.read_text(encoding="utf-8"), f"token leaked into {path.name}"

    captured = capsys.readouterr()
    assert TOKEN not in captured.out
    assert TOKEN not in captured.err


async def test_a_failure_record_keeps_the_class_not_the_message(archive: ScenarioArchive) -> None:
    """Error messages quote the URL and its parameters. The class name says as much about
    what to do next and cannot carry a query string."""
    await run_daily(
        client_factory=_client_factory(status=401),
        archive=archive,
        zones=[ZONE],
        day=DAY,
        attempts=1,
        sleep=_noop_sleep,
    )

    error = archive.ledger().runs[-1].error
    assert error in {"AccessDeniedError", "AuthenticationError"}
    assert "http" not in (error or "").lower()


# --- scheduler independence -------------------------------------------------


async def test_the_recorder_runs_with_no_cli_no_env_and_no_container(tmp_path: Path) -> None:
    """The claim ADR 0014 makes, tested rather than asserted: the recording capability is a
    function taking a client and a directory. Whatever calls it is interchangeable."""
    receipt = await run_daily(
        client_factory=_client_factory(),
        archive=ScenarioArchive(tmp_path / "anywhere"),
        zones=[ZONE],
        day=DAY,
        sleep=_noop_sleep,
    )

    assert receipt.outcome is Outcome.RECORDED
    assert (tmp_path / "anywhere" / "dk-dk2-2026-08-26.json").is_file()


async def test_the_scenario_library_ignores_the_ledger(archive: ScenarioArchive) -> None:
    """The bug that took the whole API down the first time an archive was mounted.

    `index.json` sits beside the recordings and is not one. The library globs `*.json`, so
    without an exception it tried to validate the run log as a Scenario and the app refused
    to start — a failure that only appears once there is a ledger to trip over, which is to
    say once the recorder has run for real.
    """
    from gridlab.store.scenario import ScenarioLibrary

    await run_daily(
        client_factory=_client_factory(), archive=archive, zones=[ZONE], day=DAY, sleep=_noop_sleep
    )
    assert archive.ledger_path.is_file(), "no ledger was written, so this proves nothing"

    library = ScenarioLibrary(archive.directory)
    assert [s.id for s in library.all()] == ["dk-dk2-2026-08-26"]
