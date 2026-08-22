"""Normalize every recorded fixture.

These are **verbatim responses from the live Electricity Maps API**, captured with
``make record`` on 22 August 2026. Where ``test_normalize.py`` asserts behaviour against
small hand-written payloads, this asserts that the real thing parses — which is the only
test that would have caught the three field names the first version of the normalizer
guessed wrong.

If a fixture stops parsing, either the API changed or the normalizer did. Both are worth a
failing test, and both are worth knowing before 11 September rather than during it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from gridlab.domain.models import LevelBucket, Provenance
from gridlab.emaps import normalize
from gridlab.emaps.capabilities import parse_zones

FIXTURES = Path("/app/fixtures")
ZONE = "DK-DK2"

#: electricity-mix is recorded once per breakdownType, and the two differ in more than
#: their numbers:
#:
#: * the **production** breakdown carries a nested `flows` summary and leaves sources the
#:   zone does not run as null - so it is where the parsing traps actually live;
#: * the **flow-traced** breakdown has neither, because tracing has already resolved every
#:   import into a real source.
#:
#: Tests therefore pick the fixture that exercises the case they are about, rather than
#: assuming one mix response stands for both.
MIX_FIXTURE = "electricity-mix__latest__flow-traced"
MIX_PRODUCTION_FIXTURE = "electricity-mix__latest__normal"

pytestmark = pytest.mark.skipif(
    not FIXTURES.is_dir() or not list(FIXTURES.glob("*.json")),
    reason="no recorded fixtures mounted; run `make record` with a token",
)


def load(name: str) -> dict[str, Any]:
    path = FIXTURES / f"{name}.json"
    if not path.is_file():
        pytest.skip(f"{name} was not recorded with this plan")
    payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    body: dict[str, Any] = payload["body"]
    return body


def first_row(name: str) -> dict[str, Any]:
    return dict(normalize.rows(load(name))[0])


# --- the envelope shapes ----------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "carbon-intensity__latest",
        "carbon-intensity__history",
        "carbon-intensity__forecast",
        MIX_FIXTURE,
        "electricity-flows__latest",
        "price-day-ahead__combined",
        "net-load__latest",
        "carbon-intensity-level__latest",
    ],
)
def test_every_envelope_yields_rows(name: str) -> None:
    """Three envelope shapes are in use - `data`, `forecast`, and a bare object."""
    assert normalize.rows(load(name))


# --- scalar signals ---------------------------------------------------------


def test_carbon_intensity_latest() -> None:
    obs = normalize.carbon_intensity(first_row("carbon-intensity__latest"), zone=ZONE)
    assert obs.value > 0
    assert obs.zone == ZONE
    assert obs.emission_factor_type in {"lifecycle", "direct"}
    assert obs.flow_traced is True


def test_estimation_flags_are_real_and_common() -> None:
    """Grid data is heavily modelled. A product that scores or ranks zones needs to know
    which values were measured, so losing this flag would be quietly disqualifying."""
    row = first_row("carbon-intensity__latest")
    obs = normalize.carbon_intensity(row, zone=ZONE)
    assert obs.is_estimated == bool(row.get("isEstimated"))
    if obs.is_estimated:
        assert obs.estimation_method


def test_forecast_rows_are_minimal_and_still_parse() -> None:
    """Forecast rows carry only `datetime` and the value - no isEstimated, no updatedAt.

    Every other field in `_common` therefore has to be optional, which is easy to get
    wrong and impossible to notice against a `latest` payload.
    """
    body = load("carbon-intensity__forecast")
    row = dict(normalize.rows(body)[0])
    assert set(row) <= {"datetime", "carbonIntensity"}
    obs = normalize.carbon_intensity(row, zone=ZONE)
    assert obs.value > 0
    assert obs.is_estimated is False


def test_percentages_land_in_range() -> None:
    for name in ("renewable-energy__latest", "carbon-free-energy__latest"):
        pct = normalize.percentage(first_row(name), zone=ZONE)
        assert 0.0 <= pct.value <= 100.0


def test_load_signals_parse() -> None:
    for name, kind in (("total-load__latest", "total"), ("net-load__latest", "net")):
        obs = normalize.load(first_row(name), zone=ZONE, kind=kind)
        assert obs.kind == kind
        assert obs.value != 0


# --- price ------------------------------------------------------------------


def test_price_unit_is_split_into_currency_and_denominator() -> None:
    """The API sends `unit: "EUR/MWh"`. A chart axis wants the pair; a cross-zone
    comparison needs the currency alone, and summing across currencies is a category
    error."""
    p = normalize.price(first_row("price-day-ahead__combined"), zone=ZONE)
    assert p.currency == "EUR"
    assert p.unit == "MWh"


def test_price_records_whether_it_was_settled_or_modelled() -> None:
    """`combined` blends published auction prices with Electricity Maps' modelled ones in
    one series. Dropping `source` would mix measured and modelled prices invisibly."""
    rows = normalize.rows(load("price-day-ahead__combined"))
    sources = {normalize.price(dict(r), zone=ZONE).source for r in rows}
    assert sources, "no price rows"
    assert any(s for s in sources), "no row declared a source"


# --- mix: the part most likely to be quietly wrong --------------------------


def test_mix_parses_and_reports_its_breakdown_type() -> None:
    breakdown = normalize.mix(first_row(MIX_FIXTURE), zone=ZONE)
    assert breakdown.entries
    assert breakdown.flow_traced in {True, False}
    assert breakdown.total_mw and breakdown.total_mw > 0


def test_the_two_breakdowns_are_genuinely_different_answers() -> None:
    """Flow-tracing is the reason to prefer this API over any other, so it is worth
    asserting that the toggle actually changes the numbers rather than the label."""
    production = normalize.mix(first_row(MIX_PRODUCTION_FIXTURE), zone=ZONE)
    consumption = normalize.mix(first_row(MIX_FIXTURE), zone=ZONE)

    assert production.flow_traced is False
    assert consumption.flow_traced is True
    assert production.share("wind") != consumption.share("wind")


def test_mix_excludes_the_nested_flows_object() -> None:
    """`flows` sits inside `mix` but is an import/export summary, not a source. Left in, it
    appears as several hundred MW of generation called "flows" and every percentage in the
    breakdown is wrong."""
    raw = first_row(MIX_PRODUCTION_FIXTURE)
    assert "flows" in raw["mix"], "fixture no longer exercises this case"
    breakdown = normalize.mix(raw, zone=ZONE)
    assert "flows" not in {e.source for e in breakdown.entries}


def test_mix_drops_null_sources_rather_than_plotting_zeroes() -> None:
    raw = first_row(MIX_PRODUCTION_FIXTURE)
    nulls = {k for k, v in raw["mix"].items() if v is None}
    if not nulls:
        pytest.skip("this fixture has no null sources")
    breakdown = normalize.mix(raw, zone=ZONE)
    assert not (nulls & {e.source for e in breakdown.entries})


def test_mix_percentages_sum_to_one_hundred() -> None:
    breakdown = normalize.mix(first_row(MIX_FIXTURE), zone=ZONE)
    total = sum(e.percent or 0.0 for e in breakdown.entries)
    assert total == pytest.approx(100.0, abs=0.01)


def test_storage_contributes_discharge_only() -> None:
    """`hydro storage` and `battery storage` arrive as {charge, discharge}. Charge is
    demand; counting it as generation would double-count it."""
    breakdown = normalize.mix(first_row(MIX_FIXTURE), zone=ZONE)
    assert not any(e.source.endswith("storage") for e in breakdown.entries)
    assert all((e.power_mw or 0) >= 0 for e in breakdown.entries)


def test_power_breakdown_uses_a_different_field_name_and_still_parses() -> None:
    """`power-breakdown` really does use `powerConsumptionBreakdown` - the name the first
    version of the normalizer wrongly expected from `electricity-mix`. Both are supported,
    which is why the candidate list survives here and nowhere else."""
    breakdown = normalize.mix(first_row("power-breakdown__latest"), zone=ZONE)
    assert breakdown.entries


# --- flows ------------------------------------------------------------------


def test_flows_net_imports_against_exports() -> None:
    raw = first_row("electricity-flows__latest")
    assert "import" in raw or "export" in raw, "fixture shape changed"
    flows = normalize.flows(raw, zone=ZONE)
    assert flows.edges

    expected = sum(raw.get("import", {}).values()) - sum(raw.get("export", {}).values())
    assert flows.net_import_mw == pytest.approx(expected)


def test_flow_direction_matches_sign() -> None:
    flows = normalize.flows(first_row("electricity-flows__latest"), zone=ZONE)
    for edge in flows.edges:
        assert edge.direction == ("export" if edge.net_flow_mw >= 0 else "import")


# --- levels -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "of"),
    [
        ("carbon-intensity-level__latest", "carbon-intensity"),
        ("renewable-percentage-level__latest", "renewable-percentage"),
    ],
)
def test_levels_bucket_cleanly(name: str, of: str) -> None:
    """Levels need no numeracy at all, which makes them the most useful signal in the API
    for a non-expert audience - provided they parse into a known bucket rather than
    UNKNOWN."""
    lvl = normalize.level(first_row(name), zone=ZONE, of=of)
    assert lvl.bucket is not LevelBucket.UNKNOWN


# --- series -----------------------------------------------------------------


def test_history_series_is_ordered_and_deduplicated() -> None:
    series = normalize.series(
        [load("carbon-intensity__history")],
        zone=ZONE,
        normalizer=normalize.carbon_intensity,
    )
    times = [p.at for p in series.points]
    assert times == sorted(times)
    assert len(times) == len(set(times))
    assert series.provenance is Provenance.LIVE


def test_history_is_only_the_trailing_day_on_this_plan() -> None:
    """The finding that most constrains this project. `past` and `past-range` return 401,
    and `history` gives ~24 hours - so forecast-error scoring and event replay need a
    trial or event key, not this one."""
    series = normalize.series(
        [load("carbon-intensity__history")],
        zone=ZONE,
        normalizer=normalize.carbon_intensity,
    )
    span = series.points[-1].at - series.points[0].at
    assert span.total_seconds() <= 25 * 3600


def test_forecast_series_carries_its_issue_time() -> None:
    """Without `issued_at` a forecast cannot be compared with the outcome, which is the
    single most interesting thing this dataset supports."""
    series = normalize.series(
        [load("carbon-intensity__forecast")],
        zone=ZONE,
        normalizer=normalize.carbon_intensity,
        horizon_hours=24,
    )
    assert series.issued_at is not None
    assert len(series.points) > 1


def test_series_granularity_comes_from_the_response() -> None:
    series = normalize.series(
        [load("carbon-intensity__history")],
        zone=ZONE,
        normalizer=normalize.carbon_intensity,
        granularity="wrong",
    )
    assert series.granularity == "hourly"


# --- zones ------------------------------------------------------------------


def test_zones_parse_with_tiers_and_access() -> None:
    zones, access = parse_zones(load("zones"))
    assert len(zones) > 100
    assert access, "no access keys - was this recorded without a token?"

    by_key = {z.key: z for z in zones}
    dk2 = by_key[ZONE]
    assert dk2.name == "East Denmark"
    assert dk2.country_name == "Denmark"
    assert dk2.quality.value == "A"
    assert dk2.has_day_ahead_price is True


def test_access_list_contains_no_past_range_on_this_plan() -> None:
    """Pins the constraint so a future key change is visible as a test result."""
    _, access = parse_zones(load("zones"))
    assert not any(entry.endswith("/past-range") for entry in access)
