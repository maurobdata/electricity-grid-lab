"""Find what is worth looking at, without asking a model.

A dashboard waits to be interrogated. It shows you everything, ranks nothing, and leaves
the reader to notice that the 03:00 price went negative — which they will not, because
noticing is work and the panel gives no reason to start. This module does the noticing.

Every detector is ordinary arithmetic over series the lab already has: free, instant,
reproducible, and checkable. That matters for three separate reasons.

**It is the honest place for numbers.** A language model asked to find the cheapest window
usually gets it right, occasionally does not, and the answer looks identical either way.
Anything a person might act on is computed here, and the model's job is to explain what
this found.

**It is cheaper than being asked.** Detection runs on every poll for nothing. Asking a
model to notice the same thing costs a request and a wait, per question, forever.

**It gives the UI somewhere to point.** Each finding carries a
:class:`~gridlab.domain.models.ViewIntent` — the view that would show it. That is what turns
a list of observations into navigation, and it is the same contract the agent uses to
propose a view, so a finding and an answer steer the interface identically.

A detector that fires on everything is worse than useless, so each has a threshold, and the
thresholds are named constants rather than literals buried in a comparison. **Significance
is comparable only within a kind** — a 0.8 negative-price finding is not "more important"
than a 0.6 carbon peak, and the field exists to order a list of like things, not to rank
across them.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

from gridlab.analysis.align import Aligned
from gridlab.analysis.divergence import Divergence
from gridlab.domain.models import (
    Derived,
    Evidence,
    Finding,
    Flows,
    InputRef,
    IntentKind,
    MixBreakdown,
    ScalarObservation,
    Series,
    ViewIntent,
    weakest,
)

#: A carbon swing smaller than this is weather, not an event.
CARBON_SWING_RATIO = 1.5

#: A renewable share climbing by more than this many points is a surge worth naming.
RENEWABLE_SURGE_POINTS = 20.0

#: Net imports above this share of a zone's consumption make an import story the likely
#: explanation for a carbon change rather than a coincidence.
IMPORT_DOMINANCE = 0.2

#: Cheap and clean have to be at least this far apart before the disagreement is worth a
#: finding. Under an hour and the two windows overlap in practice.
MIN_SEPARATION_HOURS = 1.0

#: How far below zero a price has to reach before it earns a place in the list.
#:
#: Every negative price is real and none are ever clamped — but a dip that does not manage
#: a whole euro below zero is the auction landing fractionally under the line, and four
#: chips for four such dips crowd out the event somebody should actually see. The threshold
#: filters the list; it never merges separate runs, and it never alters a number.
NEGATIVE_PRICE_MIN_DEPTH = 1.0


def _stamp(moment: datetime, *, span: tuple[datetime, datetime] | None) -> str:
    """A time, with the weekday attached whenever the window crosses midnight.

    The test is the date boundary rather than the length. A window can be well under 24
    hours and still contain two different 03:00s as far as a reader is concerned — and
    findings are read side by side in a list, where a bare ``03:00`` next to a
    ``Thu 06:00`` invites exactly the wrong inference about which comes first.

    Almost every forward window crosses midnight, since it starts now and runs into
    tomorrow's delivery day. So this is usually the longer form, and that is the right
    default: three extra characters against a headline somebody misreads on stage.
    """
    if span is None or span[0].date() == span[1].date():
        return moment.strftime("%H:%M")
    return moment.strftime("%a %H:%M")


def _span(series: Series[ScalarObservation]) -> tuple[datetime, datetime] | None:
    if len(series.points) < 2:
        return None
    return series.points[0].at, series.points[-1].at


def _id(kind: str, zone: str, at: datetime, *parts: str) -> str:
    """A stable identity for the same finding computed twice.

    Narration is cached against this, which is most of what keeps the AI layer cheap: the
    same negative-price window detected on two consecutive polls must not be two findings
    and must not be explained twice.
    """
    raw = "|".join([kind, zone, at.isoformat(), *parts])
    return f"{kind}:{hashlib.sha256(raw.encode()).hexdigest()[:12]}"


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


# --- price ------------------------------------------------------------------


def negative_price(
    series: Series[ScalarObservation], *, kind: str = "price_forward"
) -> list[Finding]:
    """Periods where the day-ahead price is below zero.

    Not an error and not a rounding artefact. A negative clearing price means the market is
    paying consumers to take electricity, because inflexible generation would rather pay
    than shut down. They have become structural rather than exceptional in European markets,
    and they are almost always the most interesting thing in a price series — so no value is
    ever clamped and no run is ever merged into another.

    Runs shallower than :data:`NEGATIVE_PRICE_MIN_DEPTH` are left out of the *list*, which
    is a different thing from being corrected: the price still reads negative everywhere it
    is negative. A day with four fractional dips would otherwise produce four chips and bury
    the one event a reader needed to see.
    """
    below = [p for p in series.points if p.value < 0]
    if not below:
        return []

    runs: list[list[ScalarObservation]] = []
    for point in below:
        if runs and point.at - runs[-1][-1].at <= timedelta(hours=1, minutes=1):
            runs[-1].append(point)
        else:
            runs.append([point])

    unit = _price_unit(series)
    span = _span(series)
    findings = []
    for run in runs:
        deepest = min(run, key=lambda p: p.value)
        if abs(deepest.value) < NEGATIVE_PRICE_MIN_DEPTH:
            continue
        hours = len(run)
        findings.append(
            Finding(
                id=_id("negative_price", series.zone, run[0].at, str(len(run))),
                kind="negative_price",
                zone=series.zone,
                headline=(
                    f"Price goes negative for {hours} period{'s' if hours > 1 else ''} "
                    f"from {_stamp(run[0].at, span=span)}, bottoming at "
                    f"{deepest.value:.2f} {unit}"
                ),
                detail=(
                    "The market is paying consumers to take electricity: inflexible "
                    "generation would rather pay than shut down. Using power here earns "
                    "money rather than costing it."
                ),
                at=run[0].at,
                until=run[-1].at,
                magnitude=deepest.value,
                unit=unit,
                # Depth matters more than duration: one hour at -400 is a bigger story than
                # six at -2, and the scale is capped so a record-breaking hour does not
                # saturate every other finding out of the list.
                significance=min(1.0, abs(deepest.value) / 100.0),
                evidence=(
                    Evidence(label="deepest", value=deepest.value, unit=unit, at=deepest.at),
                    Evidence(label="periods", value=float(hours)),
                ),
                intent=ViewIntent(
                    kind=IntentKind.HIGHLIGHT_WINDOW,
                    reason=(
                        f"{hours} period(s) of negative price from {_stamp(run[0].at, span=span)}"
                    ),
                    zone=series.zone,
                    signal="price",
                    panel="forecast",
                    at=run[0].at,
                    until=run[-1].at,
                ),
                derived=Derived.of(
                    "events.negative_price(threshold=0)", [_ref(series, "price", kind)]
                ),
            )
        )
    return findings


def _price_unit(series: Series[ScalarObservation]) -> str:
    if not series.points:
        return "EUR/MWh"
    first = series.points[0]
    currency = getattr(first, "currency", None) or "EUR"
    denominator = getattr(first, "unit", None) or "MWh"
    return f"{currency}/{denominator}"


# --- carbon -----------------------------------------------------------------


def carbon_swing(forecast: Series[ScalarObservation]) -> list[Finding]:
    """A large predicted move in carbon intensity, in either direction.

    Reported as a ratio rather than an absolute change so it means the same thing in a zone
    that runs at 30 gCO₂eq/kWh and one that runs at 600. A doubling is a doubling.
    """
    points = [p for p in forecast.points if p.value > 0]
    if len(points) < 3:
        return []

    low = min(points, key=lambda p: p.value)
    high = max(points, key=lambda p: p.value)
    ratio = high.value / low.value
    if ratio < CARBON_SWING_RATIO:
        return []

    span = _span(forecast)

    rising = high.at > low.at
    return [
        Finding(
            id=_id("carbon_swing", forecast.zone, low.at, f"{ratio:.2f}"),
            kind="carbon_swing",
            zone=forecast.zone,
            headline=(
                f"Carbon intensity {'climbs' if rising else 'falls'} "
                f"{ratio:.1f}x — {low.value:.0f} to {high.value:.0f} gCO₂eq/kWh "
                f"between {_stamp(min(low.at, high.at), span=span)} and "
                f"{_stamp(max(low.at, high.at), span=span)}"
            ),
            detail=(
                "A forecast, not an outcome. It is what was predicted at the issue time "
                "above, and the same hours will read differently once they have happened."
            ),
            at=min(low.at, high.at),
            until=max(low.at, high.at),
            magnitude=round(ratio, 2),
            unit="x",
            significance=min(1.0, (ratio - 1) / 3),
            evidence=(
                Evidence(label="lowest", value=low.value, unit="gCO2eq/kWh", at=low.at),
                Evidence(label="highest", value=high.value, unit="gCO2eq/kWh", at=high.at),
            ),
            intent=ViewIntent(
                kind=IntentKind.HIGHLIGHT_WINDOW,
                reason=f"carbon intensity moves {ratio:.1f}x across this window",
                zone=forecast.zone,
                signal="carbon_intensity",
                panel="forecast",
                at=min(low.at, high.at),
                until=max(low.at, high.at),
            ),
            derived=Derived.of(
                f"events.carbon_swing(ratio>={CARBON_SWING_RATIO})",
                [_ref(forecast, "carbon_intensity", "forecast")],
                "A ratio between the extremes of the window, not a trend through it.",
            ),
        )
    ]


def renewable_surge(forecast: Series[ScalarObservation]) -> list[Finding]:
    """A large predicted rise in renewable share, in percentage points."""
    points = list(forecast.points)
    if len(points) < 3:
        return []

    low = min(points, key=lambda p: p.value)
    later = [p for p in points if p.at > low.at]
    if not later:
        return []
    high = max(later, key=lambda p: p.value)

    rise = high.value - low.value
    if rise < RENEWABLE_SURGE_POINTS:
        return []

    return [
        Finding(
            id=_id("renewable_surge", forecast.zone, low.at, f"{rise:.0f}"),
            kind="renewable_surge",
            zone=forecast.zone,
            headline=(
                f"Renewable share rises {rise:.0f} points to {high.value:.0f}% "
                f"by {_stamp(high.at, span=_span(forecast))}"
            ),
            at=low.at,
            until=high.at,
            magnitude=round(rise, 1),
            unit="percentage points",
            significance=min(1.0, rise / 60.0),
            evidence=(
                Evidence(label="from", value=low.value, unit="%", at=low.at),
                Evidence(label="to", value=high.value, unit="%", at=high.at),
            ),
            intent=ViewIntent(
                kind=IntentKind.HIGHLIGHT_WINDOW,
                reason=f"renewable share climbs {rise:.0f} points across this window",
                zone=forecast.zone,
                signal="renewable_percentage",
                panel="forecast",
                at=low.at,
                until=high.at,
            ),
            derived=Derived.of(
                f"events.renewable_surge(rise>={RENEWABLE_SURGE_POINTS}pp)",
                [_ref(forecast, "renewable_percentage", "forecast")],
            ),
        )
    ]


# --- the flow-tracing story -------------------------------------------------


def import_dependence(
    production: MixBreakdown, consumption: MixBreakdown, flows: Flows
) -> list[Finding]:
    """When what a zone *uses* differs materially from what it *generates*.

    This is the finding only Electricity Maps can support, and the one most often reduced to
    a chart legend. Flow-tracing resolves imports back through the network to whatever
    actually generated them, so a zone can run on its own wind by the production numbers and
    still be consuming a neighbour's coal.

    The detector compares the two breakdowns source by source and reports the largest
    divergence, with the net import that explains it.
    """
    if not production.entries or not consumption.entries:
        return []

    net_import = flows.net_import_mw
    total = consumption.total_mw or production.total_mw
    if not total or total <= 0:
        return []

    share = net_import / total
    if abs(share) < IMPORT_DOMINANCE:
        return []

    produced = {e.source: e.percent or 0.0 for e in production.entries}
    consumed = {e.source: e.percent or 0.0 for e in consumption.entries}
    gaps = {
        source: consumed.get(source, 0.0) - produced.get(source, 0.0)
        for source in set(produced) | set(consumed)
    }
    if not gaps:
        return []

    source, gap = max(gaps.items(), key=lambda item: abs(item[1]))
    if abs(gap) < 1.0:
        return []

    importing = share > 0
    partners = sorted(
        (e for e in flows.edges if (e.net_flow_mw < 0) == importing),
        key=lambda e: abs(e.net_flow_mw),
        reverse=True,
    )
    partner = partners[0].counterpart_zone if partners else None

    verb = "imports" if importing else "exports"
    return [
        Finding(
            id=_id("import_dependence", consumption.zone, consumption.at, source),
            kind="import_dependence",
            zone=consumption.zone,
            headline=(
                f"{consumption.zone} {verb} {abs(share):.0%} of its electricity"
                + (f", mostly {'from' if importing else 'to'} {partner}" if partner else "")
                + f" — {source} is {abs(gap):.0f} points "
                + ("higher" if gap > 0 else "lower")
                + " in what it uses than in what it generates"
            ),
            detail=(
                "Flow-traced consumption against domestic production. The first is what is "
                "actually in the socket once imports are traced to their origin; the second "
                "is only what this zone generated. They answer different questions."
            ),
            at=consumption.at,
            magnitude=round(gap, 2),
            unit="percentage points",
            significance=min(1.0, abs(share)),
            evidence=(
                Evidence(label="net import", value=round(net_import, 1), unit="MW"),
                Evidence(
                    label=f"{source} produced", value=round(produced.get(source, 0.0), 1), unit="%"
                ),
                Evidence(
                    label=f"{source} consumed", value=round(consumed.get(source, 0.0), 1), unit="%"
                ),
            ),
            intent=ViewIntent(
                kind=IntentKind.FOCUS,
                reason=f"{abs(share):.0%} of this zone's electricity crosses a border",
                zone=consumption.zone,
                panel="mix",
                at=consumption.at,
            ),
            derived=Derived(
                method=f"events.import_dependence(share>={IMPORT_DOMINANCE})",
                inputs=(
                    InputRef(
                        zone=production.zone,
                        signal="electricity_mix",
                        kind="mix",
                        points=len(production.entries),
                        provenance=production.provenance,
                    ),
                    InputRef(
                        zone=consumption.zone,
                        signal="electricity_mix_flow_traced",
                        kind="mix",
                        points=len(consumption.entries),
                        provenance=consumption.provenance,
                    ),
                    InputRef(
                        zone=flows.zone,
                        signal="electricity_flows",
                        kind="flows",
                        points=len(flows.edges),
                        provenance=flows.provenance,
                    ),
                ),
                provenance=weakest(
                    (production.provenance, consumption.provenance, flows.provenance)
                ),
                caveats=(
                    "Net exchange at one instant. It names the largest trading partner, "
                    "not the origin of any particular electron — flow-tracing resolves that "
                    "across the whole network, not one border.",
                ),
            ),
        )
    ]


# --- the disagreement -------------------------------------------------------


def cheap_and_clean_disagree(divergence: Divergence, aligned: Aligned) -> list[Finding]:
    """When the cheapest window and the cleanest window are different hours.

    The finding that bridges the two questions people are told to ask — *use power when it
    is clean* and *use power when it is cheap* — and that nobody mentions can conflict.
    Reports both windows and what choosing each costs on the other objective, and stops
    there: what that trade is worth is a judgement this module does not have.
    """
    best_a, best_b = divergence.best_a, divergence.best_b
    if best_a is None or best_b is None or divergence.separation_hours is None:
        return []
    if divergence.separation_hours < MIN_SEPARATION_HOURS:
        return []

    carbon_cost = best_b.other_mean
    price_cost = best_a.other_mean
    if carbon_cost is None or price_cost is None:
        return []

    span = aligned.window()
    unit = aligned.b_unit or "EUR/MWh"
    extra = price_cost - carbon_cost
    avoided = best_b.other_mean - best_a.mean if best_b.other_mean is not None else None

    return [
        Finding(
            id=_id(
                "cheap_clean_divergence",
                divergence.zone,
                best_b.start,
                best_a.start.isoformat(),
            ),
            kind="cheap_clean_divergence",
            zone=divergence.zone,
            headline=(
                f"Cheapest and cleanest are {divergence.separation_hours:.0f} hours apart: "
                f"cheapest from {_stamp(best_b.start, span=span)}, "
                f"cleanest from {_stamp(best_a.start, span=span)}"
            ),
            detail=(
                f"Running in the cleanest window instead of the cheapest costs "
                f"{extra:+.2f} {unit} on average"
                + (
                    f" and avoids {avoided:.0f} gCO₂eq/kWh."
                    if avoided is not None and avoided > 0
                    else "."
                )
                + " Whether that is worth it is not a question this lab answers."
            ),
            at=min(best_a.start, best_b.start),
            until=max(best_a.end, best_b.end),
            magnitude=divergence.separation_hours,
            unit="hours",
            significance=min(1.0, divergence.separation_hours / 12.0),
            evidence=(
                Evidence(
                    label="cheapest window price", value=best_b.mean, unit=unit, at=best_b.start
                ),
                Evidence(
                    label="cleanest window price", value=price_cost, unit=unit, at=best_a.start
                ),
                Evidence(
                    label="cheapest window carbon",
                    value=carbon_cost,
                    unit="gCO2eq/kWh",
                    at=best_b.start,
                ),
                Evidence(
                    label="cleanest window carbon",
                    value=best_a.mean,
                    unit="gCO2eq/kWh",
                    at=best_a.start,
                ),
            ),
            intent=ViewIntent(
                kind=IntentKind.HIGHLIGHT_WINDOW,
                reason="the cheapest and cleanest windows are different hours",
                zone=divergence.zone,
                signal="price",
                panel="forecast",
                at=min(best_a.start, best_b.start),
                until=max(best_a.end, best_b.end),
            ),
            derived=Derived(
                method=f"events.cheap_and_clean_disagree over {divergence.derived.method}",
                inputs=divergence.derived.inputs,
                provenance=divergence.derived.provenance,
                caveats=(
                    *divergence.derived.caveats,
                    "The carbon figure is a flow-traced average over consumption. Shifting "
                    "demand changes the marginal unit, which is a different quantity — so "
                    "the avoided figure is an accounting difference, not a measured "
                    "abatement.",
                ),
            ),
        )
    ]


def rank(findings: list[Finding]) -> list[Finding]:
    """Most significant first, then earliest.

    Significance is only comparable within a kind, so this ordering is a presentation
    convenience rather than a claim that the first finding matters most.
    """
    return sorted(findings, key=lambda f: (-f.significance, f.at))
