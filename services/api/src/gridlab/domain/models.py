"""The domain model: what Grid Lab knows about a grid.

These types are **provider-neutral**. Nothing here mentions Electricity Maps, and nothing
outside ``gridlab.emaps.normalize`` may use an Electricity Maps field name. That boundary
is what lets us swap data sources, replay history, and survive discovering on 11 September
that a response field is called something other than we guessed.

Every observation carries two pieces of metadata that must never be dropped:

``provenance``
    Where the number came from. Measured live, replayed from a recording, or generated.
    This reaches the UI as a badge. Synthetic data must never be mistakable for measured
    data — not on a screen, not in a screenshot, not on stage.

``is_estimated``
    Electricity Maps models values it cannot measure, and says so. A zone that is mostly
    estimated is unfit for anything that scores a prediction or ranks a zone.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Provenance(StrEnum):
    """Where a value came from. Never omit it, never guess it."""

    LIVE = "live"
    """Fetched from the upstream API during this run."""

    RECORDED = "recorded"
    """Replayed from a response that was really returned by the API, at a real timestamp."""

    SYNTHETIC = "synthetic"
    """Generated. Useful for tests and for demos with no recording. Never real."""


class DataQuality(StrEnum):
    """Electricity Maps' coverage tier for a zone.

    Tier A is measured hourly. Tier C is a yearly total. Comparing a Tier A zone with a
    Tier C zone produces a number that looks meaningful and is not.
    """

    A = "A"
    B = "B"
    C = "C"
    UNKNOWN = "unknown"


class Base(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Observation(Base):
    """One value, at one time, for one zone."""

    zone: str
    at: datetime
    provenance: Provenance
    is_estimated: bool = False
    estimation_method: str | None = None
    is_stale: bool = False
    """True when this is the last good value rather than a fresh one."""

    updated_at: datetime | None = None


class ScalarObservation(Observation):
    """An observation whose payload is a single number.

    Named because it is the thing a time series is made of. Charts, forecasts, history and
    comparison all operate on scalars; mix and flows are structured and never appear in a
    series.
    """

    value: float


class CarbonIntensity(ScalarObservation):
    """gCO2eq/kWh."""

    emission_factor_type: str | None = None
    flow_traced: bool | None = None


class Percentage(ScalarObservation):
    """A share of the mix, 0-100. Used for renewable and carbon-free percentages."""

    value: float = Field(ge=0, le=100)


class Price(ScalarObservation):
    """Day-ahead price.

    ``currency`` matters: Electricity Maps returns local currency, so summing across zones
    without converting is wrong. ``source`` distinguishes a published auction price from
    Electricity Maps' own modelled one -- the ``combined`` endpoint returns both.
    """

    currency: str = "EUR"
    unit: str = "MWh"
    source: str | None = None


class MixEntry(Base):
    """One generation source's contribution."""

    source: str
    """e.g. wind, solar, nuclear, coal, gas, hydro-discharge, battery-discharge."""

    power_mw: float | None = None
    percent: float | None = None


class MixBreakdown(Observation):
    """The generation mix.

    ``flow_traced`` is the interesting bit. Production mix says what this zone generated;
    the flow-traced consumption mix says what is actually available in the socket,
    including imports traced back through the network to their origin. The two can differ
    enormously, and the difference is a story rather than a statistic.
    """

    entries: tuple[MixEntry, ...]
    flow_traced: bool
    total_mw: float | None = None

    def share(self, source: str) -> float | None:
        for entry in self.entries:
            if entry.source == source:
                return entry.percent
        return None


class FlowEdge(Base):
    """Net power on one interconnector, from this zone's point of view."""

    counterpart_zone: str
    net_flow_mw: float
    """Positive means export to the counterpart; negative means import from it."""

    @property
    def direction(self) -> str:
        return "export" if self.net_flow_mw >= 0 else "import"


class Flows(Observation):
    """Cross-border exchange for a zone at an instant."""

    edges: tuple[FlowEdge, ...]

    @property
    def net_import_mw(self) -> float:
        return -sum(e.net_flow_mw for e in self.edges)


class Load(ScalarObservation):
    """Demand in MW. ``kind`` is one of total, reported, or net (total minus wind+solar)."""

    kind: str = "total"


class LevelBucket(StrEnum):
    """The beta level signals, bucketed against a rolling baseline.

    Useful precisely because it needs no numeracy: "high" means high *for this zone*, so
    it works for Poland and Norway alike without either looking permanently virtuous.
    """

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    UNKNOWN = "unknown"


class Level(Observation):
    bucket: LevelBucket
    of: str
    """Which signal this bucket describes: carbon-intensity, renewable, carbon-free."""


class Series[ObservationT: ScalarObservation](Base):
    """An ordered run of observations of one kind.

    Used for history and for forecasts. ``horizon_hours`` is set only for forecasts;
    ``issued_at`` records *when the forecast was made*, which is the thing that makes
    forecast-versus-actual comparison possible at all.
    """

    zone: str
    points: tuple[ObservationT, ...]
    granularity: str = "hourly"
    horizon_hours: int | None = None
    issued_at: datetime | None = None

    @property
    def provenance(self) -> Provenance:
        """The weakest provenance in the series.

        A series is only as trustworthy as its least trustworthy point, so one synthetic
        value makes the whole series synthetic. This is deliberately pessimistic.
        """
        if not self.points:
            return Provenance.SYNTHETIC
        order = {Provenance.SYNTHETIC: 0, Provenance.RECORDED: 1, Provenance.LIVE: 2}
        return min((p.provenance for p in self.points), key=lambda p: order[p])

    @property
    def estimated_fraction(self) -> float:
        if not self.points:
            return 0.0
        return sum(1 for p in self.points if p.is_estimated) / len(self.points)


class Zone(Base):
    """A bidding/grid zone."""

    key: str
    """Electricity Maps zone key, e.g. DK-DK1."""

    name: str
    country_name: str | None = None
    quality: DataQuality = DataQuality.UNKNOWN
    has_day_ahead_price: bool = False
    accessible: bool = True
    """Whether the configured token can actually reach it. Set by the capability probe."""


class GridSnapshot(Base):
    """Everything the lab currently knows about one zone at one moment.

    This is what the "Now" panel renders. Fields are optional throughout: a free-tier token
    will not return prices, and a partial snapshot is far more useful than an exception.
    """

    zone: str
    at: datetime
    provenance: Provenance
    carbon_intensity: CarbonIntensity | None = None
    renewable_percentage: Percentage | None = None
    carbon_free_percentage: Percentage | None = None
    price: Price | None = None
    mix: MixBreakdown | None = None
    flows: Flows | None = None
    load: Load | None = None
    level: Level | None = None
    unavailable: tuple[str, ...] = ()
    """Signals that were asked for and could not be provided, with no exception raised.

    The UI shows these as explicitly missing rather than silently absent. "We asked and
    your plan said no" and "we never asked" look identical otherwise, and only one of them
    is worth acting on.
    """
