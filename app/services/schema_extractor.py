"""OpenAPI normalization and endpoint schema extraction."""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any

from app.models.schema_models import EndpointSchema, SecurityRequirement
from app.services.url_utils import normalize_path
from app.utils.error_utils import SchemaExtractionError


def extract_schema_for_route(
    spec: dict[str, Any],
    target_path: str,
    method: str,
) -> EndpointSchema:
    """Extract the most relevant endpoint contract for a failed route."""

    resolved_path, operation = _match_operation(spec, normalize_path(target_path), method)
    request_schema = _extract_request_schema(spec, operation)
    security_requirements = _extract_security_requirements(spec, operation)

    return EndpointSchema(
        path=resolved_path,
        method=method.upper(),
        summary=operation.get("summary"),
        description=operation.get("description"),
        required_fields=request_schema.get("required", []),
        properties=request_schema.get("properties", {}),
        request_structure=_annotate_schema_names(
            flatten_request_schema(spec, request_schema)
        ),
        security_requirements=security_requirements,
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
) -> tuple[str, dict[str, Any]]:
    paths = spec.get("paths", {})
    if not isinstance(paths, dict) or not paths:
        raise SchemaExtractionError("OpenAPI spec does not contain paths")

    method_name = method.lower()
    exact_path = paths.get(target_path)
    if isinstance(exact_path, dict) and method_name in exact_path:
        return target_path, exact_path[method_name]

    best_score = 0.0
    best_match: tuple[str, dict[str, Any]] | None = None
    target_segments = normalize_path(target_path).strip("/").split("/")

    for candidate_path, candidate_operations in paths.items():
        if not isinstance(candidate_operations, dict) or method_name not in candidate_operations:
            continue
        candidate_segments = normalize_path(candidate_path).strip("/").split("/")
        segment_overlap = len(set(target_segments) & set(candidate_segments))
        similarity = SequenceMatcher(None, target_path, candidate_path).ratio()
        score = similarity + (0.15 * segment_overlap)
        if score > best_score:
            best_score = score
            best_match = (candidate_path, candidate_operations[method_name])

    if best_match is None:
        raise SchemaExtractionError(
            f"No route match found for {method.upper()} {target_path}"
        )

    return best_match


def _extract_request_schema(
    spec: dict[str, Any],
    operation: dict[str, Any],
) -> dict[str, Any]:
    request_body = operation.get("requestBody", {})
    content = request_body.get("content", {})
    json_body = content.get("application/json", {})
    schema = json_body.get("schema", {})
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
