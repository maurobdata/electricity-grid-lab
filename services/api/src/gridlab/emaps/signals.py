"""The Electricity Maps v4 endpoint surface, as data.

The v4 API is a regular product of *signal* and *temporality*::

    /v4/{signal}/{temporality}

so rather than hand-writing sixty near-identical methods, we encode the surface as a
capability matrix and build URLs from it. A ``(signal, temporality)`` pair the matrix does
not admit cannot produce a URL, which turns "never invent an endpoint" into a property of
the code instead of a note in a review.

Every entry here is traceable to ``docs/electricity-maps-api.md``. ``tests/test_signals.py``
asserts the two stay in sync. **Add to the doc first, with a source, then add it here.**
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final


class Signal(StrEnum):
    """A measurable quantity. The value is the URL path segment."""

    CARBON_INTENSITY = "carbon-intensity"
    CARBON_INTENSITY_FOSSIL_ONLY = "carbon-intensity-fossil-only"
    RENEWABLE_ENERGY = "renewable-energy"
    CARBON_FREE_ENERGY = "carbon-free-energy"
    ELECTRICITY_MIX = "electricity-mix"
    ELECTRICITY_SOURCE = "electricity-source"
    ELECTRICITY_FLOWS = "electricity-flows"
    PRICE_DAY_AHEAD = "price-day-ahead"
    LMP_DAY_AHEAD = "locational-marginal-price-day-ahead"
    TOTAL_LOAD = "total-load"
    TOTAL_REPORTED_LOAD = "total-reported-load"
    NET_LOAD = "net-load"
    CARBON_INTENSITY_LEVEL = "carbon-intensity-level"
    RENEWABLE_LEVEL = "renewable-level"
    CARBON_FREE_LEVEL = "carbon-free-level"


class Temporality(StrEnum):
    """When the data refers to. The value is the URL path segment."""

    LATEST = "latest"
    PAST = "past"
    PAST_RANGE = "past-range"
    HISTORY = "history"
    FORECAST = "forecast"

    # price-day-ahead only
    COMBINED = "combined"
    ACTUAL = "actual"


class SourceType(StrEnum):
    """Sub-path for ``electricity-source/<sourceType>``."""

    SOLAR = "solar"
    WIND = "wind"
    HYDRO = "hydro"
    NUCLEAR = "nuclear"
    GAS = "gas"
    COAL = "coal"
    OIL = "oil"
    BIOMASS = "biomass"
    GEOTHERMAL = "geothermal"
    HYDRO_DISCHARGE = "hydro-discharge"
    BATTERY_DISCHARGE = "battery-discharge"


_STANDARD: Final = frozenset(
    {
        Temporality.LATEST,
        Temporality.PAST,
        Temporality.PAST_RANGE,
        Temporality.HISTORY,
        Temporality.FORECAST,
    }
)

#: Which temporalities each signal actually offers.
#:
#: Two documented exceptions are encoded here rather than discovered in production:
#:
#: * ``locational-marginal-price-day-ahead`` has **no** forecast variant; calling it
#:   returns HTTP 400.
#: * The beta ``*-level`` signals are real-time only.
SUPPORTED: Final[dict[Signal, frozenset[Temporality]]] = {
    Signal.CARBON_INTENSITY: _STANDARD,
    Signal.CARBON_INTENSITY_FOSSIL_ONLY: _STANDARD,
    Signal.RENEWABLE_ENERGY: _STANDARD,
    Signal.CARBON_FREE_ENERGY: _STANDARD,
    Signal.ELECTRICITY_MIX: _STANDARD,
    Signal.ELECTRICITY_SOURCE: _STANDARD,
    Signal.ELECTRICITY_FLOWS: _STANDARD,
    Signal.PRICE_DAY_AHEAD: _STANDARD | frozenset({Temporality.COMBINED, Temporality.ACTUAL}),
    Signal.LMP_DAY_AHEAD: _STANDARD - frozenset({Temporality.FORECAST}),
    Signal.TOTAL_LOAD: _STANDARD,
    Signal.TOTAL_REPORTED_LOAD: _STANDARD,
    Signal.NET_LOAD: _STANDARD,
    Signal.CARBON_INTENSITY_LEVEL: frozenset({Temporality.LATEST}),
    Signal.RENEWABLE_LEVEL: frozenset({Temporality.LATEST}),
    Signal.CARBON_FREE_LEVEL: frozenset({Temporality.LATEST}),
}

#: Signals for which day-ahead price coverage is Europe-plus-a-few, not global.
EUROPE_MOSTLY: Final = frozenset({Signal.PRICE_DAY_AHEAD, Signal.LMP_DAY_AHEAD})

#: Signals flagged beta in the documentation.
BETA: Final = frozenset(
    {Signal.CARBON_INTENSITY_LEVEL, Signal.RENEWABLE_LEVEL, Signal.CARBON_FREE_LEVEL}
)


class Granularity(StrEnum):
    """``temporalGranularity``. The coarse values are past-only."""

    FIVE_MINUTES = "5_minutes"
    FIFTEEN_MINUTES = "15_minutes"
    HOURLY = "hourly"
    DAILY = "daily"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


#: Granularities the API accepts only for past data.
PAST_ONLY_GRANULARITIES: Final = frozenset(
    {
        Granularity.DAILY,
        Granularity.MONTHLY,
        Granularity.QUARTERLY,
        Granularity.YEARLY,
    }
)

#: ``past-range`` window caps, in days, per granularity.
#:
#: Documented explicitly: 10 days at hourly, 100 days at daily. The sub-hourly
#: granularities have no separately published cap, so we apply the hourly one — being
#: conservative here costs an extra request, while being wrong costs a 400 mid-demo.
PAST_RANGE_MAX_DAYS: Final[dict[Granularity, int]] = {
    Granularity.FIVE_MINUTES: 10,
    Granularity.FIFTEEN_MINUTES: 10,
    Granularity.HOURLY: 10,
    Granularity.DAILY: 100,
    Granularity.MONTHLY: 100,
    Granularity.QUARTERLY: 100,
    Granularity.YEARLY: 100,
}

#: ``horizonHours`` values the API accepts. Which of them *your plan* returns is a
#: separate question — ``probe_capabilities`` answers it.
FORECAST_HORIZONS: Final = (6, 24, 48, 72)


class EmissionFactorType(StrEnum):
    LIFECYCLE = "lifecycle"
    DIRECT = "direct"


class BreakdownType(StrEnum):
    """Production mix vs the flow-traced consumption mix.

    Flow-tracing is Electricity Maps' distinguishing methodology: it traces imports back
    through the network to say what is actually *available on* a grid rather than what was
    generated in it. It is the difference between "Denmark generated this" and "this is
    what is in the wall socket, and a fifth of it crossed a border".
    """

    PRODUCTION = "production"
    FLOW_TRACED = "flow-traced"


def supports(signal: Signal, temporality: Temporality) -> bool:
    """Whether the documented API offers this combination."""
    return temporality in SUPPORTED.get(signal, frozenset())


def path_for(
    signal: Signal,
    temporality: Temporality,
    *,
    source_type: SourceType | None = None,
) -> str:
    """Build the path for a signal/temporality pair.

    Raises:
        UnsupportedEndpoint: if the documentation does not describe this combination, or
            if ``electricity-source`` is requested without a source type.
    """
    from gridlab.emaps.errors import UnsupportedEndpoint

    if not supports(signal, temporality):
        available = sorted(t.value for t in SUPPORTED.get(signal, frozenset()))
        raise UnsupportedEndpoint(
            f"Electricity Maps does not document {signal.value}/{temporality.value}. "
            f"Available for {signal.value}: {', '.join(available) or 'nothing'}. "
            f"If you believe this is wrong, add it to docs/electricity-maps-api.md "
            f"with a source first, then to SUPPORTED."
        )

    if signal is Signal.ELECTRICITY_SOURCE:
        if source_type is None:
            raise UnsupportedEndpoint(
                "electricity-source requires a source_type, e.g. SourceType.WIND"
            )
        return f"{signal.value}/{source_type.value}/{temporality.value}"

    if source_type is not None:
        raise UnsupportedEndpoint(
            f"source_type is only meaningful for {Signal.ELECTRICITY_SOURCE.value}, "
            f"not {signal.value}"
        )

    return f"{signal.value}/{temporality.value}"
