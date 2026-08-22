"""The Electricity Maps v4 endpoint surface, as data.

The v4 API is a regular product of *signal* and *temporality*::

    /v4/{signal}/{temporality}

so rather than hand-writing sixty near-identical methods, we encode the surface as a
capability matrix and build URLs from it. A ``(signal, temporality)`` pair the matrix does
not admit cannot produce a URL, which turns "never invent an endpoint" into a property of
the code instead of a note in a review.

**Everything here was verified against the live API on 22 August 2026** — see
``docs/electricity-maps-api.md`` for the evidence, and ``tests/test_signals.py``, which
asserts the two stay in sync. Several entries exist specifically because the first version
of this file guessed wrong:

* the level signals are ``renewable-percentage-level`` and ``carbon-free-percentage-level``,
  not ``renewable-level`` / ``carbon-free-level``;
* ``breakdownType`` takes ``normal`` or ``flow-traced``, not ``production``/``consumption``;
* ``price-day-ahead/forecast`` rejects ``horizonHours`` and requires ``start``/``end``;
* forecast horizons are **per signal**, not merely plan-dependent.

**Add to the doc first, with evidence, then add it here.**
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
    POWER_BREAKDOWN = "power-breakdown"
    PRICE_DAY_AHEAD = "price-day-ahead"
    LMP_DAY_AHEAD = "locational-marginal-price-day-ahead"
    TOTAL_LOAD = "total-load"
    TOTAL_REPORTED_LOAD = "total-reported-load"
    NET_LOAD = "net-load"
    CARBON_INTENSITY_LEVEL = "carbon-intensity-level"
    RENEWABLE_PERCENTAGE_LEVEL = "renewable-percentage-level"
    CARBON_FREE_PERCENTAGE_LEVEL = "carbon-free-percentage-level"


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
    """Sub-path for ``electricity-source/<sourceType>``.

    Note the asymmetry: the *URL* is ``electricity-source/wind``, while the capability key
    in a zone's ``access`` list is ``electricity-source-wind``. Requesting the latter as a
    path returns 400.
    """

    SOLAR = "solar"
    WIND = "wind"
    HYDRO = "hydro"
    NUCLEAR = "nuclear"
    GAS = "gas"
    COAL = "coal"
    OIL = "oil"
    BIOMASS = "biomass"
    GEOTHERMAL = "geothermal"
    UNKNOWN = "unknown"
    BATTERY = "battery"
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

_LEVEL: Final = frozenset({Temporality.LATEST, Temporality.PAST, Temporality.PAST_RANGE})
"""Level signals reject ``history``.

