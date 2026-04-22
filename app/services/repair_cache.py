"""File-backed cache for repeated repair signatures."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.models.request_models import TrappedError
from app.models.response_models import HealedRequest
from app.models.schema_models import EndpointSchema
from app.utils.logger import get_logger

logger = get_logger(__name__)


def build_repair_cache_key(
    trapped_error: TrappedError,
    endpoint_schema: EndpointSchema,
    *,
    spec_hash: str | None = None,
    spec_version: str | None = None,
) -> str:
    """Create a stable cache key for repeated drift patterns."""

    key_material = {
        "target_url": trapped_error.target_url,
        "method": trapped_error.method,
        "error_code": trapped_error.error_code,
        "failed_payload_keys": _extract_payload_shape(trapped_error.failed_payload),
        "failed_headers": sorted((trapped_error.failed_headers or {}).keys()),
        "endpoint_path": endpoint_schema.path,
        "required_fields": endpoint_schema.required_fields,
        "spec_hash": spec_hash,
        "spec_version": spec_version,
        "security_requirements": [
            requirement.model_dump(mode="json")
            for requirement in endpoint_schema.security_requirements
        ],
    }
    serialized = json.dumps(key_material, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def get_cached_repair(cache_key: str) -> HealedRequest | None:
    """Load a cached repair by key if caching is enabled and present."""

    settings = get_settings()
    if not settings.ENABLE_REPAIR_CACHE:
        return None

    cache_path = Path(settings.REPAIR_CACHE_PATH)
    if not cache_path.exists():
        return None

    try:
        cache_payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except ValueError:
        logger.warning("Repair cache is unreadable at %s", cache_path)
        return None

    cached = cache_payload.get(cache_key)
    if not isinstance(cached, dict):
        return None

    return HealedRequest.model_validate(cached)


def store_cached_repair(cache_key: str, healed_request: HealedRequest) -> None:
    """Persist a repair in the local cache for future reuse."""

    settings = get_settings()
    if not settings.ENABLE_REPAIR_CACHE:
        return

    cache_path = Path(settings.REPAIR_CACHE_PATH)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    cache_payload: dict[str, Any] = {}
    if cache_path.exists():
        try:
            existing = json.loads(cache_path.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                cache_payload = existing
        except ValueError:
            logger.warning("Repair cache could not be parsed. Overwriting %s", cache_path)

    cache_payload[cache_key] = healed_request.model_dump(mode="json")
    cache_path.write_text(
        json.dumps(cache_payload, indent=2, sort_keys=True, ensure_ascii=True),
        encoding="utf-8",
    )


def _extract_payload_shape(payload: dict[str, Any] | None, *, parent: str = "") -> list[str]:
    if not isinstance(payload, dict):
        return []

    shape: list[str] = []
    for key, value in payload.items():
        full_key = f"{parent}.{key}" if parent else key
        shape.append(full_key)
        if isinstance(value, dict):
            shape.extend(_extract_payload_shape(value, parent=full_key))
    return sorted(shape)
