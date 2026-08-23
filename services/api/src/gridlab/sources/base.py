"""What a grid data source can be asked.

One interface, two implementations: :class:`~gridlab.sources.live.LiveSource` calls
Electricity Maps, :class:`~gridlab.sources.replay.ReplaySource` plays a recording. Nothing
above this layer knows which is running, which is what makes a demo safe on venue wifi and
a test suite deterministic.

Methods return ``None`` rather than raising when a signal is simply unavailable — a
free-tier token has no day-ahead price, and a partial snapshot is far more useful than an
exception. Only genuine faults raise.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from gridlab.clock import Clock
from gridlab.domain.models import (
    CarbonIntensity,
    Flows,
    GridSnapshot,
    Load,
    MixBreakdown,
    Observation,
    Percentage,
    Price,
    Provenance,
    ScalarObservation,
    Series,
)


class GridSource(ABC):
    """A source of grid observations."""

    #: What every observation from this source is labelled with.
    provenance: Provenance

    def __init__(self, clock: Clock) -> None:
        self.clock = clock

    @property
    def now(self) -> datetime:
        return self.clock.now()

    @abstractmethod
    async def zones(self) -> tuple[str, ...]:
        """Zone keys this source can answer for."""

    @abstractmethod
    async def snapshot(self, zone: str) -> GridSnapshot:
        """Everything currently known about a zone.

        Must not raise when individual signals are unavailable; list them in
        ``GridSnapshot.unavailable`` instead, so the UI can distinguish "we asked and were
        refused" from "we never asked".
        """

    @abstractmethod
    async def carbon_intensity(self, zone: str) -> CarbonIntensity | None: ...

    @abstractmethod
    async def renewable_percentage(self, zone: str) -> Percentage | None: ...

    @abstractmethod
    async def carbon_free_percentage(self, zone: str) -> Percentage | None: ...

    @abstractmethod
    async def price(self, zone: str) -> Price | None: ...

    @abstractmethod
    async def mix(self, zone: str, *, flow_traced: bool = True) -> MixBreakdown | None:
        """The generation mix.

        ``flow_traced=True`` gives the consumption mix — what is actually available in the
        zone once imports are traced back to their origin — rather than what the zone
        generated. The two are different answers to different questions, and conflating
        them is the most common mistake made with this data.
        """

    @abstractmethod
    async def price_forward(self, zone: str) -> Series[ScalarObservation] | None:
        """Day-ahead prices for delivery periods that have not happened yet.

        Deliberately separate from :meth:`forecast` rather than a ``signal="price"`` branch
        of it, for two reasons.

        First, it is not a forecast. Day-ahead prices are an **auction result** published
        ahead of delivery: once the market clears at 12:00 CET, tomorrow's prices are
        settled fact waiting for their delivery hour. Calling that a prediction invites
        every consumer above this layer to score it against an outcome it already is.

        Second, the API agrees. ``price-day-ahead/forecast`` rejects ``horizonHours``
        outright and demands an explicit window, so the horizon-shaped signature that
        :meth:`forecast` offers cannot be honoured here. The forward view comes from
        ``price-day-ahead/combined``, which needs only a zone.

        Returns ``None`` when the plan or the zone has no day-ahead price at all — coverage
        is Europe plus a few zones, not global.
        """

    @abstractmethod
    async def flows(self, zone: str) -> Flows | None: ...

    @abstractmethod
    async def load(self, zone: str) -> Load | None: ...

    @abstractmethod
    async def forecast(
        self, zone: str, *, signal: str = "carbon_intensity", horizon_hours: int = 24
    ) -> Series[ScalarObservation] | None:
        """The forward view, as currently issued."""

    @abstractmethod
    async def history(
        self,
        zone: str,
        *,
        signal: str = "carbon_intensity",
        start: datetime,
        end: datetime,
        granularity: str = "hourly",
    ) -> Series[ScalarObservation] | None:
        """The backward view over an explicit window."""

    async def compare(
        self, zones: list[str], *, signal: str = "carbon_intensity"
    ) -> dict[str, Observation | None]:
        """The same signal across several zones at the same instant.

        Implemented once here because both sources want identical semantics: simultaneity
        is the point, and a per-source implementation would be a chance to get it wrong.

        Comparing raw levels across zones flatters hydro and punishes coal permanently —
        Norway always wins, Poland always loses, and nothing ever changes. Any *ranking*
        built on top of this should score against each zone's own baseline instead. This
        method deliberately returns the raw values and leaves that judgement to the caller.
        """
        getters = {
            "carbon_intensity": self.carbon_intensity,
            "renewable_percentage": self.renewable_percentage,
            "carbon_free_percentage": self.carbon_free_percentage,
            "price": self.price,
            "load": self.load,
        }
        getter = getters.get(signal)
        if getter is None:
            raise ValueError(f"Cannot compare {signal!r}. Comparable signals: {sorted(getters)}")
        return {zone: await getter(zone) for zone in zones}

    async def aclose(self) -> None:
        """Release resources. Safe to call more than once.

        Concrete and empty by default: a replay source holds nothing to release, and
        forcing every implementation to write a no-op override would be noise.
        """
        return None
