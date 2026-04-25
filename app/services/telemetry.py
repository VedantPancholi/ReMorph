"""Persistent telemetry sink for repair, workflow, and training observability."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from app.config import get_settings
from app.models.request_models import TrappedError
from app.models.response_models import HealedRequest, ProxyWorkflowResult
from app.utils.logger import get_logger

logger = get_logger(__name__)

_REPAIRABLE_RAW_SCENARIOS = {
    "schema_missing_key",
    "schema_type_coercion",
    "schema_extra_key",
    "schema_null_injection",
    "route_regression",
    "route_method_spoof",
    "route_invalid_path",
    "auth_missing_tenant",
}

_UNRECOVERABLE_RAW_SCENARIOS = {
    "auth_missing_token",
    "auth_malformed_jwt",
}


def record_healing_event(trapped_error: TrappedError, healed_request: HealedRequest) -> None:
    """Persist one healing event and update aggregate metrics."""

    settings = get_settings()
    if not settings.ENABLE_TELEMETRY:
        return

    telemetry_dir = Path(settings.TELEMETRY_DIR)
    telemetry_dir.mkdir(parents=True, exist_ok=True)

    diagnostics = healed_request.diagnostics
    raw_scenario_type = trapped_error.raw_scenario_type
    benchmark_partition = _classify_benchmark_partition(raw_scenario_type)
    selected_endpoint_path = diagnostics.selected_endpoint_path if diagnostics else None
    event = {
        "event_schema_version": 2,
        "event_type": "healing",
        "event_timestamp": datetime.now(UTC).isoformat(),
        "app_env": settings.APP_ENV,
        "llm_model": settings.LLM_MODEL,
        "policy_name": diagnostics.policy_name if diagnostics else settings.HEALING_POLICY_NAME,
        "policy_version": diagnostics.policy_version if diagnostics else settings.HEALING_POLICY_VERSION,
        "policy_source": diagnostics.policy_source if diagnostics else None,
        "policy_run_id": diagnostics.policy_run_id if diagnostics else (settings.HEALING_POLICY_RUN_ID or None),
        "event_group_id": _build_healing_event_group_id(
            trapped_error=trapped_error,
            selected_endpoint_path=selected_endpoint_path,
            benchmark_partition=benchmark_partition,
        ),
        "request_id": trapped_error.request_id,
        "source_component": trapped_error.source_component,
        "target_url": trapped_error.target_url,
        "method": trapped_error.method,
        "error_code": trapped_error.error_code,
        "error_message": trapped_error.error_message,
        "raw_scenario_type": raw_scenario_type,
        "benchmark_partition": benchmark_partition,
        "healing_action": healed_request.healing_action,
        "repair_status": healed_request.status,
        "healed_method": healed_request.fixed_method,
        "healed_url": healed_request.fixed_url,
        "healed_path": _path_from_url(healed_request.fixed_url),
        "selected_endpoint_path": selected_endpoint_path,
        "confidence": healed_request.confidence,
        "scenario_type": diagnostics.scenario_type if diagnostics else None,
        "repair_strategy": diagnostics.repair_strategy if diagnostics else None,
        "docs_source": diagnostics.docs_source if diagnostics else None,
        "docs_confidence": diagnostics.docs_confidence if diagnostics else None,
        "spec_hash": diagnostics.spec_hash if diagnostics else None,
        "spec_version": diagnostics.spec_version if diagnostics else None,
        "llm_attempted": diagnostics.llm_attempted if diagnostics else None,
        "llm_succeeded": diagnostics.llm_succeeded if diagnostics else None,
        "fallback_used": diagnostics.fallback_used if diagnostics else None,
        "retry_count": diagnostics.retry_count if diagnostics else trapped_error.retry_count,
        "processing_ms": diagnostics.processing_ms if diagnostics else None,
        "failure_reason": healed_request.failure_reason or (diagnostics.failure_reason if diagnostics else None),
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

    diagnostics = workflow_result.final_healed_request.diagnostics
    event = workflow_result.model_dump(mode="json")
    event.update(
        {
            "event_schema_version": 2,
            "event_type": "workflow",
            "event_timestamp": datetime.now(UTC).isoformat(),
            "app_env": settings.APP_ENV,
            "llm_model": settings.LLM_MODEL,
            "workflow_id": _build_workflow_id(workflow_result),
            "request_id": workflow_result.request_id or (diagnostics.request_id if diagnostics else None),
            "source_component": diagnostics.source_component if diagnostics else None,
            "policy_name": workflow_result.policy_name
            or (diagnostics.policy_name if diagnostics else settings.HEALING_POLICY_NAME),
            "policy_version": workflow_result.policy_version
            or (diagnostics.policy_version if diagnostics else settings.HEALING_POLICY_VERSION),
            "policy_source": workflow_result.policy_source or (diagnostics.policy_source if diagnostics else None),
            "policy_run_id": workflow_result.policy_run_id
            or (diagnostics.policy_run_id if diagnostics else (settings.HEALING_POLICY_RUN_ID or None)),
            "repair_strategy": diagnostics.repair_strategy if diagnostics else None,
            "raw_scenario_type": workflow_result.raw_scenario_type,
            "benchmark_partition": workflow_result.benchmark_partition
            or _classify_benchmark_partition(workflow_result.raw_scenario_type),
            "final_status_code": _extract_final_status_code(workflow_result),
            "final_reward": diagnostics.final_reward if diagnostics else None,
            "retry_succeeded": diagnostics.retry_succeeded if diagnostics else None,
            "processing_ms": diagnostics.processing_ms if diagnostics else None,
            "healing_action_sequence": [
                item.healed_request.healing_action
                for item in workflow_result.history
            ],
            "attempt_status_codes": [
                item.execution_result.status_code
                for item in workflow_result.history
            ],
        }
    )
    _append_jsonl(telemetry_dir / "workflow_events.jsonl", event)
    _update_workflow_summary(telemetry_dir / "workflow_summary.json", event)


def record_training_run_event(event: dict[str, Any]) -> None:
    """Persist one training-run event and update aggregate metrics."""

    settings = get_settings()
    if not settings.ENABLE_TELEMETRY:
        return

    telemetry_dir = Path(settings.TELEMETRY_DIR)
    telemetry_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "event_schema_version": 1,
        "event_type": "training_run",
        "event_timestamp": datetime.now(UTC).isoformat(),
        "app_env": settings.APP_ENV,
        **event,
    }
    _append_jsonl(telemetry_dir / "training_runs.jsonl", payload)
    _update_training_summary(telemetry_dir / "training_summary.json", payload)


def rebuild_telemetry_summaries(telemetry_dir: str) -> dict[str, str]:
    """Rebuild summary files from the JSONL event history in one telemetry directory."""

    root = Path(telemetry_dir)
    root.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, str] = {}
    for stem, updater in (
        ("healing", _update_healing_summary),
        ("workflow", _update_workflow_summary),
        ("training", _update_training_summary),
    ):
        events_path = root / f"{stem}_events.jsonl"
        if stem == "training":
            events_path = root / "training_runs.jsonl"
        summary_path = root / f"{stem}_summary.json"
        events = _load_jsonl(events_path)
        summary_path.write_text("{}", encoding="utf-8")
        for event in events:
            updater(summary_path, event)
        outputs[stem] = str(summary_path)
    return outputs


def rotate_telemetry_logs(
    telemetry_dir: str,
    *,
    max_bytes: int,
    max_rotated_files: int,
) -> dict[str, Any]:
    """Rotate all telemetry JSONL files in one directory using the same retention policy."""

    root = Path(telemetry_dir)
    root.mkdir(parents=True, exist_ok=True)
    rotated_files: list[str] = []
    for path in root.glob("*.jsonl"):
        if _rotate_jsonl_file(path, max_bytes=max_bytes, max_rotated_files=max_rotated_files):
            rotated_files.append(str(path))
    return {
        "telemetry_dir": str(root),
        "max_bytes": max_bytes,
        "max_rotated_files": max_rotated_files,
        "rotated_files": rotated_files,
    }


def build_telemetry_report(telemetry_dir: str) -> dict[str, Any]:
    """Build a compact operational report grouped by policy source and raw scenario."""

    root = Path(telemetry_dir)
    workflow_events = _load_jsonl(root / "workflow_events.jsonl")
    healing_events = _load_jsonl(root / "healing_events.jsonl")

    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for event in workflow_events:
        key = (
            str(event.get("policy_source") or "unknown"),
            str(event.get("raw_scenario_type") or "unknown"),
        )
        bucket = by_key.setdefault(
            key,
            {
                "policy_source": key[0],
                "raw_scenario_type": key[1],
                "workflow_count": 0,
                "success_count": 0,
                "processing_ms_total": 0,
                "processing_ms_count": 0,
                "final_status_code_counts": {},
            },
        )
        bucket["workflow_count"] += 1
        bucket["success_count"] += int(event.get("status") == "success")
        if event.get("processing_ms") is not None:
            bucket["processing_ms_total"] += int(event["processing_ms"])
            bucket["processing_ms_count"] += 1
        final_status_code = str(event.get("final_status_code"))
        counts = bucket["final_status_code_counts"]
        counts[final_status_code] = counts.get(final_status_code, 0) + 1

    rows = []
    for bucket in by_key.values():
        rows.append(
            {
                "policy_source": bucket["policy_source"],
                "raw_scenario_type": bucket["raw_scenario_type"],
                "workflow_count": bucket["workflow_count"],
                "success_rate": round(
                    bucket["success_count"] / max(1, bucket["workflow_count"]),
                    4,
                ),
                "average_processing_ms": round(
                    bucket["processing_ms_total"] / max(1, bucket["processing_ms_count"]),
                    2,
                )
                if bucket["processing_ms_count"]
                else None,
                "final_status_code_counts": bucket["final_status_code_counts"],
            }
        )
    rows.sort(key=lambda item: (item["policy_source"], item["raw_scenario_type"]))

    return {
        "telemetry_dir": str(root),
        "generated_at": datetime.now(UTC).isoformat(),
        "healing_event_count": len(healing_events),
        "workflow_event_count": len(workflow_events),
        "rows": rows,
    }


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    settings = get_settings()
    _rotate_jsonl_file(
        path,
        max_bytes=settings.TELEMETRY_MAX_JSONL_BYTES,
        max_rotated_files=settings.TELEMETRY_MAX_ROTATED_FILES,
    )
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, ensure_ascii=True))
        handle.write("\n")


def _rotate_jsonl_file(path: Path, *, max_bytes: int, max_rotated_files: int) -> bool:
    if not path.exists() or path.stat().st_size < max_bytes:
        return False

    try:
        oldest = path.with_name(f"{path.name}.{max_rotated_files}")
        if oldest.exists():
            oldest.unlink()
        for index in range(max_rotated_files - 1, 0, -1):
            source = path.with_name(f"{path.name}.{index}")
            target = path.with_name(f"{path.name}.{index + 1}")
            if source.exists():
                source.replace(target)
        path.replace(path.with_name(f"{path.name}.1"))
        return True
    except PermissionError:
        logger.warning("Skipping telemetry rotation for locked file %s", path)
        return False


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except ValueError:
                logger.warning("Skipping invalid telemetry row in %s", path)
                continue
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def _update_healing_summary(path: Path, event: dict[str, Any]) -> None:
    summary = _load_summary(path)
    summary["total_healings"] = summary.get("total_healings", 0) + 1
    summary["total_processing_ms"] = summary.get("total_processing_ms", 0) + int(event.get("processing_ms") or 0)
    summary["fallback_count"] = summary.get("fallback_count", 0) + int(bool(event.get("fallback_used")))
    summary["llm_attempted_count"] = summary.get("llm_attempted_count", 0) + int(bool(event.get("llm_attempted")))
    summary["llm_success_count"] = summary.get("llm_success_count", 0) + int(bool(event.get("llm_succeeded")))
    summary["cache_hit_count"] = summary.get("cache_hit_count", 0) + int(event.get("repair_strategy") == "cache")

    _increment(summary.setdefault("healing_action_counts", {}), event.get("healing_action") or "unknown")
    _increment(summary.setdefault("error_code_counts", {}), str(event.get("error_code")))
    _increment(summary.setdefault("repair_strategy_counts", {}), event.get("repair_strategy") or "unknown")
    _increment(summary.setdefault("scenario_type_counts", {}), event.get("scenario_type") or "unknown")
    _increment(summary.setdefault("raw_scenario_type_counts", {}), event.get("raw_scenario_type") or "unknown")
    _increment(summary.setdefault("benchmark_partition_counts", {}), event.get("benchmark_partition") or "other")
    _increment(summary.setdefault("source_component_counts", {}), event.get("source_component") or "unknown")
    _increment(summary.setdefault("llm_model_counts", {}), event.get("llm_model") or "unknown")
    _increment(summary.setdefault("policy_name_counts", {}), event.get("policy_name") or "unknown")
    _increment(summary.setdefault("policy_source_counts", {}), event.get("policy_source") or "unknown")

    if summary["total_healings"] > 0:
        summary["average_processing_ms"] = round(summary["total_processing_ms"] / summary["total_healings"], 2)

    _write_summary(path, summary)


def _update_workflow_summary(path: Path, event: dict[str, Any]) -> None:
    summary = _load_summary(path)
    summary["total_workflows"] = summary.get("total_workflows", 0) + 1

    status = event.get("status") or "unknown"
    _increment(summary.setdefault("status_counts", {}), status)

    attempts = int(event.get("attempts", 0))
    summary["total_attempts"] = summary.get("total_attempts", 0) + attempts
    summary["average_attempts"] = round(summary["total_attempts"] / summary["total_workflows"], 2)
    summary["success_rate"] = round(summary["status_counts"].get("success", 0) / summary["total_workflows"], 4)

    _increment(summary.setdefault("final_status_code_counts", {}), str(event.get("final_status_code")))
    _increment(summary.setdefault("raw_scenario_type_counts", {}), event.get("raw_scenario_type") or "unknown")
    _increment(summary.setdefault("benchmark_partition_counts", {}), event.get("benchmark_partition") or "other")
    _increment(summary.setdefault("policy_name_counts", {}), event.get("policy_name") or "unknown")
    _increment(summary.setdefault("policy_source_counts", {}), event.get("policy_source") or "unknown")
    _increment(summary.setdefault("repair_strategy_counts", {}), event.get("repair_strategy") or "unknown")

    _write_summary(path, summary)


def _update_training_summary(path: Path, event: dict[str, Any]) -> None:
    summary = _load_summary(path)
    summary["total_training_runs"] = summary.get("total_training_runs", 0) + 1

    _increment(summary.setdefault("trainer_counts", {}), event.get("trainer") or "unknown")
    _increment(summary.setdefault("policy_name_counts", {}), event.get("policy_name") or "unknown")
    _increment(summary.setdefault("policy_source_counts", {}), event.get("policy_source") or "unknown")
    _increment(summary.setdefault("status_counts", {}), event.get("status") or "unknown")

    if event.get("train_sample_count") is not None:
        summary["total_train_samples"] = summary.get("total_train_samples", 0) + int(event["train_sample_count"])
    if event.get("eval_sample_count") is not None:
        summary["total_eval_samples"] = summary.get("total_eval_samples", 0) + int(event["eval_sample_count"])

    _write_summary(path, summary)


def _increment(counter: dict[str, int], key: str) -> None:
    counter[key] = counter.get(key, 0) + 1


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


def _build_healing_event_group_id(
    *,
    trapped_error: TrappedError,
    selected_endpoint_path: str | None,
    benchmark_partition: str,
) -> str:
    payload = {
        "target_url": trapped_error.target_url,
        "method": trapped_error.method,
        "error_code": trapped_error.error_code,
        "raw_scenario_type": trapped_error.raw_scenario_type or "unknown",
        "benchmark_partition": benchmark_partition,
        "selected_endpoint_path": selected_endpoint_path,
        "failed_payload": trapped_error.failed_payload,
        "failed_headers": trapped_error.failed_headers,
        "query_params": trapped_error.query_params,
    }
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")).hexdigest()[:16]
    return f"healing:{fingerprint}"


def _build_workflow_id(workflow_result: ProxyWorkflowResult) -> str:
    payload = {
        "request_id": workflow_result.request_id,
        "status": workflow_result.status,
        "attempts": workflow_result.attempts,
        "fixed_method": workflow_result.final_healed_request.fixed_method,
        "fixed_url": workflow_result.final_healed_request.fixed_url,
    }
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")).hexdigest()[:16]
    return f"workflow:{fingerprint}"


def _path_from_url(url: str | None) -> str | None:
    if not url:
        return None
    path = urlsplit(url).path
    return path or None


def _classify_benchmark_partition(raw_scenario_type: str | None) -> str:
    if raw_scenario_type in _REPAIRABLE_RAW_SCENARIOS:
        return "repairable"
    if raw_scenario_type in _UNRECOVERABLE_RAW_SCENARIOS:
        return "unrecoverable"
    return "other"


def _extract_final_status_code(workflow_result: ProxyWorkflowResult) -> int | None:
    if workflow_result.history:
        return workflow_result.history[-1].execution_result.status_code
    return None
