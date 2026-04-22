"""Deterministic repair strategies for the core demo drift scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from app.models.request_models import TrappedError
from app.models.response_models import HealedRequest
from app.models.schema_models import EndpointSchema

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

    fixed_url = _rewrite_url(trapped_error.target_url, endpoint_schema.path)
    fixed_headers = _rewrite_headers(trapped_error, endpoint_schema)
    fixed_payload = _rewrite_payload(trapped_error, endpoint_schema)

    changes = []
    if fixed_url != trapped_error.target_url:
        changes.append("route")
    if fixed_headers != trapped_error.failed_headers:
        changes.append("auth")
    if fixed_payload != trapped_error.failed_payload:
        changes.append("payload")

    healing_action = _choose_healing_action(changes)
    reasoning = _build_reasoning(changes, endpoint_schema)
    confidence = _estimate_confidence(changes, endpoint_schema, trapped_error.error_code)

    return HealedRequest(
        reasoning=reasoning,
        fixed_url=fixed_url,
        fixed_method=trapped_error.method,
        fixed_payload=fixed_payload,
        fixed_headers=fixed_headers,
        schema_summary=_build_schema_summary(endpoint_schema, changes),
        healing_action=healing_action,
        confidence=confidence,
    )


def _rewrite_url(target_url: str, resolved_path: str) -> str:
    parts = urlsplit(target_url)
    if not resolved_path or parts.path == resolved_path:
        return target_url
    return urlunsplit((parts.scheme, parts.netloc, resolved_path, parts.query, parts.fragment))


def _rewrite_headers(
    trapped_error: TrappedError,
    endpoint_schema: EndpointSchema,
) -> dict[str, str] | None:
    headers = dict(trapped_error.failed_headers or {})
    if not endpoint_schema.security_requirements:
        return headers or None

    token = _extract_auth_token(headers)
    changed = False

    for requirement in endpoint_schema.security_requirements:
        if requirement.type == "apiKey" and requirement.header_name:
            if token:
                headers[requirement.header_name] = token
            headers.pop("Authorization", None)
            changed = True
        elif requirement.type == "http" and requirement.scheme == "bearer" and token:
            headers["Authorization"] = f"Bearer {token}"
            changed = True

    return headers if changed or headers else None


def _rewrite_payload(
    trapped_error: TrappedError,
    endpoint_schema: EndpointSchema,
) -> dict[str, Any] | None:
    if not endpoint_schema.request_structure:
        return trapped_error.failed_payload

    source_payload = trapped_error.failed_payload or {}
    if not source_payload:
        return source_payload or None

    rebuilt = _materialize_from_schema(endpoint_schema.request_structure, source_payload)
    return rebuilt or source_payload


def _materialize_from_schema(schema: dict[str, Any], source_payload: dict[str, Any]) -> Any:
    schema_type = schema.get("type")
    if schema_type == "object":
        result: dict[str, Any] = {}
        for key, child_schema in schema.get("properties", {}).items():
            value = _materialize_from_schema(child_schema, source_payload)
            if value is not None:
                result[key] = value
        return result

    if schema_type == "array":
        return []

    return _best_source_value(source_payload, schema)


def _best_source_value(source_payload: dict[str, Any], schema: dict[str, Any]) -> Any:
    candidates = _collect_leaf_candidates(source_payload)
    if not candidates:
        return None

    target_hint = schema.get("title") or schema.get("name")
    if target_hint:
        exact = _match_candidate(target_hint, candidates)
        if exact is not None:
            return exact

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
        reason_bits.append(f"route updated to {endpoint_schema.path}")
    if "payload" in changes:
        reason_bits.append("payload rebuilt from the normalized request schema")
    if "auth" in changes:
        reason_bits.append("headers aligned with the extracted security scheme")
    return "Deterministic repair applied: " + "; ".join(reason_bits) + "."


def _estimate_confidence(changes: list[str], endpoint_schema: EndpointSchema, error_code: int) -> float:
    confidence = 0.55
    if error_code in {400, 401, 404}:
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
        "security_requirements": [
            requirement.model_dump(mode="json")
            for requirement in endpoint_schema.security_requirements
        ],
        "applied_changes": changes,
    }
