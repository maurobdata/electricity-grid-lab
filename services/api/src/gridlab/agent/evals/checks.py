"""Deterministic checks over a transcript.

These run with no model, no key and no network, which makes them cheap enough to run on
every change. An LLM judge is reserved for the properties that genuinely need judgement
(:mod:`gridlab.agent.evals.judge`); everything here is decidable by looking.

The important one is :func:`numbers_are_grounded`. The agent's first rule is *never state a
number you did not get from a tool*, and that is mechanically checkable: pull every number
out of the answer and look for it in the tool traffic. No judge needed, no cost, no
flakiness — which makes it strictly better than an LLM for this particular property.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from gridlab.agent.evals.transcript import Transcript


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    detail: str = ""

    def __bool__(self) -> bool:
        return self.passed


#: Numbers in prose that are never data.
#:
#: A conservative list. Anything that also appears in the tool traffic is grounded anyway,
#: so this only matters for genuinely prose-y numbers — and being too generous here is how
#: a groundedness check quietly stops catching anything.
_PROSE_NUMBERS = frozenset({0, 1, 2, 100})

_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")

#: Timestamps, dates and zone keys are stripped before scanning, so their digits are not
#: mistaken for measurements.
#:
#: **Prose dates are the ones that caused trouble.** ISO timestamps were handled from the
#: start, but a live run on 24 August 2026 failed three cases on "on 23 August", "24 August"
#: and the bare year in "23 August 2026" — all correct answers, all reported as inventing a
#: figure. This is the check the README calls the most important one, and a check that cries
#: wolf on a calendar date is a check people learn to ignore.
_MONTHS = (
    r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?"
)

_STRIP = re.compile(
    r"\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?Z?)?"  # ISO timestamps
    r"|\b\d{1,2}:\d{2}\b"  # clock times
    # "23 August", "23 August 2026", "23rd Aug."
    rf"|\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{_MONTHS})\.?(?:,?\s+\d{{4}})?\b"
    # "August 23", "Aug 23, 2026"
    rf"|\b(?:{_MONTHS})\.?\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+\d{{4}})?\b"
    # The 2 in "gCO2eq/kWh" is a chemical formula, not a reading. It survived until now
    # only because 2 happens to sit on the prose allowlist below, which is a coincidence
    # rather than a reason.
    r"|CO2|CO₂"
    r"|\bDK-DK\d\b|\bNO-NO\d\b|\bSE-SE\d\b|\bIT-\w+\b",  # zone keys with digits
    re.IGNORECASE,
)


def _numbers(text: str) -> list[float]:
    return [float(match.group()) for match in _NUMBER.finditer(_STRIP.sub(" ", text))]


def _numbers_in(value: Any, into: set[float]) -> None:
    """Every number anywhere in a nested structure."""
    match value:
        case bool():
            return
        case int() | float():
            into.add(float(value))
        case str():
            into.update(_numbers(value))
        case dict():
            for item in value.values():
                _numbers_in(item, into)
        case list() | tuple():
            for item in value:
                _numbers_in(item, into)


def _grounded_values(transcript: Transcript) -> set[float]:
    """Everything the agent legitimately saw: tool results, its own arguments, the question.

    Arguments count because an answer may quote what was asked for ("the next 24 hours").
    The question counts because a user's own figure is not an invention.
    """
    values: set[float] = set()
    for tool in transcript.tools:
        _numbers_in(tool.result, values)
        _numbers_in(tool.arguments, values)
    _numbers_in(transcript.question, values)
    return values


def _matches(candidate: float, known: Iterable[float]) -> bool:
    """Whether a number in the answer can be explained by something the agent saw.

    Rounding is allowed, because an answer *should* say "75%" rather than "75.2318%".
    Scaling by 100 is allowed, because `estimated_fraction: 0.08` legitimately becomes
    "8% of points". Anything looser than that would stop the check catching inventions.
    """
    for value in known:
        if candidate == value:
            return True
        # The answer rounded a longer number.
        for places in (0, 1, 2):
            if round(value, places) == candidate:
                return True
        # Fraction rendered as a percentage, or the reverse.
        for scaled in (value * 100, value / 100):
            if candidate == scaled or round(scaled, 1) == candidate:
                return True
        # Small relative tolerance, for "about 540 MW" against 541.3.
        if value != 0 and abs(candidate - value) / abs(value) < 0.01:
            return True
    return False


def numbers_are_grounded(transcript: Transcript) -> CheckResult:
    """Every number in the answer traces to something a tool returned.

    **What this catches:** invented figures — the failure mode that matters, because a
    confidently wrong carbon intensity is worse than no answer at all.

    **What it does not catch:** arithmetic. An answer that says "the two views differ by
    5.6 points" is doing subtraction on grounded numbers, and 5.6 will not appear in any
    tool result. Such cases are reported as ungrounded and need a human or the judge to
    resolve. That is the honest trade: this check is precise about invention and imprecise
    about derivation, and it says so rather than pretending otherwise.
    """
    known = _grounded_values(transcript)
    ungrounded = [
        number
        for number in _numbers(transcript.answer)
        if number not in _PROSE_NUMBERS and not _matches(number, known)
    ]

    if not ungrounded:
        return CheckResult("numbers_are_grounded", True)
    return CheckResult(
        "numbers_are_grounded",
        False,
        f"Not found in any tool result: {sorted(set(ungrounded))}. "
        f"Either invented, or derived by arithmetic (which this check cannot verify).",
    )


def used_a_tool(transcript: Transcript) -> CheckResult:
    """The agent looked something up rather than answering from memory."""
    if transcript.tools:
        return CheckResult("used_a_tool", True, f"called {', '.join(transcript.tool_names)}")
    return CheckResult("used_a_tool", False, "answered without calling any tool")


def called(*expected: str) -> Any:
    """A check that the agent reached for at least one of these tools."""

    def check(transcript: Transcript) -> CheckResult:
        hit = set(transcript.tool_names) & set(expected)
        return CheckResult(
            f"called[{'|'.join(expected)}]",
            bool(hit),
            f"called {', '.join(transcript.tool_names) or 'nothing'}",
        )

    return check


def discloses_provenance(transcript: Transcript) -> CheckResult:
    """Replayed and generated data must be described as such.

    The single most consequential thing the agent can get wrong. Presenting a recording — or
    worse, a synthetic scenario — as the live state of a real grid is exactly the confusion
    the whole provenance contract exists to prevent.
    """
    if transcript.provenance == "live":
        return CheckResult("discloses_provenance", True, "live data needs no caveat")

    answer = transcript.answer.lower()
    wanted = {
        "recorded": ("record", "replay", "earlier", "not current", "at the time", "was "),
        "synthetic": ("synthetic", "generated", "not real", "made up", "not measured"),
    }[transcript.provenance]

    if any(word in answer for word in wanted):
        return CheckResult("discloses_provenance", True)
    return CheckResult(
        "discloses_provenance",
        False,
        f"Data was {transcript.provenance} but the answer never says so.",
    )


def names_the_breakdown(transcript: Transcript) -> CheckResult:
    """If the mix was fetched, the answer says which of the two views it used."""
    if "get_mix" not in transcript.tool_names:
        return CheckResult("names_the_breakdown", True, "no mix involved")

    answer = transcript.answer.lower()
    if any(
        word in answer
        for word in ("flow-traced", "flow traced", "production", "generated", "consumed", "imports")
    ):
        return CheckResult("names_the_breakdown", True)
    return CheckResult(
        "names_the_breakdown",
        False,
        "Used get_mix but never said whether it was production or flow-traced.",
    )


def admits_when_it_has_nothing(transcript: Transcript) -> CheckResult:
    """When every tool refused, the answer must say so rather than fill the gap."""
    if not transcript.all_tools_failed:
        return CheckResult("admits_when_it_has_nothing", True)

    answer = transcript.answer.lower()
    hedges = (
        "not available",
        "no data",
        "cannot",
        "can't",
        "unable",
        "does not",
        "doesn't",
        "unavailable",
        "no zone",
    )
    if any(word in answer for word in hedges):
        return CheckResult("admits_when_it_has_nothing", True)
    return CheckResult(
        "admits_when_it_has_nothing",
        False,
        "Every tool failed, yet the answer reads as though it knows something.",
    )


def answered_at_all(transcript: Transcript) -> CheckResult:
    if transcript.error:
        return CheckResult("answered_at_all", False, transcript.error)
    if not transcript.answer.strip():
        return CheckResult("answered_at_all", False, "empty answer")
    return CheckResult("answered_at_all", True)


def stayed_brief(limit: int = 1600) -> Any:
    """The prompt asks for brevity. Length is a cheap proxy for ignoring it."""

    def check(transcript: Transcript) -> CheckResult:
        length = len(transcript.answer)
        return CheckResult("stayed_brief", length <= limit, f"{length} characters")

    return check


#: Applied to every case, because they are properties of any good answer rather than of a
#: particular question.
UNIVERSAL = (
    answered_at_all,
    numbers_are_grounded,
    discloses_provenance,
    names_the_breakdown,
    admits_when_it_has_nothing,
    stayed_brief(),
)
