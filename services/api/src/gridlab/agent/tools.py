"""The seven tools, and nothing else.

**The declared tool list is the security boundary.** The model cannot reach anything that
is not here, so this file is the one to read when asking "what can the agent do?".

Every tool is read-only, every schema is `strict` with `additionalProperties: false`, and
every result carries the provenance and estimation flags of the data underneath. Three
constraints are enforced here rather than trusted to the model:

* **zone allowlisting** — a zone that does not exist in the current mode is refused with
  the list of ones that do, so the model corrects itself instead of guessing;
* **bounded windows** — a history request cannot ask for a decade;
* **downsampling** — a series is capped before it reaches the model, because handing over
  2,880 five-minute points wastes context and degrades the answer.

Adding a tool that can *change* anything needs an ADR. Nothing here can.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from gridlab.agent.gridclient import GridClient, GridUnavailable

log = structlog.get_logger(__name__)

SERIES_SIGNALS = (
    "carbon_intensity",
    "renewable_percentage",
    "carbon_free_percentage",
    "price",
    "load",
)

#: Horizons the API accepts vary per signal; 24 is the only value every forecasting signal
#: takes. Offering the full set here would invite a 400 the model cannot diagnose.
FORECAST_HORIZONS = (6, 24, 48, 72)

MAX_HISTORY_DAYS = 31
MAX_COMPARE_ZONES = 12


@dataclass(frozen=True)
class ToolSpec:
    """A tool, described in provider-neutral terms.

    Kept separate from any SDK's tool format so that adding a second LLM provider means
    writing one translation function, not rewriting the tools.
    """

    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Awaitable[dict[str, Any]]]
    required: tuple[str, ...] = ()

    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": self.parameters,
            "required": list(self.required),
            # Strict mode requires this, and it is what stops a hallucinated parameter
            # arriving silently rather than being rejected.
            "additionalProperties": False,
        }


@dataclass
class ToolContext:
    """Per-conversation state shared by the tools."""

    client: GridClient
    max_points: int = 400
    _zones: list[str] = field(default_factory=list)

    async def known_zones(self) -> list[str]:
        """Zones the lab can answer for right now.

        Cached for the life of a conversation. The set only changes when the scenario
        does, which cannot happen mid-turn.
        """
        if not self._zones:
            self._zones = [zone["key"] for zone in await self.client.zones()]
        return self._zones

    async def require_zone(self, zone: str) -> str:
        known = await self.known_zones()
        if zone in known:
            return zone

        # Case and separator confusion is the common failure ("dk-dk2", "DK_DK2").
        normalised = zone.strip().upper().replace("_", "-")
        for candidate in known:
            if candidate.upper() == normalised:
                return candidate

        raise GridUnavailable(
            f"There is no zone {zone!r} in the current mode. Available: {', '.join(known)}."
        )


# --- shaping results --------------------------------------------------------


def downsample(points: list[dict[str, Any]], cap: int) -> tuple[list[dict[str, Any]], bool]:
    """Reduce a series to at most ``cap`` points, keeping the extremes.

    Plain striding would be simpler and would sometimes delete the most important point in
    the series. A negative price spike or a carbon peak is exactly what somebody is asking
    about, and dropping it while returning a confident-looking curve is worse than
    returning fewer points. So the minimum, the maximum and both endpoints are pinned, and
    the rest is thinned evenly around them.
    """
    if len(points) <= cap:
        return points, False

    values = [p.get("value") for p in points]
    numeric = [(i, v) for i, v in enumerate(values) if isinstance(v, int | float)]

    keep: set[int] = {0, len(points) - 1}
    if numeric:
        keep.add(min(numeric, key=lambda pair: pair[1])[0])
        keep.add(max(numeric, key=lambda pair: pair[1])[0])

    stride = max(1, len(points) // max(1, cap - len(keep)))
    keep.update(range(0, len(points), stride))

    return [points[i] for i in sorted(keep)[:cap]], True


def _point(raw: dict[str, Any]) -> dict[str, Any]:
    """A series point, trimmed to what is worth spending context on."""
    point: dict[str, Any] = {"at": raw["at"], "value": raw.get("value")}
    if raw.get("is_estimated"):
        point["estimated"] = True
    if raw.get("currency"):
        point["currency"] = raw["currency"]
    return point


def _series(body: dict[str, Any], cap: int) -> dict[str, Any]:
    points, thinned = downsample(body.get("points", []), cap)
    result: dict[str, Any] = {
        "zone": body["zone"],
        "signal": body["signal"],
        "granularity": body.get("granularity"),
        "provenance": body.get("provenance"),
        "estimated_fraction": body.get("estimated_fraction"),
        "points": [_point(p) for p in points],
    }
    if body.get("issued_at"):
        result["issued_at"] = body["issued_at"]
        result["horizon_hours"] = body.get("horizon_hours")
    if thinned:
        result["_note"] = (
            f"Downsampled from {len(body.get('points', []))} points to {len(points)}. "
            f"The minimum, maximum and both endpoints are preserved exactly."
        )
    return result


def _observation(raw: dict[str, Any] | None) -> dict[str, Any] | None:
    if raw is None:
        return None
    trimmed: dict[str, Any] = {"value": raw.get("value"), "at": raw.get("at")}
    for key in ("is_estimated", "is_stale", "currency", "unit", "source"):
        if raw.get(key):
            trimmed[key] = raw[key]
    return trimmed


# --- the tools --------------------------------------------------------------


async def get_current_grid(ctx: ToolContext, *, zone: str) -> dict[str, Any]:
    key = await ctx.require_zone(zone)
    snapshot = await ctx.client.snapshot(key)

    mix = snapshot.get("mix")
    return {
        "zone": key,
        "at": snapshot["at"],
        "provenance": snapshot["provenance"],
        "carbon_intensity_gco2_per_kwh": _observation(snapshot.get("carbon_intensity")),
        "renewable_percentage": _observation(snapshot.get("renewable_percentage")),
        "carbon_free_percentage": _observation(snapshot.get("carbon_free_percentage")),
        "price": _observation(snapshot.get("price")),
        "load_mw": _observation(snapshot.get("load")),
        "top_sources": _top_sources(mix),
        "net_import_mw": (snapshot.get("flows") or {}).get("net_import_mw"),
        "unavailable": snapshot.get("unavailable", []),
    }


async def get_forecast(
    ctx: ToolContext,
    *,
    zone: str,
    signal: str = "carbon_intensity",
    horizon_hours: int = 24,
) -> dict[str, Any]:
    key = await ctx.require_zone(zone)
    _require_signal(signal)
    if horizon_hours not in FORECAST_HORIZONS:
        raise GridUnavailable(f"horizon_hours must be one of {list(FORECAST_HORIZONS)}.")

    body = await ctx.client.forecast(key, signal, horizon_hours)
    return _series(body, ctx.max_points)


async def get_mix(ctx: ToolContext, *, zone: str, flow_traced: bool = True) -> dict[str, Any]:
    key = await ctx.require_zone(zone)
    body = await ctx.client.mix(key, flow_traced=flow_traced)

    entries = sorted(body.get("entries", []), key=lambda e: -(e.get("percent") or 0))
    return {
        "zone": key,
        "at": body["at"],
        "provenance": body["provenance"],
        "is_estimated": body.get("is_estimated", False),
        "flow_traced": body.get("flow_traced"),
        "total_mw": body.get("total_mw"),
        "sources": [
            {
                "source": entry["source"],
                "percent": round(entry["percent"], 1) if entry.get("percent") else None,
                "mw": round(entry["power_mw"], 1) if entry.get("power_mw") else None,
            }
            for entry in entries
        ],
        "_note": (
            "flow_traced=true is what is available in this zone once imports are traced "
            "back to their origin. flow_traced=false is what the zone generated. They are "
            "different answers; say which one you used."
        ),
    }


async def get_price(ctx: ToolContext, *, zone: str) -> dict[str, Any]:
    key = await ctx.require_zone(zone)
    body = await ctx.client.price(key)
    return {
        "zone": key,
        "at": body["at"],
        "provenance": body["provenance"],
        "value": body.get("value"),
        "currency": body.get("currency"),
        "unit": body.get("unit"),
        "source": body.get("source"),
        "is_estimated": body.get("is_estimated", False),
        **(
            {
                "_note": (
                    "This price is below zero: the market is paying consumers to take "
                    "electricity. That is real and increasingly common, not an error."
                )
            }
            if (body.get("value") or 0) < 0
            else {}
        ),
    }


async def get_forward_price(ctx: ToolContext, *, zone: str) -> dict[str, Any]:
    key = await ctx.require_zone(zone)
    body = await ctx.client.price_forward(key)
    result = _series(body, ctx.max_points)
    cleared = sum(1 for p in body.get("points", []) if p.get("source"))
    result["_note"] = (
        "These are day-ahead auction results for delivery periods that have not happened "
        "yet — settled prices awaiting their hour, not a forecast. Do not describe them as "
        "predictions, and do not score them against an outcome. "
        f"{cleared} of {len(body.get('points', []))} were set by a published exchange; the "
        "rest are Electricity Maps' own modelled values."
    )
    return result


async def find_events(ctx: ToolContext, *, zone: str) -> dict[str, Any]:
    """Deterministic findings for a zone.

    Exists so the model does not have to search a series for what is interesting. It is
    slower and less reliable at that than a comparison operator, and every number it
    reported would be one it derived rather than read.
    """
    key = await ctx.require_zone(zone)
    body = await ctx.client.findings(key)
    return {
        "zone": key,
        "at": body.get("at"),
        "count": body.get("count", 0),
        "findings": [
            {
                "kind": f["kind"],
                "headline": f["headline"],
                "detail": f.get("detail") or None,
                "at": f["at"],
                "until": f.get("until"),
                "magnitude": f.get("magnitude"),
                "unit": f.get("unit"),
                "provenance": f["derived"]["provenance"],
                "evidence": [
                    {"label": e["label"], "value": e["value"], "unit": e.get("unit")}
                    for e in f.get("evidence", [])
                ],
                "caveats": f["derived"].get("caveats", []),
            }
            for f in body.get("findings", [])
        ],
        "_note": (
            "Computed arithmetically before you were asked, not by a model. Quote these "
            "numbers as they are; do not recompute them, and do not add findings of your "
            "own that no tool returned. An empty list means the grid is quiet, which is a "
            "real answer."
        ),
    }


async def explain_divergence(
    ctx: ToolContext, *, zone: str, window_periods: int = 3
) -> dict[str, Any]:
    """Whether cheap and clean mean the same periods in this zone today.

    The numbers are computed; the *explanation* is the model's job, and it is the one thing
    here a UI genuinely cannot do — saying why this zone disagrees today requires joining
    mix, flows and price and knowing how a power market works.
    """
    key = await ctx.require_zone(zone)
    body = await ctx.client.divergence(key, window_periods)
    return {
        "zone": key,
        "periods_compared": body.get("periods"),
        "rank_correlation": body.get("correlation"),
        "agreement": body.get("agreement"),
        "cleanest_window": body.get("best_a"),
        "cheapest_window": body.get("best_b"),
        "hours_apart": body.get("separation_hours"),
        "disagreeing_periods": body.get("disagreeing_periods", []),
        "provenance": body["derived"]["provenance"],
        "caveats": body["derived"].get("caveats", []),
        "_note": (
            "`cleanest_window.other_mean` is what the clean window costs in price; "
            "`cheapest_window.other_mean` is what the cheap window costs in carbon. "
            "Explain *why* the two disagree here — imports, the marginal unit, a solar or "
            "wind surplus — and cite get_flows before claiming an import effect. Do not "
            "recommend a schedule: which trade is worth making is the user's call, not "
            "yours."
        ),
    }


async def get_flows(ctx: ToolContext, *, zone: str) -> dict[str, Any]:
    key = await ctx.require_zone(zone)
    body = await ctx.client.flows(key)
    return {
        "zone": key,
        "at": body["at"],
        "provenance": body["provenance"],
        "net_import_mw": body.get("net_import_mw"),
        "neighbours": [
            {
                "zone": edge["counterpart_zone"],
                "net_mw": round(edge["net_flow_mw"], 1),
                "direction": "export" if edge["net_flow_mw"] >= 0 else "import",
            }
            for edge in sorted(body.get("edges", []), key=lambda e: -abs(e.get("net_flow_mw", 0)))
        ],
        "_note": "Positive net_mw means this zone is exporting to that neighbour.",
    }


async def query_history(
    ctx: ToolContext,
    *,
    zone: str,
    signal: str = "carbon_intensity",
    start: str | None = None,
    end: str | None = None,
) -> dict[str, Any]:
    key = await ctx.require_zone(zone)
    _require_signal(signal)

    if start and end:
        try:
            span = _parse(end) - _parse(start)
        except ValueError as exc:
            raise GridUnavailable(f"Timestamps must be ISO 8601: {exc}") from exc
        if span > timedelta(days=MAX_HISTORY_DAYS):
            raise GridUnavailable(
                f"Windows longer than {MAX_HISTORY_DAYS} days are not available to this "
                f"tool. Ask for a narrower range."
            )
        if span.total_seconds() <= 0:
            raise GridUnavailable("`end` must be after `start`.")

    body = await ctx.client.history(key, signal, start, end)
    result = _series(body, ctx.max_points)
    result["_note"] = (
        "The window returned may be shorter than the window requested. This plan's "
        "history reaches back only as far as the underlying data allows; the points "
        "returned are the truth about what is available."
    )
    return result


async def compare_zones(
    ctx: ToolContext, *, zones: list[str], signal: str = "carbon_intensity"
) -> dict[str, Any]:
    _require_signal(signal)
    if len(zones) < 2:
        raise GridUnavailable("Give at least two zones to compare.")
    if len(zones) > MAX_COMPARE_ZONES:
        raise GridUnavailable(f"At most {MAX_COMPARE_ZONES} zones at a time.")

    keys = [await ctx.require_zone(zone) for zone in zones]
    body = await ctx.client.compare(keys, signal)

    return {
        "signal": signal,
        "at": body["at"],
        "provenance": body["provenance"],
        "zones": {zone: _observation(obs) for zone, obs in body.get("zones", {}).items()},
        "_note": (
            "These are raw values at one instant. Ranking zones on them produces a table "
            "that never changes - hydro-rich zones always win and coal-heavy ones always "
            "lose. If the question is about performance rather than level, say that a fair "
            "comparison would score each zone against its own baseline."
        ),
    }


def _require_signal(signal: str) -> None:
    if signal not in SERIES_SIGNALS:
        raise GridUnavailable(f"signal must be one of {list(SERIES_SIGNALS)}.")


def _parse(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _top_sources(mix: dict[str, Any] | None, limit: int = 5) -> list[dict[str, Any]] | None:
    if not mix:
        return None
    entries = sorted(mix.get("entries", []), key=lambda e: -(e.get("percent") or 0))
    return [
        {"source": e["source"], "percent": round(e["percent"], 1)}
        for e in entries[:limit]
        if e.get("percent")
    ]


# --- the registry -----------------------------------------------------------
#
# One list, used both to declare the tools to the model and to dispatch them. A tool that
# is callable but undeclared, or declared but not callable, is not possible by
# construction — and a test asserts the two stay in step.

_ZONE = {"type": "string", "description": "Zone key, e.g. DK-DK2. Case-sensitive."}
_SIGNAL = {
    "type": "string",
    "enum": list(SERIES_SIGNALS),
    "description": "Which measurement to read.",
}


def build_tools() -> list[ToolSpec]:
    return [
        ToolSpec(
            name="get_current_grid",
            description=(
                "Everything the lab currently knows about one zone: carbon intensity, "
                "renewable and carbon-free share, day-ahead price, load, the top "
                "generation sources and net imports. Start here for 'how is X doing'."
            ),
            parameters={"zone": _ZONE},
            required=("zone",),
            handler=get_current_grid,
        ),
        ToolSpec(
            name="get_forecast",
            description=(
                "The forward view for one signal. Returns the forecast as issued, with "
                "`issued_at`. Horizons above 24 hours are not available for every signal."
            ),
            parameters={
                "zone": _ZONE,
                "signal": _SIGNAL,
                "horizon_hours": {
                    "type": "integer",
                    "enum": list(FORECAST_HORIZONS),
                    "description": "How far ahead to look. 24 works for every signal.",
                },
            },
            required=("zone",),
            handler=get_forecast,
        ),
        ToolSpec(
            name="get_mix",
            description=(
                "The generation mix by source. `flow_traced=true` (the default) gives what "
                "is actually available in the zone once imports are traced to their "
                "origin; `false` gives what the zone itself generated."
            ),
            parameters={
                "zone": _ZONE,
                "flow_traced": {
                    "type": "boolean",
                    "description": "True for the consumption mix, false for production.",
                },
            },
            required=("zone",),
            handler=get_mix,
        ),
        ToolSpec(
            name="get_price",
            description=(
                "The current day-ahead price. Coverage is Europe plus a few zones, and it "
                "is not in every plan. Prices below zero are real and increasingly common."
            ),
            parameters={"zone": _ZONE},
            required=("zone",),
            handler=get_price,
        ),
        ToolSpec(
            name="get_forward_price",
            description=(
                "Day-ahead prices for delivery periods that have not happened yet. These "
                "are auction results published ahead of delivery — settled, not predicted "
                "— so never call them a forecast. Reaches to the end of the delivery day "
                "the auction covered, usually about 24 hours."
            ),
            parameters={"zone": _ZONE},
            required=("zone",),
            handler=get_forward_price,
        ),
        ToolSpec(
            name="get_flows",
            description=(
                "Cross-border exchange with each neighbour, netted. Positive means this "
                "zone is exporting. Use this to explain where a zone's electricity is "
                "coming from or going."
            ),
            parameters={"zone": _ZONE},
            required=("zone",),
            handler=get_flows,
        ),
        ToolSpec(
            name="find_events",
            description=(
                "What the lab has already found worth looking at in this zone: negative "
                "prices, large carbon swings, renewable surges, import dependence, and "
                "windows where cheap and clean disagree. Computed arithmetically, not by a "
                "model. **Call this before searching a series yourself** — it is faster, it "
                "is exact, and the numbers come with the evidence that produced them. An "
                "empty list means the grid is quiet."
            ),
            parameters={"zone": _ZONE},
            required=("zone",),
            handler=find_events,
        ),
        ToolSpec(
            name="explain_divergence",
            description=(
                "Whether the cheapest periods and the cleanest periods are the same periods "
                "in this zone today. Returns a rank correlation, both best windows, and "
                "what each costs on the other objective. The numbers are computed for you; "
                "your job is to explain *why* they disagree, using the mix and the flows."
            ),
            parameters={
                "zone": _ZONE,
                "window_periods": {
                    "type": "integer",
                    "description": (
                        "How long the flexible block is, in periods. 3 hourly periods is a "
                        "plausible EV charge. A long enough block covers both windows and "
                        "the disagreement disappears."
                    ),
                },
            },
            required=("zone",),
            handler=explain_divergence,
        ),
        ToolSpec(
            name="query_history",
            description=(
                "A past window for one signal. Omit start and end for a sensible default. "
                "The window returned may be shorter than asked for."
            ),
            parameters={
                "zone": _ZONE,
                "signal": _SIGNAL,
                "start": {
                    "type": "string",
                    "description": "ISO 8601 UTC, e.g. 2026-08-21T00:00:00Z",
                },
                "end": {"type": "string", "description": "ISO 8601 UTC."},
            },
            required=("zone",),
            handler=query_history,
        ),
        ToolSpec(
            name="compare_zones",
            description=(
                "One signal across several zones at the same instant. Simultaneity is the "
                "point: the same moment can look completely different in two places."
            ),
            parameters={
                "zones": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Two or more zone keys.",
                },
                "signal": _SIGNAL,
            },
            required=("zones",),
            handler=compare_zones,
        ),
    ]
