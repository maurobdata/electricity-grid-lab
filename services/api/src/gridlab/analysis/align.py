"""Put two series on one time axis, without inventing anything.

This is the foundation of every cross-signal question the lab can ask, and it is the step
where the answers are most easily corrupted, because the corruption looks like tidiness.

**The signals do not share a clock.** Carbon intensity is hourly and forecast to 72 hours.
Day-ahead price is hourly today and may be quarter-hourly on a plan that returns 15-minute
market time units. Mix, flows and load forecast only 24 hours ahead. Asking "were the cheap
periods also the clean ones?" therefore requires a decision about what to do where one
series has a value and the other does not — and every available answer is wrong in some
way. The job here is to pick one, apply it identically everywhere, and say so on the result.

The policy, in three rules:

**1. Step-hold, never interpolate.** A published value stands until the next one is
published. Interpolating between two hourly carbon intensities produces numbers that were
never issued by anyone, and they are indistinguishable from measured ones once plotted.
``ReplaySource`` already made this choice for lookups; this is the same rule for series.

**2. Resample onto the coarser cadence, never the finer.** Given hourly carbon and
quarter-hourly price, the honest grid is hourly. Upsampling carbon to fifteen minutes would
repeat each value four times and imply a resolution that does not exist — and if the two
are then correlated, that invented resolution silently reweights the result.

**3. A held value expires.** Holding is only valid across a gap the size the source
normally publishes at. Beyond that the series has a hole, and a hole is reported as
``None`` rather than smoothed over by the last known number. A price held for eleven hours
is not a price.

What comes out is an :class:`Aligned` pair plus the :class:`~gridlab.domain.models.Derived`
record naming the policy, the cadence and everything that was dropped.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from itertools import pairwise
from statistics import median

from pydantic import BaseModel, ConfigDict

from gridlab.domain.models import Derived, InputRef, ScalarObservation, Series

#: How many cadence steps a value may be held across before the series is treated as
#: having a hole.
#:
#: One step is the definition of "still current". Two allows a single missing publication —
#: common, and not worth blanking an hour over — while still refusing to stretch a value
#: across a genuine outage.
MAX_HOLD_STEPS = 2

#: Used when a series declares no granularity and is too short to imply one. Every signal
#: the lab reads is hourly or finer, and an hour is the modal interval across all of them.
DEFAULT_CADENCE = timedelta(hours=1)

#: ``temporalGranularity`` values, as durations. Keyed by the strings the API uses, which
#: are what ``normalize.series`` copies onto ``Series.granularity``.
DECLARED_CADENCE: dict[str, timedelta] = {
    "5_minutes": timedelta(minutes=5),
    "15_minutes": timedelta(minutes=15),
    "hourly": timedelta(hours=1),
    "daily": timedelta(days=1),
}


class Pair(BaseModel):
    """Two values at one instant. Either may be missing; both being missing is not emitted."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    at: datetime
    a: float | None
    b: float | None

    @property
    def complete(self) -> bool:
        return self.a is not None and self.b is not None


