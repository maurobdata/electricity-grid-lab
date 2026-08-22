# 3. Model the Electricity Maps API as a signal x temporality matrix

Date: 2026-08-22 · Status: Accepted

## Context

The brief is explicit: use the official documentation as the source of truth, never invent
endpoints, and keep Electricity Maps API details out of the rest of the application.

The v4 API turns out to be an unusually regular surface: paths are
`/v4/{signal}/{temporality}` for about fifteen signals and five temporalities, with a
handful of documented exceptions. Hand-writing ~60 methods would be repetitive and would
make "is this endpoint real?" a matter of reviewer memory.

## Decision

Encode signals and temporalities as enums plus a `SUPPORTED` capability matrix in
`emaps/signals.py`. The client builds a URL only from a `(signal, temporality)` pair that
the matrix admits; anything else raises before a request is made.

A test asserts the matrix matches the table in `docs/electricity-maps-api.md`.

Separately, `emaps/normalize.py` is the **only** module that knows an Electricity Maps
field name. Everything above it sees our own domain models.

## Consequences

- "Never invent an endpoint" becomes a property of the type system rather than a comment.
- Documented exceptions are expressible: day-ahead LMP has no `forecast` variant, so the
  matrix omits it and a wrong call fails locally instead of returning a 400 in Copenhagen.
- The exact v4 response schemas are not public (see `docs/electricity-maps-api.md`). Because
  normalization is isolated, discovering a different field name on the day is a one-file fix.
- Cost: one extra indirection between HTTP and domain. Worth it.
