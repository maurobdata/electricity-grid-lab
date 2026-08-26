"""Keeping the perishable window before it rolls away.

The free tier reaches back roughly 24 hours and ``past-range`` is 401 (ADR 0008), so a day
nobody records is a day permanently gone — and forecast-versus-outcome needs consecutive
days to exist at all. This package is the recording capability itself, deliberately separate
from whatever schedules it (ADR 0014):

* :mod:`gridlab.recording.completeness` — is this artifact good enough to use?
* :mod:`gridlab.recording.archive` — the recordings on disk, and the run ledger.
* :mod:`gridlab.recording.daily` — decide, record, validate, write, log. Once per day.

Nothing here knows about cron, GitHub Actions, or Docker. :func:`gridlab.recording.daily.run_daily`
takes a client and an archive and returns a receipt; a scheduler is something that calls it.
"""
