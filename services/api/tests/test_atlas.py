"""The cross-zone atlas: its summary arithmetic, and the endpoint that serves it.

The sweep itself needs a live token and is not tested here — what is tested is everything
that decides what the sweep *means*, which is where a misleading number would come from.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from gridlab.config import Mode, Settings
from gridlab.scripts.build_atlas import EUROPEAN_ZONES, summarise
from gridlab.web.app import app
from gridlab.web.state import LabState


def scored(zone: str, **over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "zone": zone,
        "status": "ok",
        "periods": 24,
        "correlation": 0.5,
        "agreement": "moderate",
        "separation_hours": 2.0,
        "disagreeing_periods": 1,
        "negative_price_periods": 0,
        "carbon_spread": 100.0,
        "carbon_avoided": 30.0,
        "price_premium": 20.0,
        "provenance": "live",
        "estimated_fraction": 0.0,
    }
    return {**base, **over}


# --- the summary ------------------------------------------------------------


def test_the_summary_counts_every_outcome_not_just_the_successes() -> None:
    """A zone with no day-ahead market is a fact about coverage. Dropping it would make the
    atlas look more complete than it is."""
    results = {
        "DE": scored("DE"),
        "IS": {"zone": "IS", "status": "no_price", "reason": "no forward prices"},
        "XX": {"zone": "XX", "status": "no_carbon", "reason": "NotFoundError"},
    }
    summary = summarise(results)

    assert summary["zones_attempted"] == 3
    assert summary["by_status"] == {"ok": 1, "no_price": 1, "no_carbon": 1}
    assert summary["zones_scored"] == 1


def test_the_low_correlation_count_is_named_for_what_it_counts() -> None:
    """Not "zones where they disagree".

    NO-NO3 scored -0.85 on 24 August 2026 over a carbon range of three points: strongly
    opposed by the coefficient, and worth 2.7 gCO2eq/kWh to act on. The count is real; the
    interpretation it invites is not, so the field says what it measures.
    """
    results = {
        "A": scored("A", correlation=-0.85, carbon_spread=3.0, carbon_avoided=2.67),
        "B": scored("B", correlation=0.9),
    }
    summary = summarise(results)

    assert summary["zones_with_low_correlation"] == 1
    assert "zones_where_they_disagree" not in summary


def test_the_summary_reports_the_carbon_spread_beside_the_correlation() -> None:
    """A correlation cannot be read without it — that is the whole lesson of the first
    sweep, and the number has to travel with the coefficient rather than be looked up."""
    summary = summarise(
        {"A": scored("A", carbon_spread=3.0), "B": scored("B", carbon_spread=200.0)}
    )
    assert summary["median_carbon_spread"] is not None


def test_the_summary_takes_the_weakest_provenance() -> None:
    summary = summarise(
        {"A": scored("A", provenance="live"), "B": scored("B", provenance="recorded")}
    )
    assert summary["provenance"] == "recorded"


def test_the_summary_survives_a_sweep_that_scored_nothing() -> None:
    """Every zone refusing is a possible outcome — a token without price access produces
    exactly that — and it must read as an empty result rather than crash the run."""
    summary = summarise({"IS": {"zone": "IS", "status": "no_price", "reason": "none"}})

    assert summary["zones_scored"] == 0
    assert summary["median_correlation"] is None
    assert summary["median_carbon_spread"] is None


def test_the_summary_always_carries_the_marginal_caveat() -> None:
    caveats = " ".join(summarise({"A": scored("A")})["caveats"])
    assert "marginal unit" in caveats
    assert "flow-traced average" in caveats


def test_the_summary_warns_that_a_correlation_needs_its_spread() -> None:
    caveats = " ".join(summarise({"A": scored("A")})["caveats"])
    assert "NO-NO3" in caveats
    assert "carbon_avoided" in caveats


def test_the_default_zone_list_is_where_day_ahead_price_exists() -> None:
    """The capability probe cannot answer this: `has_day_ahead_price` is derived from the
    plan-level access list, which is identical for all 350 zones and therefore true
    everywhere. A first run of 300 refusals teaches nothing."""
    assert "DK-DK2" in EUROPEAN_ZONES
    assert "DE" in EUROPEAN_ZONES
    assert len(EUROPEAN_ZONES) == len(set(EUROPEAN_ZONES))


# --- the endpoint -----------------------------------------------------------


@pytest.fixture
def client(scenarios_dir: Path, tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(
        gridlab_mode=Mode.REPLAY,
        gridlab_scenario="test-scenario",
        gridlab_scenarios_dir=scenarios_dir,
        gridlab_db_path=tmp_path / "atlas.duckdb",
        electricity_maps_api_token=None,
        anthropic_api_key=None,
        gridlab_capabilities_path=tmp_path / "no-probe.json",
        gridlab_atlas_path=tmp_path / "atlas.json",
    )
    state = LabState.build(settings)
    app.state.lab = state
    with TestClient(app) as test_client:
        app.state.lab = state
        yield test_client


def write_atlas(path: Path, zones: list[dict[str, Any]]) -> None:
    path.write_text(
        json.dumps(
            {
                "computed_at": "2026-08-24T08:00:00Z",
                "horizon_hours": 24,
                "summary": summarise({z["zone"]: z for z in zones}),
                "zones": zones,
            }
        ),
        encoding="utf-8",
    )


def test_atlas_404s_before_any_sweep_and_says_how_to_run_one(client: TestClient) -> None:
    response = client.get("/api/v1/atlas")
    assert response.status_code == 404
    assert "make atlas" in response.json()["detail"]
    assert "no replay equivalent" in response.json()["detail"]


def test_atlas_sorts_by_avoidable_carbon_by_default(client: TestClient) -> None:
    """The correction the first sweep forced.

    Ranking on the coefficient puts a zone whose carbon moves three points at the top;
    ranking on what the choice avoids puts the one where it moves a hundred and twenty.
    """
    write_atlas(
        client.app.state.lab.settings.gridlab_atlas_path,  # type: ignore[attr-defined]
        [
            scored("NO-NO3", correlation=-0.85, carbon_spread=3.0, carbon_avoided=2.67),
            scored("HR", correlation=-0.28, carbon_spread=184.0, carbon_avoided=120.0),
        ],
    )
    body = client.get("/api/v1/atlas").json()

    assert body["sorted_by"] == "carbon_avoided"
    assert [z["zone"] for z in body["zones"]] == ["HR", "NO-NO3"]


def test_atlas_can_still_be_sorted_by_correlation(client: TestClient) -> None:
    write_atlas(
        client.app.state.lab.settings.gridlab_atlas_path,  # type: ignore[attr-defined]
        [
            scored("HR", correlation=-0.28, carbon_avoided=120.0),
            scored("NO-NO3", correlation=-0.85, carbon_avoided=2.67),
        ],
    )
    body = client.get("/api/v1/atlas", params={"sort": "correlation"}).json()
    assert [z["zone"] for z in body["zones"]] == ["NO-NO3", "HR"]


def test_unscored_zones_are_kept_at_the_end_and_counted(client: TestClient) -> None:
    write_atlas(
        client.app.state.lab.settings.gridlab_atlas_path,  # type: ignore[attr-defined]
        [
            {"zone": "IS", "status": "no_price", "reason": "no forward prices"},
            scored("DE"),
        ],
    )
    body = client.get("/api/v1/atlas").json()

    assert body["unscored"] == 1
    assert body["zones"][-1]["zone"] == "IS"
    assert body["zones"][-1]["status"] == "no_price"


def test_an_unknown_sort_is_refused_with_the_valid_list(client: TestClient) -> None:
    write_atlas(
        client.app.state.lab.settings.gridlab_atlas_path,  # type: ignore[attr-defined]
        [scored("DE")],
    )
    response = client.get("/api/v1/atlas", params={"sort": "vibes"})
    assert response.status_code == 400
    assert "carbon_avoided" in response.json()["detail"]["available"]
