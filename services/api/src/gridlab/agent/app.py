"""The agent service.

Runs from the same image as the API, with a different command, on a network that reaches
only `api`. See ``docs/adr/0005-agent-sandbox-container.md`` for what that does and does not
guarantee.

Phase 4 fills in the tools and the loop. Until then this exposes health and a clear
statement of what is not built yet, so the container starts, the stack comes up with one
command, and the shape of the boundary is visible from the beginning.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from gridlab import __version__
from gridlab.config import get_settings

app = FastAPI(
    title="Grid Lab Agent",
    version=__version__,
    summary="A sandboxed agent with explicit grid tools.",
    description=(
        "The agent may only act through declared tools, and reaches grid data only via the "
        "API service. It has no shell, no filesystem and no general web access."
    ),
)


@app.get("/api/v1/healthz", tags=["meta"])
async def healthz() -> dict[str, Any]:
    settings = get_settings()
    return {
        "status": "ok",
        "version": __version__,
        "model": settings.gridlab_agent_model,
        "has_anthropic_key": settings.has_anthropic_key,
        "api_url": settings.gridlab_api_url,
    }


@app.get("/api/v1/tools", tags=["agent"])
async def tools() -> dict[str, Any]:
    """The tool surface the agent will be given.

    Published before the agent works, deliberately: the tool list *is* the security
    boundary, so it should be reviewable from the outset rather than discovered later.
    """
    return {
        "status": "not_implemented",
        "planned": [
            "get_current_grid",
            "get_forecast",
            "get_mix",
            "get_price",
            "get_flows",
            "query_history",
            "compare_zones",
        ],
        "constraints": [
            "Every tool is read-only.",
            "Zones are validated against the capability list before any call.",
            "Series are downsampled to a hard point cap before reaching the model.",
            "Results carry provenance and is_estimated; the model must disclose both.",
            "No shell, no filesystem, no arbitrary HTTP, no database handle.",
        ],
    }
