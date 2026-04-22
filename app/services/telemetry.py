"""Persistent telemetry sink for repair and retry observability."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.models.request_models import TrappedError
from app.models.response_models import HealedRequest, ProxyWorkflowResult
from app.utils.logger import get_logger

logger = get_logger(__name__)


def record_healing_event(trapped_error: TrappedError, healed_request: HealedRequest) -> None:
    """Persist one healing event and update aggregate metrics."""

    settings = get_settings()
    if not settings.ENABLE_TELEMETRY:
        return

    telemetry_dir = Path(settings.TELEMETRY_DIR)
    telemetry_dir.mkdir(parents=True, exist_ok=True)

    event = {
        "event_type": "healing",
        "request_id": trapped_error.request_id,
        "source_component": trapped_error.source_component,
        "target_url": trapped_error.target_url,
        "method": trapped_error.method,
        "error_code": trapped_error.error_code,
        "healing_action": healed_request.healing_action,
        "repair_strategy": healed_request.diagnostics.repair_strategy
        if healed_request.diagnostics
        else None,
        "fallback_used": healed_request.diagnostics.fallback_used
        if healed_request.diagnostics
        else None,
        "processing_ms": healed_request.diagnostics.processing_ms
        if healed_request.diagnostics
        else None,
    }
    _append_jsonl(telemetry_dir / "healing_events.jsonl", event)
    _update_healing_summary(telemetry_dir / "healing_summary.json", event)


def record_workflow_event(workflow_result: ProxyWorkflowResult) -> None:
    """Persist retry-loop results for later reward and evaluation analysis."""

    settings = get_settings()
    if not settings.ENABLE_TELEMETRY:
        return

    telemetry_dir = Path(settings.TELEMETRY_DIR)
    telemetry_dir.mkdir(parents=True, exist_ok=True)

    event = workflow_result.model_dump(mode="json")
    event["event_type"] = "workflow"
    _append_jsonl(telemetry_dir / "workflow_events.jsonl", event)
    _update_workflow_summary(telemetry_dir / "workflow_summary.json", event)


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, ensure_ascii=True))
        handle.write("\n")


def _update_healing_summary(path: Path, event: dict[str, Any]) -> None:
    summary = _load_summary(path)
    summary["total_healings"] = summary.get("total_healings", 0) + 1
    summary["total_processing_ms"] = summary.get("total_processing_ms", 0) + int(
        event.get("processing_ms") or 0
    )
    summary["fallback_count"] = summary.get("fallback_count", 0) + int(
        bool(event.get("fallback_used"))
    )

    action_counts = summary.setdefault("healing_action_counts", {})
    action = event.get("healing_action") or "unknown"
    action_counts[action] = action_counts.get(action, 0) + 1

    error_counts = summary.setdefault("error_code_counts", {})
    error_code = str(event.get("error_code"))
    error_counts[error_code] = error_counts.get(error_code, 0) + 1

    strategy_counts = summary.setdefault("repair_strategy_counts", {})
    strategy = event.get("repair_strategy") or "unknown"
    strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1

    if summary["total_healings"] > 0:
        summary["average_processing_ms"] = round(
            summary["total_processing_ms"] / summary["total_healings"], 2
        )

    _write_summary(path, summary)


def _update_workflow_summary(path: Path, event: dict[str, Any]) -> None:
    summary = _load_summary(path)
    summary["total_workflows"] = summary.get("total_workflows", 0) + 1

    status = event.get("status", "unknown")
    status_counts = summary.setdefault("status_counts", {})
    status_counts[status] = status_counts.get(status, 0) + 1

    attempts = int(event.get("attempts", 0))
    summary["total_attempts"] = summary.get("total_attempts", 0) + attempts
    summary["average_attempts"] = round(
        summary["total_attempts"] / summary["total_workflows"], 2
    )

    _write_summary(path, summary)


def _load_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except ValueError:
        logger.warning("Telemetry summary could not be parsed at %s", path)
        return {}


def _write_summary(path: Path, summary: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=True),
        encoding="utf-8",
    )
