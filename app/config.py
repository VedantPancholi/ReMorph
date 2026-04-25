"""Central application configuration."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the ReMorph healing engine."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="REMORPH_",
        extra="ignore",
    )

    APP_NAME: str = "ReMorph"
    APP_ENV: str = "development"
    DEBUG: bool = True

    GROQ_API_KEY: str = ""
    LLM_MODEL: str = "groq/llama-3.1-8b-instant"
    HEALING_POLICY_NAME: str = "adaptive_rules"
    HEALING_POLICY_VERSION: str = "v1"
    HEALING_POLICY_RUN_ID: str = ""

    REQUEST_TIMEOUT_SECONDS: int = 10
    MAX_FETCH_RETRIES: int = 2
    DOC_PATH_CANDIDATES: list[str] = Field(
        default_factory=lambda: [
            "/openapi.json",
            "/swagger.json",
            "/v3/api-docs",
        ]
    )

    ENABLE_AUTH_HEALING: bool = True
    ENABLE_ROUTE_HEALING: bool = True
    ENABLE_PAYLOAD_HEALING: bool = True
    ENABLE_REPAIR_CACHE: bool = True
    ENABLE_TELEMETRY: bool = True

    LOCAL_SPEC_PATH: str = "app/testsupport/sample_openapi.json"
    REPAIR_CACHE_PATH: str = "runtime/repair_cache.json"
    TELEMETRY_DIR: str = "runtime/telemetry"
    TELEMETRY_MAX_JSONL_BYTES: int = 5_242_880
    TELEMETRY_MAX_ROTATED_FILES: int = 5
    LOG_LEVEL: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Return cached settings for the current process."""

    return Settings()
