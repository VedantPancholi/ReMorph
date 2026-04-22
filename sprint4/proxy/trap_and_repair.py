"""Failure trapping and handoff into Sprint 2 repair brain."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from app.main import process_trapped_error
from app.models.response_models import HealedRequest
from sprint4.proxy.request_executor import RequestExecutionResult


@dataclass(frozen=True)
class TrapAndRepairResult:
    """Result of packaging trapped error and running repair."""

    trapped_error: dict[str, Any]
    healed_request: HealedRequest | None
    failure_reason: str | None = None


def package_trapped_error(
    *,
    method: str,
    url: str,
    payload: dict[str, Any] | None,
    headers: dict[str, str] | None,
    execution_result: RequestExecutionResult,
    scenario_type: str,
    retry_count: int,
) -> dict[str, Any]:
    """Build TrappedError-compatible payload for Sprint 2."""
    return {
        "target_url": url,
        "method": method,
        "failed_payload": payload,
        "failed_headers": headers,
        "error_code": execution_result.status_code,
        "error_message": execution_result.error_message or "Unknown failure",
        "source_component": f"sprint4:{scenario_type}",
        "request_id": f"sprint4-{uuid4().hex[:12]}",
        "retry_count": retry_count,
    }


def run_repair(
    trapped_error: dict[str, Any],
    *,
    local_spec_path: str,
) -> TrapAndRepairResult:
    """Run Sprint 2 repair function and return a typed result."""
    try:
        healed_payload = process_trapped_error(
            trapped_error,
            local_spec_path=local_spec_path,
        )
        healed_request = HealedRequest.model_validate(healed_payload)
        return TrapAndRepairResult(
            trapped_error=trapped_error,
            healed_request=healed_request,
        )
    except Exception as exc:  # noqa: BLE001 - convert all to stable failure reason
        return TrapAndRepairResult(
            trapped_error=trapped_error,
            healed_request=None,
            failure_reason=exc.__class__.__name__,
        )

