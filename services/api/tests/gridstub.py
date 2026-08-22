"""A stand-in for the Grid Lab API, backed by the shapes the real one returns.

Shared by the agent tests so both exercise the same responses — including the refusals,
which is where most of the interesting agent behaviour lives.

Deliberately hand-written rather than a live call: the agent tests are about the boundary,
and a boundary that only holds when the network is up is not a boundary.
"""

from __future__ import annotations

from typing import Any

import httpx

ZONE = "DK-DK2"


def _api_handler(request: httpx.Request) -> httpx.Response:
    """Answer like the real API, including its refusals."""
    path = request.url.path.removeprefix("/api/v1")
    params = request.url.params

    if path == "/status":
        return httpx.Response(200, json={"mode": "replay", "provenance": "recorded", "now": "X"})
    if path == "/zones":
        return httpx.Response(
            200,
            json={
                "mode": "replay",
                "provenance": "recorded",
                "zones": [{"key": ZONE, "name": "East Denmark"}],
            },
        )

    if not path.startswith(f"/grid/{ZONE}") and path != "/compare":
        return httpx.Response(
            404,
            json={"detail": {"error": "Unknown zone", "available": [ZONE]}},
        )

    if path.endswith("/now"):
        return httpx.Response(200, json=_snapshot())
    if path.endswith("/mix"):
        traced = params.get("flow_traced") == "true"
        return httpx.Response(200, json=_mix(flow_traced=traced))
    if path.endswith("/price"):
        return httpx.Response(200, json=_price(-54.4))
    if path.endswith("/flows"):
        return httpx.Response(200, json=_flows())
    if path.endswith("/forecast") or path.endswith("/history"):
        return httpx.Response(200, json=_series(params.get("signal", "carbon_intensity")))
    if path == "/compare":
        return httpx.Response(200, json=_comparison())

    return httpx.Response(404, json={"detail": "nothing here"})


def _observation(value: float, **extra: Any) -> dict[str, Any]:
    return {
        "zone": ZONE,
        "at": "2026-08-22T17:00:00Z",
        "provenance": "recorded",
        "is_estimated": False,
        "is_stale": False,
        "value": value,
        **extra,
    }


def _snapshot() -> dict[str, Any]:
    return {
        "zone": ZONE,
        "at": "2026-08-22T17:00:00Z",
        "provenance": "recorded",
        "carbon_intensity": _observation(63.0, is_estimated=True, estimation_method="X"),
        "renewable_percentage": _observation(98.0),
        "carbon_free_percentage": _observation(98.0),
        "price": _observation(141.73, currency="EUR", unit="MWh", source="nordpool.com"),
        "load": _observation(662.5),
        "mix": _mix(flow_traced=True),
        "flows": _flows(),
        "unavailable": [],
    }


def _mix(*, flow_traced: bool) -> dict[str, Any]:
    entries = (
        [{"source": "wind", "power_mw": 546.1, "percent": 75.2}]
        if flow_traced
        else [{"source": "wind", "power_mw": 640.0, "percent": 79.8}]
    )
    return {
        "zone": ZONE,
        "at": "2026-08-22T17:00:00Z",
        "provenance": "recorded",
        "is_estimated": False,
        "entries": [*entries, {"source": "gas", "power_mw": 9.5, "percent": 1.3}],
        "flow_traced": flow_traced,
        "total_mw": 726.0,
    }


def _flows() -> dict[str, Any]:
    return {
        "zone": ZONE,
        "at": "2026-08-22T17:00:00Z",
        "provenance": "recorded",
        "is_estimated": False,
        "edges": [
            {"counterpart_zone": "DE", "net_flow_mw": -308.0},
            {"counterpart_zone": "SE-SE4", "net_flow_mw": 453.0},
        ],
        "net_import_mw": -145.0,
    }


def _price(value: float) -> dict[str, Any]:
    return _observation(value, currency="EUR", unit="MWh", source="nordpool.com")


def _series(signal: str, count: int = 24) -> dict[str, Any]:
    return {
        "zone": ZONE,
        "signal": signal,
        "granularity": "hourly",
        "horizon_hours": 24,
        "issued_at": "2026-08-22T17:00:00Z",
        "provenance": "recorded",
        "estimated_fraction": 0.08,
        "points": [
            {
                "at": f"2026-08-22T{hour:02d}:00:00Z",
                "value": float(50 + hour * 3),
                "is_estimated": hour % 12 == 0,
            }
            for hour in range(count)
        ],
    }


def _comparison() -> dict[str, Any]:
    return {
        "signal": "carbon_intensity",
        "at": "2026-08-22T17:00:00Z",
        "provenance": "recorded",
        "zones": {ZONE: _observation(63.0), "DE": _observation(217.0)},
        "note": "Raw values...",
    }
