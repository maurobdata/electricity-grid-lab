"""Record raw Electricity Maps responses to disk.

    make record

The exact v4 response schemas are not public — the reference sits behind an authenticated
single-page app — so ``emaps/normalize.py`` currently accepts several candidate spellings
per field and fails loudly when none match. That is a deliberate hedge, not a design.

This script closes it. It saves verbatim responses into ``fixtures/``, which then become
the normalizer's test inputs, so the parsing is shaped by what the API actually sends
rather than by what we guessed. Run it on the first day a token exists.

Tokens are never written: the request URL is stored with parameters, and the ``auth-token``
header is not part of what gets saved.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from gridlab.config import get_settings
from gridlab.emaps import errors
from gridlab.emaps.client import EMapsClient
from gridlab.emaps.signals import (
    FORECAST_NEEDS_WINDOW,
    SUPPORTED,
    BreakdownType,
    Signal,
    SourceType,
    Temporality,
    supported_horizons,
)

#: What to record. Chosen for coverage of the response *shapes* rather than of the whole
#: API: one scalar signal, one percentage, one structured breakdown, one exchange map, one
#: price (which has its own extra temporalities), one series and one forecast.
PLAN: list[tuple[Signal, Temporality, BreakdownType | None]] = [
    (Signal.CARBON_INTENSITY, Temporality.LATEST, None),
    (Signal.CARBON_INTENSITY, Temporality.HISTORY, None),
    (Signal.CARBON_INTENSITY, Temporality.FORECAST, None),
    (Signal.RENEWABLE_ENERGY, Temporality.LATEST, None),
    (Signal.CARBON_FREE_ENERGY, Temporality.LATEST, None),
    # Both breakdowns: the recorder asks for each, so the fixtures must cover each.
    # Without this the two are indistinguishable in tests and the flow-tracing toggle
    # looks broken when it is not.
    (Signal.ELECTRICITY_MIX, Temporality.LATEST, BreakdownType.NORMAL),
    (Signal.ELECTRICITY_MIX, Temporality.LATEST, BreakdownType.FLOW_TRACED),
    (Signal.ELECTRICITY_MIX, Temporality.HISTORY, BreakdownType.NORMAL),
    (Signal.ELECTRICITY_MIX, Temporality.HISTORY, BreakdownType.FLOW_TRACED),
    (Signal.ELECTRICITY_MIX, Temporality.FORECAST, None),
    (Signal.ELECTRICITY_FLOWS, Temporality.LATEST, None),
    (Signal.ELECTRICITY_FLOWS, Temporality.HISTORY, None),
    (Signal.ELECTRICITY_SOURCE, Temporality.LATEST, None),
    (Signal.POWER_BREAKDOWN, Temporality.LATEST, None),
    (Signal.PRICE_DAY_AHEAD, Temporality.LATEST, None),
    (Signal.PRICE_DAY_AHEAD, Temporality.COMBINED, None),
    (Signal.PRICE_DAY_AHEAD, Temporality.HISTORY, None),
    (Signal.TOTAL_LOAD, Temporality.LATEST, None),
    (Signal.NET_LOAD, Temporality.LATEST, None),
    (Signal.NET_LOAD, Temporality.FORECAST, None),
    (Signal.CARBON_INTENSITY_LEVEL, Temporality.LATEST, None),
    (Signal.RENEWABLE_PERCENTAGE_LEVEL, Temporality.LATEST, None),
]


async def run(zone: str, out: Path) -> int:
    settings = get_settings()
    if not settings.has_api_token:
        print(
            "No ELECTRICITY_MAPS_API_TOKEN in .env. Nothing to record.",
            file=sys.stderr,
        )
        return 2

    out.mkdir(parents=True, exist_ok=True)
    token = settings.electricity_maps_api_token

    recorded = 0
    skipped: list[str] = []

    async with EMapsClient(
        token=token.get_secret_value() if token else None,
        base_url=settings.electricity_maps_base_url,
        timeout=settings.gridlab_http_timeout,
        retries=settings.gridlab_http_retries,
    ) as client:
        # /v4/zones first: it is the one endpoint everything else depends on reading.
        try:
            _save(out, "zones", await client.zones(), zone=None)
            recorded += 1
            print("  recorded zones")
        except errors.ElectricityMapsError as exc:
            skipped.append(f"zones ({type(exc).__name__})")

        for signal, temporality, breakdown in PLAN:
            if temporality not in SUPPORTED[signal]:
                continue

            kwargs: dict[str, Any] = {"zone": zone}
            if signal is Signal.ELECTRICITY_SOURCE:
                kwargs["source_type"] = SourceType.WIND
            if signal is Signal.ELECTRICITY_MIX and breakdown is not None:
                kwargs["breakdown_type"] = breakdown
            if temporality is Temporality.PAST_RANGE:
                end = datetime.now(UTC)
                kwargs |= {"start": end - timedelta(days=2), "end": end}
            if temporality is Temporality.FORECAST:
                # 24 is the only horizon every forecasting signal accepts. The intensity
                # and percentage signals also take 6/48/72; mix, flows and load do not.
                if signal in FORECAST_NEEDS_WINDOW:
                    now = datetime.now(UTC)
                    kwargs |= {"start": now, "end": now + timedelta(hours=24)}
                elif supported_horizons(signal):
                    kwargs["horizon_hours"] = 24

            name = f"{signal.value}__{temporality.value}"
            if breakdown is not None:
                name += f"__{breakdown.value}"
            try:
                body = await client.fetch(signal, temporality, **kwargs)
            except errors.ElectricityMapsError as exc:
                skipped.append(f"{name} ({type(exc).__name__})")
                print(f"  skipped  {name}: {type(exc).__name__}")
                continue

            _save(out, name, body, zone=zone)
            recorded += 1
            print(f"  recorded {name}")

    print(f"\n{recorded} recorded, {len(skipped)} unavailable.")
    if skipped:
        print("Unavailable with this token:")
        for item in skipped:
            print(f"  - {item}")

    print(
        "\nNext: open the fixtures and compare the field names against the candidate lists\n"
        "in gridlab/emaps/normalize.py. Narrow them to what the API actually sends, and\n"
        "update docs/electricity-maps-api.md so the guesses become facts."
    )
    return 0


def _save(out: Path, name: str, body: dict[str, Any], *, zone: str | None) -> None:
    """Write one fixture, with enough context to know what it is a year from now."""
    payload = {
        "_recorded_at": datetime.now(UTC).isoformat(),
        "_zone": zone,
        "_note": (
            "Verbatim Electricity Maps v4 response. No token or header is stored here. "
            "This is the ground truth for gridlab.emaps.normalize."
        ),
        "body": body,
    }
    (out / f"{name}.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zone", default="DK-DK2")
    parser.add_argument("--out", type=Path, default=Path("fixtures"))
    args = parser.parse_args()
    return asyncio.run(run(args.zone, args.out))


if __name__ == "__main__":
    raise SystemExit(main())
