"""Deterministic in-memory API environment for Sprint 4."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from sprint4.env.interfaces import APIEnvironment


@dataclass(frozen=True)
class EnvironmentResponse:
    """Normalized response returned by Sprint 4 environments."""

    success: bool
    status_code: int
    message: str | None = None
    body: dict[str, Any] | None = None


class MutableAPIEnvironment(APIEnvironment):
    """Simulates a contract-drifting API with deterministic outcomes."""

    def __init__(
        self,
        *,
        baseline_contract: dict[str, Any],
        drift_contracts: dict[str, dict[str, Any]],
    ) -> None:
        self._baseline_contract = baseline_contract
        self._drift_contracts = drift_contracts
        self._active_contract = baseline_contract
        self._active_drift_mode = "baseline"

    def reset(self) -> None:
        self._active_contract = self._baseline_contract
        self._active_drift_mode = "baseline"

    def apply_drift(self, drift_mode: str) -> None:
        if drift_mode not in self._drift_contracts:
            raise ValueError(f"Unsupported drift mode: {drift_mode}")
        self._active_contract = self._drift_contracts[drift_mode]
        self._active_drift_mode = drift_mode

    def execute_request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> EnvironmentResponse:
        method_name = method.upper()
        path = _normalized_path(url)
        operation = _lookup_operation(self._active_contract, path, method_name)

        if operation is None:
            return EnvironmentResponse(
                success=False,
                status_code=404,
                message="Route not found for active contract",
            )

        if not _auth_satisfied(self._active_contract, operation, headers or {}):
            return EnvironmentResponse(
                success=False,
                status_code=401,
                message="Unauthorized for active contract",
            )

        if not _payload_satisfied(self._active_contract, operation, payload):
            return EnvironmentResponse(
                success=False,
                status_code=400,
                message="Invalid request body for active contract",
            )

        return EnvironmentResponse(
            success=True,
            status_code=_success_status_code(operation, method_name),
            message="ok",
            body={
                "ok": True,
                "path": path,
                "drift_mode": self._active_drift_mode,
            },
        )

    def expected_route_for_method(self, method: str) -> str | None:
        method_name = method.lower()
        for path, operations in self._active_contract.get("paths", {}).items():
            if isinstance(operations, dict) and method_name in operations:
                return path
        return None

    def is_payload_hallucinated(self, payload: dict[str, Any], route: str) -> bool:
        if not payload:
            return False
        operation = _lookup_operation(self._active_contract, route, "POST")
        if operation is None:
            operation = _lookup_operation(self._active_contract, route, "PUT")
        if operation is None:
            operation = _lookup_operation(self._active_contract, route, "PATCH")
        if operation is None:
            return False

        schema = _request_schema(self._active_contract, operation)
        allowed_fields = set(schema.get("properties", {}).keys())
        if not allowed_fields:
            return False
        return any(field not in allowed_fields for field in payload.keys())


def _normalized_path(url: str) -> str:
    path = urlparse(url).path or "/"
    return path if path.startswith("/") else f"/{path}"


def _lookup_operation(
    spec: dict[str, Any],
    path: str,
    method: str,
) -> dict[str, Any] | None:
    operations = spec.get("paths", {}).get(path)
    if not isinstance(operations, dict):
        return None
    operation = operations.get(method.lower())
    return operation if isinstance(operation, dict) else None


def _success_status_code(operation: dict[str, Any], method: str) -> int:
    responses = operation.get("responses", {})
    success_codes = sorted(
        int(code)
        for code in responses
        if str(code).isdigit() and 200 <= int(code) < 300
    )
    if success_codes:
        return success_codes[0]
    return 201 if method == "POST" else 200


def _auth_satisfied(
    spec: dict[str, Any],
    operation: dict[str, Any],
    headers: dict[str, str],
) -> bool:
    requirements = operation.get("security", spec.get("security", []))
    if not requirements:
        return True

    schemes = spec.get("components", {}).get("securitySchemes", {})
    for requirement in requirements:
        if not isinstance(requirement, dict):
            continue

        requirement_ok = True
        for scheme_name in requirement:
            scheme = schemes.get(scheme_name, {})
            scheme_type = scheme.get("type")
            if scheme_type == "apiKey":
                header_name = scheme.get("name")
                if not header_name or not headers.get(header_name):
                    requirement_ok = False
                    break
            elif scheme_type == "http" and scheme.get("scheme") == "bearer":
                auth_header = headers.get("Authorization", "")
                if not auth_header.lower().startswith("bearer "):
                    requirement_ok = False
                    break
            else:
                requirement_ok = False
                break

        if requirement_ok:
            return True

    return False


def _payload_satisfied(
    spec: dict[str, Any],
    operation: dict[str, Any],
    payload: dict[str, Any] | None,
) -> bool:
    schema = _request_schema(spec, operation)
    if not schema:
        return True
    if payload is None:
        return False
    return _matches_schema(spec, payload, schema)


def _request_schema(spec: dict[str, Any], operation: dict[str, Any]) -> dict[str, Any]:
    request_body = operation.get("requestBody", {})
    content = request_body.get("content", {})
    for content_type in (
        "application/json",
        "application/x-www-form-urlencoded",
        "multipart/form-data",
        "text/plain",
    ):
        if content_type in content and isinstance(content[content_type], dict):
            schema = content[content_type].get("schema", {})
            return _resolve_schema(spec, schema)
    return {}


def _resolve_schema(spec: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(schema, dict):
        return {}
    if "$ref" in schema:
        ref = schema["$ref"]
        if not isinstance(ref, str) or not ref.startswith("#/"):
            return {}
        current: Any = spec
        for part in ref.lstrip("#/").split("/"):
            if not isinstance(current, dict):
                return {}
            current = current.get(part)
        return _resolve_schema(spec, current if isinstance(current, dict) else {})

    resolved = dict(schema)
    if isinstance(resolved.get("properties"), dict):
        resolved["properties"] = {
            key: _resolve_schema(spec, value)
            for key, value in resolved["properties"].items()
        }
    if isinstance(resolved.get("items"), dict):
        resolved["items"] = _resolve_schema(spec, resolved["items"])
    return resolved


def _matches_schema(spec: dict[str, Any], value: Any, schema: dict[str, Any]) -> bool:
    resolved = _resolve_schema(spec, schema)
    schema_type = resolved.get("type")

    if schema_type == "object":
        if not isinstance(value, dict):
            return False
        required_fields = resolved.get("required", [])
        if any(field not in value for field in required_fields):
            return False
        properties = resolved.get("properties", {})
        if any(field not in properties for field in value):
            return False
        return all(
            _matches_schema(spec, value[field], child_schema)
            for field, child_schema in properties.items()
            if field in value
        )

    if schema_type == "array":
        if not isinstance(value, list):
            return False
        item_schema = resolved.get("items", {})
        return all(_matches_schema(spec, item, item_schema) for item in value)

    return _matches_primitive(value, schema_type)


def _matches_primitive(value: Any, schema_type: str | None) -> bool:
    if schema_type in {None, "unknown"}:
        return True
    if schema_type == "string":
        return isinstance(value, str)
    if schema_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if schema_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if schema_type == "boolean":
        return isinstance(value, bool)
    return True
