"""Grid data: now, mix, forecast, price, flows, history, compare.

These are the endpoints the PWA renders and the agent's tools call. Both go through the
same source interface, so live and replay are indistinguishable from here up.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from gridlab.domain.models import GridSnapshot, ScalarObservation, Series
from gridlab.web.state import LabState, lab

router = APIRouter(tags=["grid"])

Lab = Annotated[LabState, Depends(lab)]

#: Signals that exist as a series. Kept explicit so a typo is a 400 with a list of options
#: rather than an empty chart.
SERIES_SIGNALS = (
    "carbon_intensity",
    "renewable_percentage",
    "carbon_free_percentage",
    "price",
    "load",
)

#: The largest history window a single request may ask for.
#:
#: 366 days at hourly granularity is ~8,800 points and 37 upstream chunk requests. Beyond
#: that a caller wants a bulk export, not an HTTP endpoint, and an unbounded window is an
#: easy way to burn a trial key by accident.
MAX_HISTORY_DAYS = 366


async def _require_zone(state: LabState, zone: str) -> None:
    known = await state.source.zones()
    if known and zone not in known:
        raise HTTPException(
            status_code=404,
            detail={
                "error": f"Unknown zone {zone!r}",
                "available": list(known),
                "hint": (
                    "In replay mode only the scenario's zones exist. In live mode this is "
                    "GRIDLAB_ZONES, filtered by what the token can reach."
                ),
            },
        )


@router.get("/grid/{zone}/now", response_model=GridSnapshot, summary="Everything, right now")
async def now(zone: str, state: Lab) -> GridSnapshot:
    """A full snapshot.

    Signals that could not be provided are listed in `unavailable` rather than omitted, so
    the UI can distinguish "your plan does not include this" from "nobody asked".
    """
    await _require_zone(state, zone)
    return await state.source.snapshot(zone)


@router.get("/grid/{zone}/mix", summary="Generation mix")
async def mix(
    zone: str,
    state: Lab,
    flow_traced: Annotated[
        bool,
        Query(
            description=(
                "True (default) returns the flow-traced consumption mix: what is actually "
                "available in this zone once imports are traced back to their origin. "
                "False returns what the zone generated. These are different answers to "
                "different questions."
            )
        ),
    ] = True,
) -> dict[str, Any]:
    await _require_zone(state, zone)
    breakdown = await state.source.mix(zone, flow_traced=flow_traced)
    if breakdown is None:
        raise HTTPException(
            status_code=404,
            detail=f"No {'flow-traced' if flow_traced else 'production'} mix for {zone}",
        )
    return breakdown.model_dump(mode="json")


@router.get("/grid/{zone}/price", summary="Day-ahead price")
async def price(zone: str, state: Lab) -> dict[str, Any]:
    await _require_zone(state, zone)
    result = await state.source.price(zone)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No day-ahead price for {zone}. Coverage is Europe plus a few zones, and "
                f"price may not be included in this plan - see /api/v1/capabilities."
            ),
        )
    return result.model_dump(mode="json")


@router.get("/grid/{zone}/flows", summary="Cross-border exchange")
async def flows(zone: str, state: Lab) -> dict[str, Any]:
    """Net flow per neighbour. Positive is export, negative is import."""
    await _require_zone(state, zone)
    result = await state.source.flows(zone)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No flow data for {zone}")
    payload = result.model_dump(mode="json")
    payload["net_import_mw"] = result.net_import_mw
    return payload


@router.get("/grid/{zone}/forecast", response_model=None, summary="Forecast")
async def forecast(
    zone: str,
    state: Lab,
    signal: Annotated[str, Query(description=f"One of: {', '.join(SERIES_SIGNALS)}")] = (
        "carbon_intensity"
    ),
    horizon_hours: Annotated[int, Query(ge=1, le=72)] = 24,
) -> dict[str, Any]:
    """The forward view.

    `issued_at` on the response records when the forecast was made. Keep it: comparing a
    forecast with the outcome is only meaningful if you know when it was issued.

    Horizons above 24 hours are plan-dependent. If this returns fewer points than asked
    for, that is the plan speaking, not a bug.
    """
    await _require_zone(state, zone)
    _validate_signal(signal)
    result = await state.source.forecast(zone, signal=signal, horizon_hours=horizon_hours)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No {signal} forecast for {zone}")
    return _series_payload(result, signal)


@router.get("/grid/{zone}/history", response_model=None, summary="History")
async def history(
    zone: str,
    state: Lab,
    signal: Annotated[str, Query(description=f"One of: {', '.join(SERIES_SIGNALS)}")] = (
        "carbon_intensity"
    ),
    start: Annotated[
        datetime | None,
        Query(description="Defaults to seven days before `end`. See the note on coverage."),
    ] = None,
    end: Annotated[datetime | None, Query(description="Defaults to the current clock.")] = None,
    granularity: Annotated[str, Query()] = "hourly",
) -> dict[str, Any]:
    """The backward view over an explicit window.

    **The window you ask for is not necessarily the window you get.** This endpoint requests
    what you asked for; the response is bounded by what the underlying source can actually
    reach, and the returned points are the truth about that:

    * **Live mode** depends on the plan. `past-range` takes an arbitrary window, but a token
      without it falls back to `history`, which returns only a trailing window the API
      chooses — roughly 24 hours on the free tier measured in August 2026. Asking for seven
      days then yields about one. `GET /api/v1/capabilities` says which applies.
    * **Replay mode** is bounded by the scenario, which is typically 24-48 hours.

    The seven-day default is deliberately left alone rather than trimmed to match the
    weakest plan: it is the right request for a trial or event key, and narrowing it would
    silently under-fetch the moment a better token arrives. Nothing is padded or invented to
    fill the gap.
    """
    await _require_zone(state, zone)
    _validate_signal(signal)

    end = end or state.source.clock.now()
    start = start or end - timedelta(days=7)
    if start >= end:
        raise HTTPException(status_code=400, detail="start must be before end")
    if (end - start) > timedelta(days=MAX_HISTORY_DAYS):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Window exceeds {MAX_HISTORY_DAYS} days. Longer ranges mean dozens of "
                f"upstream requests; fetch them with a script, not a page load."
            ),
        )

    result = await state.source.history(
        zone, signal=signal, start=start, end=end, granularity=granularity
    )
    if result is None:
        raise HTTPException(status_code=404, detail=f"No {signal} history for {zone}")
    return _series_payload(result, signal)


@router.get("/compare", summary="One signal across several zones, at one instant")
async def compare(
    state: Lab,
    zones: Annotated[str, Query(description="Comma-separated zone keys")],
    signal: Annotated[str, Query()] = "carbon_intensity",
) -> dict[str, Any]:
    """Simultaneity is the point: the same moment, several places, wildly different states.

    A caution worth repeating wherever this is used: ranking zones on raw values produces a
    frozen table. Norway's hydro wins every day and Poland's coal loses every day, so
    nothing ever changes and there is no reason to look twice. Anything built on top of
    this that wants a *league* should score each zone against its own baseline instead.
    """
    keys = [z.strip() for z in zones.split(",") if z.strip()]
    if not keys:
        raise HTTPException(status_code=400, detail="No zones given")
    if len(keys) > 12:
        raise HTTPException(status_code=400, detail="At most 12 zones per request")

    known = await state.source.zones()
    unknown = [z for z in keys if known and z not in known]
    if unknown:
        raise HTTPException(
            status_code=404, detail={"unknown_zones": unknown, "available": list(known)}
        )

    try:
        results = await state.source.compare(keys, signal=signal)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "signal": signal,
        "at": state.source.clock.now().isoformat(),
        "provenance": state.source.provenance.value,
        "zones": {
            zone: (obs.model_dump(mode="json") if obs else None) for zone, obs in results.items()
        },
        "note": (
            "Raw values. Ranking zones on these flatters hydro and punishes coal "
            "permanently; score against each zone's own baseline for a league."
        ),
    }


def _series_payload(series: Series[ScalarObservation], signal: str) -> dict[str, Any]:
    """Serialize a series without letting a declared response model eat its values.

    FastAPI filters a response to the fields of its declared `response_model`. Declaring
    `Series[ScalarObservation]` therefore silently drops every subclass field — the price's
    currency, the carbon intensity's emission factor, and, before `ScalarObservation`
    existed, the value itself. Dumping the real objects keeps what is actually there.

    `provenance` and `estimated_fraction` are computed properties rather than fields, so
    they are added explicitly. They are the two things the UI needs to badge a chart
    honestly, and they must never be inferred from an empty response.
    """
    return {
        "zone": series.zone,
        "signal": signal,
        "granularity": series.granularity,
        "horizon_hours": series.horizon_hours,
        "issued_at": series.issued_at.isoformat() if series.issued_at else None,
        "provenance": series.provenance.value,
        "estimated_fraction": round(series.estimated_fraction, 4),
        "points": [p.model_dump(mode="json") for p in series.points],
    }


def _validate_signal(signal: str) -> None:
    if signal not in SERIES_SIGNALS:
        raise HTTPException(
            status_code=400,
            detail={"error": f"Unknown signal {signal!r}", "available": list(SERIES_SIGNALS)},
        )
