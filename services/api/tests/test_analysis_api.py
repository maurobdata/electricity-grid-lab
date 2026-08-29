"""The analysis HTTP contract.

Same discipline as `test_api.py`: these shapes are what the PWA and the agent consume, so
they are pinned here rather than discovered by a broken panel. Everything runs against the
hand-built scenario in replay mode — no network, no key.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gridlab.config import Mode, Settings
from gridlab.web.app import app
from gridlab.web.state import LabState


@pytest.fixture
def client(scenarios_dir: Path, tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(
        gridlab_mode=Mode.REPLAY,
        gridlab_scenario="test-scenario",
        gridlab_scenarios_dir=scenarios_dir,
        # Pinned too, or the mounted archive would leak real recordings into the test.
        gridlab_recordings_dir=scenarios_dir / "no-archive",
        gridlab_db_path=tmp_path / "analysis.duckdb",
        gridlab_replay_speed=1.0,
        electricity_maps_api_token=None,
        anthropic_api_key=None,
        gridlab_capabilities_path=tmp_path / "no-probe-here.json",
    )
    state = LabState.build(settings)
    app.state.lab = state

    from datetime import UTC, datetime

    from gridlab.clock import FrozenClock

    # The start of the window, so the whole scenario is still ahead of the clock and the
    # forward-looking analysis has something to work with.
    state.source.clock = FrozenClock(datetime(2026, 2, 4, 0, tzinfo=UTC))

    with TestClient(app) as test_client:
        app.state.lab = state
        yield test_client


# --- findings ---------------------------------------------------------------


def test_findings_are_served_with_their_evidence_and_intent(client: TestClient) -> None:
    """The two fields that make a finding usable: what proves it, and where to look."""
    body = client.get("/api/v1/analysis/DK-DK2/findings").json()

    assert body["count"] >= 1
    finding = body["findings"][0]
    assert finding["evidence"], "a finding with no evidence is an assertion"
    assert finding["intent"]["reason"], "an unexplained view change is disorienting"
    assert finding["derived"]["provenance"] == "synthetic"


def test_the_negative_price_in_the_scenario_is_found(client: TestClient) -> None:
    """The fixture opens at -12.50 EUR/MWh. If this stops firing, the detector is broken —
    a quiet detector and a quiet grid look identical from the outside."""
    body = client.get("/api/v1/analysis/DK-DK2/findings").json()
    kinds = [f["kind"] for f in body["findings"]]
    assert "negative_price" in kinds


def test_findings_say_no_model_was_involved(client: TestClient) -> None:
    body = client.get("/api/v1/analysis/DK-DK2/findings").json()
    assert "no language model" in body["note"]


def test_findings_for_an_unknown_zone_404(client: TestClient) -> None:
    response = client.get("/api/v1/analysis/PL/findings")
    assert response.status_code == 404
    assert "available" in response.json()["detail"]


# --- divergence -------------------------------------------------------------


def test_divergence_joins_forward_price_with_the_carbon_forecast(client: TestClient) -> None:
    body = client.get("/api/v1/analysis/DK-DK2/divergence").json()

    assert body["zone"] == "DK-DK2"
    assert body["a_signal"] == "carbon_intensity"
    assert body["b_signal"] == "price"
    assert body["derived"]["provenance"] == "synthetic"
    assert {ref["signal"] for ref in body["derived"]["inputs"]} == {"carbon_intensity", "price"}


def test_divergence_always_carries_the_marginal_versus_average_caveat(
    client: TestClient,
) -> None:
    """The objection a knowledgeable reader raises. It ships with the number, not in a
    footnote somebody has to find."""
    body = client.get("/api/v1/analysis/DK-DK2/divergence").json()
    assert any("marginal" in caveat for caveat in body["derived"]["caveats"])


def test_divergence_404s_with_a_reason_when_forward_price_is_missing(
    client: TestClient,
) -> None:
    """Three different things produce this, and only one is a bug. The message names them,
    because it will be read under time pressure."""
    response = client.get("/api/v1/analysis/PL/divergence")
    assert response.status_code == 404


# --- baseline ---------------------------------------------------------------


def test_baseline_refuses_a_window_too_short_to_score(client: TestClient) -> None:
    """The scenario holds four hours. A percentile over four samples looks exactly as
    authoritative as one over four hundred, so the endpoint declines and says why."""
    response = client.get("/api/v1/analysis/DK-DK2/baseline")
    assert response.status_code == 404
    assert "past-range" in response.json()["detail"]


def test_baseline_rejects_an_unknown_signal_with_the_valid_list(client: TestClient) -> None:
    response = client.get("/api/v1/analysis/DK-DK2/baseline", params={"signal": "vibes"})
    assert response.status_code == 400
    assert "carbon_intensity" in response.json()["detail"]["available"]


def test_the_rail_surfaces_a_negative_price_that_already_happened(client: TestClient) -> None:
    """The fixture opens at -12.50 EUR/MWh, an hour that has elapsed by the time the clock
    reaches the end of the window.

    Germany ran five hours below zero on 23 August 2026 and this rail said nothing, because
    the detector only ever looked forward — while the "now" panel flagged the current hour
    in red. A panel that highlights something and a rail that ignores it is worse than
    either alone.
    """
    from datetime import UTC, datetime

    from gridlab.clock import FrozenClock

    app.state.lab.source.clock = FrozenClock(datetime(2026, 2, 4, 3, tzinfo=UTC))
    body = client.get("/api/v1/analysis/DK-DK2/findings").json()

    negatives = [f for f in body["findings"] if f["kind"] == "negative_price"]
    assert negatives, "an elapsed negative price produced no finding"
    assert any("went negative" in f["headline"] for f in negatives), (
        "an elapsed dip was reported in the present tense"
    )
