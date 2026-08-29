"""Assembling the lab: which source, which clock, which scenario.

All the wiring lives here so the route modules stay about HTTP and the source modules stay
about data. It is also the single place that decides live-versus-replay, which makes that
decision easy to find and easy to change.
"""

from __future__ import annotations

from collections.abc import Sequence

import structlog
from fastapi import Request

from gridlab.clock import ReplayClock
from gridlab.config import Mode, Settings
from gridlab.domain.models import Provenance
from gridlab.emaps.client import EMapsClient
from gridlab.recording.completeness import assess
from gridlab.sources.base import GridSource
from gridlab.sources.live import LiveSource
from gridlab.sources.replay import ReplaySource
from gridlab.store.duckdb_cache import Cache
from gridlab.store.scenario import Scenario, ScenarioLibrary

log = structlog.get_logger(__name__)


class LabState:
    """Everything the API needs, built once at startup."""

    def __init__(
        self,
        *,
        settings: Settings,
        source: GridSource,
        library: ScenarioLibrary,
        cache: Cache | None,
        mode: Mode,
    ) -> None:
        self.settings = settings
        self.source = source
        self.library = library
        self.cache = cache
        self.mode = mode

    @property
    def scenario_count(self) -> int:
        return len(self.library)

    @property
    def replay_clock(self) -> ReplayClock | None:
        """The replay clock, if one is running. ``None`` in live mode."""
        clock = self.source.clock
        return clock if isinstance(clock, ReplayClock) else None

    @property
    def scenario(self) -> Scenario | None:
        """The scenario being replayed, if any.

        Routes ask through here rather than reaching into ``source``: a live source has no
        scenario, and the type system should say so rather than leaving callers to guess.
        """
        return self.source.scenario if isinstance(self.source, ReplaySource) else None

    @staticmethod
    def _fallback(available: Sequence[Scenario]) -> Scenario:
        """Which scenario to play when the configured one is missing.

        **The newest complete real recording**, and the emphasis matters on all three words.

        Completeness is checked, not assumed. A recording that a daily run judged too thin
        to keep can still reach the disk — an older one written before the checks existed,
        or one copied in by hand — and booting the lab onto three hours of one signal is a
        demo that fails in the room rather than at startup. `assess` is the same judgement
        the recorder applies before writing, so the app and the archive cannot disagree
        about what "usable" means.

        Sorting by filename and taking the first gave the *oldest* — recordings are
        date-stamped (`dk-dk2-2026-08-22.json`), so alphabetical order is chronological
        order, and the fallback reliably chose the least current data on disk. By 11
        September there will be a fortnight of these, and a typo in `GRIDLAB_SCENARIO`
        would quietly boot the lab into the oldest one.

        A recording also beats a generated scenario, because a synthetic default is a
        demo waiting to be given on made-up numbers. A fresh clone with no key has only
        synthetic ones and still gets a working lab.

        Ordering is by the window's end rather than the id, so it stays right if the
        naming convention ever changes.
        """
        return max(
            available,
            key=lambda s: (
                s.provenance is not Provenance.SYNTHETIC,
                assess(s).complete,
                s.end,
            ),
        )

    @classmethod
    def build(cls, settings: Settings) -> LabState:
        # Recordings second, so a recording wins an id collision with a generated scenario.
        library = ScenarioLibrary([settings.gridlab_scenarios_dir, settings.gridlab_recordings_dir])
        mode = settings.effective_mode

        if mode is Mode.LIVE:
            cache = Cache(settings.gridlab_db_path, ttl_seconds=settings.gridlab_cache_ttl_seconds)
            token = settings.electricity_maps_api_token
            client = EMapsClient(
                token=token.get_secret_value() if token else None,
                base_url=settings.electricity_maps_base_url,
                timeout=settings.gridlab_http_timeout,
                retries=settings.gridlab_http_retries,
            )
            source: GridSource = LiveSource(client, cache, zone_keys=settings.zones)
            return cls(settings=settings, source=source, library=library, cache=cache, mode=mode)

        scenario = library.get(settings.gridlab_scenario)
        if scenario is None:
            available = library.all()
            if not available:
                raise RuntimeError(
                    f"No scenarios found in {settings.gridlab_scenarios_dir} or "
                    f"{settings.gridlab_recordings_dir}. Replay mode needs at least one. Run "
                    f"`make scenario` to generate the bundled ones, or `make record-daily` if "
                    f"you have an Electricity Maps token."
                )
            scenario = cls._fallback(available)
            log.warning(
                "gridlab.scenario_fallback",
                requested=settings.gridlab_scenario,
                using=scenario.id,
                provenance=scenario.provenance.value,
            )

        clock = ReplayClock(
            scenario.start,
            end=scenario.end,
            speed=settings.gridlab_replay_speed,
            loop=True,
        )
        return cls(
            settings=settings,
            source=ReplaySource(scenario, clock),
            library=library,
            cache=None,
            mode=mode,
        )

    def switch_scenario(self, scenario_id: str) -> None:
        """Load a different scenario without restarting.

        A demo needs to move between "the wind dropped" and "Spain is paying you to
        consume" in one click. Restarting the container between them is not a demo.
        """
        scenario = self.library.require(scenario_id)
        clock = ReplayClock(
            scenario.start,
            end=scenario.end,
            speed=self.settings.gridlab_replay_speed,
            loop=True,
        )
        self.source = ReplaySource(scenario, clock)
        self.mode = Mode.REPLAY
        log.info("gridlab.scenario_switched", scenario=scenario.id)

    async def aclose(self) -> None:
        await self.source.aclose()
        if self.cache is not None:
            self.cache.close()


def lab(request: Request) -> LabState:
    """FastAPI dependency."""
    return request.app.state.lab  # type: ignore[no-any-return]
