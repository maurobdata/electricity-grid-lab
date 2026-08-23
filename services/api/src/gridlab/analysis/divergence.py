"""Do cheap and clean mean the same hours here, today?

Price and carbon intensity are different functions of the same physical grid, and they are
set by different mechanisms. A day-ahead price is a **marginal** quantity: uniform-price
auction clearing, so the last unit needed sets the price for everyone, and that unit is
usually gas. Flow-traced carbon intensity is an **average** quantity over consumption, with
imports traced back to their origin. Correlated, certainly. Identical, no — and the gap is
neither noise nor rounding.

This module quantifies the gap. It answers three questions, in increasing usefulness:

* **How much do they agree?** One rank correlation per zone per day. A scalar.
* **Where do they disagree?** Which periods are cheap-and-dirty or clean-and-expensive.
* **Does it change a decision?** The cheapest window versus the cleanest window for the
  same duration, and how far apart they sit.

Nothing here recommends anything, and nothing here is normative. Whether it is worth paying
more to run clean is a judgement involving values this module does not have; what it can do
is say what the choice costs, and refuse to pretend the two objectives are one.

**Rank correlation, not linear.** Spearman rather than Pearson because the question is
"do they order the periods the same way", not "are they proportional". Prices are
long-tailed — a single scarcity hour at ten times the median would dominate a Pearson
coefficient and tell you about that one hour rather than about the day. Ranks are immune to
it, and ranking is also what a scheduler actually does.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from pydantic import BaseModel, ConfigDict

from gridlab.analysis.align import Aligned, Pair
from gridlab.domain.models import Derived

#: Below this many usable periods a correlation is not worth reporting.
#:
#: Six is already generous. With four periods a coefficient can reach 1.0 by coincidence,
#: and a number that precise-looking invites more weight than it can carry.
MIN_PERIODS_FOR_CORRELATION = 6


class Window(BaseModel):
    """A contiguous run of periods, and what it would cost on one objective."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    start: datetime
    end: datetime
    periods: int
    mean: float
    """Mean of the objective being minimised over this window."""

    other_mean: float | None = None
    """Mean of the *other* signal over the same window. The price of choosing this one."""


