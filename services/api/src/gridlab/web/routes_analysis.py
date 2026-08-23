"""Derived values: findings, divergence, baselines.

These endpoints compute rather than fetch. Everything they return is arithmetic over the
same series ``/grid`` already serves, so any number here can be checked against a request a
human could make themselves — which is the property that makes the whole thing auditable,
and the reason the analysis layer is not allowed to reach past the source interface.

Every response carries a `derived` block: the weakest provenance among the inputs, what
those inputs were, the method and its parameters, and what the number is *not*. A computed
value is easier to mistake for a measured one than a measured one is.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from gridlab.analysis import baseline as baseline_analysis
from gridlab.analysis import events as event_detection
from gridlab.analysis.align import align
from gridlab.analysis.divergence import Divergence, analyse
from gridlab.domain.models import Finding, ScalarObservation, Series
from gridlab.web.routes_grid import SERIES_SIGNALS, _require_zone
from gridlab.web.state import LabState, lab

router = APIRouter(tags=["analysis"])

Lab = Annotated[LabState, Depends(lab)]

#: How long a flexible block is assumed to be, in periods, when comparing windows.
#:
#: Three hourly periods is a plausible EV charge or a wash-and-dry. It is a parameter rather
#: than a truth: a long enough block covers both the cheap and the clean periods and the
#: question dissolves, which is itself worth being able to show.
DEFAULT_WINDOW_PERIODS = 3


async def _forward_carbon(state: LabState, zone: str) -> Series[ScalarObservation] | None:
    """The carbon forecast, capped at the horizon price can actually reach.

    72 hours is available for carbon and is the wrong window for anything joining it to
    price: forward price runs out at the end of the delivery day the auction covered, so
    the extra two days would align against nothing and quietly halve the reported coverage.
    """
    return await state.source.forecast(zone, signal="carbon_intensity", horizon_hours=24)


async def _divergence(state: LabState, zone: str, *, window_periods: int) -> Divergence | None:
    carbon = await _forward_carbon(state, zone)
    price = await state.source.price_forward(zone)
    if carbon is None or price is None:
        return None

    aligned = align(
        carbon,
        price,
        a_signal="carbon_intensity",
        b_signal="price",
        a_kind="forecast",
        b_kind="price_forward",
    )
    if aligned is None:
        return None
    return analyse(aligned, window_periods=window_periods)


@router.get(
    "/analysis/{zone}/divergence",
    response_model=None,
    summary="Do cheap and clean mean the same periods here?",
)
async def divergence(
    zone: str,
    state: Lab,
    window_periods: Annotated[
        int,
        Query(ge=1, le=48, description="Length of the flexible block, in periods."),
    ] = DEFAULT_WINDOW_PERIODS,
) -> dict[str, Any]:
    """Rank correlation between forward price and forward carbon, plus the two best windows.

    Price is set by the **marginal** unit through uniform-price auction clearing; carbon
    intensity is a flow-traced **average** over consumption. They are different functions of
    the same grid, so they agree in some zones and on some days and not in others, and the
    disagreement is neither noise nor error.

    Nothing here recommends anything. It reports what choosing one objective costs on the
    other and stops, because whether that trade is worth making involves values this lab
    does not have.

    404 when the two cannot be joined: no forward price for this zone, no carbon forecast,
    or — the common case in replay — a scenario recorded before forward price was captured.
    """
    result = await _divergence(state, zone, window_periods=window_periods)
    if result is None:
        await _require_zone(state, zone)
        raise HTTPException(
            status_code=404,
            detail=(
                f"Cannot compare price and carbon for {zone}. This needs a carbon forecast "
                f"and a forward day-ahead price that overlap. Day-ahead price is Europe plus "
                f"a few zones; in replay mode, scenarios recorded before forward price was "
                f"captured have none - re-record with `make scenario-live`."
            ),
        )
    return result.model_dump(mode="json")


@router.get(
    "/analysis/{zone}/baseline",
    response_model=None,
    summary="Is this unusual for this zone?",
)
async def zone_baseline(
    zone: str,
    state: Lab,
    signal: Annotated[str, Query(description=f"One of: {', '.join(SERIES_SIGNALS)}")] = (
        "carbon_intensity"
    ),
) -> dict[str, Any]:
    """Where the current value sits in this zone's own recent distribution.

    **This is the endpoint to build a ranking on, not `/compare`.** Raw values order zones
    permanently — hydro wins every day, coal loses every day, and nothing ever changes.
    Scoring each zone against itself asks whether today is unusual *here*, which is a
    question that has different answers on different days.

    The baseline is only as deep as the history behind it. On a key without `past-range`
    that is roughly 24 hours, which supports "unusual today" and not "unusual for this time
    of year". The response says which.
    """
    await _require_zone(state, zone)
    if signal not in SERIES_SIGNALS:
        raise HTTPException(
            status_code=400,
            detail={"error": f"Unknown signal {signal!r}", "available": list(SERIES_SIGNALS)},
        )

    snapshot = await state.source.snapshot(zone)
    current = getattr(snapshot, signal, None)
    if current is None:
        raise HTTPException(status_code=404, detail=f"No current {signal} for {zone} to score.")

    end = state.source.clock.now()
    history = await state.source.history(
        zone, signal=signal, start=end - timedelta(days=7), end=end
    )
    if history is None:
        raise HTTPException(status_code=404, detail=f"No {signal} history for {zone}.")

    result = baseline_analysis.score(current.value, history, signal=signal)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Only {len(history.points)} historical points for {zone}/{signal} - fewer "
                f"than the {baseline_analysis.MIN_SAMPLES} needed before a percentile means "
                f"anything. This is the `past-range` limit, not a bug."
            ),
        )
    return result.model_dump(mode="json")


@router.get(
    "/analysis/{zone}/findings",
    response_model=None,
    summary="What is worth looking at, found without a language model",
)
async def findings(
    zone: str,
    state: Lab,
    window_periods: Annotated[int, Query(ge=1, le=48)] = DEFAULT_WINDOW_PERIODS,
) -> dict[str, Any]:
    """Everything the deterministic detectors found for this zone, most significant first.

    This is what lets the lab say *where to look* before anyone knows what to ask. Each
    finding carries the evidence that produced it and a `intent` describing the view that
    would show it, so a client can turn one into navigation without interpreting prose.

    **No model is involved.** Detection is arithmetic: free, instant, reproducible, and
    checkable. Anything a reader might act on is computed here; explaining it in language is
    a separate and optional step.

    An empty list is a real answer. A quiet grid is quiet, and inventing something to say
    about it would make every finding worth less.
    """
    await _require_zone(state, zone)
    found: list[Finding] = []

    price = await state.source.price_forward(zone)
    if price is not None:
        found += event_detection.negative_price(price)

    carbon = await _forward_carbon(state, zone)
    if carbon is not None:
        found += event_detection.carbon_swing(carbon)

    renewable = await state.source.forecast(zone, signal="renewable_percentage", horizon_hours=24)
    if renewable is not None:
        found += event_detection.renewable_surge(renewable)

    production = await state.source.mix(zone, flow_traced=False)
    consumption = await state.source.mix(zone, flow_traced=True)
    flows = await state.source.flows(zone)
    if production is not None and consumption is not None and flows is not None:
        found += event_detection.import_dependence(production, consumption, flows)

    result = await _divergence(state, zone, window_periods=window_periods)
    if result is not None and carbon is not None and price is not None:
        aligned = align(
            carbon,
            price,
            a_signal="carbon_intensity",
            b_signal="price",
            a_kind="forecast",
            b_kind="price_forward",
        )
        if aligned is not None:
            found += event_detection.cheap_and_clean_disagree(result, aligned)

    ranked = event_detection.rank(found)
    return {
        "zone": zone,
        "at": state.source.clock.now().isoformat(),
        "count": len(ranked),
        "findings": [f.model_dump(mode="json") for f in ranked],
        "note": (
            "Detected deterministically, with no language model. Significance orders "
            "findings of the same kind and does not compare across kinds."
        ),
    }
