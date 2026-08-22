"""Recording a scenario from live data, and replaying it deterministically.

Driven by the committed fixtures over a mock transport, so the recorder is exercised
offline against the shapes the API really returns.

The property that matters most here is round-tripping: a value recorded from the API must
come back out of a replay unchanged, still carrying where it came from. A recorder that
quietly rounded, reordered or relabelled would produce a file that looks fine and lies.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from gridlab.clock import FrozenClock
from gridlab.domain.models import (
    CarbonIntensity,
    FlowEdge,
    Flows,
    MixBreakdown,
    MixEntry,
    Provenance,
)
from gridlab.emaps import normalize
from gridlab.emaps.client import EMapsClient
from gridlab.scripts.record_scenario import Recorder, record
from gridlab.sources.replay import ReplaySource
from gridlab.store import scenario as sc

FIXTURES = Path("/app/fixtures")
ZONE = "DK-DK2"

pytestmark = pytest.mark.skipif(
    not FIXTURES.is_dir() or not list(FIXTURES.glob("*.json")),
    reason="no recorded fixtures mounted; run `make record` with a token",
)


def _fixture_handler(request: httpx.Request) -> httpx.Response:
    parts = [p for p in request.url.path.split("/") if p and p != "v4"]
    if request.url.params.get("zone") not in (None, ZONE):
        return httpx.Response(401, json={"error": "Request unauthorized for zoneKey."})

    # electricity-mix is recorded once per breakdownType, because the two are genuinely
    # different answers and a single fixture would make the toggle look broken.
    name = f"{parts[0]}__{parts[-1]}"
    breakdown = request.url.params.get("breakdownType")
    candidates = [f"{name}__{breakdown}", name] if breakdown else [name]

    for candidate in candidates:
        path = FIXTURES / f"{candidate}.json"
        if path.is_file():
            payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
            return httpx.Response(200, json=payload["body"])
    return httpx.Response(401, json={"error": f"Request unauthorized for {parts[0]}."})


@pytest.fixture
def client() -> Iterator[EMapsClient]:
    yield EMapsClient(
        token="test-token", transport=httpx.MockTransport(_fixture_handler), retries=0
    )


# --- the inverse converters -------------------------------------------------


def test_scalar_observation_round_trips() -> None:
    """Domain -> scenario point -> domain, unchanged."""
    original = CarbonIntensity(
        zone=ZONE,
        at=datetime(2026, 8, 22, 17, tzinfo=UTC),
        provenance=Provenance.LIVE,
        value=63.0,
        is_estimated=True,
    )
    point = sc.from_observation(original)
    restored = sc.to_carbon_intensity(point, zone=ZONE, provenance=Provenance.RECORDED)

    assert restored.value == original.value
    assert restored.at == original.at
    assert restored.is_estimated is True
    assert restored.provenance is Provenance.RECORDED


def test_mix_round_trips_and_recomputes_percentages() -> None:
    """Only megawatts are stored. Percentages are derived on load, so the two cannot
    drift apart in the file."""
    original = MixBreakdown(
        zone=ZONE,
        at=datetime(2026, 8, 22, 17, tzinfo=UTC),
        provenance=Provenance.LIVE,
        flow_traced=True,
        entries=(
            MixEntry(source="wind", power_mw=750.0, percent=75.0),
            MixEntry(source="gas", power_mw=250.0, percent=25.0),
        ),
    )
    restored = sc.to_mix(sc.from_mix(original), zone=ZONE, provenance=Provenance.RECORDED)

    assert restored.flow_traced is True
    assert restored.share("wind") == pytest.approx(75.0)
    assert restored.total_mw == pytest.approx(1000.0)


def test_flow_signs_survive_the_round_trip() -> None:
    """Sign is the whole meaning: positive is export, negative is import. Losing it would
    reverse who is carrying whom."""
    original = Flows(
        zone=ZONE,
        at=datetime(2026, 8, 22, 17, tzinfo=UTC),
        provenance=Provenance.LIVE,
        edges=(
            FlowEdge(counterpart_zone="DE", net_flow_mw=-308.0),
            FlowEdge(counterpart_zone="SE-SE4", net_flow_mw=453.0),
        ),
    )
    restored = sc.to_flows(sc.from_flows(original), zone=ZONE, provenance=Provenance.RECORDED)

    by_zone = {e.counterpart_zone: e.net_flow_mw for e in restored.edges}
    assert by_zone["DE"] == -308.0
    assert by_zone["SE-SE4"] == 453.0
    assert restored.net_import_mw == original.net_import_mw


# --- the recorder -----------------------------------------------------------


async def test_records_a_replayable_scenario(client: EMapsClient) -> None:
    scenario = await record(client, [ZONE], scenario_id="test-recording")

    assert scenario.provenance is Provenance.RECORDED
    assert scenario.zone_keys == (ZONE,)
    assert scenario.start < scenario.end

    data = scenario.zones[ZONE]
    assert data.carbon_intensity
    assert data.mix
    assert data.flows


async def test_both_mix_breakdowns_are_recorded(client: EMapsClient) -> None:
    """A recording with only one breakdown would silently remove the flow-tracing toggle —
    the most distinctive thing this data can show."""
    scenario = await record(client, [ZONE])
    kinds = {p.flow_traced for p in scenario.zones[ZONE].mix}
    assert kinds == {True, False}


async def test_forecasts_keep_the_time_they_were_issued(client: EMapsClient) -> None:
    """Without `issued_at` a stored forecast is just a second, wrong actuals series."""
    scenario = await record(client, [ZONE])
    forecasts = scenario.zones[ZONE].forecasts
    assert forecasts, "no forecast was recorded"

    for forecast in forecasts.values():
        assert forecast.issued_at is not None
        assert forecast.points
        assert forecast.horizon_hours > 0


async def test_the_window_covers_actuals_only(client: EMapsClient) -> None:
    """Forecasts describe hours that have not happened. If they extended the window, the
    replay clock would run into a stretch where every panel reads as empty."""
    scenario = await record(client, [ZONE])
    forecast = next(iter(scenario.zones[ZONE].forecasts.values()))

    assert max(p.at for p in scenario.zones[ZONE].carbon_intensity) <= scenario.end
    assert max(p.at for p in forecast.points) > scenario.end


async def test_estimation_flags_are_preserved_per_point(client: EMapsClient) -> None:
    """Electricity Maps models much of what it reports. A recording that forgot which
    values were measured would be a worse artefact than no recording."""
    scenario = await record(client, [ZONE])
    body = json.loads((FIXTURES / "carbon-intensity__history.json").read_text())
    # Via normalize.rows rather than a hard-coded envelope key: history uses `history`,
    # range endpoints use `data`, and latest is a bare object.
    expected = sum(1 for row in normalize.rows(body["body"]) if row.get("isEstimated"))

    recorded = sum(1 for p in scenario.zones[ZONE].carbon_intensity if p.is_estimated)
    assert recorded == expected


async def test_notes_say_it_is_recorded_and_when(client: EMapsClient) -> None:
    scenario = await record(client, [ZONE])
    assert "RECORDED" in scenario.notes
    assert "SYNTHETIC" not in scenario.notes.upper()


async def test_an_unreachable_signal_is_noted_not_raised(client: EMapsClient) -> None:
    """A plan that cannot reach a signal must produce a smaller scenario, not a crash."""
    recorder = Recorder(client)
    data, _ = await recorder.zone_data(ZONE)

    # Nothing was recorded for total-load/history, so it is missing and accounted for.
    assert data.load == ()
    assert any("total-load" in note for note in recorder.skipped)


async def test_a_zone_with_no_data_raises_rather_than_writing_a_broken_file() -> None:
    """A scenario with no window cannot be replayed. Failing here beats failing later and
    further from the cause."""
    denied = EMapsClient(
        token="t",
        transport=httpx.MockTransport(lambda r: httpx.Response(401, json={"error": "no"})),
        retries=0,
    )
    with pytest.raises(RuntimeError, match="no window to replay"):
        await record(denied, ["ZZ"])


async def test_multiple_zones_land_in_one_scenario(client: EMapsClient) -> None:
    """Cross-zone comparison is available on this plan, so a recording should support it.
    The second zone is refused here, which must not lose the first."""
    scenario = await record(client, [ZONE, "DE"])
    assert set(scenario.zone_keys) == {ZONE, "DE"}
    assert scenario.zones[ZONE].carbon_intensity


# --- replay -----------------------------------------------------------------


async def test_a_recording_replays_deterministically(client: EMapsClient) -> None:
    """The point of recording at all. Two reads at the same instant must be identical."""
    scenario = await record(client, [ZONE])
    moment = scenario.start + (scenario.end - scenario.start) / 2

    async def read() -> tuple[Any, ...]:
        source = ReplaySource(scenario, FrozenClock(moment))
        snapshot = await source.snapshot(ZONE)
        return (
            snapshot.carbon_intensity.value if snapshot.carbon_intensity else None,
            snapshot.mix.share("wind") if snapshot.mix else None,
            snapshot.flows.net_import_mw if snapshot.flows else None,
        )

    assert await read() == await read()


async def test_replayed_values_are_labelled_recorded_not_live(client: EMapsClient) -> None:
    """Provenance must survive the file. A replayed value is real, but it is not now."""
    scenario = await record(client, [ZONE])
    source = ReplaySource(scenario, FrozenClock(scenario.end))
    snapshot = await source.snapshot(ZONE)

    assert snapshot.provenance is Provenance.RECORDED
    assert snapshot.carbon_intensity is not None
    assert snapshot.carbon_intensity.provenance is Provenance.RECORDED


async def test_the_flow_tracing_toggle_works_after_a_round_trip(client: EMapsClient) -> None:
    scenario = await record(client, [ZONE])
    source = ReplaySource(scenario, FrozenClock(scenario.end))

    production = await source.mix(ZONE, flow_traced=False)
    consumption = await source.mix(ZONE, flow_traced=True)

    assert production is not None and consumption is not None
    assert production.flow_traced is False
    assert consumption.flow_traced is True


async def test_a_recording_survives_json(client: EMapsClient, tmp_path: Path) -> None:
    """It is written to disk and read back by a different process, so the file itself —
    not the in-memory object — has to be sufficient."""
    scenario = await record(client, [ZONE], scenario_id="disk-test")
    path = tmp_path / "disk-test.json"
    path.write_text(scenario.model_dump_json(indent=2), encoding="utf-8")

    library = sc.ScenarioLibrary(tmp_path)
    reloaded = library.require("disk-test")

    assert reloaded.provenance is Provenance.RECORDED
    assert reloaded.start == scenario.start
    assert len(reloaded.zones[ZONE].carbon_intensity) == len(scenario.zones[ZONE].carbon_intensity)


# --- the committed recording ------------------------------------------------


def test_committed_recordings_are_labelled_honestly() -> None:
    """Every scenario in the repo must declare what it is. A `recorded` scenario that was
    generated, or a `synthetic` one that does not say so, is the one failure mode this
    project cannot tolerate."""
    directory = Path("/app/scenarios")
    if not directory.is_dir():
        pytest.skip("scenarios not mounted")

    library = sc.ScenarioLibrary(directory)
    for scenario in library.all():
        if scenario.provenance is Provenance.RECORDED:
            assert "RECORDED" in scenario.notes
            assert scenario.zones, f"{scenario.id} claims to be recorded but has no zones"
        elif scenario.provenance is Provenance.SYNTHETIC:
            assert "SYNTHETIC" in scenario.notes.upper()
