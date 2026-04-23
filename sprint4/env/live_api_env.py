"""Live HTTP environment adapter for the Sprint 1 FastAPI target server."""

from __future__ import annotations

from typing import Any

import httpx

from sprint4.env.interfaces import APIEnvironment
from sprint4.env.live_support import (
    extract_failure_signals,
    map_scenario_to_category,
    parse_actual_server_response,
    summarize_error_message,
)
from sprint4.env.mutable_api_env import EnvironmentResponse


class LiveAPIEnvironment(APIEnvironment):
    """Call the live FastAPI target while matching the Sprint 4 env contract."""

    def __init__(
        self,
        *,
        base_url: str,
        baseline_contract: dict[str, Any],
        client: httpx.Client | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._baseline_contract = baseline_contract
        self._client = client or httpx.Client(timeout=timeout)
        self._active_drift_mode = "baseline"

    def reset(self) -> None:
        self._active_drift_mode = "baseline"

    def apply_drift(self, drift_mode: str) -> None:
        # The live server exposes failures through request variation, not env mutation.
        self._active_drift_mode = drift_mode

    def execute_request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> EnvironmentResponse:
        response = self._client.request(
            method.upper(),
            self._absolute_url(url),
            headers=headers or {},
            json=payload,
        )
        parsed_response = parse_actual_server_response(response.text)
        success = response.status_code < 400
        message = None
        metadata: dict[str, Any] = {"env_mode": "live", "drift_mode": self._active_drift_mode}
        body: dict[str, Any] | None = None
        if success:
            if isinstance(parsed_response, dict):
                body = parsed_response
            else:
                body = {"raw_response": response.text}
        else:
            message = summarize_error_message(
                status_code=response.status_code,
                parsed_response=parsed_response,
                fallback=response.reason_phrase,
            )
            metadata["failure_signals"] = extract_failure_signals(
                status_code=response.status_code,
                error_message=message,
                parsed_response=parsed_response,
            )
            metadata["scenario_type"] = map_scenario_to_category(
                None,
                status_code=response.status_code,
                error_message=message,
            )

        return EnvironmentResponse(
            success=success,
            status_code=response.status_code,
            message=message,
            body=body,
            raw_response_text=response.text,
            parsed_error=parsed_response if not success else None,
            metadata=metadata,
        )

    def expected_route_for_method(self, method: str) -> str | None:
        method_name = method.lower()
        for path, operations in self._baseline_contract.get("paths", {}).items():
            if isinstance(operations, dict) and method_name in operations:
                return path
        return None

    def is_payload_hallucinated(self, payload: dict[str, Any], route: str) -> bool:
        if not payload:
            return False
        operation = self._baseline_contract.get("paths", {}).get(route, {}).get("post")
        if not isinstance(operation, dict):
            return False
        request_body = operation.get("requestBody", {})
        content = request_body.get("content", {})
        schema = content.get("application/json", {}).get("schema", {})
        properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
        allowed_fields = {key for key in properties if isinstance(key, str)}
        if not allowed_fields:
            return False
        return any(field not in allowed_fields for field in payload)

    def _absolute_url(self, url: str) -> str:
        if url.startswith("http://") or url.startswith("https://"):
            return url
        if url.startswith("/"):
            return f"{self._base_url}{url}"
        return f"{self._base_url}/{url}"
