"""OpenAPI fetching helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import requests

from app.config import get_settings
from app.services.url_utils import build_doc_candidates, extract_base_url
from app.utils.error_utils import DocumentationFetchError
from app.utils.logger import get_logger

logger = get_logger(__name__)


def fetch_from_candidate(candidate_url: str) -> dict[str, Any]:
    """Fetch and parse JSON from a documentation endpoint."""

    settings = get_settings()
    try:
        response = requests.get(candidate_url, timeout=settings.REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
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
    return payload


def fetch_openapi_spec(
    target_url: str,
    *,
    local_spec_path: str | None = None,
) -> dict[str, Any]:
    """Load a local spec for tests or probe remote documentation candidates."""

    if local_spec_path:
        return load_local_spec(local_spec_path)

    settings = get_settings()
    base_url = extract_base_url(target_url)
    candidates = build_doc_candidates(base_url, settings.DOC_PATH_CANDIDATES)

    last_error: DocumentationFetchError | None = None
    for candidate in candidates:
        try:
            logger.info("Trying documentation candidate %s", candidate)
            return fetch_from_candidate(candidate)
        except DocumentationFetchError as exc:
            last_error = exc
            logger.warning("Documentation probe failed for %s", candidate)

    raise DocumentationFetchError(
        f"Unable to fetch documentation for {target_url}"
    ) from last_error


def load_local_spec(local_spec_path: str) -> dict[str, Any]:
    """Read a JSON OpenAPI file from disk."""

    path = Path(local_spec_path)
    if not path.exists():
        raise DocumentationFetchError(f"Local spec file not found: {local_spec_path}")

    try:
        return __import__("json").loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise DocumentationFetchError(
            f"Local spec file is not valid JSON: {local_spec_path}"
        ) from exc
