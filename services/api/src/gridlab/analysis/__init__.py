"""Deterministic analysis over domain observations.

Everything in this package is a **pure function over the domain models**: no network, no
clock, no cache, no model. Given the same series it returns the same answer, in
milliseconds, and a test can pin it against a committed fixture.

That is a deliberate boundary rather than an accident of implementation. Two reasons:

**Numbers must not come from a language model.** An LLM asked to find the cheapest window
will usually get it right and occasionally not, and there is no way to tell which happened
from the answer. Anything an audience might act on — a peak, a window, a correlation, a
price — is computed here, and the model's job is to explain what this package found.

**Finding things is cheaper than being asked.** A detector runs on every poll for nothing.
Asking a model to notice the same thing costs a request, a wait, and a variable answer. So
the lab looks for what is interesting first, and spends model calls only on the part that
genuinely needs language.

Every result carries a :class:`~gridlab.domain.models.Derived` record: the weakest
provenance among its inputs, what those inputs were, the method and its parameters, and
what the number is *not*. A computed value is easier to mistake for a measured one than a
measured one is, so the provenance rule from ADR 0004 is enforced harder here, not less.
"""