class Aligned(BaseModel):
    """Two series on one grid, and the record of how they got there."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    zone: str
    a_signal: str
    b_signal: str
    a_unit: str | None = None
    b_unit: str | None = None
    cadence_seconds: int
    pairs: tuple[Pair, ...]
    derived: Derived

    @property
    def complete_pairs(self) -> tuple[Pair, ...]:
        """Only the instants where both series had a value.

        Almost every calculation wants this rather than :attr:`pairs`: comparing a series
        with itself over different subsets produces numbers that look fine and mean
        nothing.
        """
        return tuple(p for p in self.pairs if p.complete)

    @property
    def coverage(self) -> float:
        """Share of the grid where both series were present. Below ~0.5, be suspicious."""
        return len(self.complete_pairs) / len(self.pairs) if self.pairs else 0.0

    def window(self) -> tuple[datetime, datetime] | None:
        return (self.pairs[0].at, self.pairs[-1].at) if self.pairs else None


def cadence(series: Series[ScalarObservation]) -> timedelta:
    """How often this series publishes.

    **The declared granularity wins where there is one**, because the gaps alone cannot
    answer this. A series holding values at 00:00 and 05:00 is either five-hourly or hourly
    with a four-hour hole, and those demand opposite treatment: the first is a legitimate
    coarse grid, the second is an outage that must read as missing. No amount of staring at
    two timestamps distinguishes them, and guessing "coarse" is the dangerous guess — it
    turns a hole into a period and hides it.

    ``Series.granularity`` is trustworthy for this because ``normalize.series`` copies it
    from the response's own ``temporalGranularity`` when the API states one, so it
    describes what arrived rather than what was requested.

    Falls back to the **median** gap when nothing is declared. Median rather than mean, so
    that one missing publication does not drag the estimate off the real interval — and the
    hold limit is derived from this number, so dragging it would quietly license longer
    holds.
    """
    declared = DECLARED_CADENCE.get(series.granularity)
    if declared is not None:
        return declared

    times = [p.at for p in series.points]
    if len(times) < 2:
        return DEFAULT_CADENCE
    gaps = [(b - a).total_seconds() for a, b in pairwise(times) if b > a]
    if not gaps:
        return DEFAULT_CADENCE
    return timedelta(seconds=median(gaps))


def _value_at(
    points: Sequence[ScalarObservation], moment: datetime, *, max_hold: timedelta
) -> float | None:
    """The last published value at or before ``moment``, if it has not gone stale.

    Linear rather than bisecting: series here are hours to days long, the caller loops over
    a grid of comparable size, and an index would be another thing to keep correct.
    """
    best: ScalarObservation | None = None
    for point in points:
        if point.at > moment:
            break
        best = point
    if best is None or moment - best.at > max_hold:
        return None
    return best.value


def _grid(start: datetime, end: datetime, step: timedelta) -> list[datetime]:
    out: list[datetime] = []
    moment = start
    while moment <= end:
        out.append(moment)
        moment += step
    return out


def _ref(series: Series[ScalarObservation], signal: str, kind: str) -> InputRef:
    return InputRef(
        zone=series.zone,
        signal=signal,
        kind=kind,
        points=len(series.points),
        provenance=series.provenance,
        estimated_fraction=round(series.estimated_fraction, 4),
        start=series.points[0].at if series.points else None,
        end=series.points[-1].at if series.points else None,
    )


def align(
    a: Series[ScalarObservation],
    b: Series[ScalarObservation],
    *,
    a_signal: str,
    b_signal: str,
    a_kind: str = "forecast",
    b_kind: str = "forecast",
) -> Aligned | None:
    """Resample two series onto their common, coarser grid.

    Returns ``None`` when there is no overlap at all — which is a real and common state on
    this plan, not an error. History reaches back about as far as a forecast reaches
    forward, so two series can both be perfectly good and share no instant.
    """
    if not a.points or not b.points:
        return None

    a_cadence, b_cadence = cadence(a), cadence(b)
    step = max(a_cadence, b_cadence)

    start = max(a.points[0].at, b.points[0].at)
    end = min(a.points[-1].at, b.points[-1].at)
    if start > end:
        return None

    # Anchor the grid on whichever series is coarser, so its published instants are used
    # as-is rather than shifted onto an offset borrowed from the finer one.
    anchor = a if a_cadence >= b_cadence else b
    origin = next((p.at for p in anchor.points if p.at >= start), start)

    pairs = [
        Pair(
            at=moment,
            a=_value_at(a.points, moment, max_hold=a_cadence * MAX_HOLD_STEPS),
            b=_value_at(b.points, moment, max_hold=b_cadence * MAX_HOLD_STEPS),
        )
        for moment in _grid(origin, end, step)
    ]
    pairs = [p for p in pairs if p.a is not None or p.b is not None]
    if not pairs:
        return None

    caveats: list[str] = []
    if a_cadence != b_cadence:
        caveats.append(
            f"{a_signal} publishes every {_human(a_cadence)} and {b_signal} every "
            f"{_human(b_cadence)}; both were resampled to {_human(step)}, so detail finer "
            f"than that is not represented."
        )
    complete = sum(1 for p in pairs if p.complete)
    if complete < len(pairs):
        caveats.append(
            f"{len(pairs) - complete} of {len(pairs)} periods had a value for only one "
            f"signal and are excluded from anything comparing the two."
        )

    return Aligned(
        zone=a.zone,
        a_signal=a_signal,
        b_signal=b_signal,
        a_unit=_unit(a),
        b_unit=_unit(b),
        cadence_seconds=int(step.total_seconds()),
        pairs=tuple(pairs),
        derived=Derived.of(
            f"align.step_hold(cadence={int(step.total_seconds())}s, "
            f"max_hold={MAX_HOLD_STEPS} steps)",
            [_ref(a, a_signal, a_kind), _ref(b, b_signal, b_kind)],
            *caveats,
        ),
    )


def _unit(series: Series[ScalarObservation]) -> str | None:
    """The unit the points carry, if they carry one. Only price does, today."""
    if not series.points:
        return None
    first = series.points[0]
    currency = getattr(first, "currency", None)
    unit = getattr(first, "unit", None)
    if currency and unit:
        return f"{currency}/{unit}"
    return unit if isinstance(unit, str) else None


def _human(delta: timedelta) -> str:
    seconds = int(delta.total_seconds())
    if seconds % 3600 == 0:
        hours = seconds // 3600
        return "hour" if hours == 1 else f"{hours} hours"
    minutes = seconds // 60
    return "minute" if minutes == 1 else f"{minutes} minutes"
