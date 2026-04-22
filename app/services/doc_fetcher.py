"""OpenAPI fetching helpers."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

from app.config import get_settings
from app.models.schema_models import SpecMetadata
from app.services.url_utils import build_doc_candidates, extract_base_url
from app.utils.error_utils import DocumentationFetchError
from app.utils.logger import get_logger

logger = get_logger(__name__)


def fetch_from_candidate(candidate_url: str) -> tuple[dict[str, Any], SpecMetadata]:
    """Fetch and parse JSON from a documentation endpoint."""

    settings = get_settings()
    fetched_at = _utcnow()
    try:
        response = requests.get(candidate_url, timeout=settings.REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        content_type = response.headers.get("content-type")
        raw_text = response.text
        payload = response.json()
    except requests.RequestException as exc:
        raise DocumentationFetchError(
            f"Failed to fetch documentation from {candidate_url}"
        ) from exc
    except ValueError as exc:
        raise DocumentationFetchError(
            f"Documentation at {candidate_url} was not valid JSON"
        ) from exc

    if not isinstance(payload, dict):
        raise DocumentationFetchError(
            f"Documentation at {candidate_url} did not return an object"
        )
    metadata = _build_spec_metadata(
        source=candidate_url,
        candidate_used=candidate_url,
        payload=payload,
        fetched_at=fetched_at,
        content_type=content_type,
        source_kind="json",
        fetch_success=True,
        parse_success=True,
    )
    return payload, metadata


def fetch_openapi_spec(
    target_url: str,
    *,
    local_spec_path: str | None = None,
) -> dict[str, Any]:
    """Load a local spec for tests or probe remote documentation candidates."""

    spec, _source = fetch_openapi_spec_with_source(
        target_url,
        local_spec_path=local_spec_path,
    )
    return spec


def fetch_openapi_spec_with_source(
    target_url: str,
    *,
    local_spec_path: str | None = None,
) -> tuple[dict[str, Any], str]:
    """Load the spec and return the source location used for the fetch."""

    spec, metadata = fetch_openapi_spec_bundle(
        target_url,
        local_spec_path=local_spec_path,
    )
    return spec, metadata.source


def fetch_openapi_spec_bundle(
    target_url: str,
    *,
    local_spec_path: str | None = None,
) -> tuple[dict[str, Any], SpecMetadata]:
    """Load the spec and return structured metadata about the source."""

    if local_spec_path:
        return load_local_spec_with_metadata(local_spec_path)

    settings = get_settings()
    base_url = extract_base_url(target_url)
    candidates = build_doc_candidates(base_url, settings.DOC_PATH_CANDIDATES)

    last_error: DocumentationFetchError | None = None
    attempted_candidates: list[str] = []
    for candidate in candidates:
        attempted_candidates.append(candidate)
        try:
            logger.info("Trying documentation candidate %s", candidate)
            return fetch_from_candidate(candidate)
        except DocumentationFetchError as exc:
            last_error = exc
            logger.warning("Documentation probe failed for %s", candidate)

    html_docs_candidate = f"{base_url}/docs"
    attempted_candidates.append(html_docs_candidate)
    metadata = SpecMetadata(
        source="unavailable",
        candidate_used=attempted_candidates[-1],
        fetch_success=False,
        parse_success=False,
        fetched_at=_utcnow(),
        source_kind="unavailable",
        completeness_flags=["docs_unavailable", "html_hint_available"],
        errors=[str(last_error)] if last_error else ["Documentation source unavailable"],
    )

    raise DocumentationFetchError(
        f"Unable to fetch documentation for {target_url}"
    ) from last_error


def load_local_spec(local_spec_path: str) -> dict[str, Any]:
    """Read a JSON OpenAPI file from disk."""

    spec, _metadata = load_local_spec_with_metadata(local_spec_path)
    return spec


def load_local_spec_with_metadata(local_spec_path: str) -> tuple[dict[str, Any], SpecMetadata]:
    """Read a local JSON spec and return it with structured metadata."""

    path = Path(local_spec_path)
    if not path.exists():
        raise DocumentationFetchError(f"Local spec file not found: {local_spec_path}")

    try:
        raw_text = path.read_text(encoding="utf-8")
        payload = json.loads(raw_text)
    except ValueError as exc:
        raise DocumentationFetchError(
            f"Local spec file is not valid JSON: {local_spec_path}"
        ) from exc

    if not isinstance(payload, dict):
        raise DocumentationFetchError(
            f"Local spec file did not contain a top-level object: {local_spec_path}"
        )

    metadata = _build_spec_metadata(
        source=f"local:{local_spec_path}",
        candidate_used=local_spec_path,
        payload=payload,
        fetched_at=_utcnow(),
        content_type="application/json",
        source_kind="local",
        fetch_success=True,
        parse_success=True,
    )
    return payload, metadata


def _build_spec_metadata(
    *,
    source: str,
    candidate_used: str,
    payload: dict[str, Any],
    fetched_at: str,
    content_type: str | None,
    source_kind: str,
    fetch_success: bool,
    parse_success: bool,
) -> SpecMetadata:
    completeness_flags = _build_completeness_flags(payload)
    spec_version = payload.get("openapi") or payload.get("swagger")
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return SpecMetadata(
        source=source,
        candidate_used=candidate_used,
        fetch_success=fetch_success,
        parse_success=parse_success,
        spec_version=str(spec_version) if spec_version else None,
        spec_hash=hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
        fetched_at=fetched_at,
        content_type=content_type,
        source_kind=source_kind,
        completeness_flags=completeness_flags,
    )


def _build_completeness_flags(payload: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    if "paths" not in payload:
        flags.append("missing_paths")
    if "components" not in payload:
        flags.append("missing_components")
    if "securitySchemes" not in payload.get("components", {}):
        flags.append("missing_security_schemes")
    if not payload.get("openapi") and not payload.get("swagger"):
        flags.append("missing_spec_version")
    if not flags:
        flags.append("complete")
    return flags


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()
