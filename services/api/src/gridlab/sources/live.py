"""Live Electricity Maps data, cached and degrading gracefully.

Every read goes through the DuckDB cache first. On a cache miss we call the API; if that
call fails, we fall back to the last good value and mark it ``is_stale``. A stale number
behind a visible badge is worth far more than an error page, and admitting the staleness is
worth more than hiding it.

Signals the token cannot reach return ``None`` rather than raising, so a free-tier key
produces a smaller lab rather than a broken one.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

import structlog

from gridlab.clock import Clock, LiveClock
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
from gridlab.emaps import errors, normalize
from gridlab.emaps.client import EMapsClient
from gridlab.emaps.signals import BreakdownType, Granularity, Signal, Temporality
from gridlab.sources.base import GridSource
from gridlab.store.duckdb_cache import Cache

log = structlog.get_logger(__name__)

#: Domain signal name -> the Electricity Maps signal and the candidate response keys.
_SERIES_SIGNALS: dict[str, tuple[Signal, tuple[str, ...]]] = {
    "carbon_intensity": (Signal.CARBON_INTENSITY, ("carbonIntensity",)),
    "renewable_percentage": (Signal.RENEWABLE_ENERGY, ("renewablePercentage", "percentage")),
    "carbon_free_percentage": (
        Signal.CARBON_FREE_ENERGY,
        ("carbonFreePercentage", "percentage"),
    ),
    "price": (Signal.PRICE_DAY_AHEAD, ("price",)),
    "load": (Signal.TOTAL_LOAD, ("load", "totalLoad")),
}


class LiveSource(GridSource):
    """Read Electricity Maps through a read-through cache."""

    provenance = Provenance.LIVE

    def __init__(
        self,
        client: EMapsClient,
        cache: Cache,
        *,
        clock: Clock | None = None,
        zone_keys: tuple[str, ...] = (),
    ) -> None:
        super().__init__(clock or LiveClock())
        self._client = client
        self._cache = cache
        self._zones = zone_keys

    async def aclose(self) -> None:
        await self._client.aclose()

    async def zones(self) -> tuple[str, ...]:
        return self._zones

    # -- the one fetch path --------------------------------------------------

    async def _fetch(
        self,
        signal: Signal,
        temporality: Temporality,
        **params: Any,
    ) -> tuple[dict[str, Any], bool] | None:
        """Cache, then network, then stale cache. Returns ``(body, is_stale)`` or ``None``.

        ``None`` means "this signal is not available", not "something broke". A caller that
        gets ``None`` should present the signal as missing, not fail.
        """
        clean = {k: v for k, v in params.items() if v is not None}
        key = self._cache.key(signal.value, temporality.value, clean)

        cached = self._cache.get_raw(key)
        if cached is not None:
            return cached

        try:
            body = await self._client.fetch(signal, temporality, **params)
        except (errors.AccessDeniedError, errors.NotFoundError) as exc:
            # Expected with a limited token. Not an error worth propagating.
            log.info("live.unavailable", signal=signal.value, error=type(exc).__name__)
            return None
        except errors.ElectricityMapsError as exc:
            stale = self._cache.get_raw(key, allow_stale=True)
            if stale is not None:
                log.warning("live.serving_stale", signal=signal.value, error=str(exc))
                return stale[0], True
            log.error("live.failed", signal=signal.value, error=str(exc))
            return None

        self._cache.put_raw(
            key,
            body,
            signal=signal.value,
            temporality=temporality.value,
            zone=clean.get("zone"),
            params=clean,
        )
        return body, False

    @staticmethod
    def _mark_stale[T: Observation](observation: T, is_stale: bool) -> T:
        return observation.model_copy(update={"is_stale": True}) if is_stale else observation

    # -- point reads ---------------------------------------------------------

    async def carbon_intensity(self, zone: str) -> CarbonIntensity | None:
        result = await self._fetch(Signal.CARBON_INTENSITY, Temporality.LATEST, zone=zone)
        if result is None:
            return None
        body, stale = result
        return self._mark_stale(normalize.carbon_intensity(body, zone=zone), stale)

    async def renewable_percentage(self, zone: str) -> Percentage | None:
        return await self._percentage(zone, Signal.RENEWABLE_ENERGY, "renewable_percentage")

    async def carbon_free_percentage(self, zone: str) -> Percentage | None:
        return await self._percentage(zone, Signal.CARBON_FREE_ENERGY, "carbon_free_percentage")

    async def _percentage(self, zone: str, signal: Signal, name: str) -> Percentage | None:
        result = await self._fetch(signal, Temporality.LATEST, zone=zone)
        if result is None:
            return None
        body, stale = result
        keys = list(_SERIES_SIGNALS[name][1])
        return self._mark_stale(normalize.percentage(body, zone=zone, keys=keys), stale)

    async def price(self, zone: str) -> Price | None:
        result = await self._fetch(Signal.PRICE_DAY_AHEAD, Temporality.LATEST, zone=zone)
        if result is None:
            return None
        body, stale = result
        return self._mark_stale(normalize.price(body, zone=zone), stale)

    async def load(self, zone: str) -> Load | None:
        result = await self._fetch(Signal.TOTAL_LOAD, Temporality.LATEST, zone=zone)
        if result is None:
            return None
        body, stale = result
        return self._mark_stale(normalize.load(body, zone=zone), stale)

    async def mix(self, zone: str, *, flow_traced: bool = True) -> MixBreakdown | None:
        result = await self._fetch(
            Signal.ELECTRICITY_MIX,
            Temporality.LATEST,
            zone=zone,
            breakdown_type=BreakdownType.FLOW_TRACED if flow_traced else BreakdownType.PRODUCTION,
        )
        if result is None:
            return None
        body, stale = result
        return self._mark_stale(normalize.mix(body, zone=zone, flow_traced=flow_traced), stale)

    async def flows(self, zone: str) -> Flows | None:
        result = await self._fetch(Signal.ELECTRICITY_FLOWS, Temporality.LATEST, zone=zone)
        if result is None:
            return None
        body, stale = result
        return self._mark_stale(normalize.flows(body, zone=zone), stale)

    # -- series reads --------------------------------------------------------

    async def forecast(
        self, zone: str, *, signal: str = "carbon_intensity", horizon_hours: int = 24
    ) -> Series[ScalarObservation] | None:
        entry = _SERIES_SIGNALS.get(signal)
        if entry is None:
            return None
        emaps_signal, _ = entry

        result = await self._fetch(
            emaps_signal, Temporality.FORECAST, zone=zone, horizon_hours=horizon_hours
        )
        if result is None:
            return None
        body, _stale = result
        return normalize.series(
            [body],
            zone=zone,
            normalizer=self._normalizer_for(signal),
            horizon_hours=horizon_hours,
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
        entry = _SERIES_SIGNALS.get(signal)
        if entry is None:
            return None
        emaps_signal, _ = entry

        # fetch_range chunks around the documented 10-day/100-day caps. Individual chunks
        # are not cached: history windows are rarely requested twice with identical bounds,
        # and caching them would fill the store with near-duplicates.
        try:
            bodies = await self._client.fetch_range(
                emaps_signal,
                zone=zone,
                start=start,
                end=end,
                granularity=Granularity(granularity),
            )
        except (errors.AccessDeniedError, errors.NotFoundError):
            return None
        except errors.ElectricityMapsError as exc:
            log.error("live.history_failed", zone=zone, signal=signal, error=str(exc))
            return None

        series = normalize.series(
            bodies, zone=zone, normalizer=self._normalizer_for(signal), granularity=granularity
        )
        self._cache.record(signal, list(series.points))
        return series

    @staticmethod
    def _normalizer_for(signal: str) -> Callable[..., ScalarObservation]:
        if signal == "carbon_intensity":
            return normalize.carbon_intensity
        if signal == "price":
            return normalize.price
        if signal == "load":
            return normalize.load
        keys = list(_SERIES_SIGNALS[signal][1])

        def as_percentage(raw: Any, **kwargs: Any) -> ScalarObservation:
            return normalize.percentage(raw, keys=keys, **kwargs)

        return as_percentage

    # -- composite -----------------------------------------------------------

    async def snapshot(self, zone: str) -> GridSnapshot:
        """Everything at once.

        Sequential rather than concurrent, deliberately. Seven parallel requests per zone
        against an undocumented rate limit is how a trial key gets throttled during a demo;
        after the first poll these are cache hits anyway.
        """
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
            provenance=Provenance.LIVE,
            carbon_intensity=carbon,
            renewable_percentage=renewable,
            carbon_free_percentage=carbon_free,
            price=price,
            mix=mix,
            flows=flows,
            load=load,
            unavailable=tuple(name for name, value in named.items() if value is None),
        )


def default_history_window(clock: Clock, days: int = 7) -> tuple[datetime, datetime]:
    """A sensible default window: the last ``days`` days ending now."""
    end = clock.now()
    return end - timedelta(days=days), end
