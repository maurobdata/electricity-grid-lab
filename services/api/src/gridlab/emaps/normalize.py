"""Raw Electricity Maps JSON -> Grid Lab domain models.

**This is the only module allowed to know an Electricity Maps field name.** Everything
above it speaks :mod:`gridlab.domain.models`. See
``docs/adr/0003-electricity-maps-adapter-signal-matrix.md``.

The field names here were read off live responses on 22 August 2026 and are recorded in
``fixtures/``. The first version of this module guessed, and guessed wrong in three places
worth remembering, because each would have failed silently or late:

* the mix lives under ``mix``, not ``powerConsumptionBreakdown`` — that name belongs to a
  different endpoint, ``power-breakdown``;
* flows are ``import`` / ``export``, not ``powerImportBreakdown`` / ``powerExportBreakdown``;
* price is ``value`` with ``unit: "EUR/MWh"``, not ``price`` with a separate ``currency``.

Where a candidate list survives it is because two endpoints genuinely disagree — the scalar
signals use ``value`` while carbon intensity uses ``carbonIntensity`` — not because we are
still guessing.
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

#: Keys inside the ``mix`` object that are not generation sources.
#:
#: ``flows`` is an import/export summary that Electricity Maps nests inside the mix. Left
#: in, it would appear as a generation source called "flows" worth several hundred MW, and
#: every percentage in the breakdown would be wrong.
_NOT_A_SOURCE = frozenset({"flows"})

#: Sources reported as ``{"charge": x, "discharge": y}`` rather than a number.
#:
#: Storage is the one genuinely two-directional entry in a mix. Only discharge contributes
#: generation; charge is demand, and adding it would double-count.
_STORAGE_KEYS = frozenset({"hydro storage", "battery storage"})


class RawShapeError(ElectricityMapsError):
    """A response did not contain a field we need, under any name we know.

    The message lists the keys that *were* present. If this fires, record the response with
    ``make record``, update this module, and update ``docs/electricity-maps-api.md``.
    """


def _pick(raw: Mapping[str, Any], *candidates: str, required: bool = True) -> Any:
    """Return the first present, non-null candidate key."""
    for key in candidates:
        if key in raw and raw[key] is not None:
            return raw[key]
    if required:
        raise RawShapeError(
            f"None of {candidates} present in response. Keys were: {sorted(raw)}. "
            f"Record the response with `make record`, then update "
            f"gridlab.emaps.normalize and docs/electricity-maps-api.md."
        )
    return None


def parse_time(value: Any) -> datetime:
    """Parse an ISO 8601 timestamp into an aware UTC datetime."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if not isinstance(value, str):
        raise RawShapeError(f"Expected an ISO 8601 string, got {value!r}")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RawShapeError(f"Unparseable timestamp {value!r}") from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def rows(body: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Extract the record list from a response.

    Three envelope shapes are in use, which is why this exists rather than being inlined:

    * most endpoints wrap rows as ``{"data": [...]}``;
    * ``carbon-intensity/forecast`` uses ``{"forecast": [...]}``;
    * ``carbon-intensity/latest`` and ``power-breakdown/latest`` are a bare object.

    A bare object is returned as a one-row list so callers never branch.
    """
    for key in ("data", "forecast", "history"):
        value = body.get(key)
        if isinstance(value, list):
            return [r for r in value if isinstance(r, Mapping)]
    if "datetime" in body:
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
    """Fields every observation shares.

    Only ``datetime`` is required. Forecast rows are stripped down to the timestamp and the
    value — no ``isEstimated``, no ``updatedAt`` — so everything else is optional.
    """
    updated = _pick(raw, "updatedAt", required=False)
    return {
        "zone": str(_pick(raw, "zone", required=False) or zone),
        "at": parse_time(_pick(raw, "datetime")),
        "provenance": provenance,
        "is_estimated": bool(_pick(raw, "isEstimated", required=False) or False),
        "estimation_method": _pick(raw, "estimationMethod", required=False),
        "updated_at": parse_time(updated) if updated else None,
    }


# --- per-signal normalizers -------------------------------------------------


def carbon_intensity(
    raw: Mapping[str, Any], *, zone: str, provenance: Provenance = Provenance.LIVE
) -> CarbonIntensity:
    """gCO2eq/kWh.

    ``emissionFactorType`` is carried because it changes the number by a factor of three or
    four: the same DK-DK2 instant reads 75 lifecycle and 20 direct. A chart that omits it is
    not saying what it thinks it is saying.
    """
    return CarbonIntensity(
        **_common(raw, zone=zone, provenance=provenance),
        value=float(_pick(raw, "carbonIntensity", "value")),
        emission_factor_type=_pick(raw, "emissionFactorType", required=False),
        flow_traced=_pick(raw, "flowTraced", required=False),
    )


def percentage(
    raw: Mapping[str, Any],
    *,
    zone: str,
    keys: Sequence[str] = ("value",),
    provenance: Provenance = Provenance.LIVE,
) -> Percentage:
    """A 0-100 share. Both ``renewable-energy`` and ``carbon-free-energy`` use ``value``."""
    value = float(_pick(raw, *keys, "value"))
    # The API reports these with `unit: "%"`, so a 0-1 fraction should not occur. Guarded
    # anyway: plotting 0.97 on a percentage axis looks like a dead grid, not a superb one.
    if 0.0 < value <= 1.0:
        value *= 100.0
    return Percentage(**_common(raw, zone=zone, provenance=provenance), value=value)


def price(raw: Mapping[str, Any], *, zone: str, provenance: Provenance = Provenance.LIVE) -> Price:
    """Day-ahead price.

    ``unit`` arrives combined as ``"EUR/MWh"`` and is split here, because summing prices
    across zones without checking the currency is a category error, and because a chart
    axis wants "EUR/MWh" while a comparison wants "EUR".

    ``source`` distinguishes a settled auction price (``"nordpool.com"``) from Electricity
    Maps' own modelled one. The ``combined`` endpoint returns both kinds in one series, so
    dropping this field would blend measured and modelled prices invisibly.
    """
    unit = str(_pick(raw, "unit", required=False) or "EUR/MWh")
    currency, _, denominator = unit.partition("/")
    return Price(
        **_common(raw, zone=zone, provenance=provenance),
        value=float(_pick(raw, "value", "price")),
        currency=currency or "EUR",
        unit=denominator or "MWh",
        source=_pick(raw, "source", required=False),
    )


def mix(
    raw: Mapping[str, Any],
    *,
    zone: str,
    flow_traced: bool | None = None,
    provenance: Provenance = Provenance.LIVE,
) -> MixBreakdown:
    """The generation mix, from ``electricity-mix``.

    The response says which breakdown it is via ``breakdownType`` (``normal`` or
    ``flow-traced``), so the caller does not have to remember what it asked for and a chart
    cannot mislabel itself. ``flow_traced`` is only a fallback for responses that omit it.

    Three things in the payload need care, and all three were found by reading a real
    response rather than the documentation:

    * null sources are common and are dropped rather than plotted as zero;
    * ``hydro storage`` and ``battery storage`` are ``{"charge", "discharge"}`` objects,
      and only discharge is generation;
    * ``flows`` is nested inside the mix but is not a source.
    """
    breakdown = _pick(raw, "mix", "powerConsumptionBreakdown", "powerProductionBreakdown")
    if not isinstance(breakdown, Mapping):
        raise RawShapeError(
            f"Mix breakdown was {type(breakdown).__name__}, not an object. "
            f"Keys were: {sorted(raw)}."
        )

    values: dict[str, float] = {}
    for source, value in breakdown.items():
        if source in _NOT_A_SOURCE or value is None:
            continue
        if source in _STORAGE_KEYS or isinstance(value, Mapping):
            discharge = value.get("discharge") if isinstance(value, Mapping) else None
            if discharge:
                values[f"{source} discharge"] = float(discharge)
            continue
        if isinstance(value, int | float):
            values[source] = float(value)

    if not values:
        raise RawShapeError(
            f"No usable generation sources in mix for {zone}. Breakdown was: {breakdown}."
        )

    total = sum(v for v in values.values() if v > 0)
    declared = _pick(raw, "breakdownType", required=False)
    is_flow_traced = declared == "flow-traced" if declared is not None else bool(flow_traced)

    return MixBreakdown(
        **_common(raw, zone=zone, provenance=provenance),
        entries=tuple(
            MixEntry(
                source=source,
                power_mw=value,
                percent=(value / total * 100.0) if total > 0 else None,
            )
            for source, value in sorted(values.items())
        ),
        flow_traced=is_flow_traced,
        total_mw=total or None,
    )


def flows(raw: Mapping[str, Any], *, zone: str, provenance: Provenance = Provenance.LIVE) -> Flows:
    """Cross-border exchange, from ``electricity-flows``.

    The payload is two unsigned maps, ``import`` and ``export``, keyed by neighbour. They
    are netted into one signed figure per neighbour, positive meaning export — a zone can
    appear in both at once, and two separate numbers would be drawn twice on a map.
    """
    edges: dict[str, float] = {}

    exports = _pick(raw, "export", "powerExportBreakdown", required=False)
    imports = _pick(raw, "import", "powerImportBreakdown", required=False)

    if isinstance(exports, Mapping):
        for counterpart, value in exports.items():
            if isinstance(value, int | float):
                edges[counterpart] = edges.get(counterpart, 0.0) + float(value)
    if isinstance(imports, Mapping):
        for counterpart, value in imports.items():
            if isinstance(value, int | float):
                edges[counterpart] = edges.get(counterpart, 0.0) - float(value)

    if not edges:
        raise RawShapeError(f"No import or export breakdown for {zone}. Keys were: {sorted(raw)}.")

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
    """Demand in MW.

    ``total-load``, ``total-reported-load`` and ``net-load`` all use ``value``; ``kind``
    records which question was asked. Net load is total minus wind and solar, which is the
    one that shows the duck curve.
    """
    return Load(
        **_common(raw, zone=zone, provenance=provenance),
        value=float(_pick(raw, "value")),
        kind=kind,
    )


def electricity_source(
    raw: Mapping[str, Any],
    *,
    zone: str,
    provenance: Provenance = Provenance.LIVE,
) -> Load:
    """A single generation source in MW, from ``electricity-source/<type>``.

    Modelled as a Load because it is the same shape: a scalar in MW at an instant. The
    source name lives in the response envelope rather than the row, so the caller labels it.
    """
    return Load(
        **_common(raw, zone=zone, provenance=provenance),
        value=float(_pick(raw, "value")),
        kind="generation",
    )


def level(
    raw: Mapping[str, Any],
    *,
    zone: str,
    of: str,
    provenance: Provenance = Provenance.LIVE,
) -> Level:
    """A bucketed level: ``low``, ``moderate`` or ``high``, against the zone's own baseline.

    The most under-used signal in the API for consumer work, because it needs no numeracy
    at all: "high" means high *for here*, so Poland and Norway can both have a good day
    without either looking permanently virtuous.
    """
    raw_bucket = _pick(raw, "level", required=False)
    try:
        bucket = LevelBucket(str(raw_bucket).lower())
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

    The granularity is taken from the response when it says one, because the API may return
    a coarser resolution than was requested and the label should match the data.
    """
    seen: dict[datetime, ScalarObservation] = {}
    issued_at: datetime | None = None
    reported_granularity: str | None = None

    for body in bodies:
        if issued_at is None:
            candidate = _pick(body, "updatedAt", required=False)
            if candidate:
                issued_at = parse_time(candidate)
        if reported_granularity is None:
            reported_granularity = _pick(body, "temporalGranularity", required=False)
        for row in rows(body):
            point = normalizer(row, zone=zone, provenance=provenance)
            seen[point.at] = point

    return Series[ScalarObservation](
        zone=zone,
        points=tuple(seen[k] for k in sorted(seen)),
        granularity=reported_granularity or granularity,
        horizon_hours=horizon_hours,
        issued_at=issued_at,
    )
