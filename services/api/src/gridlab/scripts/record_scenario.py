"""Record a real, replayable scenario from the live Electricity Maps API.

    make scenario-live

The synthetic builders in :mod:`gridlab.scripts.make_scenario` exist so a fresh clone runs.
This exists because what the API can actually give us is **perishable**: on the free tier
``past`` and ``past-range`` return 401 and ``history`` reaches back roughly 24 hours (see
ADR 0008). Whatever is reachable today is gone tomorrow, so recording is the only way to
keep it.

A recording holds, per zone:

* roughly 24 hours of **actuals** — what the replay clock plays through;
* the **forecast as issued at the moment of recording**, which extends past the end of that
  window.

Those two do not overlap, and it is worth being explicit about why. A single recording
cannot show forecast-versus-outcome, because the hours a forecast covers have not happened
yet. Recording daily builds that up: today's forecast reaches into tomorrow's actuals. The
``issued_at`` stamp is what makes that comparison possible later, so it is never dropped.

Every signal is optional. A plan that cannot reach one produces a scenario without it and a
line in the notes, rather than an exception — the same degradation rule the rest of the lab
follows.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from gridlab.config import get_settings
from gridlab.domain.models import Provenance
from gridlab.emaps import errors, normalize
from gridlab.emaps.client import EMapsClient
from gridlab.emaps.signals import (
    BreakdownType,
    Granularity,
    Signal,
    Temporality,
    supported_horizons,
)
from gridlab.store import scenario as sc

#: Scalar signals worth recording, mapped to the API signal and the normalizer that reads
#: it. Keyed by the ``ZoneData`` field they populate.
SCALAR_SIGNALS: dict[str, tuple[Signal, Callable[..., Any]]] = {
    "carbon_intensity": (Signal.CARBON_INTENSITY, normalize.carbon_intensity),
    "renewable_percentage": (Signal.RENEWABLE_ENERGY, normalize.percentage),
    "carbon_free_percentage": (Signal.CARBON_FREE_ENERGY, normalize.percentage),
    "price": (Signal.PRICE_DAY_AHEAD, normalize.price),
    "load": (Signal.TOTAL_LOAD, normalize.load),
}

#: Signals to capture a forecast for.
#:
#: Only the scalar signals that a replay can chart against their own actuals. The horizon
#: is taken from the capability matrix rather than a constant, because horizons are per
#: signal — carbon intensity accepts 72 hours, the load and breakdown signals only 24, and
#: asking for the wrong one is a 400.
FORECAST_FIELDS: tuple[str, ...] = (
    "carbon_intensity",
    "renewable_percentage",
    "carbon_free_percentage",
)


class Recorder:
    """Turns live API responses into scenario points, remembering what it could not reach."""

    def __init__(self, client: EMapsClient, *, granularity: str = "hourly") -> None:
        self._client = client
        self._granularity = Granularity(granularity)
        self.skipped: list[str] = []

    async def _history_rows(
        self, signal: Signal, zone: str, **kwargs: Any
    ) -> list[Mapping[str, Any]] | None:
        """Trailing history for one signal, as raw rows.

        Uses the ``history`` temporality rather than ``past-range``: the latter is not in
        every plan, and where it is absent this is the only history there is.
        """
        try:
            body = await self._client.fetch(
                signal,
                Temporality.HISTORY,
                zone=zone,
                granularity=self._granularity,
                **kwargs,
            )
        except errors.ElectricityMapsError as exc:
            self.skipped.append(f"{zone} {signal.value}/history ({type(exc).__name__})")
            return None
        return normalize.rows(body)

    async def scalar_series(self, field: str, zone: str) -> tuple[sc.Point, ...]:
        signal, normalizer = SCALAR_SIGNALS[field]
        rows = await self._history_rows(signal, zone)
        if rows is None:
            return ()

        points: list[sc.Point] = []
        for row in rows:
            try:
                points.append(sc.from_observation(normalizer(dict(row), zone=zone)))
            except errors.ElectricityMapsError as exc:
                self.skipped.append(f"{zone} {field} row ({exc})")
        return tuple(sorted(points, key=lambda p: p.at))

    async def mix_series(self, zone: str) -> tuple[sc.MixPoint, ...]:
        """Both breakdowns, in one series.

        Production and flow-traced are recorded together so a replay can offer the toggle
        that makes flow-tracing legible — what this zone generated, versus what is actually
        in the socket once imports are traced back to their origin. Recording only one of
        them would quietly remove the most distinctive thing this data can show.
        """
        points: list[sc.MixPoint] = []
        for breakdown_type in (BreakdownType.NORMAL, BreakdownType.FLOW_TRACED):
            rows = await self._history_rows(
                Signal.ELECTRICITY_MIX, zone, breakdown_type=breakdown_type
            )
            if rows is None:
                continue
            for row in rows:
                try:
                    points.append(sc.from_mix(normalize.mix(dict(row), zone=zone)))
                except errors.ElectricityMapsError as exc:
                    self.skipped.append(f"{zone} mix row ({exc})")
        return tuple(sorted(points, key=lambda p: (p.at, p.flow_traced)))

    async def flow_series(self, zone: str) -> tuple[sc.FlowPoint, ...]:
        rows = await self._history_rows(Signal.ELECTRICITY_FLOWS, zone)
        if rows is None:
            return ()

        points: list[sc.FlowPoint] = []
        for row in rows:
            try:
                points.append(sc.from_flows(normalize.flows(dict(row), zone=zone)))
            except errors.ElectricityMapsError as exc:
                self.skipped.append(f"{zone} flows row ({exc})")
        return tuple(sorted(points, key=lambda p: p.at))

    async def forecast(self, field: str, zone: str) -> sc.Forecast | None:
        """The forecast as issued right now, at the deepest horizon this signal allows."""
        signal, normalizer = SCALAR_SIGNALS[field]
        horizons = supported_horizons(signal)
        if not horizons:
            # price-day-ahead forecasts need an explicit window rather than a horizon;
            # `combined` is the better forward view and is left for a later pass.
            return None

        horizon = max(horizons)
        try:
            body = await self._client.fetch(
                signal, Temporality.FORECAST, zone=zone, horizon_hours=horizon
            )
        except errors.ElectricityMapsError as exc:
            self.skipped.append(f"{zone} {signal.value}/forecast ({type(exc).__name__})")
            return None

        series = normalize.series([body], zone=zone, normalizer=normalizer)
        if not series.points:
            return None

        return sc.Forecast(
            # `issued_at` is the field that makes a later forecast-versus-outcome
            # comparison possible at all. The response usually supplies it; the wall clock
            # is a truthful fallback, since that is when we asked.
            issued_at=series.issued_at or datetime.now(UTC),
            horizon_hours=horizon,
            points=tuple(sc.from_observation(p) for p in series.points),
        )

    async def zone_data(self, zone: str) -> tuple[sc.ZoneData, str | None]:
        """Everything recordable for one zone, plus its currency if a price was found."""
        scalars = {field: await self.scalar_series(field, zone) for field in SCALAR_SIGNALS}

        currency: str | None = None
        price_rows = await self._history_rows(Signal.PRICE_DAY_AHEAD, zone)
        if price_rows:
            currency = normalize.price(dict(price_rows[0]), zone=zone).currency

        forecasts: dict[str, sc.Forecast] = {}
        for field in FORECAST_FIELDS:
            forecast = await self.forecast(field, zone)
            if forecast is not None:
                forecasts[field] = forecast

        return (
            sc.ZoneData(
                **scalars,
                mix=await self.mix_series(zone),
                flows=await self.flow_series(zone),
                forecasts=forecasts,
            ),
            currency,
        )


def _actual_timestamps(zones: Mapping[str, sc.ZoneData]) -> list[datetime]:
    """Every timestamp among the actuals. Forecasts are excluded deliberately.

    The replay window must cover only hours that happened. Including forecast points would
    let the clock run into a stretch where nothing has an actual value, and every panel
    would read as empty rather than as future.
    """
    stamps: list[datetime] = []
    for data in zones.values():
        for series in (
            data.carbon_intensity,
            data.renewable_percentage,
            data.carbon_free_percentage,
            data.price,
            data.load,
        ):
            stamps.extend(p.at for p in series)
        stamps.extend(p.at for p in data.mix)
        stamps.extend(p.at for p in data.flows)
    return stamps


async def record(
    client: EMapsClient,
    zones: Sequence[str],
    *,
    scenario_id: str | None = None,
    title: str | None = None,
    granularity: str = "hourly",
) -> sc.Scenario:
    """Record the reachable window for ``zones`` as a replayable scenario.

    Raises:
        RuntimeError: if no zone yielded any actuals. A scenario with no window cannot be
            replayed, and writing one would produce a file that fails later and further
            from the cause.
    """
    recorder = Recorder(client, granularity=granularity)

    zone_data: dict[str, sc.ZoneData] = {}
    currency = "EUR"
    for zone in zones:
        data, zone_currency = await recorder.zone_data(zone)
        zone_data[zone] = data
        if zone_currency:
            currency = zone_currency

    stamps = _actual_timestamps(zone_data)
    if not stamps:
        raise RuntimeError(
            "No actuals were recorded for any zone, so there is no window to replay. "
            "Run `make probe`: a token without `history` access cannot produce a scenario."
        )

    start, end = min(stamps), max(stamps)
    recorded_on = datetime.now(UTC)
    hours = round((end - start).total_seconds() / 3600)

    notes = [
        f"RECORDED from the Electricity Maps API at {recorded_on.isoformat()}.",
        "Real measured and modelled values, not generated. Individual points keep their own"
        " is_estimated flag, because Electricity Maps models a great deal of what it"
        " reports.",
        f"Actuals span {start.isoformat()} to {end.isoformat()} at {granularity} granularity.",
    ]
    if any(data.forecasts for data in zone_data.values()):
        notes.append(
            "Forecasts are stored as issued at recording time and extend beyond the end of"
            " the window, so they describe hours that had not happened yet. One recording"
            " therefore cannot show forecast-versus-outcome; record daily and today's"
            " forecast will overlap tomorrow's actuals."
        )
    if recorder.skipped:
        notes.append(f"Not available to this token: {', '.join(sorted(set(recorder.skipped)))}")

    return sc.Scenario(
        id=scenario_id or f"{zones[0].lower()}-{recorded_on:%Y-%m-%d}",
        title=title or f"{', '.join(zones)} - recorded {recorded_on:%d %b %Y %H:%M} UTC",
        description=(
            f"{hours} hours of real grid data for {', '.join(zones)}, with the forecast "
            f"issued at the moment of recording."
        ),
        provenance=Provenance.RECORDED,
        currency=currency,
        start=start,
        end=end,
        granularity=granularity,
        zones=zone_data,
        notes=" ".join(notes),
    )


async def run(zones: list[str], out: Path, granularity: str, scenario_id: str | None) -> int:
    settings = get_settings()
    if not settings.has_api_token:
        print(
            "No ELECTRICITY_MAPS_API_TOKEN in .env, so there is nothing live to record.\n"
            "Get a token at https://portal.electricitymaps.com/, then try again.",
            file=sys.stderr,
        )
        return 2

    token = settings.electricity_maps_api_token
    async with EMapsClient(
        token=token.get_secret_value() if token else None,
        base_url=settings.electricity_maps_base_url,
        timeout=settings.gridlab_http_timeout,
        retries=settings.gridlab_http_retries,
    ) as client:
        print(f"Recording {', '.join(zones)} at {granularity} granularity.\n")
        try:
            scenario = await record(client, zones, granularity=granularity, scenario_id=scenario_id)
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 1

    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{scenario.id}.json"
    path.write_text(scenario.model_dump_json(indent=2) + "\n", encoding="utf-8")

    # -- report --------------------------------------------------------------

    print(f"  id        {scenario.id}")
    print(f"  window    {scenario.start.isoformat()} .. {scenario.end.isoformat()}")
    print(f"  provenance {scenario.provenance.value}")
    for zone, data in scenario.zones.items():
        estimated = sum(1 for p in data.carbon_intensity if p.is_estimated)
        print(
            f"\n  {zone}: {len(data.carbon_intensity)} carbon-intensity points "
            f"({estimated} estimated)"
        )
        print(
            f"      renewable {len(data.renewable_percentage)}  "
            f"carbon-free {len(data.carbon_free_percentage)}  "
            f"price {len(data.price)}  load {len(data.load)}"
        )
        traced = sum(1 for p in data.mix if p.flow_traced)
        print(f"      mix {len(data.mix)} ({traced} flow-traced)  flows {len(data.flows)}")
        for field, forecast in sorted(data.forecasts.items()):
            print(
                f"      forecast {field}: {len(forecast.points)} points, "
                f"{forecast.horizon_hours}h, issued {forecast.issued_at.isoformat()}"
            )

    print(f"\nWrote {path}")
    print(
        "\nPlay it with:  GRIDLAB_SCENARIO=" + scenario.id + " make restart"
        "\nRecord again tomorrow: today's forecast will overlap tomorrow's actuals, which is"
        "\nthe only way to get forecast-versus-outcome out of a key without `past-range`."
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--zones",
        default="DK-DK2",
        help=(
            "Comma-separated zone keys. DK-DK2 is Copenhagen and the host's home grid. "
            "Several zones make cross-zone comparison replayable."
        ),
    )
    parser.add_argument("--out", type=Path, default=Path("scenarios"))
    parser.add_argument(
        "--granularity",
        default="hourly",
        choices=["5_minutes", "15_minutes", "hourly"],
        help="Finer granularities give more points over the same trailing window.",
    )
    parser.add_argument(
        "--id",
        dest="scenario_id",
        default=None,
        help="Scenario id. Defaults to <zone>-<date>, so daily runs do not overwrite.",
    )
    args = parser.parse_args(argv)

    zones = [z.strip() for z in args.zones.split(",") if z.strip()]
    if not zones:
        print("No zones given.", file=sys.stderr)
        return 2

    return asyncio.run(run(zones, args.out, args.granularity, args.scenario_id))


if __name__ == "__main__":
    raise SystemExit(main())
