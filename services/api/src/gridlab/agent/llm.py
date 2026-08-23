"""The provider seam, and the agent loop.

The loop is written out rather than delegated to the SDK's `tool_runner`. Three reasons,
in order of weight:

1. **Event ordering.** The UI renders the tool trace inline — tool call, then result, then
   the text that used it. That requires emitting events at points inside the loop, and the
   runner owns the loop.
2. **No beta dependency in the foundation's core.** The runner is beta; this is meant to
   still work in three weeks.
3. It is about forty lines, and it is the loop *A Common-Sense Guide to AI Engineering*
   teaches in chapter 13 — the reference material this project was asked to build from.

The seam is deliberately thin. What actually varies between providers is the message
format, the tool schema, and the stream events; :class:`LLMBackend` normalises exactly
those three and nothing else. A second provider is one file, not a rewrite.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

import structlog

from gridlab import telemetry
from gridlab.agent.gridclient import GridUnavailable
from gridlab.agent.tools import ToolContext, ToolSpec

log = structlog.get_logger(__name__)

#: Ceiling on tool-calling rounds within one user turn.
#:
#: Not a safety boundary — the tools are read-only, so a runaway loop wastes tokens rather
#: than doing damage. It is a cost and latency bound. Six is comfortably more than any
#: question this lab can currently answer needs; four is the most observed.
MAX_ROUNDS = 6


# --- events -----------------------------------------------------------------


@dataclass(frozen=True)
class TextDelta:
    text: str


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    id: str
    name: str
    ok: bool
    content: Any
    duration_ms: float


@dataclass(frozen=True)
class TurnFinished:
    stop_reason: str | None
    rounds: int
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass(frozen=True)
class AgentError:
    message: str
    kind: str = "error"


AgentEvent = TextDelta | ToolCall | ToolResult | TurnFinished | AgentError


@dataclass
class Conversation:
    """Message history, in the backend's own format.

    Opaque on purpose. Normalising history across providers would mean inventing a lowest
    common denominator for thinking blocks, tool-use ids and content-block shapes — a lot
    of abstraction to support a second provider nobody has asked for. The backend that
    produced a history is the one that consumes it.
    """

    messages: list[Any] = field(default_factory=list)


class LLMBackend(Protocol):
    """One turn of conversation, as a stream of events."""

    @property
    def model(self) -> str: ...

    def available(self) -> bool:
        """Whether this backend is configured enough to be used at all."""
        ...

    def run(
        self,
        *,
        system: str,
        conversation: Conversation,
        user_message: str,
        tools: Sequence[ToolSpec],
        context: ToolContext,
    ) -> AsyncIterator[AgentEvent]: ...


# --- Anthropic --------------------------------------------------------------


class AnthropicBackend:
    """Claude, via the Anthropic SDK."""

    def __init__(self, api_key: str | None, model: str = "claude-opus-5") -> None:
        self._api_key = api_key
        self._model = model
        self._client: Any = None

    @property
    def model(self) -> str:
        return self._model

    def available(self) -> bool:
        return bool(self._api_key)

    def _ensure_client(self) -> Any:
        if self._client is None:
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(api_key=self._api_key)
        return self._client

    @staticmethod
    def _tool_payload(tools: Sequence[ToolSpec]) -> list[dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                # Strict mode plus `additionalProperties: false` means a hallucinated
                # argument is rejected by the API rather than arriving in our handler.
                "strict": True,
                "input_schema": tool.schema(),
            }
            for tool in tools
        ]

    async def run(
        self,
        *,
        system: str,
        conversation: Conversation,
        user_message: str,
        tools: Sequence[ToolSpec],
        context: ToolContext,
    ) -> AsyncIterator[AgentEvent]:
        import anthropic

        client = self._ensure_client()
        by_name = {tool.name: tool for tool in tools}
        payload = self._tool_payload(tools)

        conversation.messages.append({"role": "user", "content": user_message})

        rounds = 0
        input_tokens = 0
        output_tokens = 0

        while rounds < MAX_ROUNDS:
            rounds += 1
            stream_kwargs: dict[str, Any] = {
                "model": self._model,
                "max_tokens": 4096,
                "system": system,
                "messages": conversation.messages,
                "tools": payload,
            }
            if _supports_adaptive_thinking(self._model):
                # Adaptive lets capable models decide how much to think. Haiku currently
                # rejects it, and the cheaper model is useful for local smoke tests.
                stream_kwargs["thinking"] = {"type": "adaptive"}
            try:
                async with client.messages.stream(**stream_kwargs) as stream:
                    async for chunk in stream.text_stream:
                        yield TextDelta(chunk)
                    message = await stream.get_final_message()
            except anthropic.APIStatusError as exc:
                log.error("agent.api_error", status=exc.status_code, error=str(exc))
                yield AgentError(_explain(exc), kind="api")
                return
            except anthropic.APIError as exc:
                log.error("agent.transport_error", error=str(exc))
                yield AgentError(f"Could not reach the model: {exc}", kind="transport")
                return

            if message.usage:
                input_tokens += message.usage.input_tokens or 0
                output_tokens += message.usage.output_tokens or 0

            conversation.messages.append({"role": "assistant", "content": message.content})

            calls = [block for block in message.content if block.type == "tool_use"]
            if not calls:
                yield TurnFinished(message.stop_reason, rounds, input_tokens, output_tokens)
                return

            results: list[dict[str, Any]] = []
            for call in calls:
                arguments = dict(call.input) if isinstance(call.input, dict) else {}
                yield ToolCall(call.id, call.name, arguments)

                outcome, ok, elapsed = await _invoke(by_name, call.name, arguments, context)
                yield ToolResult(call.id, call.name, ok, outcome, elapsed)

                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": call.id,
                        "content": json.dumps(outcome, default=str),
                        # A failed tool is reported to the model rather than swallowed, so
                        # it can correct itself — usually by fixing a zone key.
                        **({"is_error": True} if not ok else {}),
                    }
                )

            # All results go back in one user message. Splitting them teaches the model to
            # stop making parallel calls.
            conversation.messages.append({"role": "user", "content": results})

        yield AgentError(
            f"Stopped after {MAX_ROUNDS} rounds of tool calls without reaching an answer.",
            kind="max_rounds",
        )


async def _invoke(
    by_name: dict[str, ToolSpec],
    name: str,
    arguments: dict[str, Any],
    context: ToolContext,
) -> tuple[Any, bool, float]:
    """Run one tool, converting every failure into something the model can read."""
    import time

    started = time.perf_counter()
    tool = by_name.get(name)
    if tool is None:
        # Only reachable if the model invents a name, which strict schemas should prevent.
        return {"error": f"No tool named {name!r}."}, False, 0.0

    with telemetry.span("agent.tool", tool=name, **_span_args(arguments)) as current:
        try:
            result = await tool.handler(context, **arguments)
            ok = True
        except GridUnavailable as exc:
            # The expected failure: a zone that does not exist, a signal outside the plan,
            # a window nobody has. This is an answer, not a crash.
            result = {"error": str(exc)}
            ok = False
        except TypeError as exc:
            result = {"error": f"Wrong arguments for {name}: {exc}"}
            ok = False
        except Exception as exc:
            log.exception("agent.tool_failed", tool=name)
            result = {"error": f"{name} failed unexpectedly: {type(exc).__name__}."}
            ok = False

        elapsed = round((time.perf_counter() - started) * 1000, 1)
        telemetry.record(current, ok=ok, duration_ms=elapsed, provenance=result.get("provenance"))

    log.info("agent.tool", tool=name, ok=ok, ms=elapsed, args=arguments)
    return result, ok, elapsed


def _supports_adaptive_thinking(model: str) -> bool:
    """Whether to send Anthropic's adaptive thinking option for this model."""
    return "haiku" not in model.lower()


def _span_args(arguments: dict[str, Any]) -> dict[str, Any]:
    """Tool arguments, flattened for a span. Scalars only; a nested object is not a tag."""
    return {
        f"arg.{key}": value
        for key, value in arguments.items()
        if isinstance(value, str | int | float | bool)
    }


def _explain(exc: Any) -> str:
    """Turn an API status error into something worth showing a user."""
    status = getattr(exc, "status_code", None)
    if status == 401:
        return "The Anthropic API rejected the key. Check ANTHROPIC_API_KEY in .env."
    if status == 429:
        return "Rate limited by the Anthropic API. Try again in a moment."
    if status == 400:
        return f"The model rejected the request: {exc}"
    return f"The model returned an error ({status})."
