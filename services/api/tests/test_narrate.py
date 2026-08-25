"""Narration: the one job a model has here, and the guard rails around it.

The detectors say what happened. This adds why. Everything below is about keeping that
addition cheap and keeping it from quietly undoing the reason the finding was computed
arithmetically in the first place.
"""

from __future__ import annotations

from typing import Any

from gridlab.agent.narrate import Narrator, claimed_numbers, grounded, template


def finding(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "carbon_swing:abc123",
        "kind": "carbon_swing",
        "zone": "DK-DK2",
        "headline": "Carbon intensity climbs 2.8x — 82 to 233 gCO2eq/kWh",
        "detail": "A forecast, not an outcome.",
        "evidence": [{"label": "lowest", "value": 82.0}, {"label": "highest", "value": 233.0}],
        "derived": {"provenance": "recorded", "caveats": ["A ratio between the extremes."]},
    }
    return {**base, **over}


class FakeBackend:
    """A backend that says whatever the test needs, and counts how often it was asked."""

    def __init__(
        self,
        reply: Any = "Wind falls away and imports cover the gap.",
        *,
        key: bool = True,
    ):
        self.reply = reply
        self.calls = 0
        self._key = key

    def available(self) -> bool:
        return self._key

    async def complete(self, prompt: str, *, max_tokens: int = 256) -> str:
        self.calls += 1
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


# --- the invented-number guard ----------------------------------------------


def test_a_narration_using_only_the_finding_is_grounded() -> None:
    ok, invented = grounded("It climbs from 82 to 233 as wind falls away.", finding())
    assert ok and not invented


def test_rounding_is_allowed() -> None:
    """A finding of 233 may be described as 230. Refusing that would reject good writing."""
    ok, _ = grounded("Carbon reaches about 230 gCO2eq/kWh by evening.", finding())
    assert ok


def test_a_number_the_finding_never_contained_is_caught() -> None:
    ok, invented = grounded("Wind drops to 450 MW as the evening peak arrives.", finding())
    assert not ok
    assert 450.0 in invented


def test_small_numbers_are_ignored_as_ordinary_prose() -> None:
    """ "both signals", "the 3 hours after midnight" — treating these as invented figures
    would discard almost every well-written sentence."""
    ok, _ = grounded("Over the 3 hours after 10:00 both drivers point the same way.", finding())
    assert ok


# --- what gets returned -----------------------------------------------------


async def test_a_grounded_narration_is_returned_and_marked_as_model_written() -> None:
    narrator = Narrator(FakeBackend("Wind falls away and imports cover the shortfall."))
    result = await narrator.narrate(finding())

    assert result["source"] == "model"
    assert "imports" in result["text"]


async def test_an_invented_number_is_discarded_for_the_detectors_own_words() -> None:
    """The failure this whole architecture is arranged to prevent. A fluent sentence with a
    made-up figure is worse than no sentence, so it never reaches a screen."""
    narrator = Narrator(FakeBackend("Wind drops to 450 MW overnight."))
    result = await narrator.narrate(finding())

    assert result["source"] == "template"
    assert result["text"] == "A forecast, not an outcome."
    assert "did not" in result["note"]


async def test_without_a_key_the_detectors_wording_is_used() -> None:
    """The feature degrades to what the deterministic layer already knew, which is why the
    finding is computed there first."""
    narrator = Narrator(FakeBackend(key=False))
    result = await narrator.narrate(finding())

    assert result["source"] == "template"
    assert "ANTHROPIC_API_KEY" in result["note"]


async def test_a_model_failure_is_never_fatal() -> None:
    """Narration is decoration on top of a finding that already stands on its own."""
    narrator = Narrator(FakeBackend(RuntimeError("upstream on fire")))
    result = await narrator.narrate(finding())

    assert result["source"] == "template"
    assert "RuntimeError" in result["note"]


def test_the_template_falls_back_to_the_headline_when_there_is_no_detail() -> None:
    assert template(finding(detail="")) == finding()["headline"]


# --- the cost discipline ----------------------------------------------------


async def test_the_same_finding_is_only_paid_for_once() -> None:
    """The reason finding ids are hashed rather than counted. A rail polled every few
    seconds costs one call per distinct finding, ever — not one per poll."""
    backend = FakeBackend()
    narrator = Narrator(backend)

    first = await narrator.narrate(finding())
    second = await narrator.narrate(finding())
    third = await narrator.narrate(finding())

    assert backend.calls == 1
    assert first["cached"] is False
    assert second["cached"] is True and third["cached"] is True
    assert second["text"] == first["text"]


