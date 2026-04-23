"""Failure trapping and handoff into Sprint 2 repair brain."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl, urlsplit
from uuid import uuid4

from app.main import process_trapped_error
from app.models.response_models import HealedRequest
from sprint4.env.live_support import extract_failure_signals, map_scenario_to_category
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
    raw_scenario_type: str | None,
    retry_count: int,
) -> dict[str, Any]:
    """Build TrappedError-compatible payload for Sprint 2."""
    metadata = execution_result.metadata or {}
    raw_scenario_type = (
        metadata.get("raw_scenario_type")
        or raw_scenario_type
    )
    mapped_scenario = metadata.get("scenario_type") or map_scenario_to_category(
        raw_scenario_type if isinstance(raw_scenario_type, str) else None,
        status_code=execution_result.status_code,
        error_message=execution_result.error_message,
    )
    failure_signals = metadata.get("failure_signals")
    if not isinstance(failure_signals, dict):
        failure_signals = extract_failure_signals(
            status_code=execution_result.status_code,
            error_message=execution_result.error_message,
            parsed_response=execution_result.parsed_error,
        )
    return {
        "target_url": url,
        "method": method,
        "failed_payload": payload,
        "failed_headers": headers,
        "error_code": execution_result.status_code,
        "error_message": execution_result.error_message or "Unknown failure",
        "query_params": _extract_query_params(url),
        "path_params": _extract_path_params(url, failure_signals),
        "source_component": metadata.get("source_component") or f"sprint4:{scenario_type}",
        "request_id": metadata.get("request_id") or f"sprint4-{uuid4().hex[:12]}",
        "retry_count": retry_count,
        "scenario_type": mapped_scenario,
        "raw_scenario_type": raw_scenario_type,
        "actual_server_response": execution_result.raw_response_text,
        "actual_server_response_json": execution_result.parsed_error,
        "failure_signals": failure_signals,
    }


def _extract_query_params(url: str) -> dict[str, Any] | None:
    pairs = parse_qsl(urlsplit(url).query, keep_blank_values=True)
    if not pairs:
        return None
    return {key: value for key, value in pairs}


def _extract_path_params(url: str, failure_signals: dict[str, Any]) -> dict[str, Any] | None:
    path_names = [
        loc[-1]
        for loc in failure_signals.get("validation_paths", [])
        if isinstance(loc, list) and len(loc) >= 2 and loc[0] == "path"
    ]
    if not path_names:
        return None

    path_segments = [segment for segment in urlsplit(url).path.split("/") if segment]
    extracted: dict[str, Any] = {}
    for name in path_names:
        placeholder = f"{{{name}}}"
        if placeholder in path_segments:
            extracted[name] = placeholder
    return extracted or None


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
