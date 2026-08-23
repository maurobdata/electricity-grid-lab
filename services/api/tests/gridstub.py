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

    known = (f"/grid/{ZONE}", f"/analysis/{ZONE}")
    if not path.startswith(known) and path != "/compare":
        return httpx.Response(
            404,
            json={"detail": {"error": "Unknown zone", "available": [ZONE]}},
        )

    if path.endswith("/now"):
        return httpx.Response(200, json=_snapshot())
    if path.endswith("/mix"):
        traced = params.get("flow_traced") == "true"
        return httpx.Response(200, json=_mix(flow_traced=traced))
    if path.endswith("/price/forward"):
        return httpx.Response(200, json=_forward_price())
    if path.endswith("/findings"):
        return httpx.Response(200, json=_findings())
    if path.endswith("/divergence"):
        return httpx.Response(200, json=_divergence())
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


def _forward_price() -> dict[str, Any]:
    """Day-ahead prices reaching past the clock, mixing cleared and modelled rows.

    The mix is deliberate: `combined` returns both, and a stub with only one kind would let
    a handler drop `source` without any test noticing.
    """
    return {
        "zone": ZONE,
        "signal": "price",
        "granularity": "hourly",
        "horizon_hours": None,
        "issued_at": "2026-08-22T11:29:42Z",
        "provenance": "recorded",
        "estimated_fraction": 0.0,
        "points": [
            {
                "at": f"2026-08-23T{hour:02d}:00:00Z",
                "value": float(40 - hour * 4),
                "is_estimated": False,
                "currency": "EUR",
                "unit": "MWh",
                **({"source": "nordpool.com"} if hour < 6 else {}),
            }
            for hour in range(12)
        ],
    }


def _findings() -> dict[str, Any]:
    return {
        "zone": ZONE,
        "at": "2026-08-22T17:00:00Z",
        "count": 1,
        "findings": [
            {
                "id": "negative_price:abc123",
                "kind": "negative_price",
                "zone": ZONE,
                "headline": (
                    "Price goes negative for 2 periods from 10:00, bottoming at -8.00 EUR/MWh"
                ),
                "detail": "The market is paying consumers to take electricity.",
                "at": "2026-08-23T10:00:00Z",
                "until": "2026-08-23T11:00:00Z",
                "magnitude": -8.0,
                "unit": "EUR/MWh",
                "significance": 0.08,
                "evidence": [{"label": "deepest", "value": -8.0, "unit": "EUR/MWh"}],
                "intent": {
                    "kind": "highlight_window",
                    "reason": "2 period(s) of negative price from 10:00",
                    "zone": ZONE,
                    "signal": "price",
                },
                "derived": {
                    "method": "events.negative_price(threshold=0)",
                    "inputs": [],
                    "provenance": "recorded",
                    "caveats": [],
                },
            }
        ],
        "note": "Detected deterministically, with no language model.",
    }


def _divergence() -> dict[str, Any]:
    return {
        "zone": ZONE,
        "a_signal": "carbon_intensity",
        "b_signal": "price",
        "a_unit": None,
        "b_unit": "EUR/MWh",
        "periods": 12,
        "correlation": 0.21,
        "agreement": "weak",
        "best_a": {
            "start": "2026-08-23T02:00:00Z",
            "end": "2026-08-23T05:00:00Z",
            "periods": 3,
            "mean": 40.0,
            "other_mean": 30.0,
        },
        "best_b": {
            "start": "2026-08-23T09:00:00Z",
            "end": "2026-08-23T12:00:00Z",
            "periods": 3,
            "mean": 8.0,
            "other_mean": 210.0,
        },
        "separation_hours": 7.0,
        "disagreeing_periods": ["2026-08-23T09:00:00Z"],
        "derived": {
            "method": "divergence.spearman + best_window(periods=3)",
            "inputs": [],
            "provenance": "recorded",
            "caveats": ["Rank correlation, not a causal claim."],
        },
    }
