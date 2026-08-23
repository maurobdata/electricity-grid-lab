"""Baselines: scoring a zone against itself rather than against Norway.

The whole reason this module exists is that raw cross-zone rankings never change. These
tests are mostly about the ways a percentile can look authoritative while resting on
nothing — too few samples, a flat window, or a window so short it cannot support the claim
being made of it.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from gridlab.analysis.baseline import MIN_SAMPLES, percentile_of, score
from gridlab.domain.models import LevelBucket, Provenance, ScalarObservation, Series


def at(hour: float) -> datetime:
    return datetime(2026, 2, 4, tzinfo=UTC) + timedelta(hours=hour)


def history(
    values: list[float],
    *,
    zone: str = "DK-DK2",
    provenance: Provenance = Provenance.RECORDED,
    estimated: int = 0,
) -> Series[ScalarObservation]:
    return Series[ScalarObservation](
        zone=zone,
        points=tuple(
            ScalarObservation(
                zone=zone,
                at=at(i),
                provenance=provenance,
                is_estimated=i < estimated,
                value=v,
            )
            for i, v in enumerate(values)
        ),
    )


def hourly(count: int, value: float = 100.0) -> list[float]:
    return [value + i for i in range(count)]


# --- the percentile itself --------------------------------------------------


def test_a_value_above_everything_scores_at_the_top() -> None:
    assert percentile_of(500.0, [10.0, 20.0, 30.0]) == 100.0


def test_a_value_below_everything_scores_at_the_bottom() -> None:
    assert percentile_of(1.0, [10.0, 20.0, 30.0]) == 0.0


def test_a_value_equal_to_every_sample_scores_in_the_middle() -> None:
    """A flat overnight price is common. Scoring it 0 or 100 would report a completely
    ordinary hour as an extreme, which is the opposite of what a baseline is for."""
    assert percentile_of(50.0, [50.0] * 10) == 50.0


def test_ties_split_the_difference() -> None:
    assert percentile_of(20.0, [10.0, 20.0, 30.0, 40.0]) == 37.5


# --- scoring ----------------------------------------------------------------


def test_an_unusually_high_value_buckets_high() -> None:
    result = score(400.0, history(hourly(24)), signal="carbon_intensity")
    assert result is not None
    assert result.bucket is LevelBucket.HIGH
    assert result.percentile == 100.0


def test_an_unusually_low_value_buckets_low() -> None:
    result = score(10.0, history(hourly(24)), signal="carbon_intensity")
    assert result is not None
    assert result.bucket is LevelBucket.LOW


def test_a_typical_value_buckets_moderate() -> None:
    result = score(112.0, history(hourly(24)), signal="carbon_intensity")
    assert result is not None
    assert result.bucket is LevelBucket.MODERATE


def test_the_same_value_scores_differently_in_different_zones() -> None:
    """The point of the whole module. 200 gCO₂eq/kWh is a catastrophe in Norway and a good
    day in Poland, and a fixed threshold cannot say both."""
    clean = score(200.0, history([20.0 + i for i in range(24)]), signal="carbon_intensity")
    dirty = score(200.0, history([600.0 + i for i in range(24)]), signal="carbon_intensity")

    assert clean is not None and dirty is not None
    assert clean.bucket is LevelBucket.HIGH
    assert dirty.bucket is LevelBucket.LOW


# --- refusing to answer -----------------------------------------------------


def test_too_few_samples_produces_no_score_at_all() -> None:
    """A percentile over four samples looks exactly as authoritative as one over four
    hundred. Returning nothing is the only honest option."""
    assert score(100.0, history(hourly(MIN_SAMPLES - 1)), signal="carbon_intensity") is None


def test_a_flat_window_has_no_z_score() -> None:
    """Zero standard deviations from the mean of a constant is arithmetic, not information,
    and dividing by zero to get it would be worse."""
    result = score(50.0, history([50.0] * 24), signal="carbon_intensity")
    assert result is not None
    assert result.z_score is None
    assert result.percentile == 50.0


# --- disclosure -------------------------------------------------------------


def test_a_short_window_says_what_it_cannot_support() -> None:
    """On a key with no `past-range` the baseline is about a day. That supports "unusual
    today" and not "unusual for February", and the difference has to be stated."""
    result = score(400.0, history(hourly(24)), signal="carbon_intensity")
    assert result is not None
    caveats = " ".join(result.derived.caveats)
    assert "unusual today" in caveats
    assert "past-range" in caveats


def test_a_mostly_modelled_baseline_says_so() -> None:
    result = score(400.0, history(hourly(24), estimated=20), signal="carbon_intensity")
    assert result is not None
    assert any("modelled" in caveat for caveat in result.derived.caveats)


def test_the_baseline_never_claims_to_compare_zones() -> None:
    result = score(400.0, history(hourly(24)), signal="carbon_intensity")
    assert result is not None
    assert any("not against other zones" in caveat for caveat in result.derived.caveats)


def test_provenance_follows_the_history_it_scored_against() -> None:
    result = score(
        400.0, history(hourly(24), provenance=Provenance.SYNTHETIC), signal="carbon_intensity"
    )
    assert result is not None
    assert result.derived.provenance is Provenance.SYNTHETIC
