"""Request execution wrapper for the mutable environment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sprint4.env.interfaces import APIEnvironment
from sprint4.env.mutable_api_env import EnvironmentResponse


@dataclass(frozen=True)
class RequestExecutionResult:
    """Normalized request execution result."""

    success: bool
    status_code: int
    error_message: str | None = None
    response_body: dict[str, Any] | None = None


def execute_against_env(
    env: APIEnvironment,
    *,
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
) -> RequestExecutionResult:
    """Run one request against the mutable environment and normalize output."""
    response = env.execute_request(method, url, headers=headers, payload=payload)
    return _normalize_response(response)


def _normalize_response(response: EnvironmentResponse) -> RequestExecutionResult:
    return RequestExecutionResult(
        success=response.success,
        status_code=response.status_code,
        error_message=None if response.success else response.message,
        response_body=response.body if response.success else None,
    )
