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
from datetime import datetime
from pathlib import Path
from typing import Any

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
)


class Point(BaseModel):
    """One scalar sample."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    at: datetime
    value: float
    is_estimated: bool = False


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


class ZoneData(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    carbon_intensity: tuple[Point, ...] = ()
    renewable_percentage: tuple[Point, ...] = ()
    carbon_free_percentage: tuple[Point, ...] = ()
    price: tuple[Point, ...] = ()
    load: tuple[Point, ...] = ()
    mix: tuple[MixPoint, ...] = ()
    flows: tuple[FlowPoint, ...] = ()
    forecasts: dict[str, Forecast] = Field(default_factory=dict)
    """Signal name to the forecast issued for it."""


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

    Loaded eagerly at startup and cached. Scenarios are small (kilobytes) and committed to
    the repository, so there is no reason to read them lazily — and doing it once at boot
    means a malformed file fails at startup rather than mid-demo.
    """

    def __init__(self, directory: Path) -> None:
        self._directory = directory
        self._scenarios: dict[str, Scenario] = {}
        self.reload()

    def reload(self) -> None:
        self._scenarios = {}
        if not self._directory.is_dir():
            return
        for path in sorted(self._directory.glob("*.json")):
            raw = json.loads(path.read_text(encoding="utf-8"))
            scenario = Scenario.model_validate(raw)
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
            raise KeyError(
                f"No scenario {scenario_id!r} in {self._directory}. Available: {known}. "
                f"Generate one with `make scenario`, or record one with `make record`."
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
    return Price(
        zone=zone,
        at=point.at,
        provenance=provenance,
        is_estimated=point.is_estimated,
        value=point.value,
        currency=currency,
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
