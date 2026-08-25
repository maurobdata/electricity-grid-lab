# 10. The agent proposes views; it never applies them

Date: 2026-08-23 · Status: Accepted · Extends [ADR 0005](0005-agent-sandbox-container.md)

## Context

The agent can currently only produce text. That makes it a chat box beside a dashboard, and
it wastes the one thing it genuinely knows that the interface does not: *which part of the
screen the answer is about*. An answer describing a negative-price window at 03:00 leaves
the reader to find 03:00 themselves, on a chart that is not currently showing price.

`PROJECT_CONTEXT.md` §17 anticipated this as "Agent v2 — use tools to update or manipulate
the application's UI", and left the role deliberately undefined. Meanwhile ADR 0005 states
the boundary plainly: the agent may act only through declared, read-only tools, and adding
one that can *change* anything needs an ADR.

So "let the agent drive the UI" runs straight into that boundary, and the question is
whether it should be moved. There is also a plainer problem: an interface that rearranges
itself while somebody is reading it is hostile, and doubly so on stage, where a mis-parsed
question would move the screen away from what the speaker was describing.

## Decision

**The agent emits a `ViewIntent`. The client decides whether to apply it.**

1. **`propose_view` is a normal read-only tool.** It validates a proposed view against the
   same `ViewIntent` model the deterministic detectors build — closed vocabulary of kinds,
   zones through the usual allowlist, signals and panels checked against the real lists —
   and returns it. It writes nothing, anywhere. **ADR 0005's boundary does not move.**

2. **The result also travels as its own SSE event, `view_intent`.** The client should not
   have to know which tool produces intents in order to render one. The `tool_call` and
   `tool_result` are still emitted alongside it, so the working stays visible.

3. **The client renders it as a control labelled with the agent's `reason`, which the user
   may click or ignore.** Nothing moves on its own. This is why `reason` is a required
   field and is written for the user rather than for a log: it is the label on a button.

4. **The answer must stand on its own in words.** The prompt says to write as though nobody
   will click, and a test pins that. A view is an addition, never the substance.

5. **One tool carries `proposes_view`, and a test asserts it.** Which tools can steer the
   interface is a property of the registry — the same place the rest of the boundary lives —
   rather than a name matched inside the agent loop.

## Consequences

- The agent becomes an interaction layer without becoming an actor. It can say *look here*
  and be wrong about it harmlessly, because being wrong costs a control nobody presses.
- `ViewIntent` now has two producers — the detectors in `analysis/events.py` and the agent —
  and one definition. A finding and an answer steer the interface identically, which is what
  makes the findings rail and the agent panel the same mechanism rather than two.
- The user stays in control of their own screen. On stage this matters more than it sounds:
  a demo where the presenter clicks is a demo where the presenter chooses the moment.
- Cost: one more round trip of intent before anything is shown, and a UI affordance that has
  to be designed rather than assumed. Worth it.

## Alternatives rejected

**Let intents apply automatically, with undo.** More impressive for about ten seconds and
worse thereafter. It also weakens the ADR 0005 story from "the agent cannot change anything"
to "the agent cannot change anything except the thing you are looking at", which is a much
less useful sentence to be able to say.

**Apply low-risk intents automatically and confirm high-risk ones.** Defensible, and the
rules turn out to be the whole design: which intents are low-risk depends on what the user
is doing, which the server does not know. Deferred rather than refused — if the click-first
model proves tedious in practice, the place to revisit it is here.

## Reverse this if

Real use shows the click is pure friction — that people click every proposal, every time. At
that point auto-applying the narrow kinds (`highlight_window`, `focus`) becomes reasonable,
and this ADR should be superseded rather than quietly relaxed. Evidence should come from
someone using it, not from it sounding better.
