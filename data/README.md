# data/

Local artefacts that are produced by running the lab, not by editing it.

* `capabilities.json` — written by `make probe`, read by `GET /api/v1/capabilities`.

The contents are gitignored; this directory is committed so that the Docker bind mount has
something to attach to. A bind mount of a path that does not exist becomes a *directory*,
which is exactly the failure this avoids: before the first probe, `capabilities.json` does
not exist.
