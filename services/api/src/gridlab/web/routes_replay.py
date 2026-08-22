"""Transport controls for replay mode.

A demo is a performance. Being able to pause on the interesting hour, talk over it, and
then let it run is worth more than smooth playback — so the clock exposes the same controls
a video player would.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from gridlab.web.state import LabState, lab

router = APIRouter(tags=["replay"])

Lab = Annotated[LabState, Depends(lab)]


def _clock(state: LabState) -> Any:
    clock = state.replay_clock
    if clock is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Not in replay mode. Set GRIDLAB_MODE=replay, or POST "
                "/api/v1/replay/scenario to load a scenario."
            ),
        )
    return clock


@router.get("/replay/scenarios", summary="Available scenarios")
async def scenarios(state: Lab) -> dict[str, Any]:
    """Every scenario on disk, with its provenance.

    `provenance` is the field that matters. A `recorded` scenario really happened; a
    `synthetic` one was generated and must never be presented as measured data.
    """
    return {
        "current": state.scenario.id if state.scenario else None,
        "scenarios": [s.summary() for s in state.library.all()],
    }


@router.post("/replay/scenario", summary="Load a scenario")
async def load_scenario(state: Lab, id: Annotated[str, Query(alias="id")]) -> dict[str, Any]:
    try:
        state.switch_scenario(id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return await state_payload(state)


@router.post("/replay/pause", summary="Pause the clock")
async def pause(state: Lab) -> dict[str, Any]:
    _clock(state).pause()
    return await state_payload(state)


@router.post("/replay/resume", summary="Resume the clock")
async def resume(state: Lab) -> dict[str, Any]:
    _clock(state).resume()
    return await state_payload(state)


@router.post("/replay/seek", summary="Jump to an instant")
async def seek(state: Lab, to: Annotated[datetime, Query()]) -> dict[str, Any]:
    """Move to a moment inside the scenario window. Out-of-range values are clamped."""
    _clock(state).seek(to)
    return await state_payload(state)


@router.post("/replay/speed", summary="Set playback speed")
async def speed(
    state: Lab,
    multiplier: Annotated[
        float,
        Query(
            gt=0,
            le=100_000,
            description="1 is real time. 60 plays an hour per minute; 1440 plays a day per minute.",
        ),
    ],
) -> dict[str, Any]:
    try:
        _clock(state).set_speed(multiplier)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await state_payload(state)


async def state_payload(state: LabState) -> dict[str, Any]:
    clock = state.replay_clock
    if clock is None:
        return {"mode": state.mode.value}
    start, end = clock.window
    return {
        "mode": state.mode.value,
        "scenario": state.scenario.summary() if state.scenario else None,
        "now": clock.now().isoformat(),
        "running": clock.running,
        "speed": clock.speed,
        "progress": round(clock.progress(), 4),
        "window": {"start": start.isoformat(), "end": end.isoformat() if end else None},
    }
