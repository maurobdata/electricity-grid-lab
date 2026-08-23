# evals/

## `examples/`

Hand-written transcripts with a human verdict attached. They are **not** model output — each
is a constructed case built to exercise one failure mode.

They do two jobs:

* they are the corpus the deterministic checkers are unit-tested against, so a checker that
  stops catching invented numbers fails a test rather than going quiet;
* they are the labelled set the LLM judge is scored against (`make eval ARGS=--align`),
  which reports true positive and true negative rates. A judge nobody has scored is a number
  that feels like evidence and is not.

Each file carries `_human_verdict` (`PASS` or `FAIL`) and a `_why` explaining the label. The
`_`-prefixed keys are stripped before the transcript is parsed.

Both verdicts are represented on purpose. A labelled set of only good answers would give a
judge that passes everything a perfect score.

## `transcripts/`

Captured from real runs by `make eval`. Empty until a run happens, and gitignored — a
transcript records one moment against one scenario, which is not a fixture.
