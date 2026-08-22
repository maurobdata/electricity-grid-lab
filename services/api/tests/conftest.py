"""Shared fixtures.

A small hand-built scenario rather than the generated ones: tests should assert against
values a reader can see in the file, not against the output of a sine wave.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from gridlab.store.scenario import Scenario

T0 = datetime(2026, 2, 4, 0, tzinfo=UTC)


def _hour(h: int) -> str:
    return datetime(2026, 2, 4, h, tzinfo=UTC).isoformat()


@pytest.fixture
def scenario_dict() -> dict[str, Any]:
    """Four hours of a zone with a deliberate, readable shape.

    Carbon intensity climbs 100 -> 400 as wind falls away and imports rise; price goes
    negative in the windy first hour and positive as scarcity arrives. The forecast is
    wrong in the last hour, which is the case worth testing.
    """
    return {
        "id": "test-scenario",
        "title": "Test scenario",
        "description": "Four readable hours.",
        "provenance": "synthetic",
        "currency": "EUR",
        "start": _hour(0),
        "end": _hour(3),
        "granularity": "hourly",
        "notes": "Fixture data. Not measured.",
        "zones": {
            "DK-DK2": {
                "carbon_intensity": [
                    {"at": _hour(0), "value": 100.0},
                    {"at": _hour(1), "value": 200.0},
                    {"at": _hour(2), "value": 300.0, "is_estimated": True},
                    {"at": _hour(3), "value": 400.0},
                ],
                "renewable_percentage": [
                    {"at": _hour(0), "value": 90.0},
                    {"at": _hour(3), "value": 20.0},
                ],
                "carbon_free_percentage": [{"at": _hour(0), "value": 90.0}],
                "price": [
                    {"at": _hour(0), "value": -12.5},
                    {"at": _hour(3), "value": 180.0},
                ],
                "load": [{"at": _hour(0), "value": 1500.0}],
                "mix": [
                    {
                        "at": _hour(0),
                        "flow_traced": True,
                        "entries": {"wind": 900.0, "gas": 100.0},
                    },
                    {
                        "at": _hour(0),
                        "flow_traced": False,
                        "entries": {"wind": 1400.0},
                    },
                    {
                        "at": _hour(3),
                        "flow_traced": True,
                        "entries": {"wind": 200.0, "coal": 600.0, "gas": 200.0},
                    },
                ],
                "flows": [
                    {"at": _hour(0), "edges": {"DE": 250.0, "SE-SE4": -50.0}},
                    {"at": _hour(3), "edges": {"DE": -800.0, "SE-SE4": -200.0}},
                ],
                "forecasts": {
                    "carbon_intensity": {
                        "issued_at": _hour(0),
                        "horizon_hours": 24,
                        "points": [
                            {"at": _hour(0), "value": 100.0},
                            {"at": _hour(1), "value": 190.0},
                            {"at": _hour(2), "value": 260.0},
                            # The forecast badly underestimates the final hour. That gap is
                            # the most interesting quantity in the whole dataset.
                            {"at": _hour(3), "value": 240.0},
                        ],
                    }
                },
            }
        },
    }


@pytest.fixture
def scenario(scenario_dict: dict[str, Any]) -> Scenario:
    return Scenario.model_validate(scenario_dict)


@pytest.fixture
def scenarios_dir(tmp_path: Path, scenario_dict: dict[str, Any]) -> Path:
    import json

    directory = tmp_path / "scenarios"
    directory.mkdir()
    (directory / "test-scenario.json").write_text(json.dumps(scenario_dict), encoding="utf-8")
    return directory