Their own ``access`` list advertises ``carbon-intensity-level/history``, but calling it
returns 400 with *"Expected one of latest, past, past-range"*. The API is the authority
over its own capability listing; the matrix follows the API.
"""

#: Which temporalities each signal actually offers.
SUPPORTED: Final[dict[Signal, frozenset[Temporality]]] = {
    Signal.CARBON_INTENSITY: _STANDARD,
    Signal.CARBON_INTENSITY_FOSSIL_ONLY: _STANDARD,
    Signal.RENEWABLE_ENERGY: _STANDARD,
    Signal.CARBON_FREE_ENERGY: _STANDARD,
    Signal.ELECTRICITY_MIX: _STANDARD,
    Signal.ELECTRICITY_SOURCE: _STANDARD,
    Signal.ELECTRICITY_FLOWS: _STANDARD,
    Signal.POWER_BREAKDOWN: _STANDARD,
    Signal.PRICE_DAY_AHEAD: _STANDARD | frozenset({Temporality.COMBINED, Temporality.ACTUAL}),
    Signal.LMP_DAY_AHEAD: _STANDARD - frozenset({Temporality.FORECAST}),
    Signal.TOTAL_LOAD: _STANDARD,
    Signal.TOTAL_REPORTED_LOAD: _STANDARD,
    Signal.NET_LOAD: _STANDARD,
    Signal.CARBON_INTENSITY_LEVEL: _LEVEL,
    Signal.RENEWABLE_PERCENTAGE_LEVEL: _LEVEL,
    Signal.CARBON_FREE_PERCENTAGE_LEVEL: _LEVEL,
}

#: Forecast horizons each signal accepts, verified by sweeping the live API.
#:
#: This is the finding that most contradicts the documentation. The docs say horizons are
#: 6/24/48/72 and "availability depends on your plan". In practice it is **per signal**:
#: the intensity and percentage signals take all four, while mix, flows and the load
#: signals accept **only 24** and return 400 for 6, 48 and 72.
#:
#: An empty tuple means the signal forecasts but takes no ``horizonHours`` at all.
FORECAST_HORIZONS: Final[dict[Signal, tuple[int, ...]]] = {
    Signal.CARBON_INTENSITY: (6, 24, 48, 72),
    Signal.CARBON_INTENSITY_FOSSIL_ONLY: (6, 24, 48, 72),
    Signal.RENEWABLE_ENERGY: (6, 24, 48, 72),
    Signal.CARBON_FREE_ENERGY: (6, 24, 48, 72),
    Signal.ELECTRICITY_MIX: (24,),
    Signal.ELECTRICITY_SOURCE: (24,),
    Signal.ELECTRICITY_FLOWS: (24,),
    Signal.POWER_BREAKDOWN: (24,),
    Signal.TOTAL_LOAD: (24,),
    Signal.TOTAL_REPORTED_LOAD: (24,),
    Signal.NET_LOAD: (24,),
    Signal.PRICE_DAY_AHEAD: (),
}

#: Signals whose ``forecast`` requires an explicit ``start``/``end`` window.
#:
#: ``price-day-ahead/forecast`` rejects ``horizonHours`` outright:
#: *"Missing or invalid date parameter \"start\""*. Use ``price-day-ahead/combined``
#: instead when you want the forward view without picking bounds — it blends published
#: auction prices with modelled ones in a single call and needs only a zone.
FORECAST_NEEDS_WINDOW: Final = frozenset({Signal.PRICE_DAY_AHEAD})

#: Signals addressed by ``node`` rather than ``zone``.
#:
#: ``locational-marginal-price-day-ahead`` returns 400 *"Missing arguments \"node\""* for a
#: zone-only request. Node-level pricing is a different addressing scheme, and nothing in
#: this lab is built around it yet.
NODE_ADDRESSED: Final = frozenset({Signal.LMP_DAY_AHEAD})

#: Signals for which day-ahead price coverage is Europe-plus-a-few, not global.
EUROPE_MOSTLY: Final = frozenset({Signal.PRICE_DAY_AHEAD, Signal.LMP_DAY_AHEAD})

#: Signals flagged beta in the documentation.
BETA: Final = frozenset(
    {
        Signal.CARBON_INTENSITY_LEVEL,
        Signal.RENEWABLE_PERCENTAGE_LEVEL,
        Signal.CARBON_FREE_PERCENTAGE_LEVEL,
    }
)


class Granularity(StrEnum):
    """``temporalGranularity``.

    ``5_minutes``, ``15_minutes`` and ``hourly`` are confirmed working on ``history``.
    The coarse values are documented as past-only and ``daily`` returns 400 on ``history``,
    so treat them as available only where a past window is.
    """

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
#: conservative costs an extra request, while being wrong costs a 400 mid-demo.
PAST_RANGE_MAX_DAYS: Final[dict[Granularity, int]] = {
    Granularity.FIVE_MINUTES: 10,
    Granularity.FIFTEEN_MINUTES: 10,
    Granularity.HOURLY: 10,
    Granularity.DAILY: 100,
    Granularity.MONTHLY: 100,
    Granularity.QUARTERLY: 100,
    Granularity.YEARLY: 100,
}


class EmissionFactorType(StrEnum):
    """Lifecycle includes construction and fuel supply chains; direct is combustion only.

    Not a rounding difference. On DK-DK2 the same instant reads 75 gCO2eq/kWh lifecycle and
    20 direct. A chart that does not say which one it is showing is not saying much.
    """

    LIFECYCLE = "lifecycle"
    DIRECT = "direct"


class BreakdownType(StrEnum):
    """``breakdownType`` on ``electricity-mix``. The API accepts exactly these two.

    ``normal`` is what the zone generated. ``flow-traced`` traces imports back through the
    network to say what is actually *available* in the zone — the difference between
    "Denmark generated this" and "this is what is in the wall socket, and some of it
    crossed a border". Flow-tracing is Electricity Maps' distinguishing methodology.

    ``production`` and ``consumption`` are **rejected** with
    *"Valid breakdown types are: normal, flow-traced"* — an earlier version of this file
    guessed those names and would have 400'd on the first live call.
    """

    NORMAL = "normal"
    FLOW_TRACED = "flow-traced"


def supports(signal: Signal, temporality: Temporality) -> bool:
    """Whether the documented API offers this combination."""
    return temporality in SUPPORTED.get(signal, frozenset())


def supported_horizons(signal: Signal) -> tuple[int, ...]:
    """``horizonHours`` values this signal accepts. Empty means it takes none."""
    return FORECAST_HORIZONS.get(signal, ())


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
            f"Electricity Maps does not offer {signal.value}/{temporality.value}. "
            f"Available for {signal.value}: {', '.join(available) or 'nothing'}. "
            f"If you believe this is wrong, verify it against the live API and record the "
            f"evidence in docs/electricity-maps-api.md before changing SUPPORTED."
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
