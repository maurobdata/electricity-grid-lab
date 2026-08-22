"""A small DuckDB cache in front of Electricity Maps.

Two jobs, both about not making the same request twice:

``raw_responses``
    Verbatim JSON, keyed by the request that produced it, with a TTL. This is the rate-limit
    shield — Electricity Maps publishes no rate limit, so we assume one exists and is not
    generous — and it doubles as the last-good value when the network drops mid-demo.

``observations``
    Normalized values, for asking questions across time and zones without re-fetching.

DuckDB rather than Postgres because it is a single embedded file with no server, and rather
than SQLite because the interesting queries here are analytical: rolling baselines, per-hour
percentiles, forecast-versus-actual error. Those are the queries any of the candidate
products will want, whichever one is chosen.
"""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import duckdb
import structlog

from gridlab.domain.models import Observation

log = structlog.get_logger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS raw_responses (
    cache_key   VARCHAR PRIMARY KEY,
    signal      VARCHAR NOT NULL,
    temporality VARCHAR NOT NULL,
    zone        VARCHAR,
    params      VARCHAR NOT NULL,
    body        VARCHAR NOT NULL,
    fetched_at  TIMESTAMPTZ NOT NULL
);

-- `observed_at`, not `at`: `at` is a reserved word in DuckDB and CREATE TABLE fails with
-- "syntax error at or near \"at\"". Nothing caught this until the first live run, because
-- replay mode never opens a cache.
CREATE TABLE IF NOT EXISTS observations (
    zone         VARCHAR NOT NULL,
    signal       VARCHAR NOT NULL,
    observed_at  TIMESTAMPTZ NOT NULL,
    value        DOUBLE,
    provenance   VARCHAR NOT NULL,
    is_estimated BOOLEAN NOT NULL DEFAULT FALSE,
    payload      VARCHAR,
    recorded_at  TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (zone, signal, observed_at)
);

CREATE INDEX IF NOT EXISTS observations_zone_signal_at
    ON observations (zone, signal, observed_at);
"""


class Cache:
    """Read-through cache and observation store.

    DuckDB connections are not thread-safe, and FastAPI runs handlers in a thread pool, so
    every statement is serialized behind one lock. At this scale — a handful of zones,
    five-minute polls — contention is irrelevant next to correctness.
    """

    def __init__(self, path: Path, *, ttl_seconds: int = 300) -> None:
        self.path = path
        self.ttl = timedelta(seconds=ttl_seconds)
        self._lock = threading.Lock()

        path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = duckdb.connect(str(path))
        with self._lock:
            self._connection.execute(SCHEMA)
        log.info("cache.opened", path=str(path), ttl_seconds=ttl_seconds)

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    # -- raw responses -------------------------------------------------------

    @staticmethod
    def key(signal: str, temporality: str, params: dict[str, Any]) -> str:
        """A stable key for a request.

        ``sort_keys`` matters: dict ordering would otherwise produce two keys for the same
        request and halve the hit rate silently.
        """
        return f"{signal}/{temporality}?{json.dumps(params, sort_keys=True, default=str)}"

    def get_raw(
        self, cache_key: str, *, allow_stale: bool = False
    ) -> tuple[dict[str, Any], bool] | None:
        """Return ``(body, is_stale)``, or ``None``.

        With ``allow_stale``, an expired entry is returned with ``is_stale=True`` instead of
        being treated as a miss. That is the graceful-degradation path: when the venue wifi
        dies, showing yesterday's number behind a clear badge beats showing an error.
        """
        with self._lock:
            row = self._connection.execute(
                "SELECT body, fetched_at FROM raw_responses WHERE cache_key = ?",
                [cache_key],
            ).fetchone()

        if row is None:
            return None

        body, fetched_at = json.loads(row[0]), row[1]
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=UTC)

        is_stale = datetime.now(UTC) - fetched_at > self.ttl
        if is_stale and not allow_stale:
            return None
        return body, is_stale

    def put_raw(
        self,
        cache_key: str,
        body: dict[str, Any],
        *,
        signal: str,
        temporality: str,
        zone: str | None,
        params: dict[str, Any],
    ) -> None:
        with self._lock:
            self._connection.execute(
                """
                INSERT OR REPLACE INTO raw_responses
                    (cache_key, signal, temporality, zone, params, body, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    cache_key,
                    signal,
                    temporality,
                    zone,
                    json.dumps(params, sort_keys=True, default=str),
                    json.dumps(body),
                    datetime.now(UTC),
                ],
            )

    # -- observations --------------------------------------------------------

    def record(self, signal: str, observations: list[Observation]) -> int:
        """Persist normalized observations. Idempotent on (zone, signal, at)."""
        if not observations:
            return 0

        now = datetime.now(UTC)
        rows = [
            [
                obs.zone,
                signal,
                obs.at,
                float(getattr(obs, "value", 0.0) or 0.0),
                obs.provenance.value,
                obs.is_estimated,
                obs.model_dump_json(),
                now,
            ]
            for obs in observations
        ]
        with self._lock:
            self._connection.executemany(
                """
                INSERT OR REPLACE INTO observations (
                    zone, signal, observed_at, value,
                    provenance, is_estimated, payload, recorded_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        return len(rows)

    def read(
        self, zone: str, signal: str, *, start: datetime, end: datetime
    ) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT observed_at, value, provenance, is_estimated
                FROM observations
                WHERE zone = ? AND signal = ? AND observed_at BETWEEN ? AND ?
                ORDER BY observed_at
                """,
                [zone, signal, start, end],
            ).fetchall()
        return [{"at": r[0], "value": r[1], "provenance": r[2], "is_estimated": r[3]} for r in rows]

    def stats(self) -> dict[str, Any]:
        """Small enough for a health endpoint, useful enough to answer "is it caching?"."""
        with self._lock:
            raw = self._connection.execute("SELECT count(*) FROM raw_responses").fetchone()
            obs = self._connection.execute(
                "SELECT count(*), min(observed_at), max(observed_at) FROM observations"
            ).fetchone()
        return {
            "path": str(self.path),
            "ttl_seconds": int(self.ttl.total_seconds()),
            "raw_responses": raw[0] if raw else 0,
            "observations": obs[0] if obs else 0,
            "earliest": obs[1].isoformat() if obs and obs[1] else None,
            "latest": obs[2].isoformat() if obs and obs[2] else None,
        }
