"""Play a recorded window of grid time.

The default mode. It needs no API key, no network, and no luck: the interesting hour is
already in the file, so a demo can reach it on cue instead of hoping the North Sea
cooperates at 17:00.

Lookup is "the most recent sample at or before the clock's now", which is how grid data
actually behaves — an hourly value stands until the next one lands.
"""

from __future__ import annotations

from bisect import bisect_right
from datetime import datetime, timedelta

import structlog

from gridlab.clock import Clock, ReplayClock
from gridlab.domain.models import (
    CarbonIntensity,
    Flows,
    GridSnapshot,
    Load,
    MixBreakdown,
    Percentage,
    Price,
    Provenance,
    ScalarObservation,
    Series,
)
from gridlab.sources.base import GridSource
from gridlab.store import scenario as sc

log = structlog.get_logger(__name__)


class ReplaySource(GridSource):
    """Serve observations from a :class:`~gridlab.store.scenario.Scenario`."""

    def __init__(self, scenario: sc.Scenario, clock: Clock | None = None) -> None:
        super().__init__(
            clock or ReplayClock(scenario.start, end=scenario.end, speed=60.0, loop=True)
        )
        self.scenario = scenario
        self.provenance = scenario.provenance
        log.info(
            "replay.loaded",
            scenario=scenario.id,
            provenance=scenario.provenance.value,
            zones=list(scenario.zone_keys),
        )

    # -- lookup --------------------------------------------------------------

    @staticmethod
    def _at_or_before[P: (sc.Point, sc.MixPoint, sc.FlowPoint)](
        points: tuple[P, ...], moment: datetime
    ) -> P | None:
        """The last sample at or before ``moment``.

        Binary search: scenarios are small today, but a full year at 15-minute granularity
        is 35,000 points per signal, and this runs on every poll of every panel.
        """
        if not points:
            return None
        index = bisect_right([p.at for p in points], moment)
        return points[index - 1] if index else None

    def _zone(self, zone: str) -> sc.ZoneData | None:
        return self.scenario.zones.get(zone)

    # -- interface -----------------------------------------------------------

    async def zones(self) -> tuple[str, ...]:
        return self.scenario.zone_keys

    async def carbon_intensity(self, zone: str) -> CarbonIntensity | None:
        data = self._zone(zone)
        if data is None:
            return None
        point = self._at_or_before(data.carbon_intensity, self.now)
        if point is None:
            return None
        return sc.to_carbon_intensity(point, zone=zone, provenance=self.provenance)

    async def renewable_percentage(self, zone: str) -> Percentage | None:
        data = self._zone(zone)
        if data is None:
            return None
        point = self._at_or_before(data.renewable_percentage, self.now)
        return sc.to_percentage(point, zone=zone, provenance=self.provenance) if point else None

    async def carbon_free_percentage(self, zone: str) -> Percentage | None:
        data = self._zone(zone)
        if data is None:
            return None
        point = self._at_or_before(data.carbon_free_percentage, self.now)
        return sc.to_percentage(point, zone=zone, provenance=self.provenance) if point else None

    async def price(self, zone: str) -> Price | None:
        data = self._zone(zone)
        if data is None:
            return None
        point = self._at_or_before(data.price, self.now)
        if point is None:
            return None
        return sc.to_price(
            point, zone=zone, provenance=self.provenance, currency=self.scenario.currency
        )

    async def load(self, zone: str) -> Load | None:
        data = self._zone(zone)
        if data is None:
            return None
        point = self._at_or_before(data.load, self.now)
        return sc.to_load(point, zone=zone, provenance=self.provenance) if point else None

    async def mix(self, zone: str, *, flow_traced: bool = True) -> MixBreakdown | None:
        data = self._zone(zone)
        if data is None:
            return None
        candidates = tuple(p for p in data.mix if p.flow_traced == flow_traced)
        point = self._at_or_before(candidates, self.now)
        return sc.to_mix(point, zone=zone, provenance=self.provenance) if point else None

    async def flows(self, zone: str) -> Flows | None:
        data = self._zone(zone)
        if data is None:
            return None
        point = self._at_or_before(data.flows, self.now)
        return sc.to_flows(point, zone=zone, provenance=self.provenance) if point else None

    async def forecast(
        self, zone: str, *, signal: str = "carbon_intensity", horizon_hours: int = 24
    ) -> Series[ScalarObservation] | None:
        """The forecast that was issued, truncated to the requested horizon.

        Points already in the past relative to the replay clock are kept deliberately: the
        interesting view is the forecast laid over what actually happened, and dropping the
        elapsed part of it would remove exactly the comparison worth showing.
        """
        data = self._zone(zone)
        if data is None:
            return None
        forecast = data.forecasts.get(signal)
        if forecast is None:
            return None

        horizon_end = forecast.issued_at + timedelta(hours=horizon_hours)
        points = tuple(p for p in forecast.points if p.at <= horizon_end)
        converted = _convert(
            points, signal, zone=zone, provenance=self.provenance, scenario=self.scenario
        )

        return Series[ScalarObservation](
            zone=zone,
            points=converted,
            granularity=self.scenario.granularity,
            horizon_hours=horizon_hours,
            issued_at=forecast.issued_at,
        )

    async def history(
        self,
        zone: str,
        *,
        signal: str = "carbon_intensity",
        start: datetime,
        end: datetime,
        granularity: str = "hourly",
    ) -> Series[ScalarObservation] | None:
        data = self._zone(zone)
        if data is None:
            return None
        points = getattr(data, signal, None)
        if not points or not isinstance(points[0], sc.Point):
            return None

        window = tuple(p for p in points if start <= p.at <= end)
        return Series[ScalarObservation](
            zone=zone,
            points=_convert(
                window, signal, zone=zone, provenance=self.provenance, scenario=self.scenario
            ),
            granularity=self.scenario.granularity,
        )

    async def snapshot(self, zone: str) -> GridSnapshot:
        if zone not in self.scenario.zones:
            return GridSnapshot(
                zone=zone,
                at=self.now,
                provenance=self.provenance,
                unavailable=("zone not in this scenario",),
            )

        carbon = await self.carbon_intensity(zone)
        renewable = await self.renewable_percentage(zone)
        carbon_free = await self.carbon_free_percentage(zone)
        price = await self.price(zone)
        mix = await self.mix(zone, flow_traced=True)
        flows = await self.flows(zone)
        load = await self.load(zone)

        named = {
            "carbon_intensity": carbon,
            "renewable_percentage": renewable,
            "carbon_free_percentage": carbon_free,
            "price": price,
            "mix": mix,
            "flows": flows,
            "load": load,
        }
        return GridSnapshot(
            zone=zone,
            at=self.now,
            provenance=self.provenance,
            carbon_intensity=carbon,
            renewable_percentage=renewable,
            carbon_free_percentage=carbon_free,
            price=price,
            mix=mix,
            flows=flows,
            load=load,
            unavailable=tuple(name for name, value in named.items() if value is None),
        )


def _convert(
    points: tuple[sc.Point, ...],
    signal: str,
    *,
    zone: str,
    provenance: Provenance,
    scenario: sc.Scenario,
) -> tuple[ScalarObservation, ...]:
    """Scenario points to domain observations, by signal name."""
    if signal == "carbon_intensity":
        return tuple(sc.to_carbon_intensity(p, zone=zone, provenance=provenance) for p in points)
    if signal == "price":
        return tuple(
            sc.to_price(p, zone=zone, provenance=provenance, currency=scenario.currency)
            for p in points
        )
    if signal == "load":
        return tuple(sc.to_load(p, zone=zone, provenance=provenance) for p in points)
    if signal in {"renewable_percentage", "carbon_free_percentage"}:
        return tuple(sc.to_percentage(p, zone=zone, provenance=provenance) for p in points)
    raise ValueError(f"No conversion for signal {signal!r}")
