"""Health, mode and capabilities.

The capabilities endpoint exists because "what can this key actually reach?" is the
question that decides what is buildable. Answering it in the UI, rather than discovering it
through a 403 during a demo, is the whole point.
"""

from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends

from gridlab import __version__
from gridlab.config import Mode
from gridlab.web.state import LabState, lab

router = APIRouter(tags=["meta"])

Lab = Annotated[LabState, Depends(lab)]


@router.get("/healthz", summary="Liveness")
async def healthz(state: Lab) -> dict[str, Any]:
    return {"status": "ok", "version": __version__, "mode": state.mode.value}


@router.get("/status", summary="What the lab is doing right now")
async def status(state: Lab) -> dict[str, Any]:
    """Mode, clock position, scenario and cache stats.

    The UI keeps this in a persistent strip. Someone watching a demo should never have to
    wonder whether they are looking at live data or a recording.
    """
    clock = state.replay_clock
    payload: dict[str, Any] = {
        "version": __version__,
        "mode": state.mode.value,
        "requested_mode": state.settings.gridlab_mode.value,
        "now": state.source.clock.now().isoformat(),
        "provenance": state.source.provenance.value,
        "zones": list(await state.source.zones()),
        "has_electricity_maps_token": state.settings.has_api_token,
        "has_anthropic_key": state.settings.has_anthropic_key,
    }

    if state.settings.gridlab_mode is Mode.LIVE and state.mode is Mode.REPLAY:
        payload["notice"] = (
            "GRIDLAB_MODE=live was requested but no Electricity Maps token is set, so the "
            "lab fell back to replay. Add ELECTRICITY_MAPS_API_TOKEN to .env."
        )

    # Keyed on the scenario, not the clock. Which scenario is playing is the thing an
    # audience needs on screen, and it stays true even when the clock has been swapped
    # (frozen for a test, stepped by a script). Transport state is added only when there
    # is actually something to transport.
    if state.scenario is not None:
        replay: dict[str, Any] = {"scenario": state.scenario.summary()}
        if clock is not None:
            start, end = clock.window
            replay |= {
                "running": clock.running,
                "speed": clock.speed,
                "progress": round(clock.progress(), 4),
                "window": {
                    "start": start.isoformat(),
                    "end": end.isoformat() if end else None,
                },
            }
        payload["replay"] = replay

    if state.cache is not None:
        payload["cache"] = state.cache.stats()

    return payload


@router.get("/capabilities", summary="What this API token can actually reach")
async def capabilities(state: Lab) -> dict[str, Any]:
    """The result of the last `make probe`, if one has been run.

    Deliberately reads a file rather than probing on request: the probe is a deliberate
    act against an API with no published rate limit, not a side effect of loading a page.

    What a plan grants is a *separate axis* from what the API offers. `/v4/zones` publishes
    an `access` list of exact `signal/temporality` pairs, so this is the authoritative
    answer to "what can we build?" — where `/zones` above only says which zones the current
    mode can answer for.
    """
    path = state.settings.gridlab_capabilities_path
    if path.is_file():
        probed: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        probed["source"] = "probe"
        return probed

    return {
        "source": "unprobed",
        "has_token": state.settings.has_api_token,
        "message": (
            f"No capability probe has been run, or its output is not readable at {path}. "
            f"With a token in .env, run `make probe`: it reads the `access` list published "
            f"by /v4/zones in a single request and writes the result here."
        ),
        # Deliberately no guess at what a token can reach. An earlier version of this
        # message asserted that the free tier covers "roughly one zone" — repeating a claim
        # from the pre-project research. A live probe measured 350 accessible zones, with
        # the real limit being history depth rather than breadth (ADR 0008). Rather than
        # replace one unverified claim with another, this now says only what it knows.
        "configured_zones": list(state.settings.zones),
        "note": (
            "`configured_zones` is GRIDLAB_ZONES, which is what this lab was asked to cover "
            "— not a statement that the token can reach any of them."
        ),
    }
