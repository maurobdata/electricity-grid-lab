"""Configuration, from environment variables only.

Secrets never appear in code, in defaults, or in a committed file. ``.env.example``
documents the shape; ``.env`` holds the values and is gitignored.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Mode(StrEnum):
    LIVE = "live"
    REPLAY = "replay"


class Settings(BaseSettings):
    """Runtime configuration.

    The default is ``replay``, deliberately. A fresh clone with no API key and no network
    must still start and still show something real — see
    ``docs/adr/0004-live-vs-replay-clock.md``.
    """

    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Electricity Maps ---------------------------------------------------
    electricity_maps_api_token: SecretStr | None = None
    electricity_maps_base_url: str = "https://api.electricitymaps.com/v4"

    # --- Runtime ------------------------------------------------------------
    gridlab_mode: Mode = Mode.REPLAY
    gridlab_scenario: str = ""
    """Which scenario to replay. Blank means the newest real recording on disk.

    Blank rather than a named scenario so that the default ages correctly. Naming one pins
    the lab to a file that gets staler every day a recording is made, and naming a
    *synthetic* one — as this used to — meant a clone with no `.env` opened on generated
    numbers while real recordings sat beside them.

    `LabState._fallback` resolves it: newest first, and a recording in preference to a
    generated scenario. A clone with neither still starts, because the synthetic ones are
    committed.
    """
    gridlab_replay_speed: float = Field(default=60.0, gt=0)
    gridlab_zones: str = "DK-DK1,DK-DK2,DE,FR,ES,PL,NO-NO2,SE-SE4"
    gridlab_log_level: str = "INFO"
    gridlab_db_path: Path = Path("/data/gridlab.duckdb")

    gridlab_scenarios_dir: Path = Path("/app/scenarios")
    gridlab_fixtures_dir: Path = Path("/app/fixtures")

    gridlab_recordings_dir: Path = Path("/app/recordings")
    """The daily archive: real Electricity Maps recordings, and the run ledger.

    Separate from `scenarios/` because the two have different licences. The generated
    scenarios are ours and are committed; a recording is Electricity Maps data, which their
    terms forbid making available to third parties, so it lives in a private archive that is
    mounted here and gitignored (ADR 0013). Absent is a normal state: a fresh clone has no
    archive and still runs, on the committed synthetic scenarios.
    """

    gridlab_atlas_path: Path = Path("/app/data/atlas.json")
    """Where `make atlas` writes, and where /api/v1/atlas reads.

    Same reasoning as the capability probe below: inside a mounted directory, because the
    file does not exist until a sweep has been run and Docker turns a bind mount of a
    missing file into a directory.
    """

    gridlab_capabilities_path: Path = Path("/app/data/capabilities.json")
    """Where `make probe` writes, and where /api/v1/capabilities reads.

    Inside a mounted directory rather than at the repository root, because Docker turns a
    bind mount of a missing file into a directory - and this file does not exist until a
    probe has been run. Mounting the directory sidesteps that entirely.
    """

    # --- HTTP behaviour -----------------------------------------------------
    gridlab_http_timeout: float = 20.0
    gridlab_http_retries: int = 3
    gridlab_cache_ttl_seconds: int = 300
    """How long a cached upstream response stays fresh.

    Five minutes. Electricity Maps publishes no rate limit, most signals update hourly,
    and a hackathon demo hitting refresh should not be able to exhaust a trial key.
    """

    # --- Agent --------------------------------------------------------------
    anthropic_api_key: SecretStr | None = None
    gridlab_agent_model: str = "claude-opus-5"
    gridlab_api_url: str = "http://api:8000"
    gridlab_agent_max_points: int = 400
    """Hard cap on series length returned to the model.

    Ten days at five-minute granularity is 2,880 points. Handing that to an LLM wastes
    context and degrades the answer; downsample instead.
    """

    # --- Tracing ------------------------------------------------------------
    gridlab_tracing_enabled: bool = False
    otel_exporter_otlp_endpoint: str = "http://phoenix:4317"

    @property
    def zones(self) -> tuple[str, ...]:
        return tuple(z.strip() for z in self.gridlab_zones.split(",") if z.strip())

    @property
    def has_api_token(self) -> bool:
        token = self.electricity_maps_api_token
        return token is not None and bool(token.get_secret_value().strip())

    @property
    def has_anthropic_key(self) -> bool:
        key = self.anthropic_api_key
        return key is not None and bool(key.get_secret_value().strip())

    @property
    def effective_mode(self) -> Mode:
        """Live mode requires a token. Without one, fall back to replay rather than crash.

        A missing key is a very likely state — the trial should not be started until early
        September — and it should degrade the lab, not stop it.
        """
        if self.gridlab_mode is Mode.LIVE and not self.has_api_token:
            return Mode.REPLAY
        return self.gridlab_mode


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
