"""HTTP client for the Electricity Maps v4 API.

Responsibilities, and deliberately nothing else:

* build URLs only from the capability matrix in :mod:`gridlab.emaps.signals`;
* attach the ``auth-token`` header;
* always send ``disableCallerLookup=true``;
* split ``past-range`` requests that exceed the documented window cap;
* retry transient failures with backoff;
* map HTTP statuses onto typed errors;
* return **raw JSON**.

It does not normalize, cache, or interpret. Normalization lives in
:mod:`gridlab.emaps.normalize`; caching lives in the source layer. Keeping those apart is
what lets us record raw responses as fixtures and replay them through the same normalizer.
"""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import Any, Self

import httpx
import structlog

from gridlab.emaps import errors
from gridlab.emaps.signals import (
    FORECAST_NEEDS_WINDOW,
    PAST_RANGE_MAX_DAYS,
    BreakdownType,
    EmissionFactorType,
    Granularity,
    Signal,
    SourceType,
    Temporality,
    path_for,
    supported_horizons,
)

log = structlog.get_logger(__name__)

_RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})


def chunk_range(
    start: datetime,
    end: datetime,
    granularity: Granularity = Granularity.HOURLY,
) -> Iterator[tuple[datetime, datetime]]:
    """Split ``[start, end]`` into windows the API will accept.

    ``past-range`` is capped at 10 days hourly and 100 days daily. Asking for more returns
    an error rather than a truncated result, so the loop has to happen somewhere; it
    happens here, once, instead of in every caller.

    Chunks are half-open at the join (each subsequent chunk starts one microsecond after
    the previous ended) so a point on a boundary is not returned twice.

    Raises:
        ValueError: if ``end`` precedes ``start``.
    """
    if end < start:
        raise ValueError(f"end ({end.isoformat()}) precedes start ({start.isoformat()})")

    max_days = PAST_RANGE_MAX_DAYS[granularity]
    window = timedelta(days=max_days)

    cursor = start
    while cursor <= end:
        chunk_end = min(cursor + window, end)
        yield cursor, chunk_end
        if chunk_end >= end:
            return
        cursor = chunk_end + timedelta(microseconds=1)


def _iso(moment: datetime) -> str:
    """ISO 8601, UTC, as the API expects.

    Naive datetimes are assumed UTC rather than rejected: every internal timestamp is
    already UTC, and a stray naive value at 17:00 in Copenhagen should not raise.
    """
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC).isoformat().replace("+00:00", "Z")


