"""Deterministic repair strategies for the core demo drift scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.models.request_models import TrappedError
from app.models.response_models import HealedRequest
from app.models.schema_models import EndpointSchema, QueryParameter

_ALIAS_GROUPS = (
    {"firstname", "fname", "givenname", "forename"},
    {"lastname", "lname", "surname", "familyname"},
    {"customerid", "accountuid", "accountid", "userid", "useruid", "patientid"},
    {"transactions", "ledger", "entries"},
)


@dataclass
class _CandidateValue:
    key: str
    value: Any


def build_deterministic_repair(
    trapped_error: TrappedError,
    endpoint_schema: EndpointSchema,
) -> HealedRequest:
    """Create a repair without depending on the model provider."""

    fixed_method = endpoint_schema.method or trapped_error.method
    fixed_url = _rewrite_url(trapped_error, endpoint_schema)
    fixed_headers = _rewrite_headers(trapped_error, endpoint_schema)
    fixed_payload = _rewrite_payload(trapped_error, endpoint_schema)

    changes: list[str] = []
    if fixed_url != trapped_error.target_url:
        changes.append("route")
    if fixed_method != trapped_error.method:
        changes.append("route")
    if fixed_headers != trapped_error.failed_headers:
        changes.append("auth")
    if fixed_payload != trapped_error.failed_payload:
        changes.append("payload")
    changes = list(dict.fromkeys(changes))

    healing_action = _choose_healing_action(changes)
    reasoning = _build_reasoning(changes, endpoint_schema)
    confidence = _estimate_confidence(changes, endpoint_schema, trapped_error.error_code)

    return HealedRequest(
        reasoning=reasoning,
        fixed_url=fixed_url,
        fixed_method=fixed_method,
        fixed_payload=fixed_payload,
        fixed_headers=fixed_headers,
        schema_summary=_build_schema_summary(endpoint_schema, changes),
        healing_action=healing_action,
        confidence=confidence,
    )


def _rewrite_url(
    trapped_error: TrappedError,
    endpoint_schema: EndpointSchema,
) -> str:
    parts = urlsplit(trapped_error.target_url)
    rewritten_path = _rewrite_path(parts.path, endpoint_schema.path, trapped_error, endpoint_schema)
    rewritten_query = _rewrite_query(parts.query, trapped_error, endpoint_schema)
    if rewritten_path == parts.path and rewritten_query == parts.query:
        return trapped_error.target_url
    return urlunsplit((parts.scheme, parts.netloc, rewritten_path, rewritten_query, parts.fragment))


def _rewrite_path(
    current_path: str,
    resolved_path: str,
    trapped_error: TrappedError,
    endpoint_schema: EndpointSchema,
) -> str:
    if not resolved_path:
        return current_path

    current_segments = [segment for segment in current_path.split("/") if segment]
    resolved_segments = [segment for segment in resolved_path.split("/") if segment]
    path_params = dict(trapped_error.path_params or {})

    for index, segment in enumerate(resolved_segments):
        if not _is_path_placeholder(segment):
            continue
        parameter_name = segment[1:-1]
        if parameter_name in path_params and path_params[parameter_name]:
            resolved_segments[index] = str(path_params[parameter_name])
            continue
        if index < len(current_segments):
            candidate = current_segments[index]
            if "{" not in candidate and "}" not in candidate:
                resolved_segments[index] = candidate
                continue
        parameter = _find_parameter(endpoint_schema.path_parameters, parameter_name)
        resolved_segments[index] = _default_parameter_value(parameter_name, parameter)

    rebuilt = "/" + "/".join(resolved_segments)
    return rebuilt or resolved_path


def _rewrite_query(
    current_query: str,
    trapped_error: TrappedError,
    endpoint_schema: EndpointSchema,
) -> str:
    params = dict(parse_qsl(current_query, keep_blank_values=True))
    params.update(
        {
            key: str(value)
            for key, value in (trapped_error.query_params or {}).items()
            if value is not None
        }
    )

    missing_query_params = {
        loc[-1]
        for loc in (trapped_error.failure_signals or {}).get("validation_paths", [])
        if isinstance(loc, list) and len(loc) >= 2 and loc[0] == "query"
    }
    invalid_query_params = set(missing_query_params)
    changed = False

    for parameter in endpoint_schema.query_parameters:
        if not parameter.required:
            if parameter.name not in invalid_query_params:
                continue
        if (
            parameter.name in params
            and params[parameter.name] not in {"", None}
            and parameter.name not in invalid_query_params
        ):
            continue
        if missing_query_params and parameter.name not in missing_query_params and parameter.required:
            continue
        params[parameter.name] = _default_parameter_value(parameter.name, parameter)
        changed = True

    if not params:
        return ""
    if not changed and params == dict(parse_qsl(current_query, keep_blank_values=True)):
        return current_query
    return urlencode(params)


def _rewrite_headers(
    trapped_error: TrappedError,
    endpoint_schema: EndpointSchema,
) -> dict[str, str] | None:
    headers = dict(trapped_error.failed_headers or {})
    failure_signals = trapped_error.failure_signals or {}
    missing_headers = {
        field
        for field in failure_signals.get("missing_headers", [])
        if isinstance(field, str)
    }
    changed = False

    token = _extract_auth_token(headers)
    for requirement in endpoint_schema.security_requirements:
        if requirement.type == "apiKey" and requirement.header_name:
            if token and requirement.header_name not in headers:
                headers[requirement.header_name] = token
                changed = True
            if token and "Authorization" in headers and requirement.header_name != "Authorization":
                headers.pop("Authorization", None)
                changed = True
        elif requirement.type == "http" and requirement.scheme == "bearer":
            if token and headers.get("Authorization") != f"Bearer {token}":
                headers["Authorization"] = f"Bearer {token}"
                changed = True

    for parameter in endpoint_schema.header_parameters:
        if not parameter.required:
            continue
        if parameter.name in headers and headers.get(parameter.name):
            continue
        if missing_headers and parameter.name not in missing_headers:
            continue
        default_value = _default_header_value(parameter.name)
        if default_value is not None:
            headers[parameter.name] = default_value
            changed = True

    return headers if changed or headers else None


def _rewrite_payload(
    trapped_error: TrappedError,
    endpoint_schema: EndpointSchema,
) -> dict[str, Any] | None:
    if not endpoint_schema.request_structure:
        return trapped_error.failed_payload

    source_payload = trapped_error.failed_payload or {}
    failure_signals = trapped_error.failure_signals or {}
    missing_fields = failure_signals.get("missing_fields", [])
    body_missing = any(
        isinstance(loc, list) and len(loc) == 1 and loc[0] == "body"
        for loc in failure_signals.get("validation_paths", [])
    )
    if not source_payload and not missing_fields and not body_missing:
        return trapped_error.failed_payload

    rebuilt = _materialize_from_schema(
        endpoint_schema.request_structure,
        source_payload,
        failure_signals=failure_signals,
    )
    return rebuilt or source_payload


def _materialize_from_schema(
    schema: dict[str, Any],
    source_payload: dict[str, Any],
    *,
    failure_signals: dict[str, Any],
) -> Any:
    schema_type = schema.get("type")
    if schema_type == "object":
        result: dict[str, Any] = {}
        required_fields = set(schema.get("required", []))
        missing_fields = {
            field
            for field in failure_signals.get("missing_fields", [])
            if isinstance(field, str)
        }
        for key, child_schema in schema.get("properties", {}).items():
            value = _materialize_from_schema(
                child_schema,
                source_payload,
                failure_signals=failure_signals,
            )
            if value is None and (key in required_fields or key in missing_fields):
                value = _default_value_for_schema(child_schema, key=key)
            if value is not None:
                result[key] = value
        return result

    if schema_type == "array":
        return []

    value = _best_source_value(source_payload, schema)
    if value is not None:
        return value
    return _default_value_for_schema(schema)


def _best_source_value(source_payload: dict[str, Any], schema: dict[str, Any]) -> Any:
    candidates = _collect_leaf_candidates(source_payload)
    if not candidates:
        return None

    target_hint = schema.get("title") or schema.get("name")
    if target_hint:
        exact = _match_candidate(target_hint, candidates)
        if exact is not None and _value_matches_schema(exact, schema):
            return exact

    return None


def _default_value_for_schema(schema: dict[str, Any], *, key: str | None = None) -> Any:
    if "default" in schema and schema["default"] is not None:
        return schema["default"]

    schema_type = schema.get("type")
    enum_values = schema.get("enum")
    if isinstance(enum_values, list) and enum_values:
        return enum_values[0]

    normalized_key = _normalize_key(key or schema.get("name", ""))
    schema_format = str(schema.get("format") or "")
    schema_pattern = str(schema.get("pattern") or "")
    minimum = schema.get("minimum")

    if "email" in normalized_key or schema_format == "email":
        return "test@example.com"
    if "expiry" in normalized_key:
        return "12/26"
    if "cvv" in normalized_key:
        return "123"
    if "cardnumber" in normalized_key or "pan" in normalized_key:
        return "1234567812345678"
    if "zipcode" in normalized_key or "postal" in normalized_key:
        return "12345"
    if "country" in normalized_key or "iso" in normalized_key:
        return "US"
    if "amount" in normalized_key:
        return 100
    if "date" in normalized_key and schema_format == "date-time":
        return "2024-01-01T00:00:00Z"
    if schema_format == "uuid" or normalized_key.endswith("id"):
        return "123e4567-e89b-12d3-a456-426614174000"
    if "[A-Z0-9]{8,12}" in schema_pattern:
        return "ABCD12345XYZ"
    if "(0[1-9]|1[0-2])" in schema_pattern:
        return "12/26"

    if schema_type == "string":
        return _default_string_value(schema, normalized_key)
    if schema_type == "integer":
        return int(minimum) if isinstance(minimum, (int, float)) else 1
    if schema_type == "number":
        return minimum if isinstance(minimum, (int, float)) else 100
    if schema_type == "boolean":
        return True
    if schema_type == "object":
        return {}
    if schema_type == "array":
        return []
    return None


def _collect_leaf_candidates(payload: Any, *, parent_key: str = "") -> list[_CandidateValue]:
    if isinstance(payload, dict):
        results: list[_CandidateValue] = []
        for key, value in payload.items():
            full_key = f"{parent_key}.{key}" if parent_key else key
            if isinstance(value, dict):
                results.extend(_collect_leaf_candidates(value, parent_key=full_key))
            else:
                results.append(_CandidateValue(key=key, value=value))
                results.append(_CandidateValue(key=full_key, value=value))
        return results
    return []


def _match_candidate(target_key: str, candidates: list[_CandidateValue]) -> Any | None:
    normalized_target = _normalize_key(target_key)

    for candidate in candidates:
        if _normalize_key(candidate.key) == normalized_target:
            return candidate.value

    best_value: Any | None = None
    best_score = 0.0
    for candidate in candidates:
        score = _key_similarity(normalized_target, _normalize_key(candidate.key))
        if score > best_score:
            best_score = score
            best_value = candidate.value

    if best_score >= 0.72:
        return best_value
    return None


def _normalize_key(key: str) -> str:
    return "".join(char.lower() for char in key if char.isalnum())


def _key_similarity(left: str, right: str) -> float:
    if left == right:
        return 1.0

    if _share_alias_group(left, right):
        return 0.95

    if left in right or right in left:
        return 0.8

    return SequenceMatcher(None, left, right).ratio()


def _share_alias_group(left: str, right: str) -> bool:
    return any(left in group and right in group for group in _ALIAS_GROUPS)


def _extract_auth_token(headers: dict[str, str]) -> str | None:
    authorization = headers.get("Authorization")
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()

    api_key = headers.get("x-api-key")
    if api_key:
        return api_key

    return None


def _choose_healing_action(changes: list[str]) -> str:
    if len(changes) > 1:
        return "combined_rewrite"
    if "payload" in changes:
        return "payload_rewrite"
    if "route" in changes:
        return "route_rewrite"
    if "auth" in changes:
        return "auth_rewrite"
    return "no_change"


def _build_reasoning(changes: list[str], endpoint_schema: EndpointSchema) -> str:
    if not changes:
        return "No deterministic repair was required because the failed request already matches the extracted schema."

    reason_bits = []
    if "route" in changes:
        reason_bits.append(f"route updated to {endpoint_schema.method} {endpoint_schema.path}")
    if "payload" in changes:
        reason_bits.append("payload rebuilt from the normalized request schema")
    if "auth" in changes:
        reason_bits.append("headers aligned with the extracted security scheme")
    return "Deterministic repair applied: " + "; ".join(reason_bits) + "."


def _estimate_confidence(changes: list[str], endpoint_schema: EndpointSchema, error_code: int) -> float:
    confidence = 0.55
    if error_code in {400, 401, 404, 422}:
        confidence += 0.1
    if endpoint_schema.path:
        confidence += 0.1
    if endpoint_schema.security_requirements:
        confidence += 0.05
    if endpoint_schema.request_structure:
        confidence += 0.1
    if changes:
        confidence += 0.05
    return min(confidence, 0.95)


def _build_schema_summary(endpoint_schema: EndpointSchema, changes: list[str]) -> dict[str, Any]:
    return {
        "path": endpoint_schema.path,
        "method": endpoint_schema.method,
        "required_fields": endpoint_schema.required_fields,
        "required_query_parameters": [
            parameter.name
            for parameter in endpoint_schema.query_parameters
            if parameter.required
        ],
        "required_path_parameters": [
            parameter.name
            for parameter in endpoint_schema.path_parameters
            if parameter.required
        ],
        "required_header_parameters": [
            parameter.name
            for parameter in endpoint_schema.header_parameters
            if parameter.required
        ],
        "security_requirements": [
            requirement.model_dump(mode="json")
            for requirement in endpoint_schema.security_requirements
        ],
        "applied_changes": changes,
    }


def _default_header_value(header_name: str) -> str | None:
    normalized = _normalize_key(header_name)
    if normalized in {"xvendorid", "vendorid"}:
        return "ven-123"
    if normalized in {"xapikey", "apikey"}:
        return "secret"
    if normalized == "authorization":
        return "Bearer demo-token"
    return None


def _find_parameter(parameters: list[QueryParameter], name: str) -> QueryParameter | None:
    for parameter in parameters:
        if parameter.name == name:
            return parameter
    return None


def _default_parameter_value(name: str, parameter: QueryParameter | None) -> str:
    schema = {
        "name": name,
        "type": parameter.schema_type if parameter else "string",
        "format": parameter.schema_format if parameter else None,
        "default": parameter.schema_default if parameter else None,
        "pattern": parameter.schema_pattern if parameter else None,
    }
    return str(_default_value_for_schema(schema, key=name))


def _is_path_placeholder(segment: str) -> bool:
    return segment.startswith("{") and segment.endswith("}")


def _value_matches_schema(value: Any, schema: dict[str, Any]) -> bool:
    schema_type = schema.get("type")
    if value is None:
        return False
    if schema_type == "string":
        if not isinstance(value, str):
            return False
        pattern = schema.get("pattern")
        if pattern == "^[A-Z0-9]{8,12}$":
            return value.isalnum() and value.upper() == value and 8 <= len(value) <= 12
        return True
    if schema_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if schema_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if schema_type == "boolean":
        return isinstance(value, bool)
    if schema_type == "object":
        return isinstance(value, dict)
    if schema_type == "array":
        return isinstance(value, list)
    return True


def _default_string_value(schema: dict[str, Any], normalized_key: str) -> str:
    pattern = str(schema.get("pattern") or "")
    min_length = schema.get("minLength")
    max_length = schema.get("maxLength")

    if pattern == "^[A-Z0-9]{8,12}$":
        return "ABCD12345XYZ"

    if normalized_key == "companyname":
        return "Acme Corp"
    if normalized_key == "currency":
        return "USD"

    candidate = "test_string"
    if isinstance(max_length, int):
        candidate = candidate[:max_length]
    if isinstance(min_length, int) and len(candidate) < min_length:
        candidate = (candidate + ("X" * min_length))[:max(min_length, len(candidate))]
    return candidate
