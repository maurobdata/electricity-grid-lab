"""Health, mode and capabilities.

The capabilities endpoint exists because "what can this key actually reach?" is the
question that decides what is buildable. Answering it in the UI, rather than discovering it
through a 403 during a demo, is the whole point.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends

from gridlab import __version__
from gridlab.config import Mode
from gridlab.web.state import LabState, lab

router = APIRouter(tags=["meta"])

Lab = Annotated[LabState, Depends(lab)]

CAPABILITIES_FILE = Path("/app/capabilities.json")


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

    Deliberately reads a file rather than probing on request: probing costs one API call
    per signal against an undocumented rate limit, and it should be a decision, not a
    side effect of loading a page.
    """
    if CAPABILITIES_FILE.is_file():
        probed: dict[str, Any] = json.loads(CAPABILITIES_FILE.read_text(encoding="utf-8"))
        probed["source"] = "probe"
        return probed

    return {
        "source": "unprobed",
        "has_token": state.settings.has_api_token,
        "message": (
            "No capability probe has been run. With a token in .env, run `make probe` to "
            "find out which zones and signals this plan can reach. Until then, assume "
            "nothing: the free tier is reported to cover roughly one zone."
        ),
        "configured_zones": list(state.settings.zones),
    }
