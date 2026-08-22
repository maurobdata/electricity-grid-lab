"""The DuckDB cache.

These exist because the schema was broken for its entire first life and no test noticed:
replay mode never opens a cache, so ``CREATE TABLE`` was not executed until the first live
run — where it failed outright on a reserved word. Anything that only live mode exercises
needs a test that does not need live mode.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from gridlab.domain.models import CarbonIntensity, Provenance
from gridlab.store.duckdb_cache import Cache

NOW = datetime(2026, 8, 22, 17, tzinfo=UTC)


def make_cache(tmp_path: Path, ttl: int = 300) -> Cache:
    return Cache(tmp_path / "test.duckdb", ttl_seconds=ttl)


def test_schema_applies(tmp_path: Path) -> None:
    """The regression. `at` is reserved in DuckDB; the table would not create at all."""
    cache = make_cache(tmp_path)
    stats = cache.stats()
    assert stats["raw_responses"] == 0
    assert stats["observations"] == 0
    cache.close()


def test_it_creates_its_own_directory(tmp_path: Path) -> None:
    """The container mounts an empty volume at /data, so this is the normal first run."""
    cache = Cache(tmp_path / "nested" / "deeper" / "grid.duckdb")
    assert (tmp_path / "nested" / "deeper").is_dir()
    cache.close()


def test_reopening_an_existing_file_is_not_an_error(tmp_path: Path) -> None:
    make_cache(tmp_path).close()
    make_cache(tmp_path).close()


# --- raw response caching ---------------------------------------------------


def test_round_trip(tmp_path: Path) -> None:
    cache = make_cache(tmp_path)
    key = cache.key("carbon-intensity", "latest", {"zone": "DK-DK2"})
    cache.put_raw(
        key,
        {"carbonIntensity": 75},
        signal="carbon-intensity",
        temporality="latest",
        zone="DK-DK2",
        params={"zone": "DK-DK2"},
    )

    result = cache.get_raw(key)
    assert result is not None
    body, is_stale = result
    assert body["carbonIntensity"] == 75
    assert is_stale is False
    cache.close()


def test_a_miss_is_none_not_an_exception(tmp_path: Path) -> None:
    cache = make_cache(tmp_path)
    assert cache.get_raw("nothing here") is None
    cache.close()


def test_key_is_stable_regardless_of_dict_order(tmp_path: Path) -> None:
    """Without sorted keys, the same request produces two cache entries and the hit rate
    silently halves — against an undocumented rate limit."""
    cache = make_cache(tmp_path)
    a = cache.key("carbon-intensity", "latest", {"zone": "DK-DK2", "horizonHours": 24})
    b = cache.key("carbon-intensity", "latest", {"horizonHours": 24, "zone": "DK-DK2"})
    assert a == b
    cache.close()


def test_different_params_are_different_entries(tmp_path: Path) -> None:
    cache = make_cache(tmp_path)
    assert cache.key("electricity-mix", "latest", {"breakdownType": "normal"}) != cache.key(
        "electricity-mix", "latest", {"breakdownType": "flow-traced"}
    )
    cache.close()


def test_expired_entries_are_a_miss_by_default(tmp_path: Path) -> None:
    cache = make_cache(tmp_path, ttl=0)
    key = cache.key("carbon-intensity", "latest", {"zone": "DK-DK2"})
    cache.put_raw(
        key, {"v": 1}, signal="carbon-intensity", temporality="latest", zone="DK-DK2", params={}
    )
    time.sleep(0.01)
    assert cache.get_raw(key) is None
    cache.close()


def test_expired_entries_are_available_as_stale_on_request(tmp_path: Path) -> None:
    """The graceful-degradation path. When the venue wifi dies, a stale number behind a
    visible badge beats an error page — and admitting the staleness beats hiding it."""
    cache = make_cache(tmp_path, ttl=0)
    key = cache.key("carbon-intensity", "latest", {"zone": "DK-DK2"})
    cache.put_raw(
        key, {"v": 1}, signal="carbon-intensity", temporality="latest", zone="DK-DK2", params={}
    )
    time.sleep(0.01)

    result = cache.get_raw(key, allow_stale=True)
    assert result is not None
    body, is_stale = result
    assert body["v"] == 1
    assert is_stale is True
    cache.close()


def test_writing_the_same_key_twice_replaces_it(tmp_path: Path) -> None:
    cache = make_cache(tmp_path)
    key = cache.key("carbon-intensity", "latest", {"zone": "DK-DK2"})
    for value in (1, 2):
        cache.put_raw(
            key,
            {"v": value},
            signal="carbon-intensity",
            temporality="latest",
            zone="DK-DK2",
            params={},
        )
    result = cache.get_raw(key)
    assert result and result[0]["v"] == 2
    assert cache.stats()["raw_responses"] == 1
    cache.close()


# --- observations -----------------------------------------------------------


def observation(hour: int, value: float) -> CarbonIntensity:
    return CarbonIntensity(
        zone="DK-DK2",
        at=NOW + timedelta(hours=hour),
        provenance=Provenance.LIVE,
        value=value,
    )


def test_observations_round_trip_in_order(tmp_path: Path) -> None:
    cache = make_cache(tmp_path)
    written = cache.record("carbon_intensity", [observation(2, 120), observation(0, 100)])
    assert written == 2

    read = cache.read("DK-DK2", "carbon_intensity", start=NOW, end=NOW + timedelta(hours=3))
    assert [r["value"] for r in read] == [100, 120]
    cache.close()


def test_recording_the_same_instant_twice_updates_rather_than_duplicates(
    tmp_path: Path,
) -> None:
    """Upstream revises values, and chunked range fetches overlap at the boundary. Two
    rows for one instant draw a vertical line through a chart."""
    cache = make_cache(tmp_path)
    cache.record("carbon_intensity", [observation(0, 100)])
    cache.record("carbon_intensity", [observation(0, 105)])

    read = cache.read("DK-DK2", "carbon_intensity", start=NOW, end=NOW + timedelta(hours=1))
    assert len(read) == 1
    assert read[0]["value"] == 105
    cache.close()


def test_recording_nothing_is_not_an_error(tmp_path: Path) -> None:
    cache = make_cache(tmp_path)
    assert cache.record("carbon_intensity", []) == 0
    cache.close()


def test_provenance_and_estimation_survive_the_round_trip(tmp_path: Path) -> None:
    cache = make_cache(tmp_path)
    cache.record(
        "carbon_intensity",
        [observation(0, 100).model_copy(update={"is_estimated": True})],
    )
    read = cache.read("DK-DK2", "carbon_intensity", start=NOW, end=NOW + timedelta(hours=1))
    assert read[0]["provenance"] == "live"
    assert read[0]["is_estimated"] is True
    cache.close()


def test_reads_are_scoped_to_zone_and_signal(tmp_path: Path) -> None:
    cache = make_cache(tmp_path)
    cache.record("carbon_intensity", [observation(0, 100)])
    cache.record("price", [observation(0, 42)])

    assert len(cache.read("DK-DK2", "price", start=NOW, end=NOW + timedelta(hours=1))) == 1
    assert cache.read("DE", "carbon_intensity", start=NOW, end=NOW + timedelta(hours=1)) == []
    cache.close()


def test_stats_report_the_stored_window(tmp_path: Path) -> None:
    cache = make_cache(tmp_path)
    cache.record("carbon_intensity", [observation(0, 100), observation(5, 200)])
    stats = cache.stats()
    assert stats["observations"] == 2
    assert stats["earliest"] and stats["latest"]
    assert stats["earliest"] < stats["latest"]
    cache.close()
