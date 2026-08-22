"""The agent's HTTP surface and its loop, without calling a model.

The loop is exercised against a stubbed backend rather than the Anthropic API: what needs
proving is that tool failures are reported to the model instead of ending the turn, that
events arrive in an order the UI can render, and that the service degrades honestly when
no key is configured. None of that needs a real model, and using one would make these
tests slow, expensive and non-deterministic.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from gridlab.agent import llm
from gridlab.agent.app import AgentState, app
from gridlab.agent.gridclient import GridClient, GridUnavailable
from gridlab.agent.tools import ToolContext, ToolSpec, build_tools
from gridlab.config import Settings
from gridstub import ZONE, _api_handler


def _state(*, key: str | None) -> AgentState:
    settings = Settings(
        anthropic_api_key=key,
        electricity_maps_api_token=None,
        gridlab_api_url="http://api:8000",
    )
    state = AgentState(settings)
    state.client._client = httpx.AsyncClient(
        base_url="http://api:8000", transport=httpx.MockTransport(_api_handler)
    )
    return state


@pytest.fixture
def client_without_key() -> Iterator[TestClient]:
    state = _state(key=None)
    app.state.agent = state
    with TestClient(app) as client:
        app.state.agent = state
        yield client


# --- the published boundary -------------------------------------------------


def test_healthz_reports_whether_it_can_think(client_without_key: TestClient) -> None:
    body = client_without_key.get("/api/v1/healthz").json()
    assert body["status"] == "ok"
    assert body["has_anthropic_key"] is False
    assert body["model"] == "claude-opus-5"


def test_tools_endpoint_publishes_the_whole_surface(client_without_key: TestClient) -> None:
    """Reviewable without reading the source: anything not listed here cannot be done."""
    body = client_without_key.get("/api/v1/tools").json()

    assert len(body["tools"]) == 7
    for tool in body["tools"]:
        assert tool["schema"]["additionalProperties"] is False
    assert any("read-only" in c for c in body["constraints"])


def test_chat_without_a_key_explains_itself_rather_than_failing(
    client_without_key: TestClient,
) -> None:
    """A missing key is the likely state, not an exceptional one. It should produce a
    sentence, not a 500 — and it should point at what still works."""
    with client_without_key.stream(
        "POST", "/api/v1/chat", json={"message": "how is DK-DK2?"}
    ) as response:
        assert response.status_code == 200
        events = _collect(response)

    assert len(events) == 1
    name, payload = events[0]
    assert name == "error"
    assert payload["kind"] == "no_key"
    assert "ANTHROPIC_API_KEY" in payload["message"]
    assert "tools themselves work" in payload["message"]


def test_chat_rejects_an_empty_message(client_without_key: TestClient) -> None:
    assert client_without_key.post("/api/v1/chat", json={"message": ""}).status_code == 422


def test_chat_bounds_the_history_it_will_accept(client_without_key: TestClient) -> None:
    """An unbounded history is an unbounded bill."""
    history = [{"role": "user", "content": "x"} for _ in range(100)]
    response = client_without_key.post("/api/v1/chat", json={"message": "hi", "history": history})
    assert response.status_code == 422


# --- the loop ---------------------------------------------------------------


async def _context() -> ToolContext:
    client = GridClient("http://api:8000")
    client._client = httpx.AsyncClient(
        base_url="http://api:8000", transport=httpx.MockTransport(_api_handler)
    )
    return ToolContext(client=client, max_points=50)


async def test_a_failing_tool_is_reported_not_raised() -> None:
    """A tool that refuses must come back to the model as a readable result. Raising would
    end the turn on the most recoverable error there is — a wrong zone key."""
    ctx = await _context()
    by_name = {tool.name: tool for tool in build_tools()}

    outcome, ok, elapsed = await llm._invoke(by_name, "get_current_grid", {"zone": "ZZ"}, ctx)

    assert ok is False
    assert "no zone" in outcome["error"].lower()
    assert ZONE in outcome["error"]
    assert elapsed >= 0


async def test_an_unknown_tool_name_is_survivable() -> None:
    ctx = await _context()
    outcome, ok, _ = await llm._invoke({}, "rm_rf", {}, ctx)
    assert ok is False
    assert "No tool named" in outcome["error"]


async def test_wrong_arguments_do_not_crash_the_turn() -> None:
    ctx = await _context()
    by_name = {tool.name: tool for tool in build_tools()}
    outcome, ok, _ = await llm._invoke(by_name, "get_current_grid", {"wrong": 1}, ctx)
    assert ok is False
    assert "Wrong arguments" in outcome["error"]


async def test_an_unexpected_tool_failure_is_contained() -> None:
    """A bug in a tool must degrade that tool, not the conversation."""

    async def explodes(_ctx: ToolContext, **_: Any) -> dict[str, Any]:
        raise RuntimeError("boom")

    spec = ToolSpec(name="boom", description="x" * 70, parameters={}, handler=explodes)
    outcome, ok, _ = await llm._invoke({"boom": spec}, "boom", {}, await _context())

    assert ok is False
    assert "RuntimeError" in outcome["error"]
    assert "boom" not in outcome["error"].replace("boom failed", "")


async def test_a_successful_tool_call_returns_its_payload() -> None:
    ctx = await _context()
    by_name = {tool.name: tool for tool in build_tools()}
    outcome, ok, _ = await llm._invoke(by_name, "get_current_grid", {"zone": ZONE}, ctx)

    assert ok is True
    assert outcome["provenance"] == "recorded"


# --- event ordering ---------------------------------------------------------


class _StubBackend:
    """A backend that replays a fixed script, so the SSE contract can be asserted."""

    def __init__(self, events: list[Any]) -> None:
        self._events = events

    @property
    def model(self) -> str:
        return "stub"

    def available(self) -> bool:
        return True

    async def run(self, **_: Any) -> Any:
        for event in self._events:
            yield event


def test_events_reach_the_client_in_order() -> None:
    """The UI renders the trace inline, so `tool_call` must precede its `tool_result`, and
    both must precede the text that used them."""
    state = _state(key="test-key")
    state.backend = _StubBackend(  # type: ignore[assignment]
        [
            llm.ToolCall("t1", "get_current_grid", {"zone": ZONE}),
            llm.ToolResult("t1", "get_current_grid", True, {"provenance": "recorded"}, 12.0),
            llm.TextDelta("DK-DK2 is at "),
            llm.TextDelta("63 gCO2eq/kWh."),
            llm.TurnFinished("end_turn", 2, 100, 50),
        ]
    )
    app.state.agent = state

    with TestClient(app) as client:
        app.state.agent = state
        with client.stream("POST", "/api/v1/chat", json={"message": "how is DK-DK2?"}) as r:
            events = _collect(r)

    names = [name for name, _ in events]
    assert names == ["tool_call", "tool_result", "text", "text", "done"]

    call = events[0][1]
    assert call["name"] == "get_current_grid"
    assert call["arguments"] == {"zone": ZONE}

    result = events[1][1]
    assert result["ok"] is True
    assert result["id"] == call["id"], "a result must be attributable to its call"

    text = "".join(payload["text"] for name, payload in events if name == "text")
    assert text == "DK-DK2 is at 63 gCO2eq/kWh."

    assert events[-1][1]["rounds"] == 2


def test_a_backend_error_becomes_an_error_event() -> None:
    state = _state(key="test-key")
    state.backend = _StubBackend([llm.AgentError("rate limited", kind="api")])  # type: ignore[assignment]
    app.state.agent = state

    with TestClient(app) as client:
        app.state.agent = state
        with client.stream("POST", "/api/v1/chat", json={"message": "hi"}) as r:
            events = _collect(r)

    assert events[-1][0] == "error"
    assert events[-1][1]["kind"] == "api"


def test_max_rounds_is_a_cost_bound_not_a_safety_one() -> None:
    """Worth stating explicitly: every tool is read-only, so a runaway loop wastes tokens
    rather than doing damage. The bound exists for the bill."""
    assert llm.MAX_ROUNDS <= 10


def _collect(response: httpx.Response) -> list[tuple[str, dict[str, Any]]]:
    """Parse an SSE stream into (event, payload) pairs."""
    events: list[tuple[str, dict[str, Any]]] = []
    name: str | None = None
    for line in response.iter_lines():
        if line.startswith("event:"):
            name = line.split(":", 1)[1].strip()
        elif line.startswith("data:") and name:
            events.append((name, json.loads(line.split(":", 1)[1].strip())))
            name = None
    return events


# --- the sandbox ------------------------------------------------------------


def test_the_agent_reaches_the_lab_and_nothing_else() -> None:
    """Structural, not aspirational: the client is constructed with one base URL and has
    no method that takes an arbitrary one."""
    state = _state(key=None)
    assert str(state.client._client.base_url).startswith("http://api:8000")

    public = [name for name in dir(GridClient) if not name.startswith("_")]
    assert "get" not in public and "request" not in public


async def test_grid_unavailable_carries_the_api_hint() -> None:
    """404 detail from the API is passed through, because it usually contains the fix."""
    ctx = await _context()
    with pytest.raises(GridUnavailable) as exc:
        await ctx.client.snapshot("NOPE")
    assert "available" in str(exc.value).lower()
