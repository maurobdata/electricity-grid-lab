"""Explanation on top of a finding, priced to be affordable.

The detectors in :mod:`gridlab.analysis.events` already say *what* happened, with the
evidence that proves it. This adds the one thing arithmetic cannot: *why* — the mechanism
joining the mix, the flows and the market that produced the number.

Three rules make it cheap enough to leave switched on.

**Cached by finding id.** Finding ids are stable for the same finding computed twice, which
was the point of hashing them rather than counting. A rail polled every few seconds
therefore costs one call per *distinct* finding, ever, rather than one per poll. Most of the
time the cache answers and nothing is spent.

**One call, no tool loop.** The finding arrives carrying its own evidence and caveats, so
there is nothing to look up. A tool-calling turn would cost three or four round trips to
reach facts already in the prompt.

**A template when there is no model.** Without a key the finding's own ``detail`` is
returned and marked as such. The feature degrades to what the deterministic layer already
knew, which is the whole point of computing it there first.

The output is never a number the finding did not contain. That is stated in the prompt and
checked before returning: a narration that introduces a figure is discarded rather than
shown, because a plausible sentence with an invented number in it is exactly what the
deterministic layer exists to prevent.
"""

from __future__ import annotations

import re
from collections import OrderedDict
from typing import Any

import structlog

log = structlog.get_logger(__name__)

#: How many narrations to keep. Each is a couple of sentences; a thousand is a rounding
#: error in memory and far more distinct findings than a day of use produces.
CACHE_SIZE = 1000

#: Hard ceiling on the reply. Two sentences of explanation, not an essay — this sits under a
#: chip in a rail, and a long one would not be read.
MAX_TOKENS = 220

#: Numbers at or below this are read as prose rather than as measurements.
#:
#: Hours of the day, counts of periods, "both signals". A grid figure worth checking —
#: a carbon intensity, a price, a megawatt — is essentially never this small, and treating
#: these as claims would discard almost every well-written sentence.
PROSE_CEILING = 24.0

#: How far a quoted figure may sit from the one the finding claims.
#:
#: 5%, or 1.0 absolute for small values. Describing 233 as 230 is rounding; describing it
#: as 180 is not. Widening this is the wrong lever for a narration being rejected — check
#: what :func:`claimed_numbers` returns first, because the usual cause is a figure the
#: finding never actually asserted.
ROUNDING_TOLERANCE = 0.05

NARRATE_PROMPT = """\
You explain one thing that has already been measured on an electricity grid.

The finding below was computed arithmetically, with the evidence that produced it. Your job
is the part a calculation cannot do: say **why** this is happening, in terms of how power
systems and power markets actually work.

## Rules

**Use only the numbers given to you.** Every figure in the finding is real. Any figure not
in the finding is one you invented, and it will be discarded. If you want to say something
you have no number for, say it qualitatively.

**Explain the mechanism, not the observation.** "Carbon intensity rises 2.8x" restates the
headline and is worthless. "Wind drops through the evening and the shortfall is covered by
imports and gas, which set both the price and the carbon" is the answer.

**Be brief.** Two sentences. This appears under a chip in a list.

**Do not recommend anything.** Say what is happening and why. What to do about it involves
the reader's own trade-offs, not yours.

If the finding is about price and carbon disagreeing, the mechanism is usually worth naming
precisely: price is set by the marginal unit — often gas — through uniform-price auction
clearing, while carbon intensity is a flow-traced average over everything consumed. They
are different functions of the same grid.
"""


def _numbers(text: str) -> set[float]:
    """Every number in a string, for the invention check."""
    found: set[float] = set()
    for token in re.findall(r"-?\d+(?:[.,]\d+)?", text.replace(",", "")):
        try:
            found.add(abs(float(token)))
        except ValueError:
            continue
    return found


def claimed_numbers(finding: dict[str, Any]) -> set[float]:
    """Every figure the finding actually asserts.

    Anchored to the fields a detector composed from real measurements — the evidence values,
    the magnitude, and the prose the detector wrote — rather than to ``str(finding)``.

    Scanning the whole record looked thorough and was the opposite. A ``cheap_clean_divergence``
    finding carried five real figures and twenty-three "known" numbers, the difference being
    the id hash (``cheap_clean_divergence:31a6af6e489b`` contributes 31, 6 and **489**), the
    ISO timestamps (**2026**), the alignment method string (``cadence=3600s`` contributes
    **3600**) and the input point counts. Measured against a live finding, "prices spike to
    489 EUR/MWh", "around 2026 MW of wind" and "the interconnector carries 3600 MW" all
    passed the guard. None of those numbers came from the grid.

    Excluded deliberately: ``id``, ``at``, ``until``, ``significance`` and the ``derived``
    plumbing. None of them is a claim about electricity, so quoting one is not grounding.
    """
    values: set[float] = set()

    for field in ("headline", "detail"):
        values |= _numbers(str(finding.get(field) or ""))

    magnitude = finding.get("magnitude")
    if isinstance(magnitude, int | float):
        values.add(abs(float(magnitude)))

    for item in finding.get("evidence") or []:
        value = item.get("value") if isinstance(item, dict) else None
        if isinstance(value, int | float):
            values.add(abs(float(value)))

    # Caveats are prose the detector wrote about this finding, and some quote a figure.
    for caveat in (finding.get("derived") or {}).get("caveats") or []:
        values |= _numbers(str(caveat))

    return values


