"""Output models for healed requests."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.constants import HEALING_ACTIONS, SUPPORTED_HTTP_METHODS

HealingAction = Literal[
    "payload_rewrite",
    "route_rewrite",
    "auth_rewrite",
    "combined_rewrite",
    "no_change",
]


class HealedRequest(BaseModel):
    """Validated request repair emitted by the reasoning layer."""

    model_config = ConfigDict(extra="forbid")

    reasoning: str
    fixed_url: str
    fixed_method: str
    fixed_payload: dict[str, Any] | None = None
    fixed_headers: dict[str, str] | None = None
    schema_summary: dict[str, Any] | None = None
    healing_action: HealingAction = "no_change"
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator("fixed_method")
    @classmethod
    def normalize_method(cls, value: str) -> str:
        method = value.upper()
        if method not in SUPPORTED_HTTP_METHODS:
            raise ValueError(f"Unsupported fixed method: {value}")
        return method

    @field_validator("healing_action")
    @classmethod
    def validate_action(cls, value: str) -> str:
        if value not in HEALING_ACTIONS:
            raise ValueError(f"Unsupported healing action: {value}")
        return value
