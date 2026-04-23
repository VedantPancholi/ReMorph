"""OpenAPI normalization and endpoint schema extraction."""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any

from app.models.schema_models import (
    EndpointSchema,
    QueryParameter,
    RouteMatchCandidate,
    SecurityRequirement,
)
from app.services.url_utils import normalize_path
from app.utils.error_utils import AmbiguousRouteMatchError, SchemaExtractionError


def extract_schema_for_route(
    spec: dict[str, Any],
    target_path: str,
    method: str,
) -> EndpointSchema:
    """Extract the most relevant endpoint contract for a failed route."""

    (
        resolved_path,
        resolved_method,
        operation,
        route_match_score,
        route_match_reason,
        ranked_candidates,
    ) = _match_operation(
        spec,
        normalize_path(target_path),
        method,
    )
    request_schema = _extract_request_schema(spec, operation)
    security_requirements = _extract_security_requirements(spec, operation)
    query_parameters = _extract_parameters(operation, location="query")
    path_parameters = _extract_parameters(operation, location="path")
    header_parameters = _extract_parameters(operation, location="header")
    supported_content_types = _extract_supported_content_types(operation)
    completeness_flags = _build_completeness_flags(
        request_schema=request_schema,
        security_requirements=security_requirements,
        supported_content_types=supported_content_types,
    )
    completeness_score = _compute_completeness_score(
        completeness_flags=completeness_flags,
        request_schema=request_schema,
        query_parameters=query_parameters,
    )
    docs_confidence = _compute_docs_confidence(
        completeness_score=completeness_score,
        route_match_score=route_match_score,
    )

    return EndpointSchema(
        path=resolved_path,
        method=resolved_method,
        summary=operation.get("summary"),
        description=operation.get("description"),
        required_fields=request_schema.get("required", []),
        properties=request_schema.get("properties", {}),
        request_structure=_annotate_schema_names(
            flatten_request_schema(spec, request_schema)
        ),
        query_parameters=query_parameters,
        path_parameters=path_parameters,
        header_parameters=header_parameters,
        supported_content_types=supported_content_types,
        security_requirements=security_requirements,
        completeness_flags=completeness_flags,
        completeness_score=completeness_score,
        docs_confidence=docs_confidence,
        route_match_score=route_match_score,
        route_match_confidence=min(route_match_score, 1.0),
        route_match_reason=route_match_reason,
        ranked_candidate_endpoints=ranked_candidates,
    )


def resolve_schema_ref(spec: dict[str, Any], ref: str) -> dict[str, Any]:
    """Resolve internal OpenAPI references such as components schemas."""

    if not ref.startswith("#/"):
        raise SchemaExtractionError(f"Unsupported schema reference: {ref}")

    current: Any = spec
    for part in ref.lstrip("#/").split("/"):
        if not isinstance(current, dict) or part not in current:
            raise SchemaExtractionError(f"Unable to resolve schema reference: {ref}")
        current = current[part]

    if not isinstance(current, dict):
        raise SchemaExtractionError(f"Resolved reference is not an object: {ref}")
    return current


