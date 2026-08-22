"""LiveSource, driven by the recorded fixtures through a mock transport.

This file exists because three bugs reached the first live run that no test could see:

1. the DuckDB schema used a reserved word and would not create;
2. DuckDB needs ``pytz`` to read a ``TIMESTAMPTZ``;
3. ``LiveSource`` passed whole response envelopes to normalizers, but half the ``latest``
   endpoints wrap their single row in ``{"data": [...]}``.

All three were invisible because replay mode never opens a cache and never touches an
Electricity Maps envelope. Serving the real recorded bodies over a mock transport gives the
live path the same offline, deterministic coverage the replay path already had.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from gridlab.clock import FrozenClock
from gridlab.domain.models import Provenance
from gridlab.emaps.client import EMapsClient
from gridlab.sources.live import LiveSource
from gridlab.store.duckdb_cache import Cache

FIXTURES = Path("/app/fixtures")
ZONE = "DK-DK2"

pytestmark = pytest.mark.skipif(
    not FIXTURES.is_dir() or not list(FIXTURES.glob("*.json")),
    reason="no recorded fixtures mounted; run `make record` with a token",
)


def _body(name: str) -> dict[str, Any] | None:
    path = FIXTURES / f"{name}.json"
    if not path.is_file():
        return None
    payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    body: dict[str, Any] = payload["body"]
    return body


def _fixture_handler(request: httpx.Request) -> httpx.Response:
    """Serve the recorded response matching the request path.

    ``/carbon-intensity/latest`` maps to ``carbon-intensity__latest.json``, and
    ``/electricity-source/wind/latest`` to ``electricity-source__latest.json``.
    """
    parts = [p for p in request.url.path.split("/") if p and p != "v4"]
    if parts == ["zones"]:
        body = _body("zones")
        return httpx.Response(200, json=body) if body else httpx.Response(404, json={})

    # Fixtures were recorded for one zone. Anything else is refused the way a real plan
    # refuses a zone it does not cover, so the degradation path gets exercised.
    if request.url.params.get("zone") not in (None, ZONE):
        return httpx.Response(
            401,
            json={"error": f"Request unauthorized for zoneKey={request.url.params.get('zone')}."},
        )

    signal, temporality = parts[0], parts[-1]
    body = _body(f"{signal}__{temporality}")
    if body is None:
        # Nothing recorded for this combination: mimic a plan that does not include it,
        # which is exactly the case LiveSource must survive without raising. `past-range`
        # is the real example — it returns 401 on the free tier.
        return httpx.Response(401, json={"error": f"Request unauthorized for dataType={signal}."})
    return httpx.Response(200, json=body)


@pytest.fixture
def source(tmp_path: Path) -> Iterator[LiveSource]:
    client = EMapsClient(
        token="test-token",
        transport=httpx.MockTransport(_fixture_handler),
        retries=0,
    )
    cache = Cache(tmp_path / "live.duckdb", ttl_seconds=300)
    yield LiveSource(
        client,
        cache,
        clock=FrozenClock(datetime(2026, 8, 22, 17, tzinfo=UTC)),
        zone_keys=(ZONE, "DE"),
    )
    cache.close()


# --- envelope handling ------------------------------------------------------


async def test_snapshot_builds_from_real_responses(source: LiveSource) -> None:
    """The regression. `electricity-mix/latest` and `electricity-flows/latest` wrap their
    single row in `data`, while `carbon-intensity/latest` is a bare object. Handing the
    envelope straight to a normalizer works for one and raises for the other."""
    snapshot = await source.snapshot(ZONE)

    assert snapshot.provenance is Provenance.LIVE
    assert snapshot.carbon_intensity is not None
    assert snapshot.mix is not None, "mix failed to normalize from its `data` envelope"
    assert snapshot.flows is not None, "flows failed to normalize from its `data` envelope"
    assert snapshot.price is not None
    assert snapshot.mix.entries
    assert snapshot.mix.total_mw and snapshot.mix.total_mw > 0


@pytest.mark.parametrize(
    "getter",
    [
        "carbon_intensity",
        "renewable_percentage",
        "carbon_free_percentage",
        "price",
        "load",
        "flows",
    ],
)
async def test_each_point_read_survives_its_own_envelope(source: LiveSource, getter: str) -> None:
    result = await getattr(source, getter)(ZONE)
    assert result is not None, f"{getter} returned nothing from a recorded response"


async def test_both_mix_breakdowns_normalize(source: LiveSource) -> None:
    for flow_traced in (True, False):
        breakdown = await source.mix(ZONE, flow_traced=flow_traced)
        assert breakdown is not None
        assert breakdown.entries


# --- degradation ------------------------------------------------------------


async def test_a_signal_outside_the_plan_is_absent_not_fatal(source: LiveSource) -> None:
    """A 401 for one signal must shrink the lab, not break it. This is the shape of a
    free-tier key, and of the level signals whose names we originally got wrong."""
    snapshot = await source.snapshot("DE")  # nothing recorded for DE
    assert snapshot.zone == "DE"
    assert snapshot.unavailable, "expected every signal to be reported unavailable"


async def test_unavailable_lists_what_was_asked_for(source: LiveSource) -> None:
    snapshot = await source.snapshot("DE")
    assert "carbon_intensity" in snapshot.unavailable
    assert "price" in snapshot.unavailable


# --- caching ----------------------------------------------------------------


async def test_the_second_read_does_not_hit_the_network(tmp_path: Path) -> None:
    """Electricity Maps publishes no rate limit, so the cache is the only thing standing
    between a demo with a refresh button and a throttled trial key."""
    calls = 0

    def counting_handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return _fixture_handler(request)

    client = EMapsClient(token="t", transport=httpx.MockTransport(counting_handler), retries=0)
    cache = Cache(tmp_path / "c.duckdb", ttl_seconds=300)
    live = LiveSource(client, cache, zone_keys=(ZONE,))

    await live.carbon_intensity(ZONE)
    first = calls
    await live.carbon_intensity(ZONE)

    assert calls == first, "second read went to the network despite a warm cache"
    cache.close()


async def test_stale_cache_is_served_when_the_network_dies(tmp_path: Path) -> None:
    """The venue-wifi path. A stale number behind a visible badge beats an error page."""
    fail = False

    def flaky(request: httpx.Request) -> httpx.Response:
        if fail:
            raise httpx.ConnectError("venue wifi")
        return _fixture_handler(request)

    client = EMapsClient(token="t", transport=httpx.MockTransport(flaky), retries=0)
    cache = Cache(tmp_path / "c.duckdb", ttl_seconds=0)  # everything expires at once
    live = LiveSource(client, cache, zone_keys=(ZONE,))

    fresh = await live.carbon_intensity(ZONE)
    assert fresh is not None and fresh.is_stale is False

    fail = True
    degraded = await live.carbon_intensity(ZONE)

    assert degraded is not None, "a dead network should degrade, not erase the value"
    assert degraded.is_stale is True
    assert degraded.value == fresh.value
    cache.close()


async def test_no_cached_value_and_no_network_yields_nothing_not_an_exception(
    tmp_path: Path,
) -> None:
    def dead(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no network")

    client = EMapsClient(token="t", transport=httpx.MockTransport(dead), retries=0)
    cache = Cache(tmp_path / "c.duckdb")
    live = LiveSource(client, cache, zone_keys=(ZONE,))

    assert await live.carbon_intensity(ZONE) is None
    snapshot = await live.snapshot(ZONE)
    assert "carbon_intensity" in snapshot.unavailable
    cache.close()


# --- series -----------------------------------------------------------------


async def test_forecast_normalizes_and_keeps_its_issue_time(source: LiveSource) -> None:
    series = await source.forecast(ZONE, horizon_hours=24)
    assert series is not None
    assert len(series.points) > 1
    assert series.issued_at is not None
    assert all(p.value is not None for p in series.points)


async def test_history_falls_back_when_past_range_is_not_in_the_plan(
    source: LiveSource,
) -> None:
    """The free tier returns 401 for `past-range` but serves `history` — a trailing 24
    hours. Refusing to fall back would leave the only history this key has unreachable."""
    end = datetime(2026, 8, 22, 17, tzinfo=UTC)
    series = await source.history(ZONE, start=end - timedelta(days=1), end=end)

    assert series is not None, "past-range was refused and no fallback was attempted"
    assert series.points


async def test_history_is_clipped_to_the_requested_window(source: LiveSource) -> None:
    """`history` returns whatever trailing window it likes. Returning more than was asked
    for would make a chart's axis disagree with its own query."""
    end = datetime(2026, 8, 22, 17, tzinfo=UTC)
    start = end - timedelta(hours=6)
    series = await source.history(ZONE, start=start, end=end)

    assert series is not None
    assert all(start <= p.at <= end for p in series.points)


async def test_history_outside_the_available_window_is_absent(source: LiveSource) -> None:
    """Asking 2024 of a key that holds 24 hours must return nothing, not a stray point."""
    end = datetime(2024, 1, 5, tzinfo=UTC)
    assert await source.history(ZONE, start=end - timedelta(days=4), end=end) is None
