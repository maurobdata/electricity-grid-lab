"""Narration: the one job a model has here, and the guard rails around it.

The detectors say what happened. This adds why. Everything below is about keeping that
addition cheap and keeping it from quietly undoing the reason the finding was computed
arithmetically in the first place.
"""

from __future__ import annotations

from typing import Any

from gridlab.agent.narrate import Narrator, grounded, template


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
