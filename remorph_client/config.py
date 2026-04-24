"""Configuration models for the product-style ReMorph client."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ReMorphClientConfig:
    """Serializable configuration for the self-healing client."""

    base_url: str
    openapi_spec_path: str
    auth_headers: dict[str, str] = field(default_factory=dict)
    safe_mode: bool = True
    max_retries: int = 2
    cache_mode: str = "reuse"
    timeout_seconds: float = 10.0

    @classmethod
    def from_file(cls, path: str) -> "ReMorphClientConfig":
        file_path = Path(path)
        payload = yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, dict):
            raise ValueError("ReMorph client config must be a mapping.")
        auth = payload.get("auth") or {}
        auth_headers = auth.get("headers") if isinstance(auth, dict) else {}
        return cls(
            base_url=str(payload.get("base_url") or ""),
            openapi_spec_path=str(payload.get("openapi_spec_path") or ""),
            auth_headers=dict(auth_headers or {}),
            safe_mode=bool(payload.get("safe_mode", True)),
            max_retries=int(payload.get("max_retries", 2)),
            cache_mode=str(payload.get("cache_mode") or "reuse"),
            timeout_seconds=float(payload.get("timeout_seconds", 10.0)),
        )

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ReMorphClientConfig":
        auth = payload.get("auth_headers") or payload.get("auth") or {}
        auth_headers = auth.get("headers") if isinstance(auth, dict) and "headers" in auth else auth
        return cls(
            base_url=str(payload.get("base_url") or ""),
            openapi_spec_path=str(payload.get("openapi_spec_path") or ""),
            auth_headers=dict(auth_headers or {}),
            safe_mode=bool(payload.get("safe_mode", True)),
            max_retries=int(payload.get("max_retries", 2)),
            cache_mode=str(payload.get("cache_mode") or "reuse"),
            timeout_seconds=float(payload.get("timeout_seconds", 10.0)),
        )
