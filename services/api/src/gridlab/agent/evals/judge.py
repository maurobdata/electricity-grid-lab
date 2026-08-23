"""An LLM judge, and the means to check whether it is any good.

A judge is only worth its cost for properties that need judgement — "did it explain the
difference between the two mixes?" is not decidable by regular expression, while "did it
invent a number?" is, and that one is left to :mod:`gridlab.agent.evals.checks`.

The second half of this module matters as much as the first. **A judge is itself a model
that can be wrong**, so it is scored against hand-labelled examples and reported as true
positive and true negative rates — the alignment step from chapter 20 of *A Common-Sense
Guide to AI Engineering*. An unaligned judge is a number that feels like evidence and is
not.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog
from pydantic import BaseModel

from gridlab.agent.evals.transcript import Transcript

log = structlog.get_logger(__name__)

RUBRIC = """\
You are grading an assistant that answers questions about electricity grids. It has
read-only tools over the Electricity Maps API and is required to:

* never state a number it did not obtain from a tool;
* say when data is replayed (`recorded`) or generated (`synthetic`) rather than live;
* say which generation mix it used — what a zone produced, or what it consumed once
  imports are traced;
* admit when something is unavailable instead of filling the gap;
* avoid presenting a ranking of raw values as a measure of performance;
* be brief.

Grade only what you are asked about. Be strict: a plausible answer that quietly breaks one
of the rules above is a FAIL, because the whole point of this system is that its numbers
can be trusted.
"""


class Judgment(BaseModel):
    reasoning: str
    verdict: str  # "PASS" or "FAIL"


@dataclass
class JudgeResult:
    passed: bool
    reasoning: str
    criteria: tuple[str, ...]


class Judge:
    """Grades a transcript against the rubric plus any per-case criteria.

    Uses a smaller model than the agent under test. A judge applying a fixed rubric to a
    short transcript is a much easier task than answering the question was, and using the
    same expensive model for both doubles the bill for no gain.
    """

    def __init__(self, api_key: str | None, model: str = "claude-sonnet-5") -> None:
        self._api_key = api_key
        self._model = model
        self._client: Any = None

    @property
    def model(self) -> str:
        return self._model

    def available(self) -> bool:
        return bool(self._api_key)

    def _ensure(self) -> Any:
        if self._client is None:
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(api_key=self._api_key)
        return self._client

    async def grade(self, transcript: Transcript, criteria: tuple[str, ...] = ()) -> JudgeResult:
        client = self._ensure()

        response = await client.messages.parse(
            model=self._model,
            max_tokens=1024,
            system=RUBRIC,
            messages=[{"role": "user", "content": _render(transcript, criteria)}],
            output_format=Judgment,
        )
        judgment = response.parsed_output
        return JudgeResult(
            passed=judgment.verdict.strip().upper() == "PASS",
            reasoning=judgment.reasoning,
            criteria=criteria,
        )


def _render(transcript: Transcript, criteria: tuple[str, ...]) -> str:
    """The transcript, as the judge sees it.

    Tool results are included in full. Grading groundedness without seeing what the tools
    returned would be guessing, and a guessing judge is worse than none.
    """
    lines = [
        f"Session: mode={transcript.mode}, all data is `{transcript.provenance}`.",
        f"Zones available: {', '.join(transcript.zones) or 'unknown'}.",
        "",
        f"<question>{transcript.question}</question>",
        "",
        "<tool_calls>",
    ]
    if not transcript.tools:
        lines.append("(none — the assistant called no tools)")
    for tool in transcript.tools:
        status = "ok" if tool.ok else "FAILED"
        lines.append(f"{tool.name}({tool.arguments}) -> {status}: {tool.result}")
    lines += ["</tool_calls>", "", f"<answer>{transcript.answer or '(empty)'}</answer>", ""]

    if criteria:
        lines.append("Judge against these specific criteria, all of which must hold:")
        lines += [f"  {i}. {c}" for i, c in enumerate(criteria, 1)]
        lines.append("")

    lines.append("Reply with your reasoning and then a verdict of exactly PASS or FAIL.")
    return "\n".join(lines)


# --- is the judge any good? -------------------------------------------------


@dataclass
class Alignment:
    """How well the judge agrees with a human.

    True positive rate is agreement on the answers a human passed; true negative rate is
    agreement on the ones a human failed. Reported separately on purpose: a judge that
    passes everything scores 100% TPR and 0% TNR, and a single accuracy figure would hide
    that completely.
    """

    true_positive: int = 0
    false_negative: int = 0
    true_negative: int = 0
    false_positive: int = 0
    disagreements: list[dict[str, Any]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.disagreements is None:
            self.disagreements = []

    @property
    def tpr(self) -> float:
        total = self.true_positive + self.false_negative
        return self.true_positive / total if total else 0.0

    @property
    def tnr(self) -> float:
        total = self.true_negative + self.false_positive
        return self.true_negative / total if total else 0.0

    @property
    def usable(self) -> bool:
        """A rough bar for trusting the judge's verdicts on unlabelled transcripts.

        0.8 on both rates. Below that the judge disagrees with a human often enough that a
        run's numbers say more about the judge than the agent.
        """
        return self.tpr >= 0.8 and self.tnr >= 0.8

    def summary(self) -> str:
        return (
            f"TPR {self.tpr:.0%} "
            f"({self.true_positive}/{self.true_positive + self.false_negative}) · "
            f"TNR {self.tnr:.0%} "
            f"({self.true_negative}/{self.true_negative + self.false_positive})"
        )


async def align(judge: Judge, labelled: list[tuple[Transcript, bool]]) -> Alignment:
    """Score the judge against hand-labelled transcripts."""
    result = Alignment()

    for transcript, human_passed in labelled:
        verdict = await judge.grade(transcript)
        if human_passed and verdict.passed:
            result.true_positive += 1
        elif human_passed and not verdict.passed:
            result.false_negative += 1
            result.disagreements.append(
                {
                    "case": transcript.case_id,
                    "human": "PASS",
                    "judge": "FAIL",
                    "why": verdict.reasoning,
                }
            )
        elif not human_passed and not verdict.passed:
            result.true_negative += 1
        else:
            result.false_positive += 1
            result.disagreements.append(
                {
                    "case": transcript.case_id,
                    "human": "FAIL",
                    "judge": "PASS",
                    "why": verdict.reasoning,
                }
            )

    return result
