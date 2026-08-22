"""What can this token actually reach?

Every research pass into this hackathon flagged the same unknown as the highest-leverage
one: **the access tier participants are given**. The free tier was reported to cover roughly
one zone, which would have killed every multi-zone concept in the backlog.

It does not. A free-tier token on 22 August 2026 reported **350 zones**. What it does not
have is *history*: ``past`` and ``past-range`` return 401 for every signal, and ``history``
returns only the trailing 24 hours. That is the opposite of what was expected, and it moves
the constraint from "how many places?" to "how far back?".

**The API publishes the answer.** ``GET /v4/zones`` with a token adds an ``access`` array to
every zone — a list of exactly ``signal/temporality`` strings. Reading it costs one request
and is authoritative, where probing costs one request per combination and only samples.

We still verify a short list, because the ``access`` array over-promises in at least one
place: it advertises ``carbon-intensity-level/history``, which returns 400.
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
    SUPPORTED,
    Signal,
    SourceType,
    Temporality,
    supported_horizons,
)

log = structlog.get_logger(__name__)

#: Capability keys whose name differs from the URL path.
#:
#: The ``access`` list names per-source generation as ``electricity-source-wind``, while the
#: URL is ``electricity-source/wind``. Requesting the capability key as a path returns 400.
_ACCESS_ALIASES: dict[str, str] = {
    f"electricity-source-{source.value}": Signal.ELECTRICITY_SOURCE.value for source in SourceType
}

#: Combinations the ``access`` list claims but the API refuses. Verified, not assumed.
_KNOWN_OVERPROMISES: frozenset[tuple[str, str]] = frozenset(
    {
        (Signal.CARBON_INTENSITY_LEVEL.value, Temporality.HISTORY.value),
        (Signal.RENEWABLE_PERCENTAGE_LEVEL.value, Temporality.HISTORY.value),
        (Signal.CARBON_FREE_PERCENTAGE_LEVEL.value, Temporality.HISTORY.value),
    }
)


class SignalAccess(BaseModel):
    """Whether one signal is reachable, and at which temporalities."""

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
    tier_counts: dict[str, int] = {}
    zones: tuple[Zone, ...]
    signals: tuple[SignalAccess, ...]
    warnings: tuple[str, ...] = ()

    def reachable_signals(self) -> tuple[str, ...]:
        return tuple(s.signal for s in self.signals if s.reachable)

    def can(self, signal: Signal, temporality: Temporality | None = None) -> bool:
        for access in self.signals:
            if access.signal != signal.value:
                continue
            if not access.reachable:
                return False
            return temporality is None or temporality.value in access.temporalities
        return False


def parse_zones(body: dict[str, Any]) -> tuple[tuple[Zone, ...], set[str]]:
    """Parse ``GET /v4/zones`` into zones and the union of their access keys.

    Access is plan-level in practice — all 350 zones returned an identical 79-entry list —
    but it is expressed per zone, so we read it per zone and union rather than assuming.
    """
    payload = body.get("zones", body)
    if not isinstance(payload, dict):
        return (), set()

    zones: list[Zone] = []
    access: set[str] = set()

    for key, meta in sorted(payload.items()):
        meta = meta if isinstance(meta, dict) else {}
        entries = meta.get("access") or []
        access.update(str(e) for e in entries)

        # Tiers arrive as "TIER_A"; the domain calls it "A".
        raw_tier = str(meta.get("tier") or "").upper().removeprefix("TIER_")
        quality = (
            DataQuality(raw_tier)
            if raw_tier in {q.value for q in DataQuality}
            else DataQuality.UNKNOWN
        )

        zones.append(
            Zone(
                key=str(meta.get("zoneKey") or key),
                name=str(meta.get("zoneName") or key),
                country_name=meta.get("countryName"),
                quality=quality,
                has_day_ahead_price=any(e.startswith("price-day-ahead/") for e in entries),
                # A zone is reachable if the token was given any access to it at all.
                # Without a token the key is absent entirely, which is how the anonymous
                # and authenticated responses differ.
                accessible=bool(entries),
            )
        )

    return tuple(zones), access


def _signal_access(access_keys: set[str]) -> tuple[SignalAccess, ...]:
    """Turn the flat ``signal/temporality`` strings into per-signal capability."""
    by_signal: dict[str, set[str]] = {}
    for entry in access_keys:
        name, _, temporality = entry.partition("/")
        name = _ACCESS_ALIASES.get(name, name)
        if not temporality:
            continue
        by_signal.setdefault(name, set()).add(temporality)

    results: list[SignalAccess] = []
    for signal in Signal:
        granted = by_signal.get(signal.value, set())

        # Intersect what the plan grants with what the API actually offers. Both sides can
        # be wrong: the plan over-promises level/history, and our matrix could lag the API.
        offered = {t.value for t in SUPPORTED[signal]}
        usable = sorted(
            t for t in granted & offered if (signal.value, t) not in _KNOWN_OVERPROMISES
        )

        note = None
        if granted and not usable:
            note = f"plan grants {sorted(granted)} but none are usable"
        elif not granted:
            note = "not in this plan"

        results.append(
            SignalAccess(
                signal=signal.value,
                reachable=bool(usable),
                temporalities=tuple(usable),
                horizons=supported_horizons(signal) if "forecast" in usable else (),
                note=note,
            )
        )
    return tuple(results)


async def probe(client: EMapsClient, *, zone: str = "DK-DK2") -> Capabilities:
    """Read what this token can reach. One request, unless verification is needed.

    ``zone`` is used only for the sanity check that the token really works; the capability
    list itself is not zone-specific.
    """
    try:
        body = await client.zones()
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

    zones, access_keys = parse_zones(body)
    accessible = tuple(z for z in zones if z.accessible)
    signals = _signal_access(access_keys)

    warnings: list[str] = []

    if not client.has_token:
        warnings.append(
            "No token was used. /v4/zones lists every zone that exists but says nothing "
            "about what you can read. Set ELECTRICITY_MAPS_API_TOKEN and run again."
        )
    elif len(accessible) <= 1:
        warnings.append(
            f"This token reaches {len(accessible)} zone(s). Comparison, cross-border flow "
            f"stories and anything league-shaped are unavailable."
        )

    # The finding that actually constrains this project.
    historical = {t for s in signals if s.reachable for t in s.temporalities} & {
        Temporality.PAST.value,
        Temporality.PAST_RANGE.value,
    }
    if not historical:
        warnings.append(
            "No `past` or `past-range` access: this token cannot read arbitrary history. "
            "`history` returns only the trailing 24 hours. Anything needing real historical "
            "windows - forecast-error scoring, replaying a named storm, backtesting - needs "
            "a trial or event key. Record scenarios now while a window is reachable."
        )

    unreachable = [s.signal for s in signals if not s.reachable]
    if unreachable:
        warnings.append(f"Not reachable with this token: {', '.join(unreachable)}")

    tiers: dict[str, int] = {}
    for z in zones:
        tiers[z.quality.value] = tiers.get(z.quality.value, 0) + 1

    return Capabilities(
        probed_at=datetime.now(UTC),
        has_token=client.has_token,
        zone_count=len(accessible),
        tier_counts=tiers,
        zones=zones,
        signals=signals,
        warnings=tuple(warnings),
    )
