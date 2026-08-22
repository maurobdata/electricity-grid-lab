"""The agent service.

Runs from the same image as the API, with a different command, on a network that reaches
only `api`. See ``docs/adr/0005-agent-sandbox-container.md`` for what that does and does
not guarantee.

``POST /chat`` streams Server-Sent Events. Tool calls and their results are emitted as
events alongside the text, so the UI can render the trace inline. That is not decoration:
an agent whose working is visible is checkable, and every number it quotes can be traced to
a request a human could make themselves.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import Annotated, Any

import structlog
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from gridlab import __version__
from gridlab.agent.gridclient import GridClient, GridUnavailable
from gridlab.agent.llm import (
    AgentError,
    AnthropicBackend,
    Conversation,
    TextDelta,
    ToolCall,
    ToolResult,
    TurnFinished,
)
from gridlab.agent.prompts import system_prompt
from gridlab.agent.tools import ToolContext, build_tools
from gridlab.config import Settings, get_settings

log = structlog.get_logger(__name__)


class AgentState:
    """Everything the service needs, built once."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = GridClient(settings.gridlab_api_url, timeout=settings.gridlab_http_timeout)
        self.tools = build_tools()
        token = settings.anthropic_api_key
        self.backend = AnthropicBackend(
            api_key=token.get_secret_value() if token else None,
            model=settings.gridlab_agent_model,
        )

    async def aclose(self) -> None:
        await self.client.aclose()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, settings.gridlab_log_level.upper(), logging.INFO),
    )
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ]
    )

    state = AgentState(settings)
    app.state.agent = state
    log.info(
        "agent.started",
        model=state.backend.model,
        has_key=state.backend.available(),
        tools=[tool.name for tool in state.tools],
        api_url=settings.gridlab_api_url,
    )
    try:
        yield
    finally:
        await state.aclose()


app = FastAPI(
    title="Grid Lab Agent",
    version=__version__,
    summary="A sandboxed agent with explicit, read-only grid tools.",
    description=(
        "The agent may act only through its declared tools, and reaches grid data only via "
        "the API service. It has no shell, no filesystem and no general web access.\n\n"
        "Tool calls are streamed to the client so its working is visible: every number it "
        "quotes corresponds to a request you could make yourself."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def agent(request: Request) -> AgentState:
    return request.app.state.agent  # type: ignore[no-any-return]


Agent = Annotated[AgentState, Depends(agent)]


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    history: list[Message] = Field(default_factory=list, max_length=40)


@app.get("/api/v1/healthz", tags=["meta"])
async def healthz(state: Agent) -> dict[str, Any]:
    return {
        "status": "ok",
        "version": __version__,
        "model": state.backend.model,
        "has_anthropic_key": state.backend.available(),
        "api_url": state.settings.gridlab_api_url,
    }


@app.get("/api/v1/tools", tags=["agent"])
async def tools(state: Agent) -> dict[str, Any]:
    """The tool surface, which *is* the security boundary.

    Published so it can be reviewed without reading the source. Anything not listed here is
    something the agent cannot do.
    """
    return {
        "model": state.backend.model,
        "tools": [
            {
                "name": tool.name,
                "description": tool.description,
                "schema": tool.schema(),
            }
            for tool in state.tools
        ],
        "constraints": [
            "Every tool is read-only. Nothing the agent can call changes any state.",
            "Zones are validated against the current mode before any request is made.",
            "History windows are bounded; series are downsampled before reaching the model.",
            "Results carry provenance and estimation flags, and the prompt requires "
            "disclosing both.",
            "No shell, no filesystem, no arbitrary HTTP, no database handle.",
        ],
    }


@app.post("/api/v1/chat", tags=["agent"])
async def chat(state: Agent, body: ChatRequest, request: Request) -> EventSourceResponse:
    """One turn, streamed as Server-Sent Events.

    Event types: `text`, `tool_call`, `tool_result`, `done`, `error`.
    """

    async def stream() -> AsyncIterator[dict[str, str]]:
        if not state.backend.available():
            yield _event(
                "error",
                {
                    "message": (
                        "No ANTHROPIC_API_KEY is set, so the agent cannot think. The tools "
                        "themselves work without it — see GET /api/v1/tools, and the grid "
                        "API on port 8000."
                    ),
                    "kind": "no_key",
                },
            )
            return

        # The prompt is rebuilt each turn from live status, so the model is told which mode
        # it is in rather than having to infer it from a provenance field it might ignore.
        try:
            status = await state.client.status()
            zones = [zone["key"] for zone in await state.client.zones()]
        except GridUnavailable as exc:
            yield _event("error", {"message": str(exc), "kind": "lab_unreachable"})
            return

        system = system_prompt(
            mode=status.get("mode", "replay"),
            provenance=status.get("provenance", "synthetic"),
            zones=zones,
            now=status.get("now", ""),
        )

        conversation = Conversation(
            messages=[{"role": m.role, "content": m.content} for m in body.history]
        )
        context = ToolContext(
            client=state.client, max_points=state.settings.gridlab_agent_max_points
        )

        log.info("agent.turn", mode=status.get("mode"), zones=len(zones))

        try:
            async for event in state.backend.run(
                system=system,
                conversation=conversation,
                user_message=body.message,
                tools=state.tools,
                context=context,
            ):
                if await request.is_disconnected():
                    log.info("agent.client_disconnected")
                    return
                yield _translate(event)
        except Exception as exc:
            log.exception("agent.turn_failed")
            yield _event("error", {"message": f"{type(exc).__name__}: {exc}", "kind": "internal"})

    return EventSourceResponse(stream())


def _translate(event: Any) -> dict[str, str]:
    match event:
        case TextDelta():
            return _event("text", {"text": event.text})
        case ToolCall():
            return _event("tool_call", asdict(event))
        case ToolResult():
            return _event("tool_result", asdict(event))
        case TurnFinished():
            return _event("done", asdict(event))
        case AgentError():
            return _event("error", asdict(event))
    return _event("error", {"message": f"Unknown event {type(event).__name__}"})


def _event(name: str, payload: dict[str, Any]) -> dict[str, str]:
    return {"event": name, "data": json.dumps(payload, default=str)}
