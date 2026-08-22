"""The HTTP API.

One surface, two consumers: the PWA and the agent. Keeping them on the same endpoints means
anything the agent can see, a human can see too — which is the property that makes the
agent auditable rather than mysterious.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from gridlab import __version__
from gridlab.config import Mode, get_settings
from gridlab.web import routes_grid, routes_meta, routes_replay, routes_zones
from gridlab.web.state import LabState

log = structlog.get_logger(__name__)


def configure_logging(level: str) -> None:
    """Structured JSON logs.

    Every Electricity Maps call is logged with endpoint, status, latency and cache
    outcome — enough to answer "are we hammering the API?" without a tracing backend, and
    enough to be worth showing when someone asks how the data gets in.
    """
    logging.basicConfig(format="%(message)s", level=getattr(logging, level.upper(), logging.INFO))
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.gridlab_log_level)

    state = LabState.build(settings)
    app.state.lab = state

    log.info(
        "gridlab.started",
        version=__version__,
        requested_mode=settings.gridlab_mode.value,
        effective_mode=state.mode.value,
        scenarios=state.scenario_count,
        zones=list(await state.source.zones()),
    )
    if settings.gridlab_mode is Mode.LIVE and state.mode is Mode.REPLAY:
        log.warning(
            "gridlab.mode_downgraded",
            reason="GRIDLAB_MODE=live but no ELECTRICITY_MAPS_API_TOKEN is set",
        )

    try:
        yield
    finally:
        await state.aclose()
        log.info("gridlab.stopped")


app = FastAPI(
    title="Grid Lab API",
    version=__version__,
    summary="Real Electricity Maps data, live or replayed, behind one stable interface.",
    description=(
        "A foundation, not a product. See docs/adr/0007-defer-product-decision.md.\n\n"
        "Every value carries a `provenance` field (`live`, `recorded`, `synthetic`) and an "
        "`is_estimated` flag. Do not present a `synthetic` value as a measured one."
    ),
    lifespan=lifespan,
)

# The PWA runs on a different port in development. Locked to localhost origins: this
# service holds an Electricity Maps token and should never be reachable from a page the
# user did not open themselves.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(routes_meta.router, prefix="/api/v1")
app.include_router(routes_zones.router, prefix="/api/v1")
app.include_router(routes_grid.router, prefix="/api/v1")
app.include_router(routes_replay.router, prefix="/api/v1")
