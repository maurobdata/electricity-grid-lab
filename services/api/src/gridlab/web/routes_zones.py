"""Zones the lab can answer for."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from gridlab.web.state import LabState, lab

router = APIRouter(tags=["zones"])

Lab = Annotated[LabState, Depends(lab)]

#: Human-readable names for the zones this lab is configured around.
#:
#: Deliberately small. The full list comes from `/v4/zones` at runtime; this is only here
#: so a picker reads "West Denmark" rather than "DK-DK1" before any probe has run.
#:
#: The zone set spans very clean (NO, FR), very dirty (PL), and very volatile (DK, DE, ES)
#: grids, so any experiment built on it meets all three shapes rather than one.
ZONE_NAMES: dict[str, str] = {
    "DK-DK1": "West Denmark (Jutland/Funen)",
    "DK-DK2": "East Denmark (Zealand, incl. Copenhagen)",
    "DE": "Germany",
    "FR": "France",
    "ES": "Spain",
    "PL": "Poland",
    "NO-NO2": "Norway South",
    "SE-SE4": "Sweden South",
    "GB": "Great Britain",
    "NL": "Netherlands",
    "BE": "Belgium",
    "IT-NO": "Italy North",
    "PT": "Portugal",
    "FI": "Finland",
    "IE": "Ireland",
}


@router.get("/zones", summary="Zones available in the current mode")
async def zones(state: Lab) -> dict[str, Any]:
    """What can be asked about right now.

    In replay mode this is the scenario's zones and nothing else. In live mode it is
    `GRIDLAB_ZONES`, and a zone appearing here is not a promise the token can reach it —
    check `/api/v1/capabilities` for that.
    """
    keys = await state.source.zones()
    return {
        "mode": state.mode.value,
        "provenance": state.source.provenance.value,
        "zones": [{"key": key, "name": ZONE_NAMES.get(key, key)} for key in keys],
    }
