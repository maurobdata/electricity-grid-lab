"""Replay: deterministic, offline, and honest about where its numbers came from."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from gridlab.clock import FrozenClock
from gridlab.domain.models import Provenance
from gridlab.sources.replay import ReplaySource
from gridlab.store.scenario import Scenario, ScenarioLibrary


def at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 2, 4, hour, minute, tzinfo=UTC)


def source(scenario: Scenario, hour: int, minute: int = 0) -> ReplaySource:
    return ReplaySource(scenario, FrozenClock(at(hour, minute)))


# --- lookup semantics -------------------------------------------------------


async def test_value_holds_until_the_next_sample(scenario: Scenario) -> None:
    """Grid data is stepwise: an hourly value stands until the next one lands.

    Interpolating instead would invent numbers that were never published.
    """
    assert (await source(scenario, 1, 0).carbon_intensity("DK-DK2")).value == 200.0
    assert (await source(scenario, 1, 59).carbon_intensity("DK-DK2")).value == 200.0
    assert (await source(scenario, 2, 0).carbon_intensity("DK-DK2")).value == 300.0


async def test_before_the_first_sample_there_is_nothing(scenario: Scenario) -> None:
    """Not a zero. A zero would plot as a spectacularly clean grid."""
    before = ReplaySource(scenario, FrozenClock(at(0) - timedelta(hours=5)))
    assert await before.carbon_intensity("DK-DK2") is None


async def test_unknown_zone_returns_nothing_rather_than_raising(scenario: Scenario) -> None:
    assert await source(scenario, 1).carbon_intensity("PL") is None


# --- provenance -------------------------------------------------------------


async def test_every_value_carries_the_scenario_provenance(scenario: Scenario) -> None:
    """The load-bearing guarantee: generated data can never look measured."""
    src = source(scenario, 0)
    for observation in (
        await src.carbon_intensity("DK-DK2"),
        await src.price("DK-DK2"),
        await src.mix("DK-DK2"),
        await src.flows("DK-DK2"),
        await src.load("DK-DK2"),
        await src.renewable_percentage("DK-DK2"),
    ):
        assert observation is not None
        assert observation.provenance is Provenance.SYNTHETIC


async def test_estimation_flag_survives_replay(scenario: Scenario) -> None:
    assert (await source(scenario, 2).carbon_intensity("DK-DK2")).is_estimated is True
    assert (await source(scenario, 1).carbon_intensity("DK-DK2")).is_estimated is False


# --- the flow-traced distinction --------------------------------------------


async def test_flow_traced_and_production_mixes_are_separate_series(scenario: Scenario) -> None:
    """The consumption mix includes imported gas; the production mix is pure wind.

    Serving one when the other was asked for would silently misattribute a fifth of the
    grid, and the chart would look completely plausible.
    """
    consumption = await source(scenario, 0).mix("DK-DK2", flow_traced=True)
    production = await source(scenario, 0).mix("DK-DK2", flow_traced=False)

    assert consumption is not None and production is not None
    assert consumption.flow_traced is True
    assert production.flow_traced is False
    assert {e.source for e in consumption.entries} == {"wind", "gas"}
    assert {e.source for e in production.entries} == {"wind"}
    assert consumption.share("wind") == pytest.approx(90.0)


# --- flows ------------------------------------------------------------------


async def test_import_export_sign_convention(scenario: Scenario) -> None:
    early = await source(scenario, 0).flows("DK-DK2")
    late = await source(scenario, 3).flows("DK-DK2")
    assert early is not None and late is not None

    assert early.net_import_mw == pytest.approx(-200.0)  # net exporter when windy
    assert late.net_import_mw == pytest.approx(1000.0)  # net importer when the wind drops


# --- forecast vs actual -----------------------------------------------------


async def test_forecast_is_the_issued_forecast_not_the_outcome(scenario: Scenario) -> None:
    """The whole point of storing both. If replay silently returned actuals, every
    forecast-error experiment built on this foundation would quietly measure zero."""
    src = source(scenario, 3)
    series = await src.forecast("DK-DK2", signal="carbon_intensity", horizon_hours=24)
    actual = await src.carbon_intensity("DK-DK2")

    assert series is not None and actual is not None
    assert series.issued_at == at(0)
    assert series.points[-1].value == 240.0
    assert actual.value == 400.0


async def test_forecast_keeps_points_already_elapsed(scenario: Scenario) -> None:
    """Trimming the elapsed part would delete exactly the comparison worth showing."""
    series = await source(scenario, 3).forecast("DK-DK2")
    assert series is not None
    assert [p.at.hour for p in series.points] == [0, 1, 2, 3]


async def test_horizon_truncates_the_forecast(scenario: Scenario) -> None:
    series = await source(scenario, 0).forecast("DK-DK2", horizon_hours=2)
    assert series is not None
    assert [p.at.hour for p in series.points] == [0, 1, 2]


# --- forward price ----------------------------------------------------------


async def test_price_forward_is_clipped_at_the_clock(scenario: Scenario) -> None:
    """The opposite of the forecast rule, and deliberately so.

    A forecast is kept over its elapsed hours because the gap against what happened is the
    comparison worth seeing. A cleared price laid over the hour it settled is the same
    number twice, and `history` already answers for it.
    """
    series = await source(scenario, 2).price_forward("DK-DK2")
    assert series is not None
    assert [p.at.hour for p in series.points] == [2, 3]


async def test_price_forward_keeps_who_set_the_price(scenario: Scenario) -> None:
    """`source` is the only thing separating a settled auction result from a model.

    `combined` returns both kinds interleaved in one series, so losing this field would
    blend a market outcome with an estimate and leave no way to tell afterwards.
    """
    series = await source(scenario, 0).price_forward("DK-DK2")
    assert series is not None
    sources = [getattr(p, "source", "missing") for p in series.points]
    assert sources == ["nordpool.com", "nordpool.com", "nordpool.com", None]


async def test_price_forward_carries_scenario_provenance(scenario: Scenario) -> None:
    series = await source(scenario, 0).price_forward("DK-DK2")
    assert series is not None
    assert series.provenance is Provenance.SYNTHETIC
    assert series.issued_at == at(0)


async def test_price_forward_runs_out_at_the_end_of_the_window(scenario: Scenario) -> None:
    """Past the last cleared period there is nothing — not a flat line held forever.

    Day-ahead prices exist only out to the end of the delivery day the auction covered.
    Extending the final value would invent a market result for hours nobody has bid on.
    """
    exhausted = ReplaySource(scenario, FrozenClock(at(3) + timedelta(hours=1)))
    assert await exhausted.price_forward("DK-DK2") is None


async def test_price_forward_is_absent_from_a_scenario_recorded_without_it(
    scenario_dict: dict[str, object],
) -> None:
    """Scenarios recorded before forward price existed must still load and still serve.

    They simply have no forward view. Failing to parse them would make every recording made
    before today unplayable, which is the opposite of what a dated archive is for.
    """
    zones: Any = scenario_dict["zones"]
    zones["DK-DK2"].pop("price_forward")
    older = Scenario.model_validate(scenario_dict)

    assert await ReplaySource(older, FrozenClock(at(0))).price_forward("DK-DK2") is None
    assert (await ReplaySource(older, FrozenClock(at(0))).price("DK-DK2")) is not None


async def test_price_forward_is_nothing_for_an_unknown_zone(scenario: Scenario) -> None:
    assert await source(scenario, 0).price_forward("PL") is None


# --- history ----------------------------------------------------------------


async def test_history_respects_its_window(scenario: Scenario) -> None:
    series = await source(scenario, 3).history(
        "DK-DK2", signal="carbon_intensity", start=at(1), end=at(2)
    )
    assert series is not None
    assert [p.value for p in series.points] == [200.0, 300.0]


async def test_history_of_price_keeps_the_currency(scenario: Scenario) -> None:
    """Summing prices across zones without the currency is a category error."""
    series = await source(scenario, 3).history("DK-DK2", signal="price", start=at(0), end=at(3))
    assert series is not None
    assert all(getattr(p, "currency", None) == "EUR" for p in series.points)
    assert series.points[0].value == -12.5


# --- snapshot ---------------------------------------------------------------


async def test_snapshot_gathers_everything_available(scenario: Scenario) -> None:
    snapshot = await source(scenario, 0).snapshot("DK-DK2")
    assert snapshot.carbon_intensity is not None
    assert snapshot.price is not None
    assert snapshot.mix is not None
    assert snapshot.flows is not None
    assert snapshot.unavailable == ()


async def test_snapshot_reports_what_is_missing_instead_of_hiding_it(
    scenario_dict: dict[str, object],
) -> None:
    """ "We asked and there was nothing" and "we never asked" must not look identical.

    A zone with no price at all is the realistic case: day-ahead price is Europe-plus-a-few
    and is often outside a free-tier plan, so the UI must be able to say "not available
    here" rather than leaving a blank card.
    """
    zones = scenario_dict["zones"]
    assert isinstance(zones, dict)
    zones["DK-DK2"]["price"] = []
    zones["DK-DK2"]["flows"] = []

    stripped = Scenario.model_validate(scenario_dict)
    snapshot = await source(stripped, 3).snapshot("DK-DK2")

    assert "price" in snapshot.unavailable
    assert "flows" in snapshot.unavailable
    assert snapshot.carbon_intensity is not None
    assert "carbon_intensity" not in snapshot.unavailable


async def test_snapshot_of_an_unknown_zone_says_so(scenario: Scenario) -> None:
    snapshot = await source(scenario, 0).snapshot("PL")
    assert snapshot.unavailable == ("zone not in this scenario",)


# --- comparison -------------------------------------------------------------


async def test_compare_is_simultaneous(scenario: Scenario) -> None:
    results = await source(scenario, 1).compare(["DK-DK2", "PL"])
    assert results["DK-DK2"] is not None
    assert results["DK-DK2"].value == 200.0
    assert results["PL"] is None


async def test_compare_rejects_a_signal_it_cannot_compare(scenario: Scenario) -> None:
    with pytest.raises(ValueError, match="Cannot compare"):
        await source(scenario, 1).compare(["DK-DK2"], signal="mix")


# --- the library ------------------------------------------------------------


def test_library_loads_scenarios_from_disk(scenarios_dir: Path) -> None:
    library = ScenarioLibrary(scenarios_dir)
    assert len(library) == 1
    assert "test-scenario" in library


def test_missing_scenario_error_lists_what_exists(scenarios_dir: Path) -> None:
    """This error is likely to be read under time pressure. It should be actionable."""
    library = ScenarioLibrary(scenarios_dir)
    with pytest.raises(KeyError) as exc:
        library.require("nope")
    assert "test-scenario" in str(exc.value)
    assert "make scenario" in str(exc.value)


def test_an_empty_directory_is_not_an_error(tmp_path: Path) -> None:
    assert len(ScenarioLibrary(tmp_path / "missing")) == 0


def test_bundled_scenarios_are_valid_and_labelled() -> None:
    """The committed scenarios must parse, and must not claim to be measured data."""
    directory = Path("/app/scenarios")
    if not directory.is_dir() or not list(directory.glob("*.json")):
        pytest.skip("bundled scenarios not mounted")

    library = ScenarioLibrary(directory)
    assert len(library) >= 1
    for scenario in library.all():
        assert scenario.provenance in {Provenance.SYNTHETIC, Provenance.RECORDED}
        if scenario.provenance is Provenance.SYNTHETIC:
            assert "SYNTHETIC" in scenario.notes.upper(), (
                f"{scenario.id} is synthetic but its notes do not say so. That note is "
                f"what stops a generated chart being shown as measured data."
            )


def test_a_generated_price_never_claims_an_auction_set_it() -> None:
    """`source` and `issued_at` are the two fields that say a real market spoke.

    A synthetic scenario has no exchange and no clearing time, and filling either with
    something plausible would forge the one piece of evidence that separates a settled
    day-ahead result from a shape somebody made up. The provenance badge says `synthetic`
    either way; these fields are what survives being quoted out of the UI.
    """
    directory = Path("/app/scenarios")
    if not directory.is_dir() or not list(directory.glob("*.json")):
        pytest.skip("bundled scenarios not mounted")

    for scenario in ScenarioLibrary(directory).all():
        if scenario.provenance is not Provenance.SYNTHETIC:
            continue
        for zone, data in scenario.zones.items():
            if data.price_forward is None:
                continue
            assert data.price_forward.issued_at is None, (
                f"{scenario.id}/{zone} is synthetic but names a time its prices cleared"
            )
            assert not any(p.source for p in data.price_forward.points), (
                f"{scenario.id}/{zone} is synthetic but names an exchange that set its prices"
            )


def test_the_fallback_scenario_is_the_newest_recording(tmp_path: Path) -> None:
    """Filename order is chronological for date-stamped recordings, so taking the first
    reliably chose the *oldest* data on disk. By 11 September there will be a fortnight of
    these, and a typo in GRIDLAB_SCENARIO would quietly boot the lab into the stalest one —
    which, before forward price was captured, also meant the degraded feature set.
    """
    from gridlab.config import Mode, Settings
    from gridlab.web.state import LabState

    directory = tmp_path / "scenarios"
    directory.mkdir()
    for day, provenance in (("2026-09-01", "recorded"), ("2026-09-09", "recorded")):
        _write_scenario(directory, f"dk-dk2-{day}", provenance, day)
    _write_scenario(directory, "zzz-synthetic", "synthetic", "2026-12-31")

    state = LabState.build(
        Settings(
            gridlab_mode=Mode.REPLAY,
            gridlab_scenario="does-not-exist",
            gridlab_scenarios_dir=directory,
            gridlab_db_path=tmp_path / "x.duckdb",
            electricity_maps_api_token=None,
            anthropic_api_key=None,
            gridlab_capabilities_path=tmp_path / "none.json",
        )
    )
    assert state.scenario is not None
    assert state.scenario.id == "dk-dk2-2026-09-09"


def test_the_fallback_prefers_a_recording_over_a_generated_scenario(tmp_path: Path) -> None:
    """A synthetic default is a demo waiting to be given on made-up numbers, even when the
    generated window happens to be more recent."""
    from gridlab.config import Mode, Settings
    from gridlab.web.state import LabState

    directory = tmp_path / "scenarios"
    directory.mkdir()
    _write_scenario(directory, "real", "recorded", "2026-09-01")
    _write_scenario(directory, "made-up", "synthetic", "2026-12-31")

    state = LabState.build(
        Settings(
            gridlab_mode=Mode.REPLAY,
            gridlab_scenario="missing",
            gridlab_scenarios_dir=directory,
            gridlab_db_path=tmp_path / "y.duckdb",
            electricity_maps_api_token=None,
            anthropic_api_key=None,
            gridlab_capabilities_path=tmp_path / "none.json",
        )
    )
    assert state.scenario is not None
    assert state.scenario.id == "real"


def _write_scenario(directory: Path, scenario_id: str, provenance: str, day: str) -> None:
    import json as _json

    directory.joinpath(f"{scenario_id}.json").write_text(
        _json.dumps(
            {
                "id": scenario_id,
                "title": scenario_id,
                "provenance": provenance,
                "start": f"{day}T00:00:00+00:00",
                "end": f"{day}T03:00:00+00:00",
                "granularity": "hourly",
                "notes": "SYNTHETIC" if provenance == "synthetic" else "",
                "zones": {
                    "DK-DK2": {
                        "carbon_intensity": [{"at": f"{day}T00:00:00+00:00", "value": 100.0}]
                    }
                },
            }
        ),
        encoding="utf-8",
    )
