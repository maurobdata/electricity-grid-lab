"""Adapter behaviour, against a mock transport. No network, no key, no flakiness."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from itertools import pairwise

import httpx
import pytest

from gridlab.emaps import errors
from gridlab.emaps.client import EMapsClient, chunk_range
from gridlab.emaps.signals import Granularity, Signal, SourceType, Temporality

JAN1 = datetime(2026, 1, 1, tzinfo=UTC)


# --- chunking ---------------------------------------------------------------
#
# `past-range` is capped at 10 days hourly and 100 days daily. Getting this wrong is a
# silent data-loss bug at best and a 400 mid-demo at worst, so the boundaries are pinned.


def test_short_range_is_one_chunk() -> None:
    chunks = list(chunk_range(JAN1, JAN1 + timedelta(days=3)))
    assert chunks == [(JAN1, JAN1 + timedelta(days=3))]


def test_exactly_the_cap_is_one_chunk() -> None:
    chunks = list(chunk_range(JAN1, JAN1 + timedelta(days=10)))
    assert len(chunks) == 1


def test_one_day_over_the_cap_splits() -> None:
    chunks = list(chunk_range(JAN1, JAN1 + timedelta(days=11)))
    assert len(chunks) == 2
    assert chunks[0][0] == JAN1
    assert chunks[-1][1] == JAN1 + timedelta(days=11)


def test_chunks_are_contiguous_and_do_not_overlap() -> None:
    """A point on a chunk boundary must appear exactly once, or charts draw it twice."""
    chunks = list(chunk_range(JAN1, JAN1 + timedelta(days=95)))
    assert len(chunks) == 10
    for earlier, later in pairwise(chunks):
        assert later[0] > earlier[1]
        assert later[0] - earlier[1] == timedelta(microseconds=1)


def test_daily_granularity_uses_the_larger_cap() -> None:
    hourly = list(chunk_range(JAN1, JAN1 + timedelta(days=90), Granularity.HOURLY))
    daily = list(chunk_range(JAN1, JAN1 + timedelta(days=90), Granularity.DAILY))
    assert len(hourly) == 9
    assert len(daily) == 1


def test_a_decade_of_history_chunks_without_blowing_up() -> None:
    """~10 years hourly is the full archive; it must terminate and stay contiguous."""
    chunks = list(chunk_range(JAN1, JAN1 + timedelta(days=3650)))
    assert len(chunks) == 365
    assert chunks[0][0] == JAN1
    assert chunks[-1][1] == JAN1 + timedelta(days=3650)


def test_zero_length_range_yields_one_chunk() -> None:
    assert list(chunk_range(JAN1, JAN1)) == [(JAN1, JAN1)]


def test_backwards_range_is_rejected() -> None:
    with pytest.raises(ValueError, match="precedes start"):
        list(chunk_range(JAN1, JAN1 - timedelta(days=1)))


# --- request construction ---------------------------------------------------


def _client(handler: object, *, token: str | None = "test-token") -> EMapsClient:
    return EMapsClient(
        token=token,
        transport=httpx.MockTransport(handler),  # type: ignore[arg-type]
        retries=0,
    )


async def test_token_goes_in_the_auth_token_header() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.headers)
        return httpx.Response(200, json={"zone": "DK-DK2", "carbonIntensity": 120})

    async with _client(handler) as client:
        await client.fetch(Signal.CARBON_INTENSITY, Temporality.LATEST, zone="DK-DK2")

    assert seen["auth-token"] == "test-token"


async def test_caller_lookup_is_always_disabled() -> None:
    """Without this the API geolocates the caller's IP and silently answers about the
    wrong country. That failure is invisible - the response looks perfectly valid."""
    captured: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request.url)
        return httpx.Response(200, json={"datetime": "2026-01-01T00:00:00Z", "carbonIntensity": 1})

    async with _client(handler) as client:
        await client.fetch(Signal.CARBON_INTENSITY, Temporality.LATEST, zone="ES")

    assert captured[0].params["disableCallerLookup"] == "true"


async def test_parameters_are_translated_to_the_documented_names() -> None:
    captured: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request.url)
        return httpx.Response(200, json={"data": []})

    async with _client(handler) as client:
        await client.fetch(
            Signal.CARBON_INTENSITY,
            Temporality.FORECAST,
            zone="DK-DK1",
            horizon_hours=72,
            granularity=Granularity.FIFTEEN_MINUTES,
        )

    params = captured[0].params
    assert params["horizonHours"] == "72"
    assert params["temporalGranularity"] == "15_minutes"
    assert captured[0].path.endswith("/carbon-intensity/forecast")


async def test_datetimes_are_sent_as_utc_iso8601() -> None:
    captured: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request.url)
        return httpx.Response(200, json={"data": []})

    async with _client(handler) as client:
        await client.fetch(
            Signal.CARBON_INTENSITY,
            Temporality.PAST,
            zone="DE",
            datetime_=datetime(2026, 2, 4, 18, 30, tzinfo=UTC),
        )

    assert captured[0].params["datetime"] == "2026-02-04T18:30:00Z"


async def test_source_type_becomes_a_path_segment() -> None:
    captured: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request.url)
        return httpx.Response(200, json={"data": []})

    async with _client(handler) as client:
        await client.fetch(
            Signal.ELECTRICITY_SOURCE,
            Temporality.HISTORY,
            zone="DK-DK1",
            source_type=SourceType.WIND,
        )

    assert captured[0].path.endswith("/electricity-source/wind/history")


async def test_undocumented_combination_never_reaches_the_network() -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("a request was made for an endpoint that does not exist")

    async with _client(handler) as client:
        with pytest.raises(errors.UnsupportedEndpoint):
            await client.fetch(Signal.LMP_DAY_AHEAD, Temporality.FORECAST, zone="DE")


async def test_fetch_range_issues_one_request_per_chunk() -> None:
    calls: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url)
        return httpx.Response(200, json={"data": []})

    async with _client(handler) as client:
        bodies = await client.fetch_range(
            Signal.CARBON_INTENSITY,
            zone="DK-DK2",
            start=JAN1,
            end=JAN1 + timedelta(days=25),
        )

    assert len(calls) == 3
    assert len(bodies) == 3
    assert all(u.path.endswith("/carbon-intensity/past-range") for u in calls)


# --- error mapping ----------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (400, errors.BadRequestError),
        (401, errors.AuthenticationError),
        (403, errors.AccessDeniedError),
        (404, errors.NotFoundError),
        (429, errors.RateLimitError),
        (503, errors.UpstreamError),
    ],
)
async def test_statuses_map_to_typed_errors(status: int, expected: type[Exception]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text="nope")

    async with _client(handler) as client:
        with pytest.raises(expected):
            await client.fetch(Signal.CARBON_INTENSITY, Temporality.LATEST, zone="DK-DK2")


async def test_403_message_points_at_the_probe() -> None:
    """403 is the likeliest failure with a free-tier key, and the least self-explanatory."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="not in plan")

    async with _client(handler) as client:
        with pytest.raises(errors.AccessDeniedError, match="make probe"):
            await client.fetch(Signal.PRICE_DAY_AHEAD, Temporality.LATEST, zone="DK-DK2")