class EMapsClient:
    """Async client for the Electricity Maps v4 API.

    Usage::

        async with EMapsClient(token="...") as client:
            raw = await client.fetch(Signal.CARBON_INTENSITY, Temporality.LATEST, zone="DK-DK2")
    """

    def __init__(
        self,
        *,
        token: str | None,
        base_url: str = "https://api.electricitymaps.com/v4",
        timeout: float = 20.0,
        retries: int = 3,
        backoff_base: float = 1.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._token = token
        self._base_url = base_url.rstrip("/")
        self._retries = max(0, retries)
        self._backoff_base = backoff_base
        headers = {"User-Agent": "gridlab/0.1 (Hack on the Grid 2026)"}
        if token:
            headers["auth-token"] = token
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers=headers,
            timeout=timeout,
            transport=transport,
            follow_redirects=False,
        )

    @property
    def has_token(self) -> bool:
        return bool(self._token)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    # -- the one place a URL is constructed ----------------------------------

    async def fetch(
        self,
        signal: Signal,
        temporality: Temporality,
        *,
        zone: str | None = None,
        lat: float | None = None,
        lon: float | None = None,
        datetime_: datetime | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        horizon_hours: int | None = None,
        granularity: Granularity | None = None,
        emission_factor_type: EmissionFactorType | None = None,
        breakdown_type: BreakdownType | None = None,
        flow_traced: bool | None = None,
        disable_estimations: bool | None = None,
        source_type: SourceType | None = None,
        data_center_provider: str | None = None,
        data_center_region: str | None = None,
    ) -> dict[str, Any]:
        """Fetch one signal at one temporality. Returns the raw JSON body.

        Raises:
            UnsupportedEndpoint: the combination is not documented (raised before any I/O).
            ElectricityMapsError: any HTTP or transport failure, typed by cause.
        """
        path = path_for(signal, temporality, source_type=source_type)

        if temporality is Temporality.FORECAST:
            horizon_hours = self._check_horizon(signal, horizon_hours, start=start, end=end)

        params: dict[str, Any] = {"disableCallerLookup": "true"}
        if zone is not None:
            params["zone"] = zone
        if lat is not None:
            params["lat"] = lat
        if lon is not None:
            params["lon"] = lon
        if datetime_ is not None:
            params["datetime"] = _iso(datetime_)
        if start is not None:
            params["start"] = _iso(start)
        if end is not None:
            params["end"] = _iso(end)
        if horizon_hours is not None:
            params["horizonHours"] = horizon_hours
        if granularity is not None:
            params["temporalGranularity"] = granularity.value
        if emission_factor_type is not None:
            params["emissionFactorType"] = emission_factor_type.value
        if breakdown_type is not None:
            params["breakdownType"] = breakdown_type.value
        if flow_traced is not None:
            params["flowTraced"] = "true" if flow_traced else "false"
        if disable_estimations is not None:
            params["disableEstimations"] = "true" if disable_estimations else "false"
        if data_center_provider is not None:
            params["dataCenterProvider"] = data_center_provider
        if data_center_region is not None:
            params["dataCenterRegion"] = data_center_region

        return await self._get(path, params)

    @staticmethod
    def _check_horizon(
        signal: Signal,
        horizon_hours: int | None,
        *,
        start: datetime | None,
        end: datetime | None,
    ) -> int | None:
        """Validate ``horizonHours`` against what this signal actually accepts.

        Forecast horizons are per signal, not merely plan-dependent: carbon intensity and
        the percentage signals take 6/24/48/72, while mix, flows and the load signals
        accept **only 24** and return 400 for the rest. Catching that here turns a 400
        during a demo into an error at the call site, with the valid values in it.
        """
        from gridlab.emaps.errors import UnsupportedEndpoint

        if signal in FORECAST_NEEDS_WINDOW:
            if horizon_hours is not None:
                raise UnsupportedEndpoint(
                    f"{signal.value}/forecast rejects horizonHours; it requires start and "
                    f"end. For a forward view without picking bounds, use "
                    f"{signal.value}/combined, which needs only a zone."
                )
            if start is None or end is None:
                raise UnsupportedEndpoint(f"{signal.value}/forecast requires both start and end.")
            return None

        allowed = supported_horizons(signal)
        if horizon_hours is None or not allowed:
            return horizon_hours
        if horizon_hours not in allowed:
            raise UnsupportedEndpoint(
                f"{signal.value}/forecast accepts horizonHours {list(allowed)}, "
                f"not {horizon_hours}. This is a per-signal limit, not a plan limit."
            )
        return horizon_hours

    async def fetch_range(
        self,
        signal: Signal,
        *,
        zone: str,
        start: datetime,
        end: datetime,
        granularity: Granularity = Granularity.HOURLY,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Fetch ``past-range`` over an arbitrary window, chunked as needed.

        Returns the raw JSON body of each chunk, in order. Merging is the normalizer's job.
        """
        bodies: list[dict[str, Any]] = []
        for chunk_start, chunk_end in chunk_range(start, end, granularity):
            bodies.append(
                await self.fetch(
                    signal,
                    Temporality.PAST_RANGE,
                    zone=zone,
                    start=chunk_start,
                    end=chunk_end,
                    granularity=granularity,
                    **kwargs,
                )
            )
        return bodies

    async def zones(self) -> dict[str, Any]:
        """``GET /v4/zones``.

        Works without a token (all zones) and with one (the zones your plan can reach),
        which makes it the capability probe. See ``gridlab.scripts.probe_capabilities``.
        """
        return await self._get("zones", {})

    # -- transport -----------------------------------------------------------

    async def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._base_url}/{path}"
        last_error: Exception | None = None

        for attempt in range(self._retries + 1):
            started = time.perf_counter()
            try:
                response = await self._client.get(f"/{path}", params=params)
            except httpx.HTTPError as exc:
                last_error = errors.TransportError(f"{type(exc).__name__} calling {url}: {exc}")
                log.warning(
                    "emaps.transport_error",
                    path=path,
                    attempt=attempt + 1,
                    error=str(exc),
                )
                if attempt < self._retries:
                    await self._backoff(attempt)
                    continue
                raise last_error from exc

            log.info(
                "emaps.request",
                path=path,
                status=response.status_code,
                ms=round((time.perf_counter() - started) * 1000, 1),
                attempt=attempt + 1,
                # Never log the token. `params` carries no secret; the header does.
                params={k: v for k, v in params.items() if k != "auth-token"},
            )

            if response.status_code == 200:
                body: Any = response.json()
                if not isinstance(body, dict):
                    raise errors.ElectricityMapsError(
                        f"Expected a JSON object from {url}, got {type(body).__name__}"
                    )
                return body

            if response.status_code in _RETRYABLE_STATUSES and attempt < self._retries:
                await self._backoff(attempt, response)
                continue

            raise errors.from_status(response.status_code, response.text, url=url)

        raise last_error or errors.ElectricityMapsError(f"exhausted retries for {url}")

    async def _backoff(self, attempt: int, response: httpx.Response | None = None) -> None:
        """Exponential backoff with jitter, honouring ``Retry-After`` when present.

        Jitter matters more than it looks: without it, a page that fetches eight zones
        retries all eight in lockstep and hammers a rate limit in phase.
        """
        if response is not None:
            header = response.headers.get("Retry-After")
            if header:
                try:
                    await asyncio.sleep(min(float(header), 30.0))
                    return
                except ValueError:
                    pass
        delay = self._backoff_base * min(2**attempt, 8) * (0.5 + random.random())
        await asyncio.sleep(delay)
