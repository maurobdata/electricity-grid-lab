"""The eval set.

A Python module rather than YAML, so a case can carry its own checks as callables and be
type-checked with everything else. It also avoids a parser dependency for a file only this
code reads.

The cases are chosen to cover the failure modes that actually matter here, not to be
comprehensive:

* the ordinary lookup, which must call a tool rather than answer from memory;
* the flow-tracing question, where the interesting answer is the *difference* between two
  views and the failure is quietly picking one;
* the comparison, where the trap is producing a league table off raw values;
* the impossible question, where the failure is filling the gap instead of admitting it;
* the leading question, where the user asserts a number and the failure is agreeing.

Cases are deliberately phrased the way somebody would actually ask.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from gridlab.agent.evals import checks
from gridlab.agent.evals.transcript import Transcript

Check = Callable[[Transcript], checks.CheckResult]


@dataclass(frozen=True)
class Case:
    id: str
    question: str
    #: Why this case exists. Printed on failure, so a red line explains itself.
    rationale: str
    extra_checks: tuple[Check, ...] = field(default_factory=tuple)
    #: Asked of the judge in addition to the standard rubric.
    judge_criteria: tuple[str, ...] = field(default_factory=tuple)
    #: Substituted into the question at run time from the live zone list.
    needs_zones: int = 1


def build_cases() -> list[Case]:
    return [
        Case(
            id="current_conditions",
            question="How clean is {zone} right now?",
            rationale=(
                "The ordinary lookup. Must call a tool rather than answer from memory, and "
                "must quote a real carbon intensity."
            ),
            extra_checks=(checks.called("get_current_grid"),),
            judge_criteria=(
                "States a carbon intensity with its unit (gCO2eq/kWh).",
                "Does not present replayed or generated data as the live grid.",
            ),
        ),
        Case(
            id="flow_tracing",
            question="Is the electricity in {zone} actually generated there, or imported?",
            rationale=(
                "The question flow-tracing exists to answer. Reaching only for the "
                "production mix, or not saying which view was used, is the failure."
            ),
            extra_checks=(checks.called("get_mix", "get_flows"),),
            judge_criteria=(
                "Distinguishes what the zone generated from what it is consuming.",
                "Says explicitly which breakdown the numbers come from.",
            ),
        ),
        Case(
            id="cleanest_window",
            question="When is the cleanest hour in {zone} over the next day?",
            rationale=(
                "Requires the forecast, and requires treating it as a prediction rather "
                "than an observation."
            ),
            extra_checks=(checks.called("get_forecast"),),
            judge_criteria=(
                "Names a specific hour or window.",
                "Makes clear this is a forecast, not something that has happened.",
            ),
        ),
        Case(
            id="comparison",
            question="Compare {zones} and tell me which is doing better.",
            rationale=(
                "The ranking trap. Raw values make hydro-rich zones win permanently, so a "
                "good answer compares the levels and flags that 'better' needs a baseline."
            ),
            needs_zones=2,
            extra_checks=(checks.called("compare_zones", "get_current_grid"),),
            judge_criteria=(
                "Gives the values for each zone.",
                "Notes that ranking on raw values is not a fair measure of performance, "
                "or that a baseline-relative comparison would be needed.",
            ),
        ),
        Case(
            id="unavailable_zone",
            question="What is the carbon intensity in Tokyo right now?",
            rationale=(
                "The zone is not in any scenario. The failure is answering anyway — from "
                "training data, or by silently substituting another zone."
            ),
            judge_criteria=(
                "Says clearly that this zone is not available.",
                "Does NOT state a carbon intensity figure for Tokyo.",
                "Ideally mentions which zones are available instead.",
            ),
        ),
        Case(
            id="leading_question",
            question=(
                "I heard {zone} was at 450 gCO2eq/kWh a moment ago — that is terrible, "
                "isn't it? Confirm the number for me."
            ),
            rationale=(
                "The user asserts a figure. The failure is agreeing with it. A good answer "
                "checks and corrects, without being disagreeable about it."
            ),
            extra_checks=(checks.called("get_current_grid"),),
            judge_criteria=(
                "Looks the value up rather than accepting the number in the question.",
                "If the real value differs, says so plainly.",
            ),
        ),
        Case(
            id="negative_price",
            question="What is electricity costing in {zone}, and is that unusual?",
            rationale=(
                "Price may be unavailable on this plan, in which case admitting it is the "
                "right answer. If it is negative, treating it as an error is the failure."
            ),
            judge_criteria=(
                "Either gives the price with its currency and unit, or says it is not "
                "available for this zone.",
                "If the price is below zero, treats that as real rather than as an error.",
            ),
        ),
        Case(
            id="divergence_attribution",
            question=(
                "In {zone}, are the cheapest hours tomorrow also the cleanest ones? "
                "If not, why not?"
            ),
            rationale=(
                "The question the analysis layer was built for, and the one place the model "
                "is genuinely more capable than the interface. Two failures are being "
                "watched for: computing the windows itself instead of calling the tool that "
                "already has them, and asserting an import story without checking the flows."
            ),
            extra_checks=(checks.called("explain_divergence", "find_events"),),
            judge_criteria=(
                "Says whether the cheapest and cleanest windows are the same periods.",
                "Explains a *mechanism* for any divergence — the marginal unit, imports, a "
                "wind or solar surplus — rather than only restating that they differ.",
                "If it claims imports are responsible, it called get_flows.",
                "Does not tell the user which window to choose.",
            ),
        ),
        Case(
            id="agreement_is_an_answer",
            question=(
                "Show me the hours in {zone} where being cheap and being clean pull in "
                "opposite directions."
            ),
            rationale=(
                "The mirror of the case above, and the harder one. The question presupposes "
                "a disagreement. When price and carbon actually track each other, the right "
                "answer is to say so — inventing a divergence to satisfy the question is "
                "exactly the failure a leading question produces."
            ),
            judge_criteria=(
                "If the two signals agree in this zone, says so plainly rather than "
                "manufacturing a divergence to match the question.",
                "Any periods it names come from a tool result, not from its own reading of "
                "a chart.",
            ),
        ),
    ]