async def test_transport_failure_is_typed_not_leaked() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("venue wifi")

    async with _client(handler) as client:
        with pytest.raises(errors.TransportError):
            await client.fetch(Signal.CARBON_INTENSITY, Temporality.LATEST, zone="DK-DK2")


async def test_a_json_array_body_is_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[1, 2, 3])

    async with _client(handler) as client:
        with pytest.raises(errors.ElectricityMapsError, match="Expected a JSON object"):
            await client.fetch(Signal.CARBON_INTENSITY, Temporality.LATEST, zone="DK-DK2")


# --- retry ------------------------------------------------------------------


async def test_retryable_status_is_retried_then_succeeds() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            return httpx.Response(503, text="unavailable")
        return httpx.Response(200, json={"datetime": "2026-01-01T00:00:00Z", "carbonIntensity": 9})

    client = EMapsClient(
        token="t",
        transport=httpx.MockTransport(handler),  # type: ignore[arg-type]
        retries=3,
        backoff_base=0.001,
    )
    async with client:
        body = await client.fetch(Signal.CARBON_INTENSITY, Temporality.LATEST, zone="DK-DK2")

    assert attempts == 3
    assert body["carbonIntensity"] == 9


async def test_client_errors_are_not_retried() -> None:
    """Retrying a 403 just burns quota against an undocumented rate limit."""
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(403, text="not in plan")

    client = EMapsClient(
        token="t",
        transport=httpx.MockTransport(handler),  # type: ignore[arg-type]
        retries=3,
        backoff_base=0.001,
    )
    async with client:
        with pytest.raises(errors.AccessDeniedError):
            await client.fetch(Signal.CARBON_INTENSITY, Temporality.LATEST, zone="DK-DK2")

    assert attempts == 1


async def test_zones_works_without_a_token() -> None:
    """/v4/zones is the one unauthenticated endpoint, and our capability probe."""
    seen: list[httpx.Headers] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers)
        return httpx.Response(200, json={"DK-DK2": {"zoneName": "East Denmark"}})

    async with _client(handler, token=None) as client:
        body = await client.zones()

    assert "auth-token" not in seen[0]
    assert "DK-DK2" in body
