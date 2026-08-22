"""The agent's tools, tested without a model.

The declared tool list is the security boundary, so it is asserted directly rather than
inferred from how the agent behaves. An LLM in the loop would make these tests slow,
non-deterministic and expensive, and would test the wrong thing: what matters is that the
boundary holds regardless of what the model asks for.

The grid API is served here by a mock transport backed by the same recorded fixtures the
rest of the suite uses, so the tools run against real response shapes, offline.
"""

from __future__ import annotations

import json
from collections.abc import Iterator

import httpx
import pytest

from gridlab.agent import tools as t
from gridlab.agent.gridclient import GridClient, GridUnavailable
from gridstub import ZONE, _api_handler


@pytest.fixture
def ctx() -> Iterator[t.ToolContext]:
    client = GridClient("http://api:8000")
    client._client = httpx.AsyncClient(
        base_url="http://api:8000", transport=httpx.MockTransport(_api_handler)
    )
    yield t.ToolContext(client=client, max_points=10)


# --- the boundary itself ----------------------------------------------------


def test_there_are_exactly_the_seven_named_tools() -> None:
    """The brief names seven. Anything else appearing here is a decision that needs an ADR,
    not a quiet addition."""
    assert {tool.name for tool in t.build_tools()} == {
        "get_current_grid",
        "get_forecast",
        "get_mix",
        "get_price",
        "get_flows",
        "query_history",
        "compare_zones",
    }


def test_every_schema_is_strict_and_closed() -> None:
    """`additionalProperties: false` is what makes a hallucinated argument an API error
    rather than something that arrives in a handler."""
    for tool in t.build_tools():
        schema = tool.schema()
        assert schema["additionalProperties"] is False, tool.name
        assert schema["type"] == "object"
        for name in schema["required"]:
            assert name in schema["properties"], f"{tool.name} requires undeclared {name}"


def test_every_declared_tool_is_callable() -> None:
    """Declaration and dispatch come from one list, so they cannot drift. Asserted anyway,
    because the day they do drift is the day a tool silently stops working."""
    for tool in t.build_tools():
        assert callable(tool.handler), tool.name


def test_no_tool_can_change_anything() -> None:
    """Read-only is the property that makes a runaway loop a cost problem rather than a
    safety one. The client exposes no write verb at all."""
    from gridlab.agent.gridclient import GridClient as Client

    verbs = [name for name in dir(Client) if not name.startswith("_")]
    assert not {"post", "put", "patch", "delete"} & set(verbs)


def test_descriptions_are_substantial() -> None:
    """The description is how the model decides which tool to reach for. A terse one is a
    routing bug waiting to happen."""
    for tool in t.build_tools():
        assert len(tool.description) > 60, tool.name


# --- zone allowlisting ------------------------------------------------------


async def test_unknown_zone_is_refused_with_the_available_list(ctx: t.ToolContext) -> None:
    """The error is the correction. Telling the model which zones exist is what lets it fix
    itself in one round instead of guessing again."""
    with pytest.raises(GridUnavailable) as exc:
        await t.get_current_grid(ctx, zone="ZZ")
    assert ZONE in str(exc.value)


async def test_zone_case_and_separator_confusion_is_forgiven(ctx: t.ToolContext) -> None:
    result = await t.get_current_grid(ctx, zone="dk_dk2")
    assert result["zone"] == ZONE


async def test_every_tool_validates_its_zone(ctx: t.ToolContext) -> None:
    for call in (
        lambda: t.get_current_grid(ctx, zone="ZZ"),
        lambda: t.get_mix(ctx, zone="ZZ"),
        lambda: t.get_price(ctx, zone="ZZ"),
        lambda: t.get_flows(ctx, zone="ZZ"),
        lambda: t.get_forecast(ctx, zone="ZZ"),
        lambda: t.query_history(ctx, zone="ZZ"),
        lambda: t.compare_zones(ctx, zones=["ZZ", "YY"]),
    ):
        with pytest.raises(GridUnavailable):
            await call()


