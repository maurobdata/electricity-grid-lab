"""Typed errors for the Electricity Maps adapter.

Callers should be able to tell "your token cannot reach that zone" from "the network is
down" from "you asked for an endpoint that does not exist", because the three call for
completely different responses — the first degrades the feature, the second serves stale
data with a badge, and the third is a bug.
"""

from __future__ import annotations


class ElectricityMapsError(Exception):
    """Base class for every adapter failure."""


class UnsupportedEndpoint(ElectricityMapsError):
    """A signal/temporality combination the documentation does not describe.

    Raised locally, before any request is made. This is a programming error, not a runtime
    condition — see ``docs/adr/0003-electricity-maps-adapter-signal-matrix.md``.
    """


class ConfigurationError(ElectricityMapsError):
    """Missing or malformed configuration, e.g. no API token in live mode."""


class AuthenticationError(ElectricityMapsError):
    """HTTP 401. The token is missing, malformed or revoked."""


class AccessDeniedError(ElectricityMapsError):
    """HTTP 403. The token is valid but your plan does not include this.

    The most likely error at a hackathon: a free-tier token reaching for a second zone or
    a paid signal. Features should degrade rather than crash — run ``make probe`` to learn
    what is actually reachable before designing around a signal.
    """


class BadRequestError(ElectricityMapsError):
    """HTTP 400. Usually a parameter the endpoint does not accept."""


class NotFoundError(ElectricityMapsError):
    """HTTP 404. No data for this zone/time, or the zone key is wrong."""


class RateLimitError(ElectricityMapsError):
    """HTTP 429.

    Electricity Maps publishes no rate limit, so we cannot pre-empt one. Treat this as a
    signal to widen the cache TTL, not to retry harder.
    """

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class UpstreamError(ElectricityMapsError):
    """HTTP 5xx from Electricity Maps."""


class TransportError(ElectricityMapsError):
    """The request never completed: DNS, TLS, connection, timeout.

    Expected at a hackathon venue. ``LiveSource`` catches this and serves the last good
    value with ``is_stale=True`` rather than failing the request.
    """


def from_status(status: int, body: str, *, url: str) -> ElectricityMapsError:
    """Map an HTTP status onto a typed error."""
    excerpt = body[:400]
    match status:
        case 400:
            return BadRequestError(f"400 from {url}: {excerpt}")
        case 401:
            return AuthenticationError(
                f"401 from {url}. Check ELECTRICITY_MAPS_API_TOKEN in .env. {excerpt}"
            )
        case 403:
            return AccessDeniedError(
                f"403 from {url}. The token is valid but your plan does not cover this. "
                f"Run `make probe` to see what it can reach. {excerpt}"
            )
        case 404:
            return NotFoundError(f"404 from {url}: {excerpt}")
        case 429:
            return RateLimitError(f"429 from {url}: {excerpt}")
        case s if 500 <= s < 600:
            return UpstreamError(f"{s} from {url}: {excerpt}")
        case s:
            return ElectricityMapsError(f"{s} from {url}: {excerpt}")
