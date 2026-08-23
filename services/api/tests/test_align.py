"""Alignment: the step where cross-signal answers are most easily corrupted.

Every test here is about a way of being wrong that *looks* like being tidy — interpolating
a gap, upsampling a coarse signal, holding a stale value across an outage. Each produces a
chart that reads beautifully and a correlation that means nothing.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from gridlab.analysis.align import MAX_HOLD_STEPS, align, cadence
from gridlab.domain.models import Price, Provenance, ScalarObservation, Series


def at(hour: float) -> datetime:
    return datetime(2026, 2, 4, tzinfo=UTC) + timedelta(hours=hour)


def series(
    values: dict[float, float],
    *,
    zone: str = "DK-DK2",
    provenance: Provenance = Provenance.RECORDED,
    estimated: set[float] | None = None,
    granularity: str = "hourly",
) -> Series[ScalarObservation]:
    estimated = estimated or set()
    return Series[ScalarObservation](
        zone=zone,
        granularity=granularity,
        points=tuple(
            ScalarObservation(
                zone=zone,
                at=at(hour),
                provenance=provenance,
                is_estimated=hour in estimated,
                value=value,
            )
            for hour, value in sorted(values.items())
        ),
    )


def aligned(a: Series[ScalarObservation], b: Series[ScalarObservation]):  # type: ignore[no-untyped-def]
    return align(a, b, a_signal="carbon_intensity", b_signal="price")


# --- the grid ---------------------------------------------------------------


def test_two_matching_hourly_series_align_one_to_one() -> None:
    result = aligned(series({0: 100, 1: 200, 2: 300}), series({0: 10, 1: 20, 2: 30}))
    assert result is not None
    assert [(p.a, p.b) for p in result.pairs] == [(100, 10), (200, 20), (300, 30)]
    assert result.cadence_seconds == 3600
    assert result.coverage == 1.0


def test_the_coarser_cadence_wins() -> None:
    """Upsampling the hourly signal to quarter-hours would repeat each value four times and
    imply a resolution nobody published — and then silently reweight any correlation.

    This is the case the 15-minute day-ahead market creates: quarter-hourly price against
    hourly carbon.
    """
    hourly = series({0: 100, 1: 200, 2: 300})
    quarterly = series({q / 4: 10.0 + q for q in range(9)}, granularity="15_minutes")

    result = aligned(hourly, quarterly)
    assert result is not None
    assert result.cadence_seconds == 3600
    assert [p.at.hour for p in result.pairs] == [0, 1, 2]


def test_alignment_uses_the_published_value_not_an_interpolated_one() -> None:
    """A value stands until the next one lands. The midpoint between 100 and 300 is 200,
    and 200 is exactly the number nobody published."""
    result = aligned(series({0: 100, 2: 300}), series({0: 1, 1: 2, 2: 3}))
    assert result is not None
    assert [p.a for p in result.pairs] == [100, 100, 300]
    assert 200 not in [p.a for p in result.pairs]


def test_only_the_overlapping_window_survives() -> None:
    result = aligned(series({0: 100, 1: 200, 2: 300, 3: 400}), series({2: 30, 3: 40, 4: 50}))
    assert result is not None
    assert [p.at.hour for p in result.pairs] == [2, 3]


def test_series_that_never_overlap_produce_nothing() -> None:
    """Common and not an error: on a key with no `past-range`, history reaches back about as
    far as a forecast reaches forward, so two good series can share no instant at all."""
    assert aligned(series({0: 100, 1: 200}), series({8: 10, 9: 20})) is None


def test_an_empty_series_produces_nothing() -> None:
    assert aligned(series({}), series({0: 10})) is None


# --- holding, and the limit of it -------------------------------------------


def test_a_missing_publication_is_held_across() -> None:
    """One dropped hour is ordinary. Blanking the period over it would lose more than it
    protects."""
    result = aligned(series({0: 100, 1: 200, 2: 300}), series({0: 10, 2: 30}))
    assert result is not None
    assert [p.b for p in result.pairs] == [10, 10, 30]


def test_a_value_is_not_held_across_a_real_outage() -> None:
    """The rule that stops a chart lying. A price held for six hours is not a price, and
    the gap must read as a gap rather than as a flat line somebody could trade on."""
    gap_start, gap_end = 0, MAX_HOLD_STEPS + 3
    result = aligned(
        series({float(h): 100.0 + h for h in range(gap_end + 1)}),
        series({float(gap_start): 10.0, float(gap_end): 90.0}),
    )
    assert result is not None
    values = [p.b for p in result.pairs]
    assert values[0] == 10.0
    assert values[-1] == 90.0
    assert None in values, "a value was stretched across an outage instead of leaving a hole"


def test_periods_missing_one_signal_are_excluded_from_comparison() -> None:
    result = aligned(
        series({float(h): 100.0 + h for h in range(6)}),
        series({0.0: 10.0, 5.0: 90.0}),
    )
    assert result is not None
    assert len(result.complete_pairs) < len(result.pairs)
    assert all(p.complete for p in result.complete_pairs)
    assert 0.0 < result.coverage < 1.0


# --- provenance and disclosure ----------------------------------------------


def test_the_result_takes_the_weakest_provenance_of_its_inputs() -> None:
    """One generated input makes the whole calculation generated, however much measured
    data it was mixed with."""
    result = aligned(
        series({0: 100, 1: 200}, provenance=Provenance.LIVE),
        series({0: 10, 1: 20}, provenance=Provenance.SYNTHETIC),
    )
    assert result is not None
    assert result.derived.provenance is Provenance.SYNTHETIC


def test_the_method_names_its_own_parameters() -> None:
    """`aligned` is not a method description. A reader has to be able to tell what was done
    without opening the source."""
    result = aligned(series({0: 100, 1: 200}), series({0: 10, 1: 20}))
    assert result is not None
    assert "step_hold" in result.derived.method
    assert "3600s" in result.derived.method


def test_a_resolution_mismatch_is_disclosed_rather_than_absorbed() -> None:
    result = aligned(
        series({0: 100, 1: 200}),
        series({q / 4: 10.0 for q in range(5)}, granularity="15_minutes"),
    )
    assert result is not None
    assert any("resampled" in caveat for caveat in result.derived.caveats)


def test_inputs_record_enough_to_check_the_answer() -> None:
    result = aligned(series({0: 100, 1: 200}, estimated={1.0}), series({0: 10, 1: 20}))
    assert result is not None
    carbon = result.derived.inputs[0]
    assert carbon.zone == "DK-DK2"
    assert carbon.signal == "carbon_intensity"
    assert carbon.points == 2
    assert carbon.estimated_fraction == 0.5


def test_price_units_survive_alignment() -> None:
    """Currency is what stops prices being compared across zones that do not share one."""
    prices = Series[ScalarObservation](
        zone="DK-DK2",
        points=tuple(
            Price(
                zone="DK-DK2",
                at=at(h),
                provenance=Provenance.RECORDED,
                value=10.0 * h,
                currency="EUR",
                unit="MWh",
            )
            for h in range(3)
        ),
    )
    result = align(
        series({0: 100, 1: 200, 2: 300}), prices, a_signal="carbon_intensity", b_signal="price"
    )
    assert result is not None
    assert result.b_unit == "EUR/MWh"


# --- cadence ----------------------------------------------------------------


def test_the_declared_granularity_decides_the_cadence() -> None:
    """Because the gaps cannot. Two points five hours apart are either a five-hourly series
    or an hourly one with a hole, and the response says which."""
    sparse = {0.0: 1.0, 5.0: 2.0}
    assert cadence(series(sparse, granularity="hourly")) == timedelta(hours=1)
    assert cadence(series(sparse, granularity="15_minutes")) == timedelta(minutes=15)


def test_a_gap_in_a_declared_hourly_series_stays_a_gap() -> None:
    """The reason the rule above matters. Reading the sparse series as coarse would turn
    a four-hour hole into a legitimate period and quietly delete the evidence of it."""
    result = aligned(
        series({float(h): 100.0 + h for h in range(6)}), series({0.0: 10.0, 5.0: 90.0})
    )
    assert result is not None
    assert result.cadence_seconds == 3600
    assert [p.at.hour for p in result.pairs] == [0, 1, 2, 3, 4, 5]
    assert result.coverage < 1.0


def test_cadence_falls_back_to_the_median_gap_not_the_mean() -> None:
    """For a series that declares nothing. One missing hour would drag a mean off the real
    publication interval, and the hold limit is derived from this number."""
    assert cadence(series({0: 1, 1: 2, 2: 3, 8: 4, 9: 5}, granularity="unknown")) == timedelta(
        hours=1
    )


def test_a_single_point_falls_back_to_an_hour() -> None:
    assert cadence(series({0: 1}, granularity="unknown")) == timedelta(hours=1)