async def test_different_findings_are_narrated_separately() -> None:
    backend = FakeBackend()
    narrator = Narrator(backend)

    await narrator.narrate(finding(id="a"))
    await narrator.narrate(finding(id="b"))

    assert backend.calls == 2
    assert narrator.cached == 2


async def test_a_discarded_narration_is_not_retried_on_every_poll() -> None:
    """Caching the rejection too. Otherwise a model that reliably invents a number would be
    paid for once per poll, forever, to produce the same discarded answer."""
    backend = FakeBackend("Wind drops to 450 MW overnight.")
    narrator = Narrator(backend)

    await narrator.narrate(finding())
    await narrator.narrate(finding())

    assert backend.calls == 1


# --- what counts as a claim -------------------------------------------------
#
# The guard used to match against `str(finding)`, which looked thorough and was the
# opposite. Measured against a live `cheap_clean_divergence` finding, five real figures
# came with eighteen more: the id hash, the ISO timestamps, the alignment method string and
# the input point counts. Three invented sentences passed because of it.


def test_the_claimed_set_is_evidence_headline_and_magnitude() -> None:
    claimed = claimed_numbers(finding())
    assert 82.0 in claimed and 233.0 in claimed, "evidence values are claims"
    assert 2.8 in claimed, "the ratio in the headline is a claim"


def test_an_id_hash_is_not_evidence() -> None:
    """`cheap_clean_divergence:31a6af6e489b` contributed 31, 6 and 489. A narration saying
    "prices spike to 489 EUR/MWh" passed the guard because of it."""
    subject = finding(id="carbon_swing:31a6af6e489b")
    assert 489.0 not in claimed_numbers(subject)

    ok, invented = grounded("Prices spike to 489 EUR/MWh in the evening.", subject)
    assert not ok and 489.0 in invented


def test_a_timestamp_is_not_evidence() -> None:
    """The year in `2026-08-23T21:00:00Z` let "around 2026 MW of wind" through."""
    subject = finding(at="2026-08-23T21:00:00Z", until="2026-08-24T13:00:00Z")
    assert 2026.0 not in claimed_numbers(subject)

    ok, invented = grounded("Around 2026 MW of wind is displaced overnight.", subject)
    assert not ok and 2026.0 in invented


def test_the_method_string_is_not_evidence() -> None:
    """`align.step_hold(cadence=3600s)` let "the interconnector carries 3600 MW" through."""
    subject = finding(
        derived={
            "provenance": "recorded",
            "method": "align.step_hold(cadence=3600s, max_hold=2 steps)",
            "inputs": [{"points": 73, "estimated_fraction": 0.0}],
            "caveats": [],
        }
    )
    assert 3600.0 not in claimed_numbers(subject)

    ok, invented = grounded("The interconnector carries 3600 MW at the peak.", subject)
    assert not ok and 3600.0 in invented


# --- valid rounding still passes --------------------------------------------
#
# Tightening the claimed set must not start rejecting good writing, so each shape a model
# actually produces is pinned.


def test_rounding_a_claimed_figure_passes() -> None:
    for text in (
        "Carbon reaches about 230 gCO2eq/kWh by evening.",  # 233 -> 230
        "It starts near 80 gCO2eq/kWh overnight.",  # 82 -> 80
        "Roughly 235 gCO2eq/kWh at the peak.",  # 233 -> 235
    ):
        ok, invented = grounded(text, finding())
        assert ok, f"valid rounding was rejected: {text!r} flagged {sorted(invented)}"


def test_the_exact_figures_pass() -> None:
    ok, _ = grounded("It climbs from 82 to 233 gCO2eq/kWh.", finding())
    assert ok


def test_a_finding_headline_always_passes_its_own_guard() -> None:
    """The strongest form of "nothing legitimate was lost": whatever the detector itself
    wrote about the finding must be sayable about it."""
    subject = finding()
    ok, invented = grounded(subject["headline"], subject)
    assert ok, f"a detector's own headline failed the guard: {sorted(invented)}"


def test_a_qualitative_sentence_needs_no_numbers_at_all() -> None:
    ok, _ = grounded("Wind falls away and gas covers the shortfall, setting both.", finding())
    assert ok


def test_a_genuinely_invented_figure_is_still_caught() -> None:
    ok, invented = grounded("Gas plants run at 450 MW to cover the gap.", finding())
    assert not ok and 450.0 in invented


def test_a_figure_outside_the_rounding_tolerance_is_caught() -> None:
    """233 described as 180 is not rounding. The tolerance was not widened to make
    rejections go away — the set being matched against was corrected instead."""
    ok, invented = grounded("Carbon peaks around 180 gCO2eq/kWh.", finding())
    assert not ok and 180.0 in invented
