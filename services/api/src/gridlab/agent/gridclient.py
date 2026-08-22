"""The agent's only window onto the world.

Every fact the agent can reach comes through this client, and this client talks to exactly
one place: the Grid Lab API on the internal network. There is no filesystem access, no
shell, no arbitrary HTTP, and no database handle — see
``docs/adr/0005-agent-sandbox-container.md``.

That has a useful consequence beyond safety: anything the agent can see, a human can see
too, at the same URL. An answer it gives is checkable rather than mysterious.
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

log = structlog.get_logger(__name__)


class GridUnavailable(Exception):
    """The lab could not answer. Not an error the model should be shielded from.

    A signal outside the plan, a zone missing from the current scenario, or a request for
    a window nobody has — all of these are answers, and the agent should say so rather
    than have the turn fail.
    """


class GridClient:
    """Read-only HTTP client for the Grid Lab API."""

    def __init__(self, base_url: str, *, timeout: float = 20.0) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            headers={"User-Agent": "gridlab-agent/0.1"},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        clean = {k: v for k, v in (params or {}).items() if v is not None}
        try:
            response = await self._client.get(f"/api/v1{path}", params=clean)
        except httpx.HTTPError as exc:
            raise GridUnavailable(f"The lab is unreachable: {exc}") from exc

        if response.status_code == 404:
            detail = _detail(response)
            raise GridUnavailable(detail or "No data for that request.")
        if response.status_code == 400:
            raise GridUnavailable(_detail(response) or "That request is not valid.")
        if response.status_code >= 400:
            raise GridUnavailable(f"The lab returned {response.status_code}.")

        return response.json()

    # -- reads ---------------------------------------------------------------

    async def status(self) -> dict[str, Any]:
        return await self._get("/status")  # type: ignore[no-any-return]

    async def zones(self) -> list[dict[str, str]]:
        body = await self._get("/zones")
        return list(body.get("zones", []))

    async def snapshot(self, zone: str) -> dict[str, Any]:
        return await self._get(f"/grid/{zone}/now")  # type: ignore[no-any-return]

    async def mix(self, zone: str, *, flow_traced: bool) -> dict[str, Any]:
        return await self._get(f"/grid/{zone}/mix", {"flow_traced": str(flow_traced).lower()})  # type: ignore[no-any-return]

    async def price(self, zone: str) -> dict[str, Any]:
        return await self._get(f"/grid/{zone}/price")  # type: ignore[no-any-return]

    async def flows(self, zone: str) -> dict[str, Any]:
        return await self._get(f"/grid/{zone}/flows")  # type: ignore[no-any-return]

    async def forecast(self, zone: str, signal: str, horizon_hours: int) -> dict[str, Any]:
        return await self._get(  # type: ignore[no-any-return]
            f"/grid/{zone}/forecast", {"signal": signal, "horizon_hours": horizon_hours}
        )

    async def history(
        self, zone: str, signal: str, start: str | None, end: str | None
    ) -> dict[str, Any]:
        return await self._get(  # type: ignore[no-any-return]
            f"/grid/{zone}/history", {"signal": signal, "start": start, "end": end}
        )

    async def compare(self, zones: list[str], signal: str) -> dict[str, Any]:
        return await self._get("/compare", {"zones": ",".join(zones), "signal": signal})  # type: ignore[no-any-return]


def _detail(response: httpx.Response) -> str | None:
    """Pull the human-readable part out of a FastAPI error body.

    The API puts genuinely useful things in `detail` — the list of zones that *do* exist,
    why a window was rejected. Passing that through to the model is what lets it correct
    itself instead of guessing again.
    """
    try:
        detail = response.json().get("detail")
    except ValueError:
        return None
    if isinstance(detail, str):
        return detail
    if isinstance(detail, dict):
        parts = [str(detail.get("error") or detail.get("hint") or "")]
        for key in ("available", "available_zones", "unknown_zones"):
            if key in detail:
                parts.append(f"{key}: {detail[key]}")
        return " ".join(p for p in parts if p).strip() or None
    return None
