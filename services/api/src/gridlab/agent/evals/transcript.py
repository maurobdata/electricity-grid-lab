"""A transcript: one question, the tools it triggered, and the answer.

Everything downstream evaluates transcripts rather than live conversations. That split is
the whole design, and it comes straight from the error-analysis chapters of *A Common-Sense
Guide to AI Engineering*:

* a transcript can be **captured once and checked many times**, so improving a checker does
  not cost another set of model calls;
* the checkers can be **unit-tested offline**, against committed transcripts, with no key
  and no network;
* a failure can be **read** — the tool calls are right there next to the answer, which is
  usually enough to see what went wrong without reproducing it.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class ToolInvocation:
    name: str
    arguments: dict[str, Any]
    ok: bool
    result: Any
    duration_ms: float = 0.0


@dataclass
class Transcript:
    """One turn, in full."""

    question: str
    answer: str = ""
    tools: list[ToolInvocation] = field(default_factory=list)
    error: str | None = None
    rounds: int = 0

    #: The session the turn happened in. Provenance matters for grading: an answer that
    #: does not disclose synthetic data is a failure only when the data *was* synthetic.
    mode: str = "replay"
    provenance: str = "recorded"
    zones: list[str] = field(default_factory=list)

    case_id: str | None = None
    model: str | None = None
    captured_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    @property
    def tool_names(self) -> list[str]:
        return [tool.name for tool in self.tools]

    @property
    def all_tools_failed(self) -> bool:
        """True when the agent had nothing to work with. Different from having no tools."""
        return bool(self.tools) and all(not tool.ok for tool in self.tools)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Transcript:
        tools = [ToolInvocation(**tool) for tool in raw.get("tools", [])]
        return cls(**{**raw, "tools": tools})

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, default=str) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> Transcript:
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))

    @classmethod
    def load_all(cls, directory: Path) -> list[Transcript]:
        if not directory.is_dir():
            return []
        return [cls.load(path) for path in sorted(directory.glob("*.json"))]


async def capture(
    backend: Any,
    *,
    question: str,
    system: str,
    tools: Any,
    context: Any,
    case_id: str | None = None,
    mode: str = "replay",
    provenance: str = "recorded",
    zones: list[str] | None = None,
) -> Transcript:
    """Run one turn and record everything that happened.

    Consumes the same event stream the SSE endpoint does, so a captured transcript is
    exactly what a user would have seen — not a separate code path that might diverge from
    the one being shipped.
    """
    from gridlab.agent.llm import (
        AgentError,
        Conversation,
        TextDelta,
        ToolCall,
        ToolResult,
        TurnFinished,
    )

    transcript = Transcript(
        question=question,
        case_id=case_id,
        mode=mode,
        provenance=provenance,
        zones=zones or [],
        model=getattr(backend, "model", None),
    )
    pending: dict[str, ToolInvocation] = {}

    async for event in backend.run(
        system=system,
        conversation=Conversation(),
        user_message=question,
        tools=tools,
        context=context,
    ):
        match event:
            case TextDelta():
                transcript.answer += event.text
            case ToolCall():
                started = ToolInvocation(
                    name=event.name, arguments=event.arguments, ok=False, result=None
                )
                pending[event.id] = started
                transcript.tools.append(started)
            case ToolResult():
                if (finished := pending.get(event.id)) is not None:
                    finished.ok = event.ok
                    finished.result = event.content
                    finished.duration_ms = event.duration_ms
            case TurnFinished():
                transcript.rounds = event.rounds
            case AgentError():
                transcript.error = event.message

    return transcript
