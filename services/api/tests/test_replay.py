"""Replay: deterministic, offline, and honest about where its numbers came from."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

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
