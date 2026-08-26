"""Is a recording complete enough to use?

Every signal in the recorder is optional — a plan that cannot reach one produces a smaller
scenario rather than an exception, which is the right rule for an adapter and the wrong rule
for an archive. Somewhere the degradation has to stop being graceful and start being a
failure, or a run that got three points and no forecast would quietly replace yesterday's
good recording and nobody would notice until the analysis.

This module is that line. It is deliberately a *separate* judgement from "did the requests
succeed": a run can make twenty successful requests and still produce something not worth
keeping, and the archive needs to know the difference.

The thresholds are minimums, not targets. A full hourly day is 24 points; twelve is the
point below which the window is too short to show a shape.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from gridlab.domain.models import Provenance
from gridlab.store.scenario import Scenario

#: Fewest carbon-intensity points a usable recording must hold, for at least one zone.
#:
#: Carbon intensity is the one signal every panel and every analysis depends on, and the
#: only one whose absence makes the rest pointless.
MIN_POINTS = 12

#: Shortest actuals window worth keeping, in hours.
MIN_WINDOW_HOURS = 12.0


class Completeness(BaseModel):
    """The verdict, and how it was reached.

    Carries the individual checks rather than only the boolean, because "incomplete" is not
    actionable and "no forecast was recorded, so this cannot be scored against tomorrow" is.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    complete: bool
    checks: dict[str, bool] = Field(default_factory=dict)
    reasons: tuple[str, ...] = ()

    def __bool__(self) -> bool:
        return self.complete


def assess(
    scenario: Scenario,
    *,
    min_points: int = MIN_POINTS,
    min_window_hours: float = MIN_WINDOW_HOURS,
) -> Completeness:
    """Judge a recording against the minimum an archive should accept.

    A ``synthetic`` scenario is never complete *as a recording*. That is not a comment on
    its quality — the generated scenarios are useful and honest — but an archive of what the
    grid did must not accept something nobody measured.
    """
    checks: dict[str, bool] = {}
    reasons: list[str] = []

    checks["is_recorded"] = scenario.provenance is Provenance.RECORDED
    if not checks["is_recorded"]:
        reasons.append(
            f"provenance is {scenario.provenance.value}, and an archive of measured data "
            f"cannot accept anything else"
        )

    checks["has_zones"] = bool(scenario.zones)
    if not checks["has_zones"]:
        reasons.append("no zones")

    best = max((len(z.carbon_intensity) for z in scenario.zones.values()), default=0)
    checks["has_carbon_intensity"] = best >= min_points
    if not checks["has_carbon_intensity"]:
        reasons.append(
            f"best zone has {best} carbon-intensity points, fewer than the {min_points} "
            f"needed for a window with a shape"
        )

    hours = (scenario.end - scenario.start).total_seconds() / 3600
    checks["window_long_enough"] = hours >= min_window_hours
    if not checks["window_long_enough"]:
        reasons.append(f"window spans {hours:.1f}h, under the {min_window_hours:.0f}h minimum")

    # The forecast is what makes the archive worth building. Actuals alone can be compared
    # with nothing: forecast-versus-outcome needs today's prediction to survive until
    # tomorrow's measurement exists, and `issued_at` is what makes that join possible.
    forecasts = [f for zone in scenario.zones.values() for f in zone.forecasts.values() if f.points]
    checks["has_forecast"] = bool(forecasts)
    if not checks["has_forecast"]:
        reasons.append(
            "no forecast with points, so this day can never be scored against its outcome"
        )

    return Completeness(complete=all(checks.values()), checks=checks, reasons=tuple(reasons))
