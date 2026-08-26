# data/

Local artefacts that are produced by running the lab, not by editing it.

* `capabilities.json` — written by `make probe`, read by `GET /api/v1/capabilities`.
* `atlas.json` and `atlas-<date>.json` — written by `make atlas`, read by `GET /api/v1/atlas`.

The contents are gitignored; this directory is committed so that the Docker bind mount has
something to attach to. A bind mount of a path that does not exist becomes a *directory*,
which is exactly the failure this avoids: before the first probe, `capabilities.json` does
not exist.

**Daily recordings are not here.** They live in the private archive at `recordings/` — see
[`docs/RECORDING.md`](../docs/RECORDING.md) and
[ADR 0013](../docs/adr/0013-recorded-data-is-not-published.md). What lands in `data/` is
derived and re-derivable by re-running a command; a recording is a moment that cannot be
asked for twice.
