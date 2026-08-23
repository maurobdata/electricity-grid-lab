"""The eval checkers, tested against the labelled examples.

A checker that has stopped catching anything looks exactly like a checker that has nothing
to catch. So each one is run against a transcript built to break it, and the test fails if
it passes. Without that, an eval suite degrades into decoration — green, and meaningless.

Everything here is offline: no model, no key, no network.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gridlab.agent.evals import checks
from gridlab.agent.evals.cases import build_cases
from gridlab.agent.evals.judge import Alignment
from gridlab.agent.evals.transcript import ToolInvocation, Transcript

EXAMPLES = Path("/app/evals/examples")

pytestmark = pytest.mark.skipif(
    not EXAMPLES.is_dir() or not list(EXAMPLES.glob("*.json")),
    reason="evals/examples not mounted",
)


def example(name: str) -> Transcript:
    raw = json.loads((EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))
    raw.pop("_human_verdict", None)
    raw.pop("_why", None)
    return Transcript.from_dict(raw)


def transcript(**overrides: object) -> Transcript:
    base: dict[str, object] = {
        "question": "How clean is DK-DK2?",
        "answer": "",
        "provenance": "live",
        "tools": [],
    }
    return Transcript(**{**base, **overrides})  # type: ignore[arg-type]


def tool(result: object, *, name: str = "get_current_grid", ok: bool = True) -> ToolInvocation:
    return ToolInvocation(name=name, arguments={"zone": "DK-DK2"}, ok=ok, result=result)


# --- groundedness: the one that matters -------------------------------------


def test_a_number_from_a_tool_is_grounded() -> None:
    result = checks.numbers_are_grounded(
        transcript(answer="It is 63 gCO2eq/kWh.", tools=[tool({"value": 63.0})])
    )
    assert result.passed


def test_an_invented_number_is_caught() -> None:
    """The failure this whole system exists to prevent."""
    result = checks.numbers_are_grounded(example("invented_number"))
    assert not result.passed
    assert "210" in result.detail


def test_rounding_is_allowed() -> None:
    """An answer should say 75%, not 75.2318%. Punishing that would train verbosity."""
    assert checks.numbers_are_grounded(
        transcript(answer="Wind is 75%.", tools=[tool({"percent": 75.2318})])
    ).passed


def test_a_fraction_rendered_as_a_percentage_is_allowed() -> None:
    """`estimated_fraction: 0.08` legitimately becomes "8% of points"."""
    assert checks.numbers_are_grounded(
        transcript(
            answer="8% of the points were modelled.", tools=[tool({"estimated_fraction": 0.08})]
        )
    ).passed


def test_a_number_the_user_supplied_is_not_an_invention() -> None:
    """The leading-question case: quoting back what was asked is not making it up."""
    assert checks.numbers_are_grounded(
        transcript(
            question="I heard it was 450 gCO2eq/kWh — is that right?",
            answer="No — 450 is well above the recorded 63 gCO2eq/kWh.",
            tools=[tool({"value": 63.0})],
        )
    ).passed


def test_timestamps_are_not_mistaken_for_measurements() -> None:
    assert checks.numbers_are_grounded(
        transcript(
            answer="At 2026-08-22T17:00:00Z the value was 63 gCO2eq/kWh.",
            tools=[tool({"value": 63.0, "at": "2026-08-22T17:00:00Z"})],
        )
    ).passed


def test_zone_keys_containing_digits_are_not_measurements() -> None:
    assert checks.numbers_are_grounded(
        transcript(answer="DK-DK2 and SE-SE4 were both clean.", tools=[tool({"value": 63.0})])
    ).passed


def test_a_number_nested_deep_in_a_tool_result_still_counts() -> None:
    assert checks.numbers_are_grounded(
        transcript(
            answer="Wind was 546.1 MW.",
            tools=[tool({"sources": [{"source": "wind", "mw": 546.1}]})],
        )
    ).passed


def test_the_check_reports_what_it_cannot_verify() -> None:
    """Arithmetic on grounded numbers is flagged rather than silently passed.

    The docstring promises this is a limitation, not a capability. Pinning it means nobody
    later reads a red line as proof of invention when it is really subtraction.
    """
    result = checks.numbers_are_grounded(
        transcript(
            answer="The two views differ by 4.6 points.",
            tools=[tool({"a": 79.8, "b": 75.2})],
        )
    )
    assert not result.passed
    assert "derived by arithmetic" in result.detail


# --- provenance disclosure --------------------------------------------------


def test_synthetic_data_presented_as_real_is_caught() -> None:
    assert not checks.discloses_provenance(example("undisclosed_synthetic")).passed


def test_saying_it_is_generated_passes() -> None:
    assert checks.discloses_provenance(
        transcript(provenance="synthetic", answer="These are generated figures, not measured.")
    ).passed


def test_recorded_data_described_as_replayed_passes() -> None:
    assert checks.discloses_provenance(example("good_current_conditions")).passed


def test_live_data_needs_no_caveat() -> None:
    assert checks.discloses_provenance(transcript(provenance="live", answer="63 g.")).passed


# --- the other checkers -----------------------------------------------------


def test_answering_without_a_tool_is_caught() -> None:
    assert not checks.used_a_tool(example("answered_from_memory")).passed


def test_using_the_mix_without_naming_the_view_is_caught() -> None:
    assert not checks.names_the_breakdown(example("unnamed_breakdown")).passed


def test_naming_the_view_passes() -> None:
    assert checks.names_the_breakdown(example("good_flow_tracing")).passed


def test_the_check_is_skipped_when_no_mix_was_fetched() -> None:
    assert checks.names_the_breakdown(example("good_current_conditions")).passed


def test_filling_a_gap_after_every_tool_failed_is_caught() -> None:
    assert not checks.admits_when_it_has_nothing(example("filled_the_gap")).passed


def test_admitting_the_gap_passes() -> None:
    assert checks.admits_when_it_has_nothing(example("good_unavailable")).passed


def test_a_partial_failure_is_not_treated_as_nothing() -> None:
    """One failed tool among several is normal. Only a total blank demands a hedge."""
    assert checks.admits_when_it_has_nothing(
        transcript(
            answer="It was 63 gCO2eq/kWh.",
            tools=[tool({"error": "nope"}, ok=False), tool({"value": 63.0})],
        )
    ).passed


def test_an_empty_answer_fails() -> None:
    assert not checks.answered_at_all(transcript(answer="   ")).passed


def test_an_errored_turn_fails() -> None:
    assert not checks.answered_at_all(transcript(answer="hi", error="rate limited")).passed


def test_called_matches_any_of_the_named_tools() -> None:
    check = checks.called("get_mix", "get_flows")
    assert check(transcript(tools=[tool({}, name="get_flows")])).passed
    assert not check(transcript(tools=[tool({}, name="get_price")])).passed


# --- the whole suite against the labelled set -------------------------------


def test_every_example_labelled_pass_survives_the_deterministic_checks() -> None:
    """The labels and the checkers must agree on the good cases.

    If a checker rejects an answer a human called good, the checker is wrong — that is the
    direction of authority, and it is worth a failing test rather than a shrug.
    """
    for path in sorted(EXAMPLES.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        if raw.get("_human_verdict") != "PASS":
            continue

        script = example(path.stem)
        failures = [c(script) for c in checks.UNIVERSAL if not c(script).passed]
        assert not failures, f"{path.name} is labelled PASS but failed {[f.name for f in failures]}"


def test_every_example_labelled_fail_is_caught_by_something() -> None:
    """Each FAIL example exists to break one checker. If none fire, the example is stale or
    the checker has quietly stopped working."""
    for path in sorted(EXAMPLES.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        if raw.get("_human_verdict") != "FAIL":
            continue

        script = example(path.stem)
        applicable = [*checks.UNIVERSAL, checks.used_a_tool]
        failures = [c(script) for c in applicable if not c(script).passed]
        assert failures, f"{path.name} is labelled FAIL but every checker passed it"


def test_the_labelled_set_contains_both_verdicts() -> None:
    """A set of only good answers gives a judge that passes everything a perfect score."""
    verdicts = {
        json.loads(p.read_text(encoding="utf-8")).get("_human_verdict")
        for p in EXAMPLES.glob("*.json")
    }
    assert verdicts == {"PASS", "FAIL"}


# --- cases ------------------------------------------------------------------


def test_every_case_explains_why_it_exists() -> None:
    """The rationale is printed when a case fails, so a red line explains itself."""
    for case in build_cases():
        assert len(case.rationale) > 40, case.id


def test_case_ids_are_unique() -> None:
    ids = [case.id for case in build_cases()]
    assert len(ids) == len(set(ids))


def test_cases_cover_the_failure_modes_that_matter() -> None:
    ids = {case.id for case in build_cases()}
    assert {"flow_tracing", "unavailable_zone", "leading_question", "comparison"} <= ids


# --- judge alignment arithmetic ---------------------------------------------


def test_a_judge_that_passes_everything_scores_zero_on_negatives() -> None:
    """Why the two rates are reported separately. A single accuracy figure would hide this
    completely, and a judge that never says FAIL is worthless."""
    alignment = Alignment(true_positive=5, false_negative=0, true_negative=0, false_positive=5)
    assert alignment.tpr == 1.0
    assert alignment.tnr == 0.0
    assert not alignment.usable


def test_a_well_aligned_judge_is_usable() -> None:
    alignment = Alignment(true_positive=9, false_negative=1, true_negative=9, false_positive=1)
    assert alignment.usable
    assert "TPR 90%" in alignment.summary()


def test_disagreements_start_empty_rather_than_shared() -> None:
    """A mutable default would make every Alignment share one list."""
    assert Alignment().disagreements == []
    assert Alignment().disagreements is not Alignment().disagreements


# --- transcripts ------------------------------------------------------------


def test_a_transcript_round_trips_through_json(tmp_path: Path) -> None:
    original = example("good_flow_tracing")
    path = tmp_path / "t.json"
    original.save(path)
    restored = Transcript.load(path)

    assert restored.question == original.question
    assert restored.answer == original.answer
    assert len(restored.tools) == len(original.tools)
    assert restored.tools[0].name == original.tools[0].name


def test_all_tools_failed_distinguishes_from_no_tools() -> None:
    """ "Everything refused" and "nothing was asked" call for different answers."""
    assert example("filled_the_gap").all_tools_failed
    assert not example("answered_from_memory").all_tools_failed