def grounded(narration: str, finding: dict[str, Any]) -> tuple[bool, set[float]]:
    """Whether every number in the narration is one the finding actually claims.

    The same idea as the deterministic eval check, applied before the text is ever shown
    rather than afterwards.

    Two allowances, both deliberate and neither widened to make failures go away. **Rounding
    passes**: a finding of 233 described as 230 is good writing, not invention, so a value
    within 5% or 1.0 of a claimed figure counts. **Small integers are ignored**: "both
    signals", "the 3 hours after midnight", an hour named as 10 — treating those as figures
    would discard almost every well-written sentence.

    What changed is the *set* being matched against, not the tolerance. See
    :func:`claimed_numbers`.
    """
    known = claimed_numbers(finding)
    invented = set()
    for value in _numbers(narration):
        if value <= PROSE_CEILING:
            continue
        if any(abs(value - k) <= max(1.0, abs(k) * ROUNDING_TOLERANCE) for k in known):
            continue
        invented.add(value)
    return not invented, invented


def template(finding: dict[str, Any]) -> str:
    """What the deterministic layer already knew, when no model is available."""
    detail = str(finding.get("detail") or "").strip()
    return detail or str(finding.get("headline") or "")


class Narrator:
    """One short explanation per finding, cached."""

    def __init__(self, backend: Any) -> None:
        self._backend = backend
        self._cache: OrderedDict[str, dict[str, Any]] = OrderedDict()

    @property
    def cached(self) -> int:
        return len(self._cache)

    def _remember(self, key: str, value: dict[str, Any]) -> dict[str, Any]:
        self._cache[key] = value
        self._cache.move_to_end(key)
        while len(self._cache) > CACHE_SIZE:
            self._cache.popitem(last=False)
        return value

    async def narrate(self, finding: dict[str, Any]) -> dict[str, Any]:
        """Explain one finding. Cheap on a cache hit, absent without a key."""
        key = str(finding.get("id") or finding.get("headline") or "")
        if key in self._cache:
            hit = dict(self._cache[key])
            hit["cached"] = True
            return hit

        if not self._backend.available():
            return self._remember(
                key,
                {
                    "id": key,
                    "text": template(finding),
                    "source": "template",
                    "cached": False,
                    "note": (
                        "No ANTHROPIC_API_KEY, so this is what the detector itself said. "
                        "The explanation is the only part a model adds."
                    ),
                },
            )

        prompt = (
            f"{NARRATE_PROMPT}\n\n## The finding\n\n"
            f"{finding.get('headline')}\n\n"
            f"{finding.get('detail') or ''}\n\n"
            f"Evidence: {finding.get('evidence')}\n"
            f"Zone: {finding.get('zone')}\n"
            f"Provenance: {(finding.get('derived') or {}).get('provenance')}\n"
            f"Caveats: {(finding.get('derived') or {}).get('caveats')}\n"
        )

        try:
            text = await self._backend.complete(prompt, max_tokens=MAX_TOKENS)
        except Exception as exc:
            log.warning("narrate.failed", error=str(exc), finding=key)
            return {
                "id": key,
                "text": template(finding),
                "source": "template",
                "cached": False,
                "note": f"The model could not be reached ({type(exc).__name__}).",
            }

        ok, invented = grounded(text, finding)
        if not ok:
            # Discarded rather than shown. The detector's own words are always safe, and a
            # confident sentence with a made-up figure in it is the failure this whole
            # architecture is arranged to prevent.
            log.warning("narrate.invented_numbers", finding=key, numbers=sorted(invented))
            return self._remember(
                key,
                {
                    "id": key,
                    "text": template(finding),
                    "source": "template",
                    "cached": False,
                    "note": (
                        "The explanation was discarded: it contained numbers the finding "
                        "did not. This is the detector's own wording instead."
                    ),
                },
            )

        return self._remember(
            key,
            {"id": key, "text": text.strip(), "source": "model", "cached": False},
        )
