"""Sprint 4 runtime settings for backend and training integration."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Sprint4Settings(BaseSettings):
    """Environment-driven settings for Sprint 4 runtime."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="REMORPH_S4_",
        extra="ignore",
    )

    ENV_BACKEND: str = "simulated"
    OPENENV_CLIENT_MODULE: str = "echo_env"
    OPENENV_CLIENT_CLASS: str = "EchoEnv"
    OPENENV_BASE_URL: str = ""
    OPENENV_STRICT: bool = False

    EPISODE_LOG_PATH: str = "runtime/sprint4/episodes.jsonl"
    BENCHMARK_OUTPUT_DIR: str = "runtime/sprint4"
    MAX_REPAIR_CYCLES: int = Field(default=2, ge=1, le=5)


@lru_cache
def get_sprint4_settings() -> Sprint4Settings:
    """Return cached settings object."""
    return Sprint4Settings()

