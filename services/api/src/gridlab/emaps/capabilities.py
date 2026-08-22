"""What can this token actually reach?

Every research pass into this hackathon flagged the same unknown as the highest-leverage
one: **the access tier participants are given**. The free tier is reported to cover roughly
one zone. If that is what we get, every multi-zone concept in the idea backlog is dead on
arrival, and it is much better to learn that from a script in August than from a 403 on
stage in September.

``GET /v4/zones`` answers half of it in one unauthenticated-or-authenticated call: without
a token it lists all zones, with a token it reports the zones your plan can reach. The rest
— which signals, which forecast horizons — needs one probing request per combination, which
is what :func:`probe` does.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from pydantic import BaseModel, ConfigDict

from gridlab.domain.models import DataQuality, Zone
from gridlab.emaps import errors
from gridlab.emaps.client import EMapsClient
from gridlab.emaps.signals import (
    BETA,
    FORECAST_HORIZONS,
    SUPPORTED,
    Signal,
    SourceType,
    Temporality,
)

log = structlog.get_logger(__name__)


class SignalAccess(BaseModel):
    """Whether one signal is reachable, and how we know."""

    model_config = ConfigDict(frozen=True)

    signal: str
    reachable: bool
    temporalities: tuple[str, ...] = ()
    horizons: tuple[int, ...] = ()
    note: str | None = None


class Capabilities(BaseModel):
    """The answer to "what can we build with this key?"."""

    model_config = ConfigDict(frozen=True)

    probed_at: datetime
    has_token: bool
    zone_count: int
    zones: tuple[Zone, ...]
    signals: tuple[SignalAccess, ...]
    warnings: tuple[str, ...] = ()

    def reachable_signals(self) -> tuple[str, ...]:
        return tuple(s.signal for s in self.signals if s.reachable)

    def can(self, signal: Signal) -> bool:
        return any(s.signal == signal.value and s.reachable for s in self.signals)


def parse_zones(body: dict[str, Any]) -> tuple[Zone, ...]:
    """Parse ``GET /v4/zones``.

    The documented shape is a mapping of zone key to metadata. We keep only what we need
    and tolerate extra or missing fields, because this response is the one thing we must
    be able to read before we know anything else.
    """
    payload = body.get("zones", body)
    if not isinstance(payload, dict):
        return ()

    zones: list[Zone] = []
    for key, meta in sorted(payload.items()):
        meta = meta if isinstance(meta, dict) else {}
        raw_quality = str(meta.get("dataQuality") or meta.get("tier") or "").upper()
        quality = (
            DataQuality(raw_quality)
            if raw_quality in {q.value for q in DataQuality}
            else DataQuality.UNKNOWN
        )
        zones.append(
            Zone(
                key=key,
                name=str(meta.get("zoneName") or meta.get("name") or key),
                country_name=meta.get("countryName") or meta.get("country"),
                quality=quality,
                has_day_ahead_price=bool(meta.get("hasDayAheadPrice", False)),
                accessible=bool(meta.get("access", True)),
            )
        )
    return tuple(zones)


async def probe(
    client: EMapsClient,
    *,
    zone: str,
    include_beta: bool = True,
) -> Capabilities:
    """Ask the API what this token can do, one careful request at a time.

    Probing is intentionally shallow — one ``latest`` call per signal, plus one forecast
    call to find the horizon ceiling. Walking the full matrix would be dozens of requests
    against an undocumented rate limit for information nothing needs.
    """
    warnings: list[str] = []

    try:
        zones = parse_zones(await client.zones())
    except errors.ElectricityMapsError as exc:
        log.error("capabilities.zones_failed", error=str(exc))
        return Capabilities(
            probed_at=datetime.now(UTC),
            has_token=client.has_token,
            zone_count=0,
            zones=(),
            signals=(),
            warnings=(f"/v4/zones failed: {exc}",),
        )

    accessible = tuple(z for z in zones if z.accessible)
    if len(accessible) <= 1:
        warnings.append(
            f"This token reports {len(accessible)} accessible zone(s). Every multi-zone "
            f"feature (comparison, flows, leagues) will be unavailable. This is the "
            f"documented free-tier behaviour; a trial or event key should lift it."
        )

    results: list[SignalAccess] = []
    for signal in Signal:
        if signal in BETA and not include_beta:
            continue
        results.append(await _probe_signal(client, signal, zone=zone))

    unreachable = [s.signal for s in results if not s.reachable]
    if unreachable:
        warnings.append(f"Not reachable with this token: {', '.join(unreachable)}")

    return Capabilities(
        probed_at=datetime.now(UTC),
        has_token=client.has_token,
        zone_count=len(accessible),
        zones=zones,
        signals=tuple(results),
        warnings=tuple(warnings),
    )


async def _probe_signal(client: EMapsClient, signal: Signal, *, zone: str) -> SignalAccess:
    """One ``latest`` call, plus a horizon sweep if the signal forecasts."""
    temporalities = SUPPORTED[signal]
    probe_temporality = (
        Temporality.LATEST if Temporality.LATEST in temporalities else next(iter(temporalities))
    )
    source_type = SourceType.WIND if signal is Signal.ELECTRICITY_SOURCE else None

    try:
        await client.fetch(signal, probe_temporality, zone=zone, source_type=source_type)
    except errors.AccessDeniedError:
        return SignalAccess(signal=signal.value, reachable=False, note="403 - not in plan")
    except errors.NotFoundError:
        return SignalAccess(
            signal=signal.value,
            reachable=False,
            note=f"404 - no data for {zone}; may exist for other zones",
        )
    except errors.ElectricityMapsError as exc:
        return SignalAccess(
            signal=signal.value, reachable=False, note=f"{type(exc).__name__}: {exc}"
        )

    horizons: list[int] = []
    if Temporality.FORECAST in temporalities:
        for hours in FORECAST_HORIZONS:
            try:
                await client.fetch(
                    signal,
                    Temporality.FORECAST,
                    zone=zone,
                    horizon_hours=hours,
                    source_type=source_type,
                )
            except errors.ElectricityMapsError:
                # Horizons are plan-dependent, so the first refusal is the ceiling.
                break
            horizons.append(hours)

    return SignalAccess(
        signal=signal.value,
        reachable=True,
        temporalities=tuple(sorted(t.value for t in temporalities)),
        horizons=tuple(horizons),
    )
