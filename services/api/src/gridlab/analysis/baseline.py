"""Score a value against the zone's own history, not against other zones.

This is the module that makes cross-zone comparison mean anything.

Raw values rank zones permanently. Norway's hydro is clean every hour of every year and
Poland's coal is not, so a league table of gCO₂eq/kWh has the same order today that it had
last year and will have next year. It is true, it is useless, and nobody looks at it twice.
The API's own ``/compare`` endpoint says as much in its response.

Scoring against a zone's **own** recent distribution asks a different and answerable
question: *is this unusual for here?* Norway can have a bad day. Poland can have a
remarkable one. Both become visible, both are news, and a reader learns something about the
grid rather than about geography.

Electricity Maps ships this idea as the beta ``*-level`` signals — ``low`` / ``moderate`` /
``high``, bucketed against a rolling baseline. Those are ``latest``-only on this plan, so
they cannot score a forecast or a recorded window. This computes the same shape from data
the lab already holds.

**The baseline is only as good as the window behind it.** On a key with no ``past-range``,
that window is about 24 hours — enough to say "unusual today", nowhere near enough to say
"unusual for February". Every result says which it is.
"""

from __future__ import annotations

from statistics import fmean, pstdev

from pydantic import BaseModel, ConfigDict

from gridlab.domain.models import (
    Derived,
    InputRef,
    LevelBucket,
    ScalarObservation,
    Series,
)

#: Below this many samples a percentile is arithmetic rather than evidence.
#:
#: Twelve is half a day of hourly data. It is a low bar, chosen because the alternative on
#: this plan is refusing to score anything at all — but it is a bar, and falling under it
#: produces no score rather than a confident-looking one.
MIN_SAMPLES = 12

#: Percentile boundaries for the three buckets, matching the shape of the beta level
#: signals so the vocabulary is the same wherever a reader meets it.
LOW_BELOW = 33.0
HIGH_ABOVE = 67.0


class Baseline(BaseModel):
    """Where one value sits in its own zone's recent distribution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    zone: str
    signal: str
    value: float
    percentile: float
    """0-100. The share of the baseline window this value is at or above."""

    bucket: LevelBucket
    z_score: float | None = None
    """Standard deviations from the window mean. None when the window is flat."""

    samples: int
    window_hours: float
    mean: float
    minimum: float
    maximum: float
    derived: Derived


def percentile_of(value: float, distribution: list[float]) -> float:
    """Where ``value`` falls in ``distribution``, 0-100.

    Uses the midpoint of the tied range, so a value equal to every sample scores 50 rather
    than 0 or 100. On a flat overnight price — genuinely common — the alternatives both
    read as an extreme, and neither is true.
    """
    if not distribution:
        return 50.0
    below = sum(1 for sample in distribution if sample < value)
    equal = sum(1 for sample in distribution if sample == value)
    return (below + equal / 2) / len(distribution) * 100.0


def bucket_for(percentile: float) -> LevelBucket:
    if percentile < LOW_BELOW:
        return LevelBucket.LOW
    if percentile > HIGH_ABOVE:
        return LevelBucket.HIGH
    return LevelBucket.MODERATE


def score(
    value: float,
    history: Series[ScalarObservation],
    *,
    signal: str,
    kind: str = "history",
) -> Baseline | None:
    """Score ``value`` against ``history`` from the same zone.

    Returns ``None`` rather than a weak answer when the window is too short: a percentile
    over four samples looks exactly as authoritative as one over four hundred, and only one
    of them is.
    """
    samples = [p.value for p in history.points]
    if len(samples) < MIN_SAMPLES:
        return None

    span = history.points[-1].at - history.points[0].at
    hours = span.total_seconds() / 3600
    centile = percentile_of(value, samples)
    mean = fmean(samples)
    deviation = pstdev(samples)

    caveats = [
        f"Scored against {len(samples)} samples covering {hours:.0f} hours of this zone's "
        f"own history — not against other zones, and not against a seasonal norm."
    ]
    if hours < 48:
        caveats.append(
            "That window is about a day. It supports 'unusual today' and does not support "
            "'unusual for this time of year'. A longer baseline needs `past-range` access."
        )
    if history.estimated_fraction > 0.5:
        caveats.append(
            f"{history.estimated_fraction:.0%} of the baseline was modelled by Electricity "
            f"Maps rather than measured."
        )

    return Baseline(
        zone=history.zone,
        signal=signal,
        value=value,
        percentile=round(centile, 2),
        bucket=bucket_for(centile),
        z_score=round((value - mean) / deviation, 3) if deviation > 0 else None,
        samples=len(samples),
        window_hours=round(hours, 2),
        mean=round(mean, 4),
        minimum=min(samples),
        maximum=max(samples),
        derived=Derived.of(
            f"baseline.percentile(window={hours:.0f}h, samples={len(samples)})",
            [
                InputRef(
                    zone=history.zone,
                    signal=signal,
                    kind=kind,
                    points=len(history.points),
                    provenance=history.provenance,
                    estimated_fraction=round(history.estimated_fraction, 4),
                    start=history.points[0].at,
                    end=history.points[-1].at,
                )
            ],
            *caveats,
        ),
    )
