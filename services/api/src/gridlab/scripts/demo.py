"""Walk a scenario and narrate what the lab sees.

    make demo

The PWA is the real demonstration. This exists for the times you cannot use it: checking a
freshly recorded scenario is worth showing before you build a screen around it, confirming
over SSH that a deployment sees what you think it sees, or reading what happened in a
window without scrubbing a slider to find it.

It talks to the running API rather than reaching into the domain directly, so what it
prints is exactly what the front end would receive.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any

import httpx

from gridlab.config import get_settings

BAR = "█"


async def walk(base_url: str, *, steps: int, zone: str | None) -> int:
    async with httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=20.0) as client:

        async def get(path: str, **params: Any) -> Any:
            response = await client.get(f"/api/v1{path}", params=params)
            response.raise_for_status()
            return response.json()

        try:
            status = await get("/status")
            zones = (await get("/zones"))["zones"]
        except httpx.HTTPError as exc:
            print(f"Cannot reach the lab at {base_url}: {exc}", file=sys.stderr)
            print("Is it running? Try `make up`.", file=sys.stderr)
            return 2

        if not zones:
            print("The lab has no zones loaded.", file=sys.stderr)
            return 2

        key = zone or zones[0]["key"]
        scenario = (status.get("replay") or {}).get("scenario")

        print(f"\n  mode        {status['mode']}   provenance: {status['provenance']}")
        if scenario:
            print(f"  scenario    {scenario['title']}")
            print(f"              {scenario['start'][:16]} .. {scenario['end'][:16]}")
        print(f"  zone        {key}")

        if status["provenance"] == "synthetic":
            print("\n  ! Synthetic scenario. Every number below was generated, not measured.")

        window = (status.get("replay") or {}).get("window")
        if not window or not window.get("end"):
            print("\nLive mode: showing the current state once rather than walking a window.\n")
            await show(get, key, status["now"])
            return 0

        # Pause first. Stepping through a window while the clock is also running would
        # produce readings from moments nobody asked for.
        await client.post("/api/v1/replay/pause")

        from datetime import datetime

        start = datetime.fromisoformat(window["start"])
        end = datetime.fromisoformat(window["end"])
        stride = (end - start) / max(1, steps - 1)

        print(f"\n  walking {steps} points across the window\n")
        print(f"  {'time':<17} {'gCO2eq/kWh':>11}  {'renew':>6}  {'price':>9}  mix")
        print(f"  {'-' * 17} {'-' * 11}  {'-' * 6}  {'-' * 9}  {'-' * 28}")

        for step in range(steps):
            moment = start + stride * step
            await client.post(
                "/api/v1/replay/seek", params={"to": moment.isoformat().replace("+00:00", "Z")}
            )
            await show(get, key, moment.isoformat(), compact=True)

        await show_forward_price(get, key)

        print("\n  The clock is left paused. `make up` or the PWA will resume it.\n")
        return 0


async def show_forward_price(get: Any, zone: str) -> None:
    """What the day-ahead auction has already settled for hours still ahead.

    Worth its own line rather than a column in the walk: it is the only forward-looking
    thing in this output that is not a forecast. The prices below are a cleared market
    result waiting for its delivery hour, and saying that out loud is the difference
    between a prediction and a fact.
    """
    try:
        forward = await get(f"/grid/{zone}/price/forward")
    except httpx.HTTPError:
        print(
            "\n  forward price   none in this scenario."
            "\n                  Recordings made before forward price was captured have"
            "\n                  none; re-record with `make scenario-live`."
        )
        return

    points = forward.get("points") or []
    if not points:
        return

    values = [p["value"] for p in points if p.get("value") is not None]
    cleared = sum(1 for p in points if p.get("source"))
    unit = f"{points[0].get('currency', 'EUR')}/{points[0].get('unit', 'MWh')}"

    plural = "" if len(points) == 1 else "s"
    print(f"\n  forward price   {len(points)} period{plural} to {points[-1]['at'][:16]}")
    print(f"                  {min(values):.2f} .. {max(values):.2f} {unit}")
    if forward.get("issued_at"):
        print(f"                  cleared {forward['issued_at'][:16]} — settled, not forecast")
    if cleared:
        print(f"                  {cleared} of {len(points)} set by a published auction")
    else:
        print("                  no exchange named: modelled, or generated for this scenario")
    if any(v < 0 for v in values):
        print("                  ! goes negative — the market pays you to consume")


async def show(get: Any, zone: str, when: str, *, compact: bool = False) -> None:
    try:
        snapshot = await get(f"/grid/{zone}/now")
    except httpx.HTTPError:
        print(f"  {when[:16]}  (no data)")
        return

    carbon = snapshot.get("carbon_intensity")
    renewable = snapshot.get("renewable_percentage")
    price = snapshot.get("price")
    mix = snapshot.get("mix")

    value = carbon["value"] if carbon else None
    estimated = "~" if carbon and carbon.get("is_estimated") else " "

    # A bar in the terminal reads faster than a column of numbers, and the point of walking
    # a window is to see the shape.
    bar = BAR * min(28, int((value or 0) / 20))

    top = ""
    if mix and mix.get("entries"):
        best = max(mix["entries"], key=lambda e: e.get("percent") or 0)
        top = f"{best['source']} {best.get('percent', 0):.0f}%"

    if compact:
        print(
            f"  {when[11:16]:<17} "
            f"{estimated}{value if value is not None else '—':>10} "
            f" {renewable['value'] if renewable else '—':>5} "
            f" {price['value'] if price else '—':>8}  "
            f"{bar} {top}"
        )
        return

    print(f"  carbon      {value} gCO2eq/kWh{'  (modelled)' if estimated == '~' else ''}")
    if renewable:
        print(f"  renewable   {renewable['value']}%")
    if price:
        print(f"  price       {price['value']} {price.get('currency')}/{price.get('unit')}")
    if top:
        print(f"  largest     {top}")
    if snapshot.get("unavailable"):
        print(f"  unavailable {', '.join(snapshot['unavailable'])}")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--steps", type=int, default=16, help="How many points to sample.")
    parser.add_argument("--zone", default=None, help="Defaults to the first zone available.")
    parser.add_argument("--url", default=None, help="Defaults to GRIDLAB_API_URL.")
    args = parser.parse_args()

    url = args.url or get_settings().gridlab_api_url
    return asyncio.run(walk(url, steps=max(2, args.steps), zone=args.zone))


if __name__ == "__main__":
    raise SystemExit(main())
