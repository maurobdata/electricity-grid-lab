"""The eval harness.

    make eval                 # run the cases against the live agent, then check
    make eval ARGS=--offline  # re-check committed transcripts, no key needed
    make eval ARGS=--judge    # add the LLM judge
    make eval ARGS=--align    # score the judge against hand-labelled transcripts

Two modes, and the split is the point. Capturing a transcript costs model calls; checking
one costs nothing. So capture is a separate step, transcripts are written to disk, and
every later run of the checkers is free. Improving a checker never means paying for the
answers again.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from gridlab.agent.evals import checks
from gridlab.agent.evals.cases import Case, build_cases
from gridlab.agent.evals.judge import Alignment, Judge, JudgeResult, align
from gridlab.agent.evals.transcript import Transcript, capture
from gridlab.agent.gridclient import GridClient
from gridlab.agent.llm import AnthropicBackend
from gridlab.agent.prompts import system_prompt
from gridlab.agent.tools import ToolContext, build_tools
from gridlab.config import get_settings

TRANSCRIPTS = Path("/app/evals/transcripts")
EXAMPLES = Path("/app/evals/examples")


@dataclass
class CaseOutcome:
    case_id: str
    rationale: str
    transcript: Transcript
    results: list[checks.CheckResult] = field(default_factory=list)
    judgment: JudgeResult | None = None

    @property
    def passed(self) -> bool:
        deterministic = all(result.passed for result in self.results)
        return deterministic and (self.judgment is None or self.judgment.passed)

    @property
    def failures(self) -> list[checks.CheckResult]:
        return [result for result in self.results if not result.passed]


# --- capture ----------------------------------------------------------------


async def capture_all(cases: list[Case], out: Path) -> list[Transcript]:
    """Run every case against the live agent and write the transcripts."""
    settings = get_settings()
    key = settings.anthropic_api_key
    if not key:
        print(
            "No ANTHROPIC_API_KEY. Use --offline to check committed transcripts.", file=sys.stderr
        )
        return []

    client = GridClient(settings.gridlab_api_url, timeout=settings.gridlab_http_timeout)
    backend = AnthropicBackend(key.get_secret_value(), settings.gridlab_agent_model)
    tools = build_tools()

    try:
        status = await client.status()
        zones = [zone["key"] for zone in await client.zones()]
        if not zones:
            print("The lab reports no zones. Is the API running?", file=sys.stderr)
            return []

        system = system_prompt(
            mode=status.get("mode", "replay"),
            provenance=status.get("provenance", "recorded"),
            zones=zones,
            now=status.get("now", ""),
        )

        transcripts: list[Transcript] = []
        for case in cases:
            if case.needs_zones > len(zones):
                print(f"  skipped  {case.id}: needs {case.needs_zones} zones, {len(zones)} loaded")
                continue

            question = case.question.format(
                zone=zones[0], zones=" and ".join(zones[: max(2, case.needs_zones)])
            )
            print(f"  running  {case.id}…", flush=True)

            transcript = await capture(
                backend,
                question=question,
                system=system,
                tools=tools,
                # A fresh context per case: a cached zone list carried between cases would
                # hide a tool that fails to fetch one.
                context=ToolContext(client=client, max_points=settings.gridlab_agent_max_points),
                case_id=case.id,
                mode=status.get("mode", "replay"),
                provenance=status.get("provenance", "recorded"),
                zones=zones,
            )
            transcript.save(out / f"{case.id}.json")
            transcripts.append(transcript)

        return transcripts
    finally:
        await client.aclose()


# --- check ------------------------------------------------------------------


def check_all(transcripts: list[Transcript], cases: list[Case]) -> list[CaseOutcome]:
    by_id = {case.id: case for case in cases}
    outcomes: list[CaseOutcome] = []

    for transcript in transcripts:
        case = by_id.get(transcript.case_id or "")
        applicable = [*checks.UNIVERSAL, *(case.extra_checks if case else ())]
        outcomes.append(
            CaseOutcome(
                case_id=transcript.case_id or "unknown",
                rationale=case.rationale if case else "",
                transcript=transcript,
                results=[check(transcript) for check in applicable],
            )
        )

    return outcomes


async def judge_all(outcomes: list[CaseOutcome], cases: list[Case], judge: Judge) -> None:
    by_id = {case.id: case for case in cases}
    for outcome in outcomes:
        case = by_id.get(outcome.case_id)
        outcome.judgment = await judge.grade(
            outcome.transcript, case.judge_criteria if case else ()
        )


# --- reporting --------------------------------------------------------------


def report(outcomes: list[CaseOutcome]) -> bool:
    passed = sum(1 for outcome in outcomes if outcome.passed)
    print(f"\n{'=' * 72}\n{passed}/{len(outcomes)} cases passed\n{'=' * 72}")

    for outcome in outcomes:
        mark = "PASS" if outcome.passed else "FAIL"
        print(f"\n[{mark}] {outcome.case_id}")
        print(f"       {outcome.transcript.question}")
        print(f"       tools: {', '.join(outcome.transcript.tool_names) or 'none'}")

        if not outcome.passed and outcome.rationale:
            print(f"       why this case exists: {outcome.rationale}")

        for failure in outcome.failures:
            print(f"       x {failure.name}: {failure.detail}")

        if outcome.judgment and not outcome.judgment.passed:
            print(f"       x judge: {outcome.judgment.reasoning[:300]}")

        if not outcome.passed:
            answer = outcome.transcript.answer.replace("\n", " ")[:240]
            print(f"       answer: {answer or '(empty)'}")

    # Which checks fail most often is more actionable than which cases do — it points at a
    # prompt or a tool, where a case only points at a question.
    tally: dict[str, int] = {}
    for outcome in outcomes:
        for failure in outcome.failures:
            tally[failure.name] = tally.get(failure.name, 0) + 1
    if tally:
        print("\nMost frequent failures:")
        for name, count in sorted(tally.items(), key=lambda pair: -pair[1]):
            print(f"  {count}x  {name}")

    return passed == len(outcomes)


async def run_alignment(judge: Judge) -> Alignment | None:
    """Score the judge itself against hand-labelled transcripts."""
    labelled: list[tuple[Transcript, bool]] = []
    for path in sorted(EXAMPLES.glob("*.json")) if EXAMPLES.is_dir() else []:
        raw = json.loads(path.read_text(encoding="utf-8"))
        verdict = raw.pop("_human_verdict", None)
        raw.pop("_why", None)
        if verdict is None:
            print(f"  {path.name} has no _human_verdict; skipping", file=sys.stderr)
            continue
        labelled.append((Transcript.from_dict(raw), verdict == "PASS"))

    if not labelled:
        print("No labelled transcripts in evals/examples/. Nothing to align against.")
        return None

    print(f"\nScoring the judge against {len(labelled)} hand-labelled transcripts…")
    result = await align(judge, labelled)

    print(f"\nJudge alignment: {result.summary()}")
    if not result.usable:
        print(
            "  ! The judge disagrees with the human too often to be trusted on unlabelled\n"
            "  ! transcripts. Its verdicts say more about the judge than about the agent.\n"
            "  ! Fix the rubric before believing a run's judge column."
        )
    for disagreement in result.disagreements:
        print(
            f"  - {disagreement['case']}: "
            f"human {disagreement['human']}, judge {disagreement['judge']}"
        )
        print(f"    {disagreement['why'][:200]}")

    return result


async def main_async(args: argparse.Namespace) -> int:
    cases = build_cases()
    settings = get_settings()
    key = settings.anthropic_api_key

    judge = Judge(key.get_secret_value() if key else None, args.judge_model)

    if args.align:
        if not judge.available():
            print("Alignment needs ANTHROPIC_API_KEY.", file=sys.stderr)
            return 2
        result = await run_alignment(judge)
        return 0 if result and result.usable else 1

    if args.offline:
        transcripts = Transcript.load_all(TRANSCRIPTS)
        if transcripts:
            print(f"Checking {len(transcripts)} captured transcripts (no model calls).")
        else:
            # Falling back to the hand-written examples keeps `--offline` useful on a fresh
            # clone — but they are constructed cases, several built specifically to fail,
            # so the pass rate below is a property of the checkers, not of the agent.
            transcripts = _load_examples()
            if not transcripts:
                print(f"Nothing to check in {TRANSCRIPTS} or {EXAMPLES}.", file=sys.stderr)
                return 2
            print(
                f"No captured transcripts yet, so checking the {len(transcripts)} hand-written\n"
                f"examples in evals/examples/ instead. Several are built to fail on purpose —\n"
                f"this exercises the checkers, and says nothing about the agent.\n"
            )
            args.expect_failures = True
    else:
        print(f"Running {len(cases)} cases against the live agent.\n")
        transcripts = await capture_all(cases, TRANSCRIPTS)
        if not transcripts:
            return 2

    outcomes = check_all(transcripts, cases)

    if args.judge:
        if not judge.available():
            print("--judge needs ANTHROPIC_API_KEY; skipping.", file=sys.stderr)
        else:
            print(f"\nGrading with {judge.model}…")
            await judge_all(outcomes, cases, judge)

    all_passed = report(outcomes)

    if getattr(args, "expect_failures", False):
        # The examples include cases built to fail. Exiting non-zero would make a green
        # suite impossible and train everyone to ignore the result.
        print(
            "\nThose were the hand-written examples, not a run. Several are meant to fail; "
            "what this shows is that the checkers still catch them."
        )
        return 0

    return 0 if all_passed else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Re-check committed transcripts instead of capturing new ones. No key needed.",
    )
    parser.add_argument("--judge", action="store_true", help="Also grade with an LLM judge.")
    parser.add_argument(
        "--align",
        action="store_true",
        help="Score the judge against hand-labelled transcripts and report TPR/TNR.",
    )
    parser.add_argument("--judge-model", default="claude-sonnet-5")
    args = parser.parse_args()
    args.expect_failures = False

    return asyncio.run(main_async(args))


def _load_examples() -> list[Transcript]:
    """The hand-written examples, with their human labels stripped.

    Used only as a fallback for `--offline` on a fresh clone. They are fixtures for the
    checkers, not a record of anything the agent did.
    """
    transcripts: list[Transcript] = []
    for path in sorted(EXAMPLES.glob("*.json")) if EXAMPLES.is_dir() else []:
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw.pop("_human_verdict", None)
        raw.pop("_why", None)
        transcripts.append(Transcript.from_dict(raw))
    return transcripts


if __name__ == "__main__":
    raise SystemExit(main())
