"""The HTTP contract.

Both the PWA and the agent depend on these shapes, so they are pinned here rather than
discovered by a broken chart. Everything runs against a hand-built scenario in replay
mode — no network, no key.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from gridlab.config import Mode, Settings
from gridlab.web.app import app
from gridlab.web.state import LabState


@pytest.fixture
def client(scenarios_dir: Path, tmp_path: Path) -> Iterator[TestClient]:
    # Every environment-dependent setting is pinned explicitly. pydantic-settings reads
    # `.env` and the process environment for anything not passed here, so a developer with
    # a real token — or a `data/capabilities.json` from `make probe` — would otherwise find
    # these tests asserting against their machine rather than against the code.
    settings = Settings(
        gridlab_mode=Mode.REPLAY,
        gridlab_scenario="test-scenario",
        gridlab_scenarios_dir=scenarios_dir,
        gridlab_db_path=tmp_path / "test.duckdb",
        gridlab_replay_speed=1.0,
        electricity_maps_api_token=None,
        anthropic_api_key=None,
        gridlab_capabilities_path=tmp_path / "no-probe-here.json",
    )
    state = LabState.build(settings)
    app.state.lab = state

    # Pin the clock so assertions are about behaviour, not about how long the test took.
    from datetime import UTC, datetime

    from gridlab.clock import FrozenClock

    state.source.clock = FrozenClock(datetime(2026, 2, 4, 3, tzinfo=UTC))

    with TestClient(app) as test_client:
        # TestClient's lifespan rebuilds state from the environment; put ours back.
        app.state.lab = state
        yield test_client


# --- meta -------------------------------------------------------------------


def test_healthz(client: TestClient) -> None:
    body = client.get("/api/v1/healthz").json()
    assert body["status"] == "ok"
    assert body["mode"] == "replay"


def test_status_says_which_mode_and_which_provenance(client: TestClient) -> None:
    """A demo audience should never have to wonder whether this is live or a recording."""
    body = client.get("/api/v1/status").json()
    assert body["mode"] == "replay"
    assert body["provenance"] == "synthetic"
    assert body["replay"]["scenario"]["id"] == "test-scenario"
    assert body["has_electricity_maps_token"] is False


def test_capabilities_is_honest_about_not_having_probed(client: TestClient) -> None:
    body = client.get("/api/v1/capabilities").json()
    assert body["source"] == "unprobed"
    assert "make probe" in body["message"]


def test_unprobed_capabilities_guesses_at_nothing(client: TestClient) -> None:
    """It used to assert the free tier covers "roughly one zone", repeating a claim from
    the pre-project research. A live probe measured 350. An endpoint whose entire job is to
    say what is verified must not ship an unverified number as a fallback."""
    body = client.get("/api/v1/capabilities").json()
    blob = json.dumps(body).lower()

    assert "one zone" not in blob
    assert "free tier" not in blob
    assert "zone_count" not in body, "an unprobed response must not imply a count"


def test_capabilities_serves_the_probe_when_one_exists(client: TestClient, tmp_path: Path) -> None:
    """The regression. `capabilities.json` was written to the repository root, which the
    api container does not mount, so this endpoint reported "no probe has been run" however
    many times you ran one."""
    probe_result = {"zone_count": 350, "has_token": True, "signals": []}
    path = tmp_path / "capabilities.json"
    path.write_text(json.dumps(probe_result), encoding="utf-8")

    app.state.lab.settings = app.state.lab.settings.model_copy(
        update={"gridlab_capabilities_path": path}
    )

    body = client.get("/api/v1/capabilities").json()
    assert body["source"] == "probe"
    assert body["zone_count"] == 350


def test_capabilities_path_is_inside_a_mounted_directory() -> None:
    """A bind mount of a path that does not exist becomes a directory, and this file does
    not exist until a probe has been run. Mounting `data/` sidesteps that, so the default
    must stay inside a directory rather than sitting at a bare root path."""
    default = Settings.model_fields["gridlab_capabilities_path"].default
    assert default.parent.name == "data"
    assert default.name == "capabilities.json"


def test_zones_lists_only_what_the_scenario_has(client: TestClient) -> None:
    body = client.get("/api/v1/zones").json()
    assert [z["key"] for z in body["zones"]] == ["DK-DK2"]
    assert body["zones"][0]["name"].startswith("East Denmark")


# --- grid -------------------------------------------------------------------


def test_snapshot_shape(client: TestClient) -> None:
    body = client.get("/api/v1/grid/DK-DK2/now").json()
    assert body["zone"] == "DK-DK2"
    assert body["provenance"] == "synthetic"
    assert body["carbon_intensity"]["value"] == 400.0
    assert body["carbon_intensity"]["provenance"] == "synthetic"


def test_unknown_zone_404s_with_the_available_list(client: TestClient) -> None:
    response = client.get("/api/v1/grid/PL/now")
    assert response.status_code == 404
    assert response.json()["detail"]["available"] == ["DK-DK2"]


def test_mix_defaults_to_flow_traced(client: TestClient) -> None:
    """Flow-traced consumption is the more useful and less obvious answer, so it is the
    default. The response says which one it is, so a chart cannot mislabel itself."""
    body = client.get("/api/v1/grid/DK-DK2/mix").json()
    assert body["flow_traced"] is True
    assert {e["source"] for e in body["entries"]} == {"wind", "coal", "gas"}


def test_production_mix_is_a_different_answer(client: TestClient) -> None:
    body = client.get("/api/v1/grid/DK-DK2/mix?flow_traced=false").json()
    assert body["flow_traced"] is False


def test_flows_include_the_derived_net_import(client: TestClient) -> None:
    body = client.get("/api/v1/grid/DK-DK2/flows").json()
    assert body["net_import_mw"] == pytest.approx(1000.0)


def test_negative_prices_survive_the_api(client: TestClient) -> None:
    """Negative prices are the most interesting thing in this data. Clamping or rejecting
    them would delete the story."""
    body = client.get(
        "/api/v1/grid/DK-DK2/history",
        params={"signal": "price", "start": "2026-02-04T00:00:00Z", "end": "2026-02-04T03:00:00Z"},
    ).json()
    assert body["points"][0]["value"] == -12.5
    assert body["points"][0]["currency"] == "EUR"


def test_series_points_actually_carry_values(client: TestClient) -> None:
    """Regression: declaring a response model of the base Observation type silently
    stripped `value` from every point, and the chart rendered as an empty axis."""
    body = client.get("/api/v1/grid/DK-DK2/forecast").json()
    assert body["points"], "forecast returned no points"
    for point in body["points"]:
        assert "value" in point, f"point without a value: {point}"


def test_forecast_reports_when_it_was_issued(client: TestClient) -> None:
    body = client.get("/api/v1/grid/DK-DK2/forecast").json()
    assert body["issued_at"] == "2026-02-04T00:00:00+00:00"
    assert body["provenance"] == "synthetic"


def test_forecast_differs_from_the_outcome(client: TestClient) -> None:
    """The gap is the point. If these ever match exactly, replay is serving actuals."""
    forecast = client.get("/api/v1/grid/DK-DK2/forecast").json()
    actual = client.get("/api/v1/grid/DK-DK2/now").json()
    assert forecast["points"][-1]["value"] == 240.0
    assert actual["carbon_intensity"]["value"] == 400.0


def test_unknown_signal_400s_with_the_valid_list(client: TestClient) -> None:
    response = client.get("/api/v1/grid/DK-DK2/forecast", params={"signal": "vibes"})
    assert response.status_code == 400
    assert "carbon_intensity" in response.json()["detail"]["available"]


def test_history_rejects_a_backwards_window(client: TestClient) -> None:
    response = client.get(
        "/api/v1/grid/DK-DK2/history",
        params={"start": "2026-02-05T00:00:00Z", "end": "2026-02-04T00:00:00Z"},
    )
    assert response.status_code == 400


def test_history_rejects_an_absurd_window(client: TestClient) -> None:
    """An unbounded window is dozens of upstream requests and an easy way to burn a key."""
    response = client.get(
        "/api/v1/grid/DK-DK2/history",
        params={"start": "2019-01-01T00:00:00Z", "end": "2026-01-01T00:00:00Z"},
    )
    assert response.status_code == 400
    assert "366 days" in response.json()["detail"]


def test_compare_returns_values_and_the_ranking_caveat(client: TestClient) -> None:
    body = client.get("/api/v1/compare", params={"zones": "DK-DK2"}).json()
    assert body["zones"]["DK-DK2"]["value"] == 400.0
    assert "baseline" in body["note"]


def test_compare_rejects_an_empty_zone_list(client: TestClient) -> None:
    assert client.get("/api/v1/compare", params={"zones": " , "}).status_code == 400


# --- replay controls --------------------------------------------------------


def test_scenarios_are_listed_with_their_provenance(client: TestClient) -> None:
    body = client.get("/api/v1/replay/scenarios").json()
    assert body["current"] == "test-scenario"
    assert body["scenarios"][0]["provenance"] == "synthetic"


def test_pause_and_resume(client: TestClient) -> None:
    # Restore a real replay clock; the fixture froze it for deterministic assertions.
    from datetime import UTC, datetime

    from gridlab.clock import ReplayClock

    app.state.lab.source.clock = ReplayClock(
        datetime(2026, 2, 4, tzinfo=UTC), end=datetime(2026, 2, 4, 3, tzinfo=UTC), speed=1.0
    )

    assert client.post("/api/v1/replay/pause").json()["running"] is False
    assert client.post("/api/v1/replay/resume").json()["running"] is True


def test_seek_moves_the_data_not_just_the_clock(client: TestClient) -> None:
    from datetime import UTC, datetime

    from gridlab.clock import ReplayClock

    app.state.lab.source.clock = ReplayClock(
        datetime(2026, 2, 4, tzinfo=UTC), end=datetime(2026, 2, 4, 3, tzinfo=UTC), speed=1.0
    )
    client.post("/api/v1/replay/pause")
    client.post("/api/v1/replay/seek", params={"to": "2026-02-04T01:00:00Z"})

    body = client.get("/api/v1/grid/DK-DK2/now").json()
    assert body["carbon_intensity"]["value"] == 200.0


def test_speed_must_be_positive(client: TestClient) -> None:
    assert client.post("/api/v1/replay/speed", params={"multiplier": 0}).status_code == 422


def test_loading_an_unknown_scenario_404s(client: TestClient) -> None:
    response = client.post("/api/v1/replay/scenario", params={"id": "nope"})
    assert response.status_code == 404
    assert "test-scenario" in response.json()["detail"]


# --- openapi ----------------------------------------------------------------


def test_openapi_documents_the_provenance_contract() -> None:
    """The agent and any future client read this. The provenance rule belongs in it."""
    schema: dict[str, Any] = app.openapi()
    assert "provenance" in schema["info"]["description"]
    assert "synthetic" in schema["info"]["description"]