# --- bounds -----------------------------------------------------------------


async def test_history_window_is_bounded(ctx: t.ToolContext) -> None:
    with pytest.raises(GridUnavailable, match="days"):
        await t.query_history(
            ctx, zone=ZONE, start="2019-01-01T00:00:00Z", end="2026-01-01T00:00:00Z"
        )


async def test_backwards_history_window_is_refused(ctx: t.ToolContext) -> None:
    with pytest.raises(GridUnavailable, match="after"):
        await t.query_history(
            ctx, zone=ZONE, start="2026-08-22T00:00:00Z", end="2026-08-21T00:00:00Z"
        )


async def test_unknown_signal_is_refused(ctx: t.ToolContext) -> None:
    with pytest.raises(GridUnavailable, match="signal must be"):
        await t.get_forecast(ctx, zone=ZONE, signal="vibes")


async def test_unsupported_horizon_is_refused_locally(ctx: t.ToolContext) -> None:
    """Better a clear message than a 400 the model cannot diagnose."""
    with pytest.raises(GridUnavailable, match="horizon_hours"):
        await t.get_forecast(ctx, zone=ZONE, horizon_hours=13)


async def test_compare_needs_at_least_two_zones(ctx: t.ToolContext) -> None:
    with pytest.raises(GridUnavailable, match="at least two"):
        await t.compare_zones(ctx, zones=[ZONE])


async def test_compare_is_capped(ctx: t.ToolContext) -> None:
    with pytest.raises(GridUnavailable, match="At most"):
        await t.compare_zones(ctx, zones=[ZONE] * 20)


# --- downsampling -----------------------------------------------------------


def test_short_series_is_untouched() -> None:
    points = [{"at": str(i), "value": float(i)} for i in range(5)]
    result, thinned = t.downsample(points, 10)
    assert result == points
    assert thinned is False


def test_downsampling_preserves_the_extremes() -> None:
    """The whole reason not to stride blindly. A negative price spike is exactly what
    someone is asking about; dropping it while returning a confident curve is worse than
    returning fewer points."""
    points = [{"at": str(i), "value": float(i)} for i in range(500)]
    points[123]["value"] = -999.0  # the spike
    points[400]["value"] = 999.0  # the peak

    result, thinned = t.downsample(points, 20)

    assert thinned is True
    assert len(result) <= 20
    values = [p["value"] for p in result]
    assert -999.0 in values, "the minimum was dropped"
    assert 999.0 in values, "the maximum was dropped"


def test_downsampling_keeps_both_endpoints() -> None:
    points = [{"at": str(i), "value": float(i)} for i in range(300)]
    result, _ = t.downsample(points, 15)
    assert result[0]["at"] == "0"
    assert result[-1]["at"] == "299"


def test_downsampling_survives_missing_values() -> None:
    points = [{"at": str(i), "value": None} for i in range(100)]
    result, thinned = t.downsample(points, 10)
    assert thinned is True
    assert len(result) <= 10


async def test_series_tools_respect_the_point_cap(ctx: t.ToolContext) -> None:
    result = await t.get_forecast(ctx, zone=ZONE)
    assert len(result["points"]) <= ctx.max_points


# --- what the model is told -------------------------------------------------


async def test_every_tool_result_carries_provenance(ctx: t.ToolContext) -> None:
    """The provenance contract does not stop at the UI. An agent that cannot see whether a
    number was measured cannot disclose it."""
    for result in (
        await t.get_current_grid(ctx, zone=ZONE),
        await t.get_mix(ctx, zone=ZONE),
        await t.get_price(ctx, zone=ZONE),
        await t.get_flows(ctx, zone=ZONE),
        await t.get_forecast(ctx, zone=ZONE),
        await t.query_history(ctx, zone=ZONE),
        await t.compare_zones(ctx, zones=[ZONE, "DK-DK2"]),
    ):
        assert result.get("provenance") == "recorded", result


