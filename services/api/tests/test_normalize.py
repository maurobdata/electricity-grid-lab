"""Normalization: raw JSON in, domain models out.

These tests encode what we currently believe the Electricity Maps v4 responses look like.
Only the carbon-intensity shape is publicly evidenced; the rest is inferred (see
``docs/electricity-maps-api.md``). When ``make record`` produces real fixtures, replace the
inline payloads here with them and narrow the candidate key lists in ``normalize``.

The point of these tests is therefore less "we parse the API correctly" — we cannot yet
know that — and more "when the API differs from our guess, we find out loudly, with the
real keys in the error message, instead of silently plotting zeroes".
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from gridlab.domain.models import Provenance
from gridlab.emaps import normalize
from gridlab.emaps.normalize import RawShapeError

# The one response shape with public evidence behind it.
CARBON_LATEST = {
    "zone": "DE",
    "carbonIntensity": 302,
    "datetime": "2026-04-25T18:07:00.350Z",
    "updatedAt": "2026-04-25T18:07:01.000Z",
    "emissionFactorType": "lifecycle",
    "isEstimated": True,
    "estimationMethod": "TIME_SLICER_AVERAGE",
}


def test_carbon_intensity_round_trips() -> None:
    obs = normalize.carbon_intensity(CARBON_LATEST, zone="DE")
    assert obs.value == 302
    assert obs.zone == "DE"
    assert obs.at == datetime(2026, 4, 25, 18, 7, 0, 350_000, tzinfo=UTC)
    assert obs.emission_factor_type == "lifecycle"
    assert obs.provenance is Provenance.LIVE


def test_estimation_flags_survive_normalization() -> None:
    """A zone that is mostly estimated is unfit for scoring or ranking. Losing this flag
    would make modelled numbers indistinguishable from measured ones."""
    obs = normalize.carbon_intensity(CARBON_LATEST, zone="DE")
    assert obs.is_estimated is True
    assert obs.estimation_method == "TIME_SLICER_AVERAGE"


def test_provenance_is_carried_not_inferred() -> None:
    obs = normalize.carbon_intensity(CARBON_LATEST, zone="DE", provenance=Provenance.RECORDED)
    assert obs.provenance is Provenance.RECORDED


def test_missing_value_names_the_keys_that_were_present() -> None:
    """The error must be actionable at 16:00 on a hackathon day, not just correct."""
    with pytest.raises(RawShapeError) as exc:
        normalize.carbon_intensity({"datetime": "2026-01-01T00:00:00Z", "ci": 1}, zone="DE")
    assert "'ci'" in str(exc.value)
    assert "normalize" in str(exc.value)


# --- timestamps -------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        "2026-02-04T18:00:00Z",
        "2026-02-04T18:00:00+00:00",
        "2026-02-04T19:00:00+01:00",
    ],
)
def test_timestamps_normalize_to_utc(raw: str) -> None:
    assert normalize.parse_time(raw) == datetime(2026, 2, 4, 18, tzinfo=UTC)


def test_naive_timestamps_are_treated_as_utc() -> None:
    assert normalize.parse_time("2026-02-04T18:00:00").tzinfo is UTC


def test_unparseable_timestamp_raises() -> None:
    with pytest.raises(RawShapeError, match="Unparseable"):
        normalize.parse_time("last Tuesday")


# --- row extraction ---------------------------------------------------------


def test_range_responses_unwrap_the_data_key() -> None:
    body = {"zone": "DE", "data": [{"datetime": "2026-01-01T00:00:00Z", "carbonIntensity": 1}]}
    assert len(normalize.rows(body)) == 1


def test_a_bare_object_is_treated_as_one_row() -> None:
    assert normalize.rows(CARBON_LATEST) == [CARBON_LATEST]


def test_unrecognisable_body_raises_with_its_keys() -> None:
    with pytest.raises(RawShapeError, match="surprise"):
        normalize.rows({"surprise": 1})


# --- mix --------------------------------------------------------------------


MIX_LATEST = {
    "zone": "DK-DK1",
    "datetime": "2026-02-04T18:00:00Z",
    "powerConsumptionBreakdown": {"wind": 1200, "coal": 300, "gas": 500},
    "powerProductionBreakdown": {"wind": 2000, "gas": 100},
    "powerConsumptionTotal": 2000,
}


def test_flow_traced_and_production_are_different_answers() -> None:
    """This is the distinction the whole project cares about: what a zone *generated*
    versus what is actually in the socket once imports are traced to their origin."""
    consumption = normalize.mix(MIX_LATEST, zone="DK-DK1", flow_traced=True)
    production = normalize.mix(MIX_LATEST, zone="DK-DK1", flow_traced=False)

    assert consumption.flow_traced is True
    assert production.flow_traced is False
    assert {e.source for e in consumption.entries} == {"wind", "coal", "gas"}
    assert {e.source for e in production.entries} == {"wind", "gas"}


def test_mix_percentages_are_derived_when_absent() -> None:
    mix = normalize.mix(MIX_LATEST, zone="DK-DK1", flow_traced=True)
    assert mix.share("wind") == pytest.approx(60.0)
    assert sum(e.percent or 0 for e in mix.entries) == pytest.approx(100.0)


def test_mix_without_a_recognisable_breakdown_raises() -> None:
    with pytest.raises(RawShapeError, match="No mix breakdown"):
        normalize.mix({"datetime": "2026-01-01T00:00:00Z"}, zone="DE", flow_traced=True)


# --- flows ------------------------------------------------------------------


def test_imports_are_negative_and_exports_positive() -> None:
    body = {
        "zone": "DK-DK2",
        "datetime": "2026-02-04T18:00:00Z",
        "powerExportBreakdown": {"SE-SE4": 300},
        "powerImportBreakdown": {"DE": 900},
    }
    flows = normalize.flows(body, zone="DK-DK2")

    by_zone = {e.counterpart_zone: e for e in flows.edges}
    assert by_zone["SE-SE4"].net_flow_mw == 300
    assert by_zone["SE-SE4"].direction == "export"
    assert by_zone["DE"].net_flow_mw == -900
    assert by_zone["DE"].direction == "import"
    assert flows.net_import_mw == 600


def test_a_zone_both_importing_and_exporting_to_one_neighbour_nets_out() -> None:
    body = {
        "zone": "DK-DK1",
        "datetime": "2026-02-04T18:00:00Z",
        "powerExportBreakdown": {"DE": 400},
        "powerImportBreakdown": {"DE": 100},
    }
    flows = normalize.flows(body, zone="DK-DK1")
    assert len(flows.edges) == 1
    assert flows.edges[0].net_flow_mw == 300


# --- percentages ------------------------------------------------------------


def test_fractional_shares_are_scaled_to_percent() -> None:
    """Some responses express shares as 0-1. Plotting 0.82 on a 0-100 axis looks like a
    dead grid rather than a very good day."""
    body = {"zone": "DK-DK1", "datetime": "2026-02-04T18:00:00Z", "renewablePercentage": 0.82}
    pct = normalize.percentage(body, zone="DK-DK1", keys=["renewablePercentage"])
    assert pct.value == pytest.approx(82.0)


def test_percent_values_pass_through_unchanged() -> None:
    body = {"zone": "DK-DK1", "datetime": "2026-02-04T18:00:00Z", "renewablePercentage": 82}
    pct = normalize.percentage(body, zone="DK-DK1", keys=["renewablePercentage"])
    assert pct.value == pytest.approx(82.0)


# --- price ------------------------------------------------------------------


def test_price_keeps_its_currency_and_source() -> None:
    """Currency matters because summing local-currency prices across zones is wrong, and
    `source` distinguishes a settled auction price from a modelled one."""
    body = {
        "zone": "ES",
        "datetime": "2026-05-20T13:00:00Z",
        "price": -41.0,
        "currency": "EUR",
        "source": "modelled",
    }
    price = normalize.price(body, zone="ES")
    assert price.value == -41.0
    assert price.currency == "EUR"
    assert price.source == "modelled"


def test_negative_prices_are_not_clamped() -> None:
    """Negative prices are the most interesting thing in this dataset - Europe cleared
    1,223 negative hours in Q1 2026. Treating them as invalid would delete the story."""
    body = {"zone": "DE", "datetime": "2026-05-20T13:00:00Z", "price": -250.0}
    assert normalize.price(body, zone="DE").value == -250.0


# --- series -----------------------------------------------------------------


def _ci_row(hour: int, value: float) -> dict[str, object]:
    return {"datetime": f"2026-02-04T{hour:02d}:00:00Z", "carbonIntensity": value}


def test_series_merges_chunks_in_time_order() -> None:
    bodies = [
        {"data": [_ci_row(2, 120), _ci_row(0, 100)]},
        {"data": [_ci_row(1, 110)]},
    ]
    series = normalize.series(bodies, zone="DK-DK2", normalizer=normalize.carbon_intensity)
    assert [p.at.hour for p in series.points] == [0, 1, 2]


def test_series_deduplicates_chunk_boundaries() -> None:
    """Chunk edges and upstream revisions both produce the same instant twice. Two points
    at 14:00 draw a vertical line through the chart."""
    bodies = [{"data": [_ci_row(0, 100)]}, {"data": [_ci_row(0, 105), _ci_row(1, 110)]}]
    series = normalize.series(bodies, zone="DK-DK2", normalizer=normalize.carbon_intensity)
    assert len(series.points) == 2
    assert series.points[0].value == 105  # later body wins


def test_series_provenance_is_the_weakest_point() -> None:
    """A series is only as trustworthy as its least trustworthy value."""
    series = normalize.series(
        [{"data": [_ci_row(0, 100)]}],
        zone="DK-DK2",
        normalizer=normalize.carbon_intensity,
        provenance=Provenance.SYNTHETIC,
    )
    assert series.provenance is Provenance.SYNTHETIC


def test_empty_series_is_synthetic_not_live() -> None:
    """Fail closed: an empty series must not claim to be measured data."""
    series = normalize.series([{"data": []}], zone="DK-DK2", normalizer=normalize.carbon_intensity)
    assert series.provenance is Provenance.SYNTHETIC
    assert series.estimated_fraction == 0.0
