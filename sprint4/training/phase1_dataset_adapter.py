"""Adapters for Sprint 1 live chaos-gym dataset records."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sprint4.env.live_support import (
    extract_failure_signals,
    map_scenario_to_category,
    parse_actual_server_response,
    summarize_error_message,
)
from sprint4.training.benchmark_contract import classify_raw_scenario


def load_phase1_dataset(path: str = "target_api/training_dataset.json") -> list[dict[str, Any]]:
    """Load the raw Sprint 1 dataset from disk."""

    file_path = Path(path)
    if not file_path.exists():
        return []
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, list) else []


def normalize_phase1_record(record: dict[str, Any]) -> dict[str, Any]:
    """Normalize one live dataset record into an episode-like structure."""

    parsed_response = parse_actual_server_response(record.get("actual_server_response"))
    success = "success_payload" in record or (
        "error_code" not in record and int(record.get("status_code", 500)) < 400
    )
    status_code = _status_code(record, success=success)
    error_message = None
    if not success:
        error_message = summarize_error_message(
            status_code=status_code,
            parsed_response=parsed_response,
            fallback=str(record.get("actual_server_response") or ""),
        )
    raw_scenario_type = str(record.get("scenario_type") or "unknown")
    scenario_type = map_scenario_to_category(
        raw_scenario_type,
        status_code=status_code,
        error_message=error_message,
    )
    payload = record.get("failed_payload") or record.get("success_payload")
    headers = record.get("failed_headers") or record.get("success_headers")

    return {
        "environment_mode": "live",
        "scenario_type": scenario_type,
        "raw_scenario_type": raw_scenario_type,
        "request": {
            "method": record.get("method"),
            "url": record.get("target_url"),
            "headers": headers if isinstance(headers, dict) else None,
            "payload": payload if isinstance(payload, dict) else None,
        },
        "response": {
            "success": success,
            "status_code": status_code,
            "error_message": error_message,
            "actual_server_response": record.get("actual_server_response"),
            "parsed_response": parsed_response,
            "failure_signals": extract_failure_signals(
                status_code=status_code,
                error_message=error_message,
                parsed_response=parsed_response,
            )
            if not success
            else {},
        },
        "metadata": {
            "request_id": record.get("request_id"),
            "source_component": record.get("source_component"),
            "benchmark_partition": classify_raw_scenario(raw_scenario_type),
        },
    }


def normalize_phase1_dataset(path: str = "target_api/training_dataset.json") -> list[dict[str, Any]]:
    """Load and normalize all Sprint 1 dataset rows."""

    return [normalize_phase1_record(record) for record in load_phase1_dataset(path)]


def summarize_phase1_dataset(path: str = "target_api/training_dataset.json") -> dict[str, Any]:
    """Return a compact summary for offline analysis and replay planning."""

    rows = normalize_phase1_dataset(path)
    scenario_counts: dict[str, int] = {}
    partition_counts: dict[str, int] = {}
    success_count = 0
    for row in rows:
        scenario = row["scenario_type"]
        scenario_counts[scenario] = scenario_counts.get(scenario, 0) + 1
        partition = str(row.get("metadata", {}).get("benchmark_partition") or "other")
        partition_counts[partition] = partition_counts.get(partition, 0) + 1
        success_count += int(bool(row["response"]["success"]))
    return {
        "sample_count": len(rows),
        "success_count": success_count,
        "failure_count": len(rows) - success_count,
        "scenario_distribution": scenario_counts,
        "benchmark_partition_distribution": partition_counts,
    }


def _status_code(record: dict[str, Any], *, success: bool) -> int:
    key = "status_code" if success else "error_code"
    value = record.get(key, record.get("status_code", record.get("error_code", 500)))
    try:
        return int(value)
    except (TypeError, ValueError):
        return 500