async def test_estimation_flags_reach_the_model(ctx: t.ToolContext) -> None:
    snapshot = await t.get_current_grid(ctx, zone=ZONE)
    assert snapshot["carbon_intensity_gco2_per_kwh"]["is_estimated"] is True

    series = await t.get_forecast(ctx, zone=ZONE)
    assert series["estimated_fraction"] == 0.08
    assert any(point.get("estimated") for point in series["points"])


async def test_mix_states_which_breakdown_it_is(ctx: t.ToolContext) -> None:
    traced = await t.get_mix(ctx, zone=ZONE, flow_traced=True)
    produced = await t.get_mix(ctx, zone=ZONE, flow_traced=False)

    assert traced["flow_traced"] is True
    assert produced["flow_traced"] is False
    assert traced["sources"][0]["percent"] != produced["sources"][0]["percent"]
    assert "different answers" in traced["_note"]


async def test_negative_price_is_flagged_not_hidden(ctx: t.ToolContext) -> None:
    """The most counter-intuitive thing in this data. A model that reads it as an error
    will "correct" it."""
    result = await t.get_price(ctx, zone=ZONE)
    assert result["value"] == -54.4
    assert "paying consumers" in result["_note"]


async def test_compare_carries_the_ranking_caveat(ctx: t.ToolContext) -> None:
    result = await t.compare_zones(ctx, zones=[ZONE, "DK-DK2"])
    assert "baseline" in result["_note"]


async def test_flows_explain_their_sign_convention(ctx: t.ToolContext) -> None:
    result = await t.get_flows(ctx, zone=ZONE)
    assert "exporting" in result["_note"]
    by_zone = {n["zone"]: n for n in result["neighbours"]}
    assert by_zone["DE"]["direction"] == "import"
    assert by_zone["SE-SE4"]["direction"] == "export"


async def test_history_admits_it_may_return_less_than_asked(ctx: t.ToolContext) -> None:
    """On a plan without `past-range` the window is roughly 24 hours whatever you ask for.
    A model that assumes it got what it requested will describe the gap wrongly."""
    result = await t.query_history(ctx, zone=ZONE)
    assert "shorter than the window requested" in result["_note"]


async def test_tool_results_are_json_serialisable(ctx: t.ToolContext) -> None:
    """They are serialised into the tool_result block; a stray object would fail the turn."""
    for result in (
        await t.get_current_grid(ctx, zone=ZONE),
        await t.get_forecast(ctx, zone=ZONE),
        await t.compare_zones(ctx, zones=[ZONE, "DK-DK2"]),
    ):
        json.loads(json.dumps(result))


# --- the published surface --------------------------------------------------


def test_prompt_forbids_inventing_numbers() -> None:
    """The softest guardrail, and still worth pinning: it is the one instruction whose
    removal would not break anything visible."""
    from gridlab.agent.prompts import SYSTEM_PROMPT

    assert "Never state a number you did not get from a tool" in SYSTEM_PROMPT


def test_prompt_names_all_three_provenance_values() -> None:
    from gridlab.agent.prompts import SYSTEM_PROMPT

    for value in ("live", "recorded", "synthetic"):
        assert f"`{value}`" in SYSTEM_PROMPT


def test_synthetic_sessions_get_an_explicit_warning() -> None:
    from gridlab.agent.prompts import system_prompt

    prompt = system_prompt(mode="replay", provenance="synthetic", zones=[ZONE], now="X")
    assert "generated, not measured" in prompt


def test_recorded_sessions_are_told_not_to_speak_in_the_present() -> None:
    from gridlab.agent.prompts import system_prompt

    prompt = system_prompt(mode="replay", provenance="recorded", zones=[ZONE], now="X")
    assert "not current" in prompt
