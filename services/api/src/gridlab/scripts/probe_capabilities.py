"""Ask a real token what it can actually reach.

    make probe

Every research pass into this hackathon named the same unknown as the highest-leverage
one: **what access tier do participants get?** The free tier is reported to cover roughly
one zone. If that is what the token gives, every multi-zone idea in the backlog — league
tables, comparisons, flow stories between neighbours — is dead, and it is much better to
learn that from a script in August than from a 403 on stage in September.

This writes ``capabilities.json``, which ``/api/v1/capabilities`` then serves to the UI.
It is deliberately a script rather than a request handler: probing costs one API call per
signal against an undocumented rate limit, and that should be a decision, not a side effect
of someone loading a page.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from gridlab.config import get_settings
from gridlab.emaps.capabilities import probe
from gridlab.emaps.client import EMapsClient
from gridlab.emaps.signals import Signal, Temporality


async def run(zone: str, out: Path) -> int:
    settings = get_settings()

    if not settings.has_api_token:
        print(
            "No ELECTRICITY_MAPS_API_TOKEN in .env.\n"
            "\n"
            "Without a token, /v4/zones still lists every zone that exists, but it cannot\n"
            "tell you which of them YOUR plan can reach - and that is the question worth\n"
            "asking. Get a token at https://portal.electricitymaps.com/ and try again.\n"
            "\n"
            "Timing note: a 14-day trial started today expires before 11 September.\n"
            "Start it 5-8 September.",
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
        print("Reading the access list published by /v4/zones.\n")
        capabilities = await probe(client, zone=zone)

    out.write_text(capabilities.model_dump_json(indent=2) + "\n", encoding="utf-8")

    # -- report --------------------------------------------------------------

    print(f"Accessible zones: {capabilities.zone_count}  tiers={capabilities.tier_counts}")
    reachable = capabilities.reachable_signals()
    print(f"Reachable signals: {len(reachable)}/{len(capabilities.signals)}\n")

    for access in capabilities.signals:
        mark = "  ok" if access.reachable else "MISS"
        temporalities = f"  {','.join(access.temporalities)}" if access.temporalities else ""
        horizons = f"  horizons={list(access.horizons)}" if access.horizons else ""
        note = f"  ({access.note})" if access.note else ""
        print(f"  [{mark}] {access.signal:36s}{temporalities}{horizons}{note}")

    if capabilities.warnings:
        print("\nWorth knowing:")
        for warning in capabilities.warnings:
            print(f"  - {warning}")

    print(f"\nWritten to {out}")

    # Two findings change what is worth building. Say them loudly rather than leaving
    # them as one line among forty.
    if capabilities.zone_count <= 1:
        print(
            "\n"
            "  ! This token reaches at most one zone.\n"
            "  ! Comparison, cross-border flow stories and anything league-shaped are out.\n"
            "  ! Design for a single zone; treat multi-zone as an enhancement."
        )

    if not capabilities.can(Signal.CARBON_INTENSITY, Temporality.PAST_RANGE):
        print(
            "\n"
            "  ! No arbitrary history: `past` and `past-range` are not in this plan, and\n"
            "  ! `history` returns only the trailing 24 hours.\n"
            "  ! Forecast-error scoring, replaying a named event and backtesting all need\n"
            "  ! a window this key cannot fetch. Record scenarios from the live 24h now,\n"
            "  ! and plan to re-record once a trial or event key is available."
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--zone",
        default="DK-DK2",
        help="Zone to probe with. DK-DK2 is Copenhagen, and the host's home grid.",
    )
    parser.add_argument("--out", type=Path, default=Path("capabilities.json"))
    args = parser.parse_args()
    return asyncio.run(run(args.zone, args.out))


if __name__ == "__main__":
    raise SystemExit(main())
