"""The command a scheduler runs.

    make record-daily          # record today, if today is not already recorded
    make recordings            # what the archive holds, and what is missing

Deliberately thin. Everything this does is argument parsing, printing, and turning a
:class:`~gridlab.recording.daily.Outcome` into an exit code — the recording itself lives in
:mod:`gridlab.recording.daily`, so that a different scheduler (or a test, or a person at a
REPL) can drive the same logic without going through a command line. See ADR 0014.

Exit codes, because a scheduler reads those and not prose:

===  =========================================================================
  0  Recorded, or a valid recording for the day already existed.
  1  Failed, or the result was incomplete. Nothing was written.
  2  Misconfigured — no API token. Fix the environment, not the run.
===  =========================================================================
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from datetime import UTC, date, datetime
from pathlib import Path

from gridlab.config import get_settings
from gridlab.emaps.client import EMapsClient
from gridlab.recording.archive import ScenarioArchive
from gridlab.recording.daily import DEFAULT_ATTEMPTS, Outcome, RunReceipt, run_daily


def _print_status(archive: ScenarioArchive) -> int:
    status = archive.status()

    print(f"archive     {status['directory']}")
    if not status["exists"]:
        print(
            "\nThe archive directory does not exist yet.\n"
            "Recordings hold Electricity Maps data and are kept out of this repository on\n"
            "purpose (ADR 0013). See ops/README.md to clone the private archive, or just\n"
            "run `make record-daily` to start one locally."
        )
        return 0

    print(f"recordings  {status['recordings']}")
    if status["days"]:
        print(f"days        {status['days'][0]} .. {status['days'][-1]}")
    if status["missing_days"]:
        # The number that matters. Every one of these is permanently unrecoverable: the API
        # cannot be asked for a day that has rolled out of the trailing window.
        print(f"MISSING     {', '.join(status['missing_days'])}")
    else:
        print("missing     none")

    latest = status["latest_valid"]
    if latest:
        print(
            f"\nlatest valid  {latest['id']}"
            f"\n  window      {latest['start']} .. {latest['end']}"
            f"\n  zones       {', '.join(latest['zones'])}"
            f"\n  recorded    {latest['recorded_at'] or 'unknown'}"
        )
    else:
        print("\nNo complete recording in the archive.")

    last = status["last_run"]
    if last:
        print(
            f"\nlast run      {last['outcome']} for {last['day']} at {last['finished_at']}"
            f"\n  attempts    {last['attempts']}"
        )
        if last.get("reasons"):
            print(f"  reasons     {'; '.join(last['reasons'])}")
        if last.get("error"):
            print(f"  error       {last['error']}")
    print(f"\nruns logged   {status['runs']}")
    return 0


def _report(receipt: RunReceipt) -> None:
    print(f"\n  outcome    {receipt.outcome.value}")
    print(f"  day        {receipt.day}")
    print(f"  scenario   {receipt.scenario_id}")
    print(f"  attempts   {receipt.attempts}")
    if receipt.completeness is not None:
        for name, passed in receipt.completeness.checks.items():
            print(f"    {'ok  ' if passed else 'FAIL'} {name}")
    if receipt.path:
        print(f"  path       {receipt.path}")
    print(f"\n{receipt.message}")

    if receipt.outcome is Outcome.RECORDED:
        print(
            "\nRecord again tomorrow: today's forecast will overlap tomorrow's actuals, "
            "which is\nthe only way to get forecast-versus-outcome out of a key without "
            "`past-range`."
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=None, help="Archive directory.")
    parser.add_argument("--zones", default="DK-DK2", help="Comma-separated zone keys.")
    parser.add_argument(
        "--granularity", default="hourly", choices=["5_minutes", "15_minutes", "hourly"]
    )
    parser.add_argument("--day", default=None, help="UTC day to record for, YYYY-MM-DD.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Record even if a valid recording for the day already exists.",
    )
    parser.add_argument("--attempts", type=int, default=DEFAULT_ATTEMPTS)
    parser.add_argument("--backoff", type=float, default=None, help="Seconds before retry #2.")
    parser.add_argument(
        "--status", action="store_true", help="Report the archive and exit. No network."
    )
    parser.add_argument("--json", action="store_true", help="Machine-readable output.")
    args = parser.parse_args(argv)

    settings = get_settings()
    directory = args.out or settings.gridlab_recordings_dir
    archive = ScenarioArchive(directory)

    if args.status:
        if args.json:
            print(json.dumps(archive.status(), indent=2))
            return 0
        return _print_status(archive)

    zones = [z.strip() for z in args.zones.split(",") if z.strip()]
    if not zones:
        print("No zones given.", file=sys.stderr)
        return 2

    if not settings.has_api_token:
        print(
            "No ELECTRICITY_MAPS_API_TOKEN, so there is nothing live to record.\n"
            "Get a token at https://portal.electricitymaps.com/, put it in .env, and try "
            "again.",
            file=sys.stderr,
        )
        return Outcome.MISCONFIGURED.exit_code

    day = date.fromisoformat(args.day) if args.day else datetime.now(UTC).date()

    def client_factory() -> EMapsClient:
        token = settings.electricity_maps_api_token
        return EMapsClient(
            token=token.get_secret_value() if token else None,
            base_url=settings.electricity_maps_base_url,
            timeout=settings.gridlab_http_timeout,
            retries=settings.gridlab_http_retries,
        )

    kwargs = {} if args.backoff is None else {"backoff": args.backoff}
    receipt = asyncio.run(
        run_daily(
            client_factory=client_factory,
            archive=archive,
            zones=zones,
            granularity=args.granularity,
            day=day,
            force=args.force,
            attempts=args.attempts,
            **kwargs,
        )
    )

    if args.json:
        print(receipt.model_dump_json(indent=2))
    else:
        _report(receipt)
    return receipt.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
