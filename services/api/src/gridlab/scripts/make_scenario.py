"""Generate the bundled replay scenarios.

These are **synthetic**. They are shaped after events that really happen — a Danish evening
wind lull, an Iberian midday solar surplus with negative prices — but no number in them was
measured. Every point they produce is labelled ``provenance: synthetic`` and the label
survives all the way to a badge in the UI.

They exist so a fresh clone runs, and looks like something, before anyone has an API key.
The moment a token exists, ``make record`` produces ``recorded`` scenarios from real data
and these should be replaced for anything that will be shown to an audience.

    python -m gridlab.scripts.make_scenario --out scenarios/
    python -m gridlab.scripts.make_scenario --from-live --zones DK-DK2,DE

The second form records real data instead; see :mod:`gridlab.scripts.record_scenario`.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

SEED = 20260911  # the date of the hackathon; deterministic output


def _hours(start: datetime, count: int) -> list[datetime]:
    return [start + timedelta(hours=h) for h in range(count)]


def _round(value: float, places: int = 1) -> float:
    return round(value, places)


def dk2_wind_lull() -> dict[str, Any]:
    """West-to-east Denmark, 48 hours across an evening wind collapse.

    The shape being imitated: wind carries the grid overnight, drops through the afternoon,
    and the evening peak is covered by imports and gas. Carbon intensity roughly triples.
    The forecast, issued the previous midnight, sees the lull coming but underestimates how
    fast it arrives — which is the realistic failure and the interesting one.
    """
    rng = random.Random(SEED)
    start = datetime(2026, 2, 4, 0, tzinfo=UTC)
    stamps = _hours(start, 48)

    dk2_ci: list[dict[str, Any]] = []
    dk2_renew: list[dict[str, Any]] = []
    dk2_cfe: list[dict[str, Any]] = []
    dk2_price: list[dict[str, Any]] = []
    dk2_load: list[dict[str, Any]] = []
    dk2_mix: list[dict[str, Any]] = []
    dk2_flows: list[dict[str, Any]] = []

    for index, at in enumerate(stamps):
        hour = at.hour
        day = index // 24

        # Wind: strong on day one, collapsing through the afternoon of day two.
        if day == 0:
            wind_factor = 0.80 + 0.10 * math.sin(index / 5.0)
        else:
            collapse = max(0.0, min(1.0, (hour - 10) / 8.0))
            wind_factor = 0.78 - 0.62 * collapse
        wind_factor = max(0.08, min(0.95, wind_factor + rng.uniform(-0.03, 0.03)))

        # Demand: the familiar double hump, morning and evening.
        load = 1500 + 420 * math.exp(-(((hour - 8) / 2.4) ** 2))
        load += 620 * math.exp(-(((hour - 18) / 2.6) ** 2))
        load += rng.uniform(-25, 25)

        wind_mw = load * wind_factor
        solar_mw = max(0.0, 180 * math.sin(math.pi * (hour - 7) / 11)) if 7 <= hour <= 18 else 0.0
        deficit = max(0.0, load - wind_mw - solar_mw)
        gas_mw = deficit * 0.45
        import_mw = deficit * 0.55

        # Imports over the German link are lignite-heavy, so they dominate the spike. This
        # is the number worth showing: the dirty evening is partly someone else's coal.
        carbon = (wind_mw * 11 + solar_mw * 45 + gas_mw * 490 + import_mw * 610) / max(load, 1.0)
        renewable = (wind_mw + solar_mw) / max(load, 1.0) * 100
        carbon_free = renewable  # no nuclear in DK2

        # Price tracks scarcity, and goes slightly negative in the windiest night hours.
        price = -8 + 190 * (1 - wind_factor) ** 2 + (18 if 17 <= hour <= 20 else 0)
        price += rng.uniform(-4, 4)

        dk2_ci.append({"at": at.isoformat(), "value": _round(carbon)})
        dk2_renew.append({"at": at.isoformat(), "value": _round(min(100.0, renewable))})
        dk2_cfe.append({"at": at.isoformat(), "value": _round(min(100.0, carbon_free))})
        dk2_price.append({"at": at.isoformat(), "value": _round(price, 2)})
        dk2_load.append({"at": at.isoformat(), "value": _round(load)})
        dk2_mix.append(
            {
                "at": at.isoformat(),
                "flow_traced": True,
                "entries": {
                    "wind": _round(wind_mw),
                    "solar": _round(solar_mw),
                    "gas": _round(gas_mw),
                    "coal": _round(import_mw * 0.55),
                    "nuclear": _round(import_mw * 0.10),
                    "hydro": _round(import_mw * 0.35),
                },
            }
        )
        dk2_flows.append(
            {
                "at": at.isoformat(),
                "edges": {
                    "DE": _round(-import_mw * 0.7),
                    "SE-SE4": _round(-import_mw * 0.3 + (wind_mw - load) * 0.05),
                },
            }
        )

    # The forecast, issued at the start of day two, sees the lull but arrives late to it.
    issued = stamps[24]
    forecast_points = []
    for at in stamps[24:]:
        actual = next(p["value"] for p in dk2_ci if p["at"] == at.isoformat())
        lag = 0.62 if at.hour >= 14 else 1.04  # optimistic exactly when it matters
        forecast_points.append({"at": at.isoformat(), "value": _round(actual * lag)})

    return {
        "id": "dk2-wind-lull",
        "title": "East Denmark - evening wind lull",
        "description": (
            "48 hours across a wind collapse. Carbon intensity roughly triples into the "
            "evening peak, and most of the increase arrives over the interconnector."
        ),
        "provenance": "synthetic",
        "currency": "EUR",
        "start": stamps[0].isoformat(),
        "end": stamps[-1].isoformat(),
        "granularity": "hourly",
        "notes": (
            "SYNTHETIC DATA - generated, not measured. Shaped after a real and common "
            "Danish pattern, but no value here was observed. Replace with `make record` "
            "output before showing this to anyone. Denmark logged 441 negative-price "
            "hours in DK1 in 2025, so the negative night hours are realistic in kind."
        ),
        "zones": {
            "DK-DK2": {
                "carbon_intensity": dk2_ci,
                "renewable_percentage": dk2_renew,
                "carbon_free_percentage": dk2_cfe,
                "price": dk2_price,
                "load": dk2_load,
                "mix": dk2_mix,
                "flows": dk2_flows,
                "forecasts": {
                    "carbon_intensity": {
                        "issued_at": issued.isoformat(),
                        "horizon_hours": 24,
                        "points": forecast_points,
                    }
                },
                # The same prices, offered as the forward view. Replay clips them at the
                # clock, so whatever is still ahead reads as day-ahead.
                #
                # `source` and `issued_at` are both null, and deliberately: no auction
                # cleared these, so there is no exchange to name and no publication time to
                # quote. Putting a plausible timestamp here would be inventing the one field
                # whose entire job is to say when a real market spoke.
                "price_forward": {"points": dk2_price},
            }
        },
    }


def es_solar_surplus() -> dict[str, Any]:
    """Iberian spring: so much midday solar that the price goes below zero.

    The point of this one is the joke that pays out. For several hours the grid is paying
    people to consume, which is the single most counter-intuitive and most delightful thing
    in this dataset - and a product built on "use less" gives the wrong advice for every one
    of those hours.
    """
    rng = random.Random(SEED + 1)
    start = datetime(2026, 5, 20, 0, tzinfo=UTC)
    stamps = _hours(start, 24)

    ci: list[dict[str, Any]] = []
    renew: list[dict[str, Any]] = []
    cfe: list[dict[str, Any]] = []
    price: list[dict[str, Any]] = []
    load: list[dict[str, Any]] = []
    mix: list[dict[str, Any]] = []
    flows: list[dict[str, Any]] = []

    for at in stamps:
        hour = at.hour
        demand = 24000 + 4200 * math.exp(-(((hour - 21) / 3.0) ** 2))
        demand += 2600 * math.exp(-(((hour - 13) / 3.4) ** 2)) + rng.uniform(-200, 200)

        solar = max(0.0, 21000 * math.sin(math.pi * (hour - 6) / 13)) if 6 <= hour <= 19 else 0.0
        wind = 5200 + 1800 * math.sin(hour / 3.5) + rng.uniform(-300, 300)
        nuclear = 6100.0
        clean = solar + wind + nuclear
        gas = max(0.0, demand - clean)
        surplus = max(0.0, clean - demand)

        carbon = (solar * 45 + wind * 11 + nuclear * 12 + gas * 490) / max(demand, 1.0)
        renewable_pct = min(100.0, (solar + wind) / max(demand, 1.0) * 100)
        carbon_free_pct = min(100.0, clean / max(demand, 1.0) * 100)

        # Below zero whenever must-run generation exceeds demand. The floor was lowered to
        # -600 EUR/MWh in 2026 because prices kept hitting the old one.
        value = 62 - 0.0000021 * solar**2 + (26 if hour >= 20 else 0)
        if surplus > 0:
            value = -min(78.0, surplus / 90.0)
        value += rng.uniform(-3, 3)

        ci.append({"at": at.isoformat(), "value": _round(carbon)})
        renew.append({"at": at.isoformat(), "value": _round(renewable_pct)})
        cfe.append({"at": at.isoformat(), "value": _round(carbon_free_pct)})
        price.append({"at": at.isoformat(), "value": _round(value, 2)})
        load.append({"at": at.isoformat(), "value": _round(demand)})
        mix.append(
            {
                "at": at.isoformat(),
                "flow_traced": True,
                "entries": {
                    "solar": _round(solar),
                    "wind": _round(wind),
                    "nuclear": nuclear,
                    "gas": _round(gas),
                },
            }
        )
        # Spain exports its surplus to France and Portugal - until the link is full.
        flows.append(
            {
                "at": at.isoformat(),
                "edges": {
                    "FR": _round(min(2800.0, surplus * 0.6)),
                    "PT": _round(min(3000.0, surplus * 0.4)),
                },
            }
        )

    issued = stamps[0]
    forecast_points = [
        {
            "at": p["at"],
            # The forecast underestimates the solar peak, so it misses the depth of the
            # negative window - which is exactly where the money and the story are.
            "value": _round(
                float(p["value"]) * (1.18 if 10 <= int(p["at"][11:13]) <= 16 else 1.02)
            ),
        }
        for p in ci
    ]

    return {
        "id": "es-solar-surplus",
        "title": "Spain - midday solar surplus, negative prices",
        "description": (
            "24 hours in Iberian spring. Solar overwhelms demand around midday and the "
            "day-ahead price goes below zero: the grid pays you to consume."
        ),
        "provenance": "synthetic",
        "currency": "EUR",
        "start": stamps[0].isoformat(),
        "end": stamps[-1].isoformat(),
        "granularity": "hourly",
        "notes": (
            "SYNTHETIC DATA - generated, not measured. The pattern is real: EU-27 markets "
            "cleared 1,223 negative-price hours in Q1 2026, more than double Q1 2025, and "
            "exchanges lowered the floor from -500 to -600 EUR/MWh because prices kept "
            "hitting it. The numbers here are not."
        ),
        "zones": {
            "ES": {
                "carbon_intensity": ci,
                "renewable_percentage": renew,
                "carbon_free_percentage": cfe,
                "price": price,
                "load": load,
                "mix": mix,
                "flows": flows,
                "forecasts": {
                    "carbon_intensity": {
                        "issued_at": issued.isoformat(),
                        "horizon_hours": 24,
                        "points": forecast_points,
                    }
                },
                # See the note in `dk2_wind_lull`: the forward view is the same series,
                # clipped at the replay clock, and none of it cleared anywhere — so there is
                # no exchange and no publication time to record.
                "price_forward": {"points": price},
            }
        },
    }


BUILDERS = {"dk2-wind-lull": dk2_wind_lull, "es-solar-surplus": es_solar_surplus}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("scenarios"))
    parser.add_argument(
        "--from-live",
        action="store_true",
        help=(
            "Record a real scenario from the live API instead of generating synthetic ones. "
            "Accepts --zones, --granularity and --id; see "
            "`python -m gridlab.scripts.record_scenario --help`."
        ),
    )
    args, extra = parser.parse_known_args()

    if args.from_live:
        # Delegated rather than inlined: generating fiction and recording fact are different
        # jobs with different failure modes, and only one of them touches the network.
        from gridlab.scripts import record_scenario

        return record_scenario.main(["--out", str(args.out), *extra])

    if extra:
        parser.error(f"unrecognized arguments: {' '.join(extra)}")

    args.out.mkdir(parents=True, exist_ok=True)
    for name, build in BUILDERS.items():
        path = args.out / f"{name}.json"
        path.write_text(json.dumps(build(), indent=2) + "\n", encoding="utf-8")
        print(f"wrote {path}")

    print("\nThese scenarios are SYNTHETIC. They are labelled as such and the label reaches")
    print("the UI. Run `make record` with a real token to replace them with measured data.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
