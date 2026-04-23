"""Helpers for live-environment response parsing and taxonomy mapping."""

from __future__ import annotations

import json
from typing import Any


_PAYLOAD_SCENARIOS = {
    "schema_missing_key",
    "schema_type_coercion",
    "schema_extra_key",
    "schema_null_injection",
    "type_coercion",
    "null_injection",
}
_ROUTE_SCENARIOS = {
    "route_regression",
    "route_method_spoof",
    "route_invalid_path",
    "bad_method",
}
_AUTH_SCENARIOS = {
    "auth_missing_token",
    "auth_malformed_jwt",
    "auth_missing_tenant",
    "jwt_missing",
    "signature_forgery",
}


def map_scenario_to_category(
    raw_scenario_type: str | None,
    *,
    status_code: int | None = None,
    error_message: str | None = None,
) -> str:
    """Map rich live failure labels into the Sprint 4 reporting taxonomy."""

    normalized = (raw_scenario_type or "").strip().lower()
    if normalized in _PAYLOAD_SCENARIOS or normalized.startswith("schema_"):
        return "payload_drift"
    if normalized in _ROUTE_SCENARIOS or normalized.startswith("route_"):
        return "route_drift"
    if normalized in _AUTH_SCENARIOS or normalized.startswith("auth_"):
        return "auth_drift"

    message = (error_message or "").lower()
    if status_code == 422:
        return "payload_drift"
    if status_code == 404:
        return "route_drift"
    if status_code in {401, 403}:
        return "auth_drift"
    if any(token in message for token in {"field required", "validation", "schema"}):
        return "payload_drift"
    if any(token in message for token in {"not found", "method not allowed", "route"}):
        return "route_drift"
    if any(token in message for token in {"auth", "token", "jwt", "unauthorized", "forbidden"}):
        return "auth_drift"
    return "unknown"


def parse_actual_server_response(value: Any) -> dict[str, Any] | list[Any] | None:
    """Parse a stringified JSON server response without raising."""

    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str):
        return None

    payload = value.strip()
    if not payload:
        return None
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, (dict, list)) else None


def extract_failure_signals(
    *,
    status_code: int,
    error_message: str | None,
    parsed_response: dict[str, Any] | list[Any] | None,
) -> dict[str, Any]:
    """Extract structured hints from live server error details."""

    signals: dict[str, Any] = {
        "missing_fields": [],
        "missing_headers": [],
        "validation_paths": [],
        "auth_error_detail": None,
        "route_error_detail": None,
    }
    detail = _extract_detail(parsed_response)
    if isinstance(detail, list):
        missing_fields: list[str] = []
        missing_headers: list[str] = []
        validation_paths: list[list[str]] = []
        for item in detail:
            if not isinstance(item, dict):
                continue
            loc = item.get("loc")
            if isinstance(loc, list):
                normalized_path = [str(part) for part in loc]
                validation_paths.append(normalized_path)
                if len(normalized_path) >= 2:
                    location = normalized_path[0]
                    field_name = normalized_path[-1]
                    if location == "body" and field_name not in {"body", "query", "path"}:
                        missing_fields.append(field_name)
                    if location == "header" and field_name not in missing_headers:
                        missing_headers.append(field_name)
            if item.get("type") == "missing" and validation_paths:
                last_path = validation_paths[-1]
                if len(last_path) >= 2:
                    location = last_path[0]
                    field_name = last_path[-1]
                    if location == "body" and field_name not in missing_fields:
                        missing_fields.append(field_name)
                    if location == "header" and field_name not in missing_headers:
                        missing_headers.append(field_name)
        signals["missing_fields"] = missing_fields
        signals["missing_headers"] = missing_headers
        signals["validation_paths"] = validation_paths
    elif isinstance(detail, str):
        lowered = detail.lower()
        if status_code == 422 or "validation" in lowered:
            signals["validation_paths"] = []
        if any(token in lowered for token in {"auth", "token", "jwt", "unauthorized", "forbidden"}):
            signals["auth_error_detail"] = detail
        if any(token in lowered for token in {"route", "path", "method", "not found"}):
            signals["route_error_detail"] = detail

    if signals["auth_error_detail"] is None and error_message:
        lowered = error_message.lower()
        if any(token in lowered for token in {"auth", "token", "jwt", "unauthorized", "forbidden"}):
            signals["auth_error_detail"] = error_message
    if signals["route_error_detail"] is None and error_message:
        lowered = error_message.lower()
        if any(token in lowered for token in {"route", "path", "method", "not found"}):
            signals["route_error_detail"] = error_message
    return signals


def summarize_error_message(
    *,
    status_code: int,
    parsed_response: dict[str, Any] | list[Any] | None,
    fallback: str | None = None,
) -> str:
    """Create a stable top-level error message for downstream repair."""

    detail = _extract_detail(parsed_response)
    if isinstance(detail, str) and detail.strip():
        return detail
    if isinstance(detail, list):
        messages = [
            str(item.get("msg"))
            for item in detail
            if isinstance(item, dict) and item.get("msg")
        ]
        if messages:
            return "; ".join(messages)
    if fallback:
        return fallback
    return f"HTTP {status_code}"


def _extract_detail(parsed_response: dict[str, Any] | list[Any] | None) -> Any:
    if isinstance(parsed_response, dict):
        return parsed_response.get("detail")
    if isinstance(parsed_response, list):
        return parsed_response
    return None