def flatten_request_schema(spec: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    """Recursively resolve refs and preserve a compact nested structure."""

    resolved = _resolve_schema(spec, schema)
    schema_type = resolved.get("type")

    if schema_type == "object":
        properties = {
            key: flatten_request_schema(spec, value)
            for key, value in resolved.get("properties", {}).items()
        }
        return {
            "type": "object",
            "required": resolved.get("required", []),
            "properties": properties,
        }

    if schema_type == "array":
        items = resolved.get("items", {})
        return {
            "type": "array",
            "items": flatten_request_schema(spec, items) if items else {},
        }

    flattened = {"type": schema_type or "unknown"}
    if "enum" in resolved:
        flattened["enum"] = resolved["enum"]
    if "format" in resolved:
        flattened["format"] = resolved["format"]
    if "pattern" in resolved:
        flattened["pattern"] = resolved["pattern"]
    if "default" in resolved:
        flattened["default"] = resolved["default"]
    if "minLength" in resolved:
        flattened["minLength"] = resolved["minLength"]
    if "maxLength" in resolved:
        flattened["maxLength"] = resolved["maxLength"]
    if "minimum" in resolved:
        flattened["minimum"] = resolved["minimum"]
    if "maximum" in resolved:
        flattened["maximum"] = resolved["maximum"]
    return flattened


def _annotate_schema_names(
    schema: dict[str, Any],
    *,
    field_name: str | None = None,
) -> dict[str, Any]:
    annotated = dict(schema)
    if field_name:
        annotated["name"] = field_name

    if annotated.get("type") == "object":
        annotated["properties"] = {
            key: _annotate_schema_names(value, field_name=key)
            for key, value in annotated.get("properties", {}).items()
        }
    elif annotated.get("type") == "array" and isinstance(annotated.get("items"), dict):
        annotated["items"] = _annotate_schema_names(annotated["items"], field_name=field_name)

    return annotated


def _match_operation(
    spec: dict[str, Any],
    target_path: str,
    method: str,
) -> tuple[str, str, dict[str, Any], float, str, list[RouteMatchCandidate]]:
    paths = spec.get("paths", {})
    if not isinstance(paths, dict) or not paths:
        raise SchemaExtractionError("OpenAPI spec does not contain paths")

    method_name = method.lower()
    exact_path = paths.get(target_path)
    if isinstance(exact_path, dict) and method_name in exact_path:
        return (
            target_path,
            method.upper(),
            exact_path[method_name],
            1.0,
            "Exact path and method match found in spec.",
            [
                RouteMatchCandidate(
                    path=target_path,
                    score=1.0,
                    reason="Exact path and method match found in spec.",
                )
            ],
        )

    if isinstance(exact_path, dict) and exact_path:
        selected_method, selected_operation = _pick_exact_path_operation(
            exact_path,
            payload_expected=method_name in {"post", "put", "patch"},
        )
        return (
            target_path,
            selected_method.upper(),
            selected_operation,
            0.98,
            f"Exact path match found in spec; method corrected to {selected_method.upper()}.",
            [
                RouteMatchCandidate(
                    path=target_path,
                    score=0.98,
                    reason=f"Exact path match found in spec; method corrected to {selected_method.upper()}.",
                )
            ],
        )

    for candidate_path, candidate_operations in paths.items():
        if not isinstance(candidate_operations, dict):
            continue
        if not _path_template_matches_target(candidate_path, target_path):
            continue
        selected_method, selected_operation = _pick_exact_path_operation(
            candidate_operations,
            payload_expected=method_name in {"post", "put", "patch"},
        )
        return (
            candidate_path,
            selected_method.upper(),
            selected_operation,
            0.97,
            f"Parameterized path match found in spec; method corrected to {selected_method.upper()}.",
            [
                RouteMatchCandidate(
                    path=candidate_path,
                    score=0.97,
                    reason=f"Parameterized path match found in spec; method corrected to {selected_method.upper()}.",
                )
            ],
        )

    best_score = 0.0
    best_match: tuple[str, str, dict[str, Any]] | None = None
    second_best_score = 0.0
    target_segments = normalize_path(target_path).strip("/").split("/")
    candidate_scores: list[tuple[str, dict[str, Any], float, str]] = []

    for candidate_path, candidate_operations in paths.items():
        if not isinstance(candidate_operations, dict) or method_name not in candidate_operations:
            continue
        score, reason = _score_candidate_path(target_segments, target_path, candidate_path)
        candidate_scores.append((candidate_path, candidate_operations[method_name], score, reason))
        if score > best_score:
            second_best_score = best_score
            best_score = score
            best_match = (candidate_path, method_name.upper(), candidate_operations[method_name])
        elif score > second_best_score:
            second_best_score = score

    if best_match is None:
        raise SchemaExtractionError(
            f"No route match found for {method.upper()} {target_path}"
        )

    ranked_candidates = [
        RouteMatchCandidate(path=path, score=round(max(score, 0.0), 4), reason=reason)
        for path, _operation, score, reason in sorted(
            candidate_scores,
            key=lambda item: item[2],
            reverse=True,
        )[:3]
    ]

    if best_score < 0.45:
        raise SchemaExtractionError(
            f"No confident route match found for {method.upper()} {target_path}"
        )
    if second_best_score and (best_score - second_best_score) < 0.05:
        raise AmbiguousRouteMatchError(
            f"Ambiguous route match for {method.upper()} {target_path}"
        )

    best_reason = next(
        reason for path, _operation, score, reason in candidate_scores if path == best_match[0] and score == best_score
    )
    return best_match[0], best_match[1], best_match[2], best_score, best_reason, ranked_candidates


def _pick_exact_path_operation(
    operations: dict[str, Any],
    *,
    payload_expected: bool,
) -> tuple[str, dict[str, Any]]:
    """Choose the best operation when the path is exact but the method drifted."""

    preferred_order = ["post", "put", "patch"] if payload_expected else ["get", "delete"]
    for method_name in preferred_order:
        operation = operations.get(method_name)
        if isinstance(operation, dict):
            return method_name, operation

    for method_name, operation in operations.items():
        if isinstance(operation, dict):
            return method_name, operation
    raise SchemaExtractionError("Exact path match did not contain a usable operation")


def _score_candidate_path(
    target_segments: list[str],
    target_path: str,
    candidate_path: str,
) -> tuple[float, str]:
    candidate_segments = normalize_path(candidate_path).strip("/").split("/")
    similarity = SequenceMatcher(None, target_path, candidate_path).ratio()
    segment_overlap = len(set(target_segments) & set(candidate_segments))

    param_score = 0.0
    reason_bits: list[str] = []
    for target_segment, candidate_segment in zip(target_segments, candidate_segments):
        if target_segment == candidate_segment:
            param_score += 0.3
            reason_bits.append(f"exact segment '{target_segment}'")
        elif _is_path_parameter(candidate_segment):
            param_score += 0.22
            reason_bits.append(f"path parameter '{candidate_segment}'")
        elif _normalize_token(target_segment) == _normalize_token(candidate_segment):
            param_score += 0.2
            reason_bits.append(f"semantic token match '{target_segment}'")

    length_penalty = abs(len(target_segments) - len(candidate_segments)) * 0.1
    score = max(similarity + (0.15 * segment_overlap) + param_score - length_penalty, 0.0)
    reason = "; ".join(reason_bits) if reason_bits else "fallback string similarity"
    return score, reason


def _is_path_parameter(segment: str) -> bool:
    return segment.startswith("{") and segment.endswith("}")


def _normalize_token(segment: str) -> str:
    return "".join(character.lower() for character in segment if character.isalnum())


def _path_template_matches_target(candidate_path: str, target_path: str) -> bool:
    candidate_segments = normalize_path(candidate_path).strip("/").split("/")
    target_segments = normalize_path(target_path).strip("/").split("/")
    if len(candidate_segments) != len(target_segments):
        return False

    for candidate_segment, target_segment in zip(candidate_segments, target_segments):
        if _is_path_parameter(candidate_segment):
            continue
        if candidate_segment != target_segment:
            return False
    return True


def _extract_request_schema(
    spec: dict[str, Any],
    operation: dict[str, Any],
) -> dict[str, Any]:
    request_body = operation.get("requestBody", {})
    content = request_body.get("content", {})
    supported_content_types = [
        "application/json",
        "application/x-www-form-urlencoded",
        "multipart/form-data",
        "text/plain",
    ]
    schema: dict[str, Any] = {}
    for content_type in supported_content_types:
        if content_type in content:
            schema = content[content_type].get("schema", {})
            break
    return _resolve_schema(spec, schema)


def _resolve_schema(spec: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(schema, dict):
        return {}

    if "$ref" in schema:
        return _resolve_schema(spec, resolve_schema_ref(spec, schema["$ref"]))

    resolved = dict(schema)
    if "properties" in resolved and isinstance(resolved["properties"], dict):
        resolved["properties"] = {
            key: _resolve_schema(spec, value)
            for key, value in resolved["properties"].items()
        }
    if "items" in resolved and isinstance(resolved["items"], dict):
        resolved["items"] = _resolve_schema(spec, resolved["items"])
    return resolved


def _extract_security_requirements(
    spec: dict[str, Any],
    operation: dict[str, Any],
) -> list[SecurityRequirement]:
    requirements = operation.get("security", spec.get("security", []))
    schemes = spec.get("components", {}).get("securitySchemes", {})

    normalized: list[SecurityRequirement] = []
    for requirement in requirements:
        if not isinstance(requirement, dict):
            continue
        for scheme_name in requirement:
            scheme = schemes.get(scheme_name, {})
            normalized.append(
                SecurityRequirement(
                    name=scheme_name,
                    type=scheme.get("type"),
                    location=scheme.get("in"),
                    scheme=scheme.get("scheme"),
                    header_name=scheme.get("name"),
                )
            )
    return normalized


def _extract_parameters(
    operation: dict[str, Any],
    *,
    location: str,
) -> list[QueryParameter]:
    parameters = operation.get("parameters", [])
    normalized: list[QueryParameter] = []
    for parameter in parameters:
        if not isinstance(parameter, dict) or parameter.get("in") != location:
            continue
        schema = parameter.get("schema", {})
        normalized.append(
            QueryParameter(
                name=parameter.get("name", "unknown"),
                location=location,
                required=bool(parameter.get("required", False)),
                schema_type=schema.get("type"),
                schema_format=schema.get("format"),
                schema_default=schema.get("default"),
                schema_pattern=schema.get("pattern"),
            )
        )
    return normalized


def _extract_supported_content_types(operation: dict[str, Any]) -> list[str]:
    request_body = operation.get("requestBody", {})
    content = request_body.get("content", {})
    return sorted(content.keys()) if isinstance(content, dict) else []


def _build_completeness_flags(
    *,
    request_schema: dict[str, Any],
    security_requirements: list[SecurityRequirement],
    supported_content_types: list[str],
) -> list[str]:
    flags: list[str] = []
    if not request_schema:
        flags.append("missing_request_schema")
    if request_schema and request_schema.get("type") != "object":
        flags.append("non_object_request_schema")
    if not supported_content_types:
        flags.append("missing_request_content_type")
    if security_requirements:
        unsupported = [
            requirement.name
            for requirement in security_requirements
            if requirement.type not in {"apiKey", "http", "oauth2"}
        ]
        if unsupported:
            flags.append("contains_unsupported_auth_scheme")
    if not flags:
        flags.append("complete")
    return flags


def _compute_completeness_score(
    *,
    completeness_flags: list[str],
    request_schema: dict[str, Any],
    query_parameters: list[QueryParameter],
) -> float:
    score = 1.0
    if "missing_request_schema" in completeness_flags:
        score -= 0.35
    if "missing_request_content_type" in completeness_flags:
        score -= 0.15
    if "contains_unsupported_auth_scheme" in completeness_flags:
        score -= 0.2
    if request_schema.get("properties"):
        score += 0.05
    if query_parameters:
        score += 0.05
    return max(0.0, min(score, 1.0))


def _compute_docs_confidence(
    *,
    completeness_score: float,
    route_match_score: float,
) -> float:
    return max(0.0, min((0.55 * completeness_score) + (0.45 * min(route_match_score, 1.0)), 1.0))
