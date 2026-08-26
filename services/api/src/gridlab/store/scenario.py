"""Scenarios: a recorded (or generated) stretch of grid time, playable on demand.

A scenario is one JSON file in ``scenarios/``. It holds, for one or more zones, the actual
series over a window **and** the forecasts that were issued during it. Keeping both is the
whole point: the gap between what was predicted and what happened is the most interesting
thing in this dataset, and it cannot be shown from live data alone.

Scenarios carry their own provenance. A scenario built by ``make record`` from a real API
key is ``recorded``; one built by ``make_scenario`` without a key is ``synthetic``. The
distinction is propagated into every observation the replay source emits, so a generated
number can never be presented as a measured one.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog
from pydantic import BaseModel, ConfigDict, Field

from gridlab.domain.models import (
    CarbonIntensity,
    FlowEdge,
    Flows,
    Load,
    MixBreakdown,
    MixEntry,
    Percentage,
    Price,
    Provenance,
    ScalarObservation,
)

log = structlog.get_logger(__name__)


class Point(BaseModel):
    """One scalar sample."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    at: datetime
    value: float
    is_estimated: bool = False


class PricePoint(Point):
    """A price sample, which additionally records *who set it*.

    ``source`` is ``"nordpool.com"`` (or another exchange) for a settled auction price, and
    something else — or nothing — for Electricity Maps' own modelled value. The
    ``price-day-ahead/combined`` response returns both kinds in one series, so a scenario
    that dropped this field would blend a cleared market result with a model and leave no
    way to tell them apart afterwards.
    """

    source: str | None = None


