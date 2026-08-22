"""Raw Electricity Maps JSON -> Grid Lab domain models.

**This is the only module allowed to know an Electricity Maps field name.** Everything
above it speaks :mod:`gridlab.domain.models`. See
``docs/adr/0003-electricity-maps-adapter-signal-matrix.md``.

The exact v4 response schema is not public — the full reference sits behind an
authenticated single-page app, and only the carbon-intensity shape is publicly evidenced
(see ``docs/electricity-maps-api.md``). Rather than guess and be confidently wrong, the
functions here accept a small set of plausible key spellings per field and fail loudly,
with the actual keys in the message, when none match.

That is a deliberate trade. It is slightly loose, and it means the first live call is a
five-minute fix rather than an afternoon of archaeology at a hackathon. Once real fixtures
are recorded (``make record``), the candidate lists should be narrowed to what the API
actually sends.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from gridlab.domain.models import (
    CarbonIntensity,
    FlowEdge,
    Flows,
    Level,
    LevelBucket,
    Load,
    MixBreakdown,
    MixEntry,
    Percentage,
    Price,
    Provenance,
    ScalarObservation,
    Series,
)
from gridlab.emaps.errors import ElectricityMapsError


class RawShapeError(ElectricityMapsError):
    """A response did not contain a field we need, under any spelling we know.

    The message lists the keys that *were* present. Add the real one to the candidate list
    in this module and to ``docs/electricity-maps-api.md``.
    """


def _pick(raw: Mapping[str, Any], *candidates: str, required: bool = True) -> Any:
    """Return the first present, non-null candidate key."""
    for key in candidates:
        if key in raw and raw[key] is not None:
            return raw[key]
    if required:
        raise RawShapeError(
            f"None of {candidates} present in response. Keys were: {sorted(raw)}. "
            f"Update gridlab.emaps.normalize and docs/electricity-maps-api.md."
        )
    return None


def parse_time(value: Any) -> datetime:
    """Parse an ISO 8601 timestamp into an aware UTC datetime."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if not isinstance(value, str):
        raise RawShapeError(f"Expected an ISO 8601 string, got {value!r}")
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise RawShapeError(f"Unparseable timestamp {value!r}") from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def rows(body: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Extract the list of records from a range/history/forecast response.

    Range endpoints are documented to wrap rows as ``{"data": [...]}``; forecast endpoints
    are reported to use ``forecast``. A single-object response is treated as a one-row list
    so callers do not need to branch.
    """
    for key in ("data", "history", "forecast", "prices", "results"):
        value = body.get(key)
        if isinstance(value, list):
            return [r for r in value if isinstance(r, Mapping)]
    if any(k in body for k in ("datetime", "carbonIntensity", "powerConsumptionBreakdown")):
        return [body]
    raise RawShapeError(
        f"No recognisable row list in response. Keys were: {sorted(body)}. "
        f"Update gridlab.emaps.normalize.rows()."
    )


def _common(
    raw: Mapping[str, Any],
    *,
    zone: str,
    provenance: Provenance,
) -> dict[str, Any]:
    """Fields every observation shares."""
    updated = _pick(raw, "updatedAt", "updated_at", required=False)
    return {
        "zone": str(_pick(raw, "zone", required=False) or zone),
        "at": parse_time(_pick(raw, "datetime", "date", "time")),
        "provenance": provenance,
        "is_estimated": bool(_pick(raw, "isEstimated", "is_estimated", required=False) or False),
        "estimation_method": _pick(raw, "estimationMethod", "estimation_method", required=False),
        "updated_at": parse_time(updated) if updated else None,
    }


# --- per-signal normalizers -------------------------------------------------


def carbon_intensity(
    raw: Mapping[str, Any], *, zone: str, provenance: Provenance = Provenance.LIVE
) -> CarbonIntensity:
    return CarbonIntensity(
        **_common(raw, zone=zone, provenance=provenance),
        value=float(_pick(raw, "carbonIntensity", "carbon_intensity", "value")),
        emission_factor_type=_pick(raw, "emissionFactorType", required=False),
        flow_traced=_pick(raw, "isFlowTraced", "flowTraced", required=False),
    )


def percentage(
    raw: Mapping[str, Any],
    *,
    zone: str,
    keys: Sequence[str],
    provenance: Provenance = Provenance.LIVE,
) -> Percentage:
    """Normalize a 0-100 share. ``keys`` are the candidate field names for this signal."""
    value = float(_pick(raw, *keys, "value", "percentage"))
    # Some responses express shares as a 0-1 fraction. Anything at or below 1 is
    # ambiguous, but a grid at 0.8% renewable is far rarer than one at 80%, and the
    # alternative is silently plotting a flat line along the axis.
    if 0.0 < value <= 1.0:
        value *= 100.0
    return Percentage(**_common(raw, zone=zone, provenance=provenance), value=value)


def price(raw: Mapping[str, Any], *, zone: str, provenance: Provenance = Provenance.LIVE) -> Price:
    return Price(
        **_common(raw, zone=zone, provenance=provenance),
        value=float(_pick(raw, "price", "value", "dayAheadPrice")),
        currency=str(_pick(raw, "currency", required=False) or "EUR"),
        unit=str(_pick(raw, "unit", required=False) or "MWh"),
        # The `combined` endpoint blends published auction prices with modelled ones and
        # says which is which. That distinction must survive to the UI.
        source=_pick(raw, "source", "priceSource", required=False),
    )


def mix(
    raw: Mapping[str, Any],
    *,
    zone: str,
    flow_traced: bool,
    provenance: Provenance = Provenance.LIVE,
) -> MixBreakdown:
    """Normalize a generation mix.

    ``flow_traced`` selects consumption (imports traced to origin) over production. The
    caller decides which it asked for; we record it on the result so a chart cannot
    mislabel itself.
    """
    power_keys = (
        ("powerConsumptionBreakdown", "consumptionBreakdown")
        if flow_traced
        else ("powerProductionBreakdown", "productionBreakdown")
    )
    breakdown = _pick(raw, *power_keys, "powerBreakdown", "breakdown", required=False)
    percentages = _pick(raw, "powerConsumptionPercentage", "percentage", required=False)

    entries: list[MixEntry] = []
    if isinstance(breakdown, Mapping):
        total = sum(float(v) for v in breakdown.values() if isinstance(v, int | float) and v > 0)
        for source, value in sorted(breakdown.items()):
            if not isinstance(value, int | float):
                continue
            share = None
            if isinstance(percentages, Mapping) and source in percentages:
                share = float(percentages[source])
            elif total > 0:
                share = float(value) / total * 100.0
            entries.append(MixEntry(source=source, power_mw=float(value), percent=share))
    elif isinstance(percentages, Mapping):
        entries = [
            MixEntry(source=s, percent=float(v))
            for s, v in sorted(percentages.items())
            if isinstance(v, int | float)
        ]
    else:
        raise RawShapeError(
            f"No mix breakdown in response. Keys were: {sorted(raw)}. "
            f"Update gridlab.emaps.normalize.mix()."
        )

    total_key = ("powerConsumptionTotal",) if flow_traced else ("powerProductionTotal",)
    total_mw = _pick(raw, *total_key, required=False)

    return MixBreakdown(
        **_common(raw, zone=zone, provenance=provenance),
        entries=tuple(entries),
        flow_traced=flow_traced,
        total_mw=float(total_mw) if total_mw is not None else None,
    )


def flows(raw: Mapping[str, Any], *, zone: str, provenance: Provenance = Provenance.LIVE) -> Flows:
    """Normalize cross-border exchange.

    Imports and exports may arrive as one signed map or as two unsigned maps. Both are
    reduced to a single net figure per neighbour, positive meaning export.
    """
    edges: dict[str, float] = {}

    net = _pick(raw, "netFlows", "exchange", "flows", required=False)
    if isinstance(net, Mapping):
        for counterpart, value in net.items():
            if isinstance(value, int | float):
                edges[counterpart] = float(value)

    exports = _pick(raw, "powerExportBreakdown", "exports", required=False)
    imports = _pick(raw, "powerImportBreakdown", "imports", required=False)
    if isinstance(exports, Mapping):
        for counterpart, value in exports.items():
            if isinstance(value, int | float):
                edges[counterpart] = edges.get(counterpart, 0.0) + float(value)
    if isinstance(imports, Mapping):
        for counterpart, value in imports.items():
            if isinstance(value, int | float):
                edges[counterpart] = edges.get(counterpart, 0.0) - float(value)

    if not edges:
        raise RawShapeError(
            f"No flow breakdown in response. Keys were: {sorted(raw)}. "
            f"Update gridlab.emaps.normalize.flows()."
        )

    return Flows(
        **_common(raw, zone=zone, provenance=provenance),
        edges=tuple(FlowEdge(counterpart_zone=k, net_flow_mw=v) for k, v in sorted(edges.items())),
    )


def load(
    raw: Mapping[str, Any],
    *,
    zone: str,
    kind: str = "total",
    provenance: Provenance = Provenance.LIVE,
) -> Load:
    return Load(
        **_common(raw, zone=zone, provenance=provenance),
        value=float(_pick(raw, "load", "totalLoad", "netLoad", "value")),
        kind=kind,
    )


def level(
    raw: Mapping[str, Any],
    *,
    zone: str,
    of: str,
    provenance: Provenance = Provenance.LIVE,
) -> Level:
    bucket_raw = _pick(raw, "level", "carbonIntensityLevel", "value", required=False)
    try:
        bucket = LevelBucket(str(bucket_raw).lower())
    except ValueError:
        bucket = LevelBucket.UNKNOWN
    return Level(**_common(raw, zone=zone, provenance=provenance), bucket=bucket, of=of)


# --- series -----------------------------------------------------------------


def series(
    bodies: Sequence[Mapping[str, Any]],
    *,
    zone: str,
    normalizer: Callable[..., ScalarObservation],
    granularity: str = "hourly",
    horizon_hours: int | None = None,
    provenance: Provenance = Provenance.LIVE,
) -> Series[ScalarObservation]:
    """Normalize one or more response bodies into a single ordered, deduplicated series.

    ``fetch_range`` returns one body per chunk, so merging happens here. Points are sorted
    by time and deduplicated by timestamp, keeping the last occurrence — chunk boundaries
    and upstream revisions can both produce the same instant twice, and a chart with two
    points at 14:00 draws a vertical line through itself.
    """
    seen: dict[datetime, ScalarObservation] = {}
    issued_at: datetime | None = None

    for body in bodies:
        if issued_at is None:
            candidate = _pick(body, "updatedAt", "issuedAt", required=False)
            if candidate:
                issued_at = parse_time(candidate)
        for row in rows(body):
            point = normalizer(row, zone=zone, provenance=provenance)
            seen[point.at] = point

    return Series[ScalarObservation](
        zone=zone,
        points=tuple(seen[k] for k in sorted(seen)),
        granularity=granularity,
        horizon_hours=horizon_hours,
        issued_at=issued_at,
    )