class Divergence(BaseModel):
    """How far apart cheap and clean are, for one zone over one window."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    zone: str
    a_signal: str
    b_signal: str
    a_unit: str | None = None
    b_unit: str | None = None
    periods: int
    correlation: float | None = None
    """Spearman rank correlation over the aligned window. None when there is too little."""

    agreement: str = "unknown"
    """`strong`, `moderate`, `weak`, `opposed`, or `unknown`. A label for the coefficient."""

    best_a: Window | None = None
    """The window minimising the first signal — the cleanest, when `a` is carbon."""

    best_b: Window | None = None
    """The window minimising the second signal — the cheapest, when `b` is price."""

    separation_hours: float | None = None
    """How far apart those two windows start. Zero means the decision does not arise."""

    disagreeing_periods: tuple[datetime, ...] = ()
    """Periods in the top third on one signal and the bottom third on the other."""

    derived: Derived


def _ranks(values: list[float]) -> list[float]:
    """Ranks, averaging ties.

    Ties matter here rather than being an edge case: a flat overnight price is genuinely
    several periods at one value, and breaking those ties arbitrarily would manufacture an
    ordering the market never expressed.
    """
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        shared = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = shared
        i = j + 1
    return ranks


def spearman(xs: list[float], ys: list[float]) -> float | None:
    """Rank correlation in [-1, 1], or None when it is not defined.

    Pearson over ranks, computed directly rather than with the shortcut formula, because
    the shortcut is only correct without ties and the ties here are real.
    """
    if len(xs) != len(ys) or len(xs) < 2:
        return None

    rx, ry = _ranks(xs), _ranks(ys)
    n = len(rx)
    mean_x, mean_y = sum(rx) / n, sum(ry) / n

    covariance = sum((a - mean_x) * (b - mean_y) for a, b in zip(rx, ry, strict=True))
    var_x = sum((a - mean_x) ** 2 for a in rx)
    var_y = sum((b - mean_y) ** 2 for b in ry)
    if var_x <= 0 or var_y <= 0:
        # One series is entirely flat, so it orders nothing and correlates with nothing.
        # Reporting 0.0 would read as "unrelated", which is a stronger claim than the data
        # supports.
        return None

    return float(covariance / (var_x * var_y) ** 0.5)


def label(correlation: float | None) -> str:
    """A word for a coefficient, so a reader does not have to interpret 0.42 unaided.

    The thresholds are conventional and arbitrary, which is why the number is always
    reported alongside the word rather than replaced by it.
    """
    if correlation is None:
        return "unknown"
    if correlation < -0.2:
        return "opposed"
    if correlation < 0.3:
        return "weak"
    if correlation < 0.7:
        return "moderate"
    return "strong"


def best_window(
    pairs: tuple[Pair, ...], *, periods: int, use_a: bool, cadence: timedelta
) -> Window | None:
    """The contiguous run of ``periods`` with the lowest mean on one signal.

    Contiguous rather than the best scattered periods, because most real flexible loads are
    a block: a wash cycle, a charging session, a batch job. The scattered version is a
    different question and belongs to a solver, not here.

    Runs are only considered where **both** signals are present, so that the reported cost
    on the other objective is a real number rather than a partial one.
    """
    usable = [p for p in pairs if p.complete]
    if len(usable) < periods or periods < 1:
        return None

    best: tuple[float, int] | None = None
    for start in range(len(usable) - periods + 1):
        run = usable[start : start + periods]
        # Skip runs broken by a gap: three consecutive entries in the list are not three
        # consecutive periods if an incomplete one was filtered out between them.
        if run[-1].at - run[0].at != cadence * (periods - 1):
            continue
        values = [p.a if use_a else p.b for p in run]
        mean = sum(v for v in values if v is not None) / periods
        if best is None or mean < best[0]:
            best = (mean, start)

    if best is None:
        return None

    mean, start = best
    run = usable[start : start + periods]
    others = [p.b if use_a else p.a for p in run]
    return Window(
        start=run[0].at,
        end=run[-1].at + cadence,
        periods=periods,
        mean=round(mean, 4),
        other_mean=round(sum(v for v in others if v is not None) / periods, 4),
    )


def analyse(aligned: Aligned, *, window_periods: int = 3) -> Divergence:
    """Everything this module can say about one aligned pair.

    ``window_periods`` is the length of the flexible block being considered — three hourly
    periods is a plausible EV charge or a dishwasher plus a dryer. It changes the answer:
    a long enough window covers both the cheap and the clean periods and the question
    dissolves, which is itself worth being able to show.
    """
    complete = aligned.complete_pairs
    cadence = timedelta(seconds=aligned.cadence_seconds)

    xs = [p.a for p in complete if p.a is not None]
    ys = [p.b for p in complete if p.b is not None]
    correlation = spearman(xs, ys) if len(complete) >= MIN_PERIODS_FOR_CORRELATION else None

    best_a = best_window(aligned.pairs, periods=window_periods, use_a=True, cadence=cadence)
    best_b = best_window(aligned.pairs, periods=window_periods, use_a=False, cadence=cadence)
    separation = (
        abs((best_a.start - best_b.start).total_seconds()) / 3600 if best_a and best_b else None
    )

    caveats = list(aligned.derived.caveats)
    caveats.append(
        "Rank correlation, not a causal claim. Price is set by the marginal unit and "
        "carbon intensity is a flow-traced average over consumption; they are different "
        "functions of the same grid, so agreement and disagreement both have mechanisms "
        "behind them that this number does not identify."
    )
    if correlation is None and len(complete) < MIN_PERIODS_FOR_CORRELATION:
        caveats.append(
            f"Only {len(complete)} periods had both signals — fewer than the "
            f"{MIN_PERIODS_FOR_CORRELATION} needed before a correlation is worth quoting."
        )

    return Divergence(
        zone=aligned.zone,
        a_signal=aligned.a_signal,
        b_signal=aligned.b_signal,
        a_unit=aligned.a_unit,
        b_unit=aligned.b_unit,
        periods=len(complete),
        correlation=round(correlation, 4) if correlation is not None else None,
        agreement=label(correlation),
        best_a=best_a,
        best_b=best_b,
        separation_hours=round(separation, 2) if separation is not None else None,
        disagreeing_periods=_disagreeing(complete),
        derived=Derived(
            method=(
                f"divergence.spearman + best_window(periods={window_periods}) "
                f"over {aligned.derived.method}"
            ),
            inputs=aligned.derived.inputs,
            provenance=aligned.derived.provenance,
            caveats=tuple(caveats),
        ),
    )


def _disagreeing(pairs: tuple[Pair, ...]) -> tuple[datetime, ...]:
    """Periods that are cheap-and-dirty, or clean-and-expensive.

    Terciles rather than a fixed threshold, so the answer means the same thing in a zone
    where prices span five euros and one where they span five hundred. A period only counts
    when it is extreme on *both* signals in opposite directions — the alternative catches
    every period that is merely unremarkable on one of them.

    **By rank, not by value**, and for the same reason the correlation is: a value cutoff
    breaks on ties. A day whose middle four hours all clear at the same price puts that
    price on the tercile boundary, and a ``<=`` test then sweeps every one of those hours
    into the "cheapest third". Averaged ranks put tied periods together in the middle,
    where they belong — and a completely flat signal gives every period the same rank, so
    nothing is extreme and nothing is flagged.
    """
    usable = [p for p in pairs if p.complete]
    if len(usable) < 3:
        return ()

    a_ranks = _ranks([p.a for p in usable if p.a is not None])
    b_ranks = _ranks([p.b for p in usable if p.b is not None])

    n = len(usable)
    low, high = n / 3, 2 * n / 3

    return tuple(
        p.at
        for p, a, b in zip(usable, a_ranks, b_ranks, strict=True)
        if (a <= low and b > high) or (a > high and b <= low)
    )
