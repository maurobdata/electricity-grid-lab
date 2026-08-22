"""Assembling the lab: which source, which clock, which scenario.

All the wiring lives here so the route modules stay about HTTP and the source modules stay
about data. It is also the single place that decides live-versus-replay, which makes that
decision easy to find and easy to change.
"""

from __future__ import annotations

import structlog
from fastapi import Request

from gridlab.clock import ReplayClock
from gridlab.config import Mode, Settings
from gridlab.emaps.client import EMapsClient
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

    @classmethod
    def build(cls, settings: Settings) -> LabState:
        library = ScenarioLibrary(settings.gridlab_scenarios_dir)
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
                    f"No scenarios found in {settings.gridlab_scenarios_dir}. Replay mode "
                    f"needs at least one. Run `make scenario` to generate the bundled ones, "
                    f"or `make record` if you have an Electricity Maps token."
                )
            scenario = available[0]
            log.warning(
                "gridlab.scenario_fallback",
                requested=settings.gridlab_scenario,
                using=scenario.id,
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
