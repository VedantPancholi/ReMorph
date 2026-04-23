"""Adapter that normalizes an OpenEnv-style client behind the Sprint 4 interface."""

from __future__ import annotations

from typing import Any

from sprint4.env.interfaces import APIEnvironment
from sprint4.env.mutable_api_env import EnvironmentResponse


class OpenEnvAPIEnvironment(APIEnvironment):
    """Wrap an OpenEnv client with the APIEnvironment contract."""

    def __init__(
        self,
        *,
        client: Any,
        baseline_contract: dict[str, Any],
        strict: bool = False,
    ) -> None:
        self._client = client
        self._baseline_contract = baseline_contract
        self._strict = strict

    def reset(self) -> None:
        if hasattr(self._client, "reset"):
            self._client.reset()

    def apply_drift(self, drift_mode: str) -> None:
        if hasattr(self._client, "apply_drift"):
            self._client.apply_drift(drift_mode)
            return
        if hasattr(self._client, "step"):
            try:
                self._client.step({"type": "apply_drift", "drift_mode": drift_mode})
            except Exception:
                if self._strict:
                    raise

    def execute_request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> EnvironmentResponse:
        result = self._client.step(
            {
                "type": "http_request",
                "method": method.upper(),
                "url": url,
                "headers": headers or {},
                "payload": payload,
            }
        )
        return _normalize_step_result(result)

    def expected_route_for_method(self, method: str) -> str | None:
        state = self._safe_state()
        route_map = state.get("expected_route_by_method")
        if isinstance(route_map, dict):
            route = route_map.get(method.upper()) or route_map.get(method.lower())
            if isinstance(route, str):
                return route
        for path, operations in self._baseline_contract.get("paths", {}).items():
            if isinstance(operations, dict) and method.lower() in operations:
                return path
        return None

    def is_payload_hallucinated(self, payload: dict[str, Any], route: str) -> bool:
        if not payload:
            return False
        state = self._safe_state()
        allowed_fields = state.get("allowed_payload_fields")
        if isinstance(allowed_fields, dict) and isinstance(allowed_fields.get(route), list):
            allowed = {
                field
                for field in allowed_fields[route]
                if isinstance(field, str)
            }
            return any(field not in allowed for field in payload.keys())
        return False

    def _safe_state(self) -> dict[str, Any]:
        if not hasattr(self._client, "state"):
            return {}
        state = self._client.state()
        return state if isinstance(state, dict) else {}


def _normalize_step_result(result: Any) -> EnvironmentResponse:
    if not isinstance(result, dict):
        return EnvironmentResponse(
            success=False,
            status_code=500,
            message="OpenEnv client returned a non-dict response",
        )

    status_code = int(result.get("status_code", 500))
    success = bool(result.get("success", status_code < 400))
    message = result.get("error_message") or result.get("message")
    body = result.get("body") if isinstance(result.get("body"), dict) else None
    return EnvironmentResponse(
        success=success,
        status_code=status_code,
        message=message if isinstance(message, str) else None,
        body=body,
    )
