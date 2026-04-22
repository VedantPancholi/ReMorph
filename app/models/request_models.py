"""Input models for trapped error events."""

from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from app.constants import SUPPORTED_HTTP_METHODS


class AuthContext(BaseModel):
    """Auth metadata supplied by the proxy or caller."""

    scheme: str | None = None
    header_name: str | None = None
    token_hint: str | None = None


class TrappedError(BaseModel):
    """Normalized failure payload sent to the reasoning layer."""

    model_config = ConfigDict(extra="ignore")

    target_url: str
    method: str
    failed_payload: dict[str, Any] | None = None
    failed_headers: dict[str, str] | None = None
    error_code: int
    error_message: str
    query_params: dict[str, Any] | None = None
    path_params: dict[str, Any] | None = None
    auth_context: AuthContext | None = None

    @field_validator("method")
    @classmethod
    def normalize_method(cls, value: str) -> str:
        method = value.upper()
        if method not in SUPPORTED_HTTP_METHODS:
            raise ValueError(f"Unsupported HTTP method: {value}")
        return method
