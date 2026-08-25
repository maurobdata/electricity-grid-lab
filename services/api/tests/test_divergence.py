"""Divergence: whether cheap and clean mean the same periods.

The failure modes worth guarding are quiet ones. A correlation that reports 0.0 for a flat
series reads as "unrelated" when the truth is "undefined". A best-window search that steps
over a gap reports a block nobody could actually run. A tercile rule with no tie handling
flags half a flat day as remarkable.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from gridlab.analysis.align import align
from gridlab.analysis.divergence import (
    MIN_PERIODS_FOR_CORRELATION,
    analyse,
    best_window,
    label,
    spearman,
)
from gridlab.domain.models import Provenance, ScalarObservation, Series


def at(hour: float) -> datetime:
    return datetime(2026, 2, 4, tzinfo=UTC) + timedelta(hours=hour)


def series(values: dict[float, float], *, granularity: str = "hourly") -> Series[ScalarObservation]:
    return Series[ScalarObservation](
        zone="DK-DK2",
        granularity=granularity,
        points=tuple(
            ScalarObservation(zone="DK-DK2", at=at(h), provenance=Provenance.RECORDED, value=v)
            for h, v in sorted(values.items())
        ),
    )


def pair(carbon: dict[float, float], price: dict[float, float]):  # type: ignore[no-untyped-def]
    result = align(series(carbon), series(price), a_signal="carbon_intensity", b_signal="price")
    assert result is not None
    return result


# --- rank correlation -------------------------------------------------------


def test_identical_orderings_correlate_perfectly() -> None:
    assert spearman([1.0, 2.0, 3.0, 4.0], [10.0, 20.0, 30.0, 40.0]) == 1.0


def test_reversed_orderings_correlate_negatively() -> None:
    assert spearman([1.0, 2.0, 3.0, 4.0], [40.0, 30.0, 20.0, 10.0]) == -1.0


def test_rank_correlation_ignores_a_single_extreme_value() -> None:
    """The reason it is Spearman and not Pearson. One scarcity hour at ten times the median
    would dominate a linear coefficient and describe that hour rather than the day."""
    carbon = [1.0, 2.0, 3.0, 4.0, 5.0]
    ordinary = [10.0, 20.0, 30.0, 40.0, 50.0]
    with_spike = [10.0, 20.0, 30.0, 40.0, 5000.0]
    assert spearman(carbon, ordinary) == spearman(carbon, with_spike)


def test_tied_values_share_a_rank() -> None:
    """A flat overnight price is genuinely several periods at one value. Breaking those
    ties would manufacture an ordering the market never expressed."""
    assert spearman([1.0, 1.0, 2.0, 3.0], [5.0, 5.0, 6.0, 7.0]) == 1.0


def test_a_flat_series_correlates_with_nothing_rather_than_zero() -> None:
    """0.0 would read as "these are unrelated", which is a stronger claim than the data
    supports. A series that orders nothing cannot agree or disagree with an ordering."""
    assert spearman([5.0, 5.0, 5.0, 5.0], [1.0, 2.0, 3.0, 4.0]) is None


def test_correlation_is_undefined_below_two_points() -> None:
    assert spearman([1.0], [2.0]) is None


def test_labels_describe_the_coefficient_without_replacing_it() -> None:
    assert label(0.95) == "strong"
    assert label(0.5) == "moderate"
    assert label(0.1) == "weak"
    assert label(-0.8) == "opposed"
    assert label(None) == "unknown"


# --- best window ------------------------------------------------------------


def test_the_cheapest_window_is_found_and_priced_on_the_other_signal() -> None:
    """The whole point: choosing on one objective has a cost on the other, and the cost is
    only visible if both are reported for the same block."""
    aligned = pair(
        carbon={0: 400, 1: 400, 2: 400, 3: 100, 4: 100, 5: 100},
        price={0: 10, 1: 10, 2: 10, 3: 200, 4: 200, 5: 200},
    )
    result = analyse(aligned, window_periods=3)

    assert result.best_b is not None and result.best_b.start == at(0)
    assert result.best_b.mean == 10.0
    assert result.best_b.other_mean == 400.0, "the carbon cost of choosing cheap was lost"

    assert result.best_a is not None and result.best_a.start == at(3)
    assert result.best_a.other_mean == 200.0
    assert result.separation_hours == 3.0


def test_when_the_two_agree_the_windows_coincide() -> None:
    """Not every zone disagrees, and a zone where cheap is also clean is a finding rather
    than a failure. Separation of zero is the honest way to say the choice never arises."""
    aligned = pair(
        carbon={0: 400, 1: 400, 2: 400, 3: 100, 4: 100, 5: 100},
        price={0: 200, 1: 200, 2: 200, 3: 10, 4: 10, 5: 10},
    )
    result = analyse(aligned, window_periods=3)
    assert result.separation_hours == 0.0
    assert result.correlation is not None and result.correlation > 0.9
    assert result.agreement == "strong"


def test_a_window_is_never_reported_across_a_gap() -> None:
    """Usable periods either side of an outage are not one continuous block.

    Price here exists at 00:00 and 06:00 only. Holding covers 00:00-02:00 and 06:00, so the
    longest genuinely continuous run is three periods — and a four-period block would have
    to step over the hole. Reporting one would name a schedule nobody could run.
    """
    aligned = align(
        series({float(h): 100.0 for h in range(7)}),
        series({0.0: 5.0, 6.0: 1.0}),
        a_signal="carbon_intensity",
        b_signal="price",
    )
    assert aligned is not None
    assert [p.at.hour for p in aligned.complete_pairs] == [0, 1, 2, 6]

    assert (
        best_window(aligned.pairs, periods=3, use_a=False, cadence=timedelta(hours=1)) is not None
    )
    assert best_window(aligned.pairs, periods=4, use_a=False, cadence=timedelta(hours=1)) is None


def test_a_window_longer_than_the_data_is_not_invented() -> None:
    aligned = pair(carbon={0: 100, 1: 200}, price={0: 10, 1: 20})
    assert analyse(aligned, window_periods=12).best_a is None


# --- disagreement -----------------------------------------------------------


def test_cheap_and_dirty_periods_are_identified() -> None:
    aligned = pair(
        carbon={0: 500, 1: 300, 2: 300, 3: 300, 4: 300, 5: 50},
        price={0: 5, 1: 100, 2: 100, 3: 100, 4: 100, 5: 400},
    )
    result = analyse(aligned)
    assert at(0) in result.disagreeing_periods, "cheap-and-dirty hour not flagged"
    assert at(5) in result.disagreeing_periods, "clean-and-expensive hour not flagged"


def test_a_flat_day_flags_nothing() -> None:
    aligned = pair(
        carbon={float(h): 200.0 for h in range(8)},
        price={float(h): 50.0 for h in range(8)},
    )
    assert analyse(aligned).disagreeing_periods == ()


# --- honesty ----------------------------------------------------------------


def test_too_few_periods_yields_no_correlation_and_says_why() -> None:
    """A coefficient over four points can hit 1.0 by coincidence, and it looks just as
    precise as one over ninety-six."""
    aligned = pair(carbon={0: 100, 1: 200, 2: 300}, price={0: 10, 1: 20, 2: 30})
    result = analyse(aligned)

    assert result.periods < MIN_PERIODS_FOR_CORRELATION
    assert result.correlation is None
    assert result.agreement == "unknown"
    assert any("fewer than" in caveat for caveat in result.derived.caveats)


def test_the_marginal_versus_average_caveat_is_always_present() -> None:
    """The critique a knowledgeable reader will raise. Stating it unprompted costs one
    sentence; being caught by it costs the whole claim."""
    aligned = pair(
        carbon={float(h): 100.0 + h for h in range(8)},
        price={float(h): 50.0 - h for h in range(8)},
    )
    caveats = " ".join(analyse(aligned).derived.caveats)
    assert "marginal" in caveats
    assert "flow-traced average" in caveats


def test_provenance_and_inputs_survive_from_the_alignment() -> None:
    aligned = pair(
        carbon={float(h): 100.0 + h for h in range(8)},
        price={float(h): 50.0 - h for h in range(8)},
    )
    result = analyse(aligned)
    assert result.derived.provenance is Provenance.RECORDED
    assert {ref.signal for ref in result.derived.inputs} == {"carbon_intensity", "price"}
