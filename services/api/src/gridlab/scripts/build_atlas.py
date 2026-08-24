"""Compute the cheap-versus-clean picture for many zones at once.

    make atlas

Breadth is the one thing this plan gives away for free — 350 zones, all signals, `latest`
and `forecast` (ADR 0008). One zone's price/carbon divergence is an observation. The same
number computed across every grid we can reach is a different kind of object: it says where
the disagreement is severe, where it barely exists, and where clean happens to be cheap.

**Precomputed to a file, never on a page load.** Two requests per zone against an API with
no published rate limit is not something to do while somebody is waiting, and certainly not
something to do live on stage. This follows the pattern `make probe` already established:
a script writes a dated artifact into ``data/``, the api container mounts it, and a
read-only endpoint serves whatever the last run produced. See ADR 0011.

Three properties matter more than speed:

**Throttled.** A configurable pause between zones. The limit is undocumented, so the
default is deliberately unhurried and the flag exists for when somebody knows better.

**Resumable.** Each zone is written as it completes. Interrupt it, run it again, and it
skips what it already has — because the expensive part is the requests, and losing forty
zones' worth to a dropped connection at zone forty-one would mean starting the whole sweep
over.

**Honest about failure.** A zone that has no day-ahead market is recorded as *why*, not
dropped. `has_day_ahead_price` in the capability probe is derived from the plan-level
access list, which is identical for all 350 zones — so it is `true` everywhere and cannot
tell you which zones actually have a price. Only asking finds out, and the record of what
came back is itself a result worth keeping.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from gridlab.analysis.align import align
from gridlab.analysis.divergence import analyse
from gridlab.analysis.events import NEGATIVE_PRICE_MIN_DEPTH
from gridlab.config import get_settings
from gridlab.domain.models import Provenance, ScalarObservation, Series, weakest
from gridlab.emaps import errors, normalize
from gridlab.emaps.client import EMapsClient
from gridlab.emaps.signals import Signal, Temporality

#: Pause between zones, in seconds.
#:
#: Electricity Maps publishes no rate limit, so this is a guess made on the safe side. A
#: full sweep is a batch job nobody is waiting on; being slow costs nothing and being
#: throttled at zone 200 costs the whole run.
DEFAULT_DELAY = 0.5

#: The horizon both signals can actually reach.
#:
#: Carbon forecasts run to 72 hours and forward price is a rolling 24 (see
#: ``docs/electricity-maps-api.md``), so anything joining them is a one-day object. Asking
#: for more would align against nothing and quietly halve the reported coverage.
HORIZON_HOURS = 24

#: European bidding zones, which is where day-ahead price actually exists.
#:
#: A default rather than a limit — `--zones` takes anything and `--all` sweeps every zone
#: the token can reach. Kept here because the capability probe cannot answer "which zones
#: have a price", and a first run that returns 300 refusals teaches nothing.
EUROPEAN_ZONES: tuple[str, ...] = (
    "AT",
    "BE",
    "BG",
    "CH",
    "CZ",
    "DE",
    "DK-DK1",
    "DK-DK2",
    "EE",
    "ES",
    "FI",
    "FR",
    "GB",
    "GR",
    "HR",
    "HU",
    "IE",
    "IT-CNO",
    "IT-CSO",
    "IT-NO",
    "IT-SAR",
    "IT-SIC",
    "IT-SO",
    "LT",
    "LV",
    "NL",
    "NO-NO1",
    "NO-NO2",
    "NO-NO3",
    "NO-NO4",
    "NO-NO5",
    "PL",
    "PT",
    "RO",
    "RS",
    "SE-SE1",
    "SE-SE2",
    "SE-SE3",
    "SE-SE4",
    "SI",
    "SK",
)


async def carbon_forecast(client: EMapsClient, zone: str) -> Series[ScalarObservation] | None:
    body = await client.fetch(
        Signal.CARBON_INTENSITY, Temporality.FORECAST, zone=zone, horizon_hours=HORIZON_HOURS
    )
    series = normalize.series(
        [body], zone=zone, normalizer=normalize.carbon_intensity, horizon_hours=HORIZON_HOURS
    )
    return series if series.points else None


async def forward_price(client: EMapsClient, zone: str) -> Series[ScalarObservation] | None:
    """Day-ahead prices still ahead, from ``combined``.

    Split at wall time rather than a replay clock: this script talks to the live API, so
    "now" is now. See ADR 0012 for why this is `combined` and not `forecast`.
    """
    body = await client.fetch(Signal.PRICE_DAY_AHEAD, Temporality.COMBINED, zone=zone)
    full = normalize.series([body], zone=zone, normalizer=normalize.price)
    now = datetime.now(UTC)
    forward = tuple(p for p in full.points if p.at >= now)
    if not forward:
        return None
    return Series[ScalarObservation](zone=zone, points=forward, granularity=full.granularity)


async def one_zone(client: EMapsClient, zone: str) -> dict[str, Any]:
    """Everything the atlas records for a single zone, or why it could not."""
    try:
        carbon = await carbon_forecast(client, zone)
    except errors.ElectricityMapsError as exc:
        return {"zone": zone, "status": "no_carbon", "reason": type(exc).__name__}
    if carbon is None:
        return {"zone": zone, "status": "no_carbon", "reason": "empty forecast"}

    try:
        price = await forward_price(client, zone)
    except errors.ElectricityMapsError as exc:
        return {"zone": zone, "status": "no_price", "reason": type(exc).__name__}
    if price is None:
        return {"zone": zone, "status": "no_price", "reason": "no forward prices"}

    aligned = align(
        carbon,
        price,
        a_signal="carbon_intensity",
        b_signal="price",
        a_kind="forecast",
        b_kind="price_forward",
    )
    if aligned is None:
        return {"zone": zone, "status": "no_overlap", "reason": "carbon and price share no period"}

    divergence = analyse(aligned)
    values = [p.b for p in aligned.complete_pairs if p.b is not None]
    carbon_values = [p.a for p in aligned.complete_pairs if p.a is not None]

    # What each choice actually buys, in the units of the other objective.
    #
    # The correlation alone is not enough, and NO-NO3 on 24 August is why: r = -0.85 says
    # "strongly opposed" over a carbon range of 36 to 39 gCO2eq/kWh. Rank correlation is
    # scale-free, which is what makes it robust to a price spike and what makes it
    # misleading when a signal barely moves. Paying 95 EUR/MWh to avoid 2.7 gCO2eq/kWh is
    # not a disagreement worth acting on, and a number that cannot show the difference
    # would put that zone at the top of the list.
    #
    # Both deltas are reported and neither is divided by the other: the ratio is a shadow
    # carbon price, which is a product thesis rather than a description (ADR 0007).
    carbon_avoided = None
    price_premium = None
    if (
        divergence.best_a
        and divergence.best_b
        and divergence.best_a.other_mean is not None
        and divergence.best_b.other_mean is not None
    ):
        carbon_avoided = round(divergence.best_b.other_mean - divergence.best_a.mean, 2)
        price_premium = round(divergence.best_a.other_mean - divergence.best_b.mean, 2)

    return {
        "zone": zone,
        "status": "ok",
        "periods": divergence.periods,
        # The headline scalar: how much the two signals order the day the same way.
        "correlation": divergence.correlation,
        "agreement": divergence.agreement,
        # How far apart the decision puts you. Zero means the question never arises here.
        "separation_hours": divergence.separation_hours,
        "cheapest_window": divergence.best_b.model_dump(mode="json") if divergence.best_b else None,
        "cleanest_window": divergence.best_a.model_dump(mode="json") if divergence.best_a else None,
        "disagreeing_periods": len(divergence.disagreeing_periods),
        "negative_price_periods": sum(1 for v in values if v <= -NEGATIVE_PRICE_MIN_DEPTH),
        "price_min": round(min(values), 2) if values else None,
        "price_max": round(max(values), 2) if values else None,
        "price_unit": aligned.b_unit,
        "carbon_min": round(min(carbon_values), 1),
        "carbon_max": round(max(carbon_values), 1),
        # The dynamic range of each signal. Without this the correlation cannot be read.
        "carbon_spread": round(max(carbon_values) - min(carbon_values), 1),
        "price_spread": round(max(values) - min(values), 2) if values else None,
        # What choosing the clean window instead of the cheap one buys, and what it costs.
        "carbon_avoided": carbon_avoided,
        "price_premium": price_premium,
        "provenance": divergence.derived.provenance.value,
        "estimated_fraction": max(ref.estimated_fraction for ref in divergence.derived.inputs),
    }


async def build(
    client: EMapsClient,
    zones: list[str],
    *,
    delay: float,
    existing: dict[str, dict[str, Any]],
    on_zone: Any = None,
) -> dict[str, dict[str, Any]]:
    results = dict(existing)
    for index, zone in enumerate(zones):
        if zone in results:
            continue
        results[zone] = await one_zone(client, zone)
        if on_zone:
            on_zone(index + 1, len(zones), results[zone])
        if delay and index + 1 < len(zones):
            await asyncio.sleep(delay)
    return results


def summarise(results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """The atlas as a whole, which is the part that is actually novel.

    Individually these are ordinary numbers. Together they answer a question nobody has
    published: across the grids we can see, how often do cheap and clean mean the same
    hours?
    """
    ok = [r for r in results.values() if r["status"] == "ok"]
    scored = [r for r in ok if r.get("correlation") is not None]
    correlations = sorted(r["correlation"] for r in scored)

    counts: dict[str, int] = {}
    for r in results.values():
        counts[r["status"]] = counts.get(r["status"], 0) + 1

    return {
        "zones_attempted": len(results),
        "by_status": counts,
        "zones_scored": len(scored),
        "median_correlation": (
            round(correlations[len(correlations) // 2], 4) if correlations else None
        ),
        # Named for what it counts, not for what it might mean. A low correlation says the
        # two signals order the day differently; whether that matters depends on how far
        # the carbon actually moves, which `carbon_avoided` reports per zone.
        "zones_with_low_correlation": sum(1 for r in scored if r["correlation"] < 0.3),
        "median_carbon_spread": (
            round(sorted(r["carbon_spread"] for r in ok)[len(ok) // 2], 1) if ok else None
        ),
        "zones_with_negative_prices": sum(
            1 for r in ok if (r.get("negative_price_periods") or 0) > 0
        ),
        "widest_separation": max(
            (r for r in ok if r.get("separation_hours") is not None),
            key=lambda r: r["separation_hours"],
            default={},
        ).get("zone"),
        "provenance": weakest(Provenance(r["provenance"]) for r in ok if r.get("provenance")).value,
        "caveats": [
            "Rank correlation between forward price and forward carbon over roughly the "
            "next 24 hours. Not a causal claim: price is set by the marginal unit and "
            "carbon intensity is a flow-traced average over consumption.",
            "One day, in one direction. A zone that agrees today may not tomorrow, and "
            "nothing here is a seasonal statement.",
            "A correlation cannot be read without the spread beside it. NO-NO3 scored "
            "-0.85 on 24 August 2026 over a carbon range of 36-39 gCO2eq/kWh: strongly "
            "opposed, and worth nothing to act on. Sort by `carbon_avoided` to see where "
            "the choice has consequences.",
            "Zones without a day-ahead market are recorded as such rather than dropped. "
            "The capability probe cannot identify them in advance - its "
            "`has_day_ahead_price` comes from the plan-level access list, which is "
            "identical for all 350 zones.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("/out"), help="Directory to write into.")
    parser.add_argument("--zones", default=None, help="Comma-separated. Defaults to Europe.")
    parser.add_argument("--all", action="store_true", help="Every zone the token can reach.")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY)
    parser.add_argument(
        "--resume",
        type=Path,
        default=None,
        help="A previous artifact to continue. Zones already recorded are not re-fetched.",
    )
    args = parser.parse_args()

    settings = get_settings()
    if not settings.has_api_token:
        print(
            "No ELECTRICITY_MAPS_API_TOKEN. The atlas is a live sweep and has no replay "
            "equivalent — one zone's numbers can be replayed, a picture of every grid "
            "cannot.",
            file=sys.stderr,
        )
        return 1

    return asyncio.run(_run(settings, args))


async def _run(settings: Any, args: argparse.Namespace) -> int:
    token = settings.electricity_maps_api_token
    async with EMapsClient(
        token=token.get_secret_value(),
        base_url=settings.electricity_maps_base_url,
        timeout=settings.gridlab_http_timeout,
        retries=settings.gridlab_http_retries,
    ) as client:
        if args.all:
            zones = sorted(await client.zones())
        elif args.zones:
            zones = [z.strip() for z in args.zones.split(",") if z.strip()]
        else:
            zones = list(EUROPEAN_ZONES)

        existing: dict[str, dict[str, Any]] = {}
        if args.resume and args.resume.is_file():
            previous = json.loads(args.resume.read_text(encoding="utf-8"))
            existing = {z["zone"]: z for z in previous.get("zones", [])}
            print(f"Resuming: {len(existing)} zones already recorded.")

        print(f"Sweeping {len(zones)} zones at {args.delay}s between each.\n")

        def report(done: int, total: int, result: dict[str, Any]) -> None:
            if result["status"] == "ok":
                detail = (
                    f"r={result['correlation']} ({result['agreement']}), "
                    f"{result['separation_hours']}h apart"
                )
            else:
                detail = f"{result['status']}: {result['reason']}"
            print(f"  [{done:>3}/{total}] {result['zone']:<10} {detail}")

        results = await build(client, zones, delay=args.delay, existing=existing, on_zone=report)

    ordered = [results[z] for z in zones if z in results]
    artifact: dict[str, Any] = {
        "computed_at": datetime.now(UTC).isoformat(),
        "horizon_hours": HORIZON_HOURS,
        "summary": summarise(results),
        "zones": ordered,
    }

    args.out.mkdir(parents=True, exist_ok=True)
    dated = args.out / f"atlas-{datetime.now(UTC):%Y-%m-%d}.json"
    dated.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    # A stable name too, so the endpoint has something to read without globbing for a date.
    (args.out / "atlas.json").write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")

    summary = artifact["summary"]
    print(f"\n  attempted   {summary['zones_attempted']}")
    print(f"  by status   {summary['by_status']}")
    print(f"  scored      {summary['zones_scored']}")
    print(f"  median r    {summary['median_correlation']}")
    print(f"  low r       {summary['zones_with_low_correlation']} zones under 0.3")
    print(f"  median span {summary['median_carbon_spread']} gCO2eq/kWh of carbon range")
    print(f"  negative    {summary['zones_with_negative_prices']} zones go below zero")
    print(f"\nWrote {dated} and {args.out / 'atlas.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