class MixPoint(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    at: datetime
    entries: dict[str, float]
    """Source name to MW."""

    flow_traced: bool = True
    is_estimated: bool = False


class FlowPoint(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    at: datetime
    edges: dict[str, float]
    """Counterpart zone to net MW; positive is export."""

    is_estimated: bool = False


class Forecast(BaseModel):
    """A forecast as it was issued — not as it turned out."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    issued_at: datetime
    horizon_hours: int
    points: tuple[Point, ...]


class PriceForward(BaseModel):
    """Day-ahead prices for delivery hours that have not happened yet.

    Deliberately *not* a :class:`Forecast`. Day-ahead prices are an **auction result**
    published ahead of delivery, not a prediction of one: once the market clears at 12:00
    CET, tomorrow's prices are settled fact awaiting its delivery hour. Filing them under
    ``forecasts`` would invite every consumer to treat them as a model output and to score
    them against an outcome they already are.

    ``issued_at`` is the clearing publication time, taken from the rows themselves.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    issued_at: datetime | None = None
    points: tuple[PricePoint, ...] = ()


class ZoneData(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    carbon_intensity: tuple[Point, ...] = ()
    renewable_percentage: tuple[Point, ...] = ()
    carbon_free_percentage: tuple[Point, ...] = ()
    price: tuple[PricePoint, ...] = ()
    load: tuple[Point, ...] = ()
    mix: tuple[MixPoint, ...] = ()
    flows: tuple[FlowPoint, ...] = ()
    forecasts: dict[str, Forecast] = Field(default_factory=dict)
    """Signal name to the forecast issued for it."""

    price_forward: PriceForward | None = None
    """Day-ahead prices reaching past the end of the replay window. See :class:`PriceForward`."""


class EndpointUse(BaseModel):
    """One request the recorder made, and what came back.

    Recorded per attempt rather than per success. "Which endpoints answered" and "which the
    plan refused" are the same question asked twice, and a scenario that lists only what it
    got leaves a reader unable to tell a signal that does not exist on this plan from one
    that was never asked for.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    signal: str
    temporality: str
    zone: str
    outcome: str
    """``ok`` or ``skipped``."""

    detail: str | None = None
    """Breakdown type, horizon, or whatever else distinguished this request."""

    reason: str | None = None
    """Why it was skipped. The error class name, not its message: messages can quote a URL."""

    rows: int | None = None
    """How many points it yielded, when it yielded any."""


class RecordingMeta(BaseModel):
    """How this scenario came to exist.

    Separate from ``notes``, which is prose for a human reading the UI. This is the machine
    -readable answer to the questions a later analysis will ask of an archive: which day was
    recorded, when the recording actually happened, which Electricity Maps endpoints were
    used, and whether the result was judged complete enough to use.

    Optional on :class:`Scenario`, so scenarios recorded before this existed still validate.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    recorded_at: datetime
    """When the recorder ran — not the window it captured. Both are needed and they differ."""

    day: str
    """The UTC calendar day this recording is *for*, ``YYYY-MM-DD``. The archive's key."""

    tool_version: str
    api_base_url: str
    granularity: str
    zones: tuple[str, ...] = ()
    endpoints: tuple[EndpointUse, ...] = ()
    complete: bool | None = None
    completeness_checks: dict[str, bool] = Field(default_factory=dict)
    completeness_reasons: tuple[str, ...] = ()


class Scenario(BaseModel):
    """A playable window of grid time."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    title: str
    description: str = ""
    provenance: Provenance
    currency: str = "EUR"
    start: datetime
    end: datetime
    granularity: str = "hourly"
    zones: dict[str, ZoneData]
    notes: str = ""
    """Free text shown in the UI. Use it to say what actually happened, and when."""

    recording: RecordingMeta | None = None
    """Provenance of the *recording act*, when there was one. ``None`` for generated
    scenarios and for anything recorded before this field existed."""

    @property
    def zone_keys(self) -> tuple[str, ...]:
        return tuple(sorted(self.zones))

    def summary(self) -> dict[str, Any]:
        """Small enough to list many of these in a picker."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "provenance": self.provenance.value,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "zones": list(self.zone_keys),
            "notes": self.notes,
        }


class ScenarioLibrary:
    """The scenarios on disk.

    Loaded eagerly at startup and cached. Scenarios are small (kilobytes), so there is no
    reason to read them lazily — and doing it once at boot means a malformed file fails at
    startup rather than mid-demo.

    Reads **several directories**, in order, because the two kinds of scenario now live
    apart: the generated ones are committed beside the code, while recordings hold
    Electricity Maps data and are kept in a private archive that the licence permits
    (ADR 0013). Later directories win on an id collision, so a real recording shadows a
    generated scenario that happens to share its name rather than the reverse.
    """

    def __init__(self, directories: Path | Sequence[Path]) -> None:
        self._directories: tuple[Path, ...] = (
            (directories,) if isinstance(directories, Path) else tuple(directories)
        )
        self._scenarios: dict[str, Scenario] = {}
        self.reload()

    @property
    def directories(self) -> tuple[Path, ...]:
        return self._directories

    def reload(self) -> None:
        self._scenarios = {}
        for directory in self._directories:
            if not directory.is_dir():
                continue
            for path in sorted(directory.glob("*.json")):
                raw = json.loads(path.read_text(encoding="utf-8"))
                scenario = Scenario.model_validate(raw)
                if scenario.id in self._scenarios:
                    log.warning(
                        "gridlab.scenario_shadowed",
                        scenario=scenario.id,
                        by=str(path),
                    )
                self._scenarios[scenario.id] = scenario

    def __contains__(self, scenario_id: str) -> bool:
        return scenario_id in self._scenarios

    def __len__(self) -> int:
        return len(self._scenarios)

    def get(self, scenario_id: str) -> Scenario | None:
        return self._scenarios.get(scenario_id)

    def require(self, scenario_id: str) -> Scenario:
        scenario = self._scenarios.get(scenario_id)
        if scenario is None:
            known = ", ".join(sorted(self._scenarios)) or "none found"
            where = ", ".join(str(d) for d in self._directories)
            raise KeyError(
                f"No scenario {scenario_id!r} in {where}. Available: {known}. "
                f"Generate one with `make scenario`, or record one with `make record-daily`."
            )
        return scenario

    def all(self) -> tuple[Scenario, ...]:
        return tuple(self._scenarios[k] for k in sorted(self._scenarios))


# --- converting scenario points into domain observations --------------------
#
# Replay must produce exactly the same domain types as live, or every consumer above the
# source layer needs two code paths. These functions are the bridge.


def to_carbon_intensity(point: Point, *, zone: str, provenance: Provenance) -> CarbonIntensity:
    return CarbonIntensity(
        zone=zone,
        at=point.at,
        provenance=provenance,
        is_estimated=point.is_estimated,
        value=point.value,
        flow_traced=True,
    )


def to_percentage(point: Point, *, zone: str, provenance: Provenance) -> Percentage:
    return Percentage(
        zone=zone,
        at=point.at,
        provenance=provenance,
        is_estimated=point.is_estimated,
        value=point.value,
    )


def to_price(point: Point, *, zone: str, provenance: Provenance, currency: str) -> Price:
    """A price point as a domain observation.

    Accepts a plain :class:`Point` as well as a :class:`PricePoint` because scenarios
    recorded before ``source`` existed have no such field, and a missing exchange name is
    "we do not know", not "modelled".
    """
    return Price(
        zone=zone,
        at=point.at,
        provenance=provenance,
        is_estimated=point.is_estimated,
        value=point.value,
        currency=currency,
        source=point.source if isinstance(point, PricePoint) else None,
    )


def to_load(point: Point, *, zone: str, provenance: Provenance) -> Load:
    return Load(
        zone=zone,
        at=point.at,
        provenance=provenance,
        is_estimated=point.is_estimated,
        value=point.value,
    )


def to_mix(point: MixPoint, *, zone: str, provenance: Provenance) -> MixBreakdown:
    total = sum(v for v in point.entries.values() if v > 0)
    return MixBreakdown(
        zone=zone,
        at=point.at,
        provenance=provenance,
        is_estimated=point.is_estimated,
        flow_traced=point.flow_traced,
        total_mw=total or None,
        entries=tuple(
            MixEntry(
                source=source,
                power_mw=value,
                percent=(value / total * 100.0) if total > 0 else None,
            )
            for source, value in sorted(point.entries.items())
        ),
    )


def to_flows(point: FlowPoint, *, zone: str, provenance: Provenance) -> Flows:
    return Flows(
        zone=zone,
        at=point.at,
        provenance=provenance,
        is_estimated=point.is_estimated,
        edges=tuple(
            FlowEdge(counterpart_zone=counterpart, net_flow_mw=value)
            for counterpart, value in sorted(point.edges.items())
        ),
    )


# --- domain observations back into scenario points --------------------------
#
# The inverse of the converters above, used when recording a scenario from live data.
# Keeping both directions in one module means a field added to a scenario point has one
# obvious place to be handled on the way in and on the way out.


def from_observation(observation: ScalarObservation) -> Point:
    """A scalar observation as a scenario point.

    ``is_estimated`` is carried deliberately. Electricity Maps models a great deal of what
    it reports, and a recorded scenario that forgot which values were measured would be a
    worse artefact than no recording at all.
    """
    return Point(
        at=observation.at,
        value=observation.value,
        is_estimated=observation.is_estimated,
    )


def from_price(observation: Price) -> PricePoint:
    """A price observation as a scenario point, keeping who set it.

    ``source`` is the only thing separating a settled auction result from a modelled one
    once the response envelope is gone, so it is recorded rather than recomputed.
    """
    return PricePoint(
        at=observation.at,
        value=observation.value,
        is_estimated=observation.is_estimated,
        source=observation.source,
    )


def from_mix(breakdown: MixBreakdown) -> MixPoint:
    """A mix breakdown as a scenario point.

    Only ``power_mw`` is stored; percentages are recomputed on load. Storing both would
    let them disagree, and the megawatts are the measurement.
    """
    return MixPoint(
        at=breakdown.at,
        entries={e.source: e.power_mw for e in breakdown.entries if e.power_mw is not None},
        flow_traced=breakdown.flow_traced,
        is_estimated=breakdown.is_estimated,
    )


def from_flows(flows: Flows) -> FlowPoint:
    """Cross-border exchange as a scenario point, keeping the signed convention."""
    return FlowPoint(
        at=flows.at,
        edges={e.counterpart_zone: e.net_flow_mw for e in flows.edges},
        is_estimated=flows.is_estimated,
    )
