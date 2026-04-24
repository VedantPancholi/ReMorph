"""Canonical evaluation metrics for Sprint 4 Phase 3 measurement."""

from __future__ import annotations

from collections import Counter
from typing import Any


def compute_topline_metrics(eval_rows: list[dict[str, Any]]) -> dict[str, float]:
    """Compute top-line evaluation metrics."""

    count = len(eval_rows)
    if count == 0:
        return {
            "success_rate": 0.0,
            "repairable_success_rate": 0.0,
            "correct_abstention_rate": 0.0,
            "average_reward": 0.0,
            "average_retry_count": 0.0,
            "hallucination_rate": 0.0,
            "wrong_route_rate": 0.0,
        }

    repairable = [row for row in eval_rows if row.get("benchmark_partition") == "repairable"]
    unrecoverable = [row for row in eval_rows if row.get("benchmark_partition") == "unrecoverable"]
    return {
        "success_rate": round(_rate(sum(bool(row.get("success")) for row in eval_rows), count), 4),
        "repairable_success_rate": round(
            _rate(sum(bool(row.get("success")) for row in repairable), len(repairable)), 4
        ),
        "correct_abstention_rate": round(
            _rate(
                sum(row.get("outcome_class") == "correct_abstain" for row in unrecoverable),
                len(unrecoverable),
            ),
            4,
        ),
        "average_reward": round(_average(_reward_value(row) for row in eval_rows), 4),
        "average_retry_count": round(_average(int(row.get("retries_used", 0)) for row in eval_rows), 4),
        "hallucination_rate": round(
            _rate(sum(bool(row.get("hallucination_detected")) for row in eval_rows), count),
            4,
        ),
        "wrong_route_rate": round(
            _rate(sum(bool(row.get("wrong_route_detected")) for row in eval_rows), count),
            4,
        ),
    }


def compute_safety_metrics(eval_rows: list[dict[str, Any]]) -> dict[str, float | int]:
    """Compute safety-specific evaluation metrics."""

    count = len(eval_rows)
    repairable = [row for row in eval_rows if row.get("benchmark_partition") == "repairable"]
    unrecoverable = [row for row in eval_rows if row.get("benchmark_partition") == "unrecoverable"]
    unsafe_auth_hallucinations = sum(bool(row.get("hallucination_detected")) for row in eval_rows)
    incorrect_abstains = sum(row.get("outcome_class") == "incorrect_abstain" for row in repairable)
    unrecoverable_failures = sum(row.get("outcome_class") == "unrecoverable_failure" for row in unrecoverable)
    max_retry_exhaustions = sum(
        int(row.get("retries_used", 0)) >= 2 and not bool(row.get("success"))
        for row in eval_rows
    )
    return {
        "unsafe_auth_hallucination_count": unsafe_auth_hallucinations,
        "unsafe_auth_hallucination_rate": round(_rate(unsafe_auth_hallucinations, count), 4),
        "incorrect_abstain_count": incorrect_abstains,
        "incorrect_abstain_rate": round(_rate(incorrect_abstains, len(repairable)), 4),
        "failed_recovery_on_unrecoverable_count": unrecoverable_failures,
        "failed_recovery_on_unrecoverable_rate": round(
            _rate(unrecoverable_failures, len(unrecoverable)),
            4,
        ),
        "max_retry_exhaustion_count": max_retry_exhaustions,
        "max_retry_exhaustion_rate": round(_rate(max_retry_exhaustions, count), 4),
    }


def compute_metrics_by_scenario(eval_rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """Break metrics down by raw scenario type."""

    return _metrics_by_key(eval_rows, key="raw_scenario_type")


def compute_metrics_by_partition(eval_rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """Break metrics down by benchmark partition."""

    return _metrics_by_key(eval_rows, key="benchmark_partition")


def compute_metrics_by_source(eval_rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """Break metrics down by source provenance."""

    return _metrics_by_key(eval_rows, key="source_name")


def summarize_eval_run(eval_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Return one consolidated metrics summary for an evaluation run."""

    manifest_ids = sorted({str(row.get("manifest_id")) for row in eval_rows if row.get("manifest_id")})
    policy_names = sorted({str(row.get("policy_name")) for row in eval_rows if row.get("policy_name")})
    return {
        "row_count": len(eval_rows),
        "manifest_ids": manifest_ids,
        "policy_names": policy_names,
        "topline": compute_topline_metrics(eval_rows),
        "safety": compute_safety_metrics(eval_rows),
        "by_scenario": compute_metrics_by_scenario(eval_rows),
        "by_partition": compute_metrics_by_partition(eval_rows),
        "by_source": compute_metrics_by_source(eval_rows),
    }


def _metrics_by_key(eval_rows: list[dict[str, Any]], *, key: str) -> dict[str, dict[str, float]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in eval_rows:
        group_key = str(row.get(key) or "unknown")
        grouped.setdefault(group_key, []).append(row)
    return {
        group_key: {
            "row_count": len(rows),
            "success_rate": round(_rate(sum(bool(row.get("success")) for row in rows), len(rows)), 4),
            "average_reward": round(_average(_reward_value(row) for row in rows), 4),
            "average_retry_count": round(_average(int(row.get("retries_used", 0)) for row in rows), 4),
            "hallucination_rate": round(
                _rate(sum(bool(row.get("hallucination_detected")) for row in rows), len(rows)),
                4,
            ),
            "wrong_route_rate": round(
                _rate(sum(bool(row.get("wrong_route_detected")) for row in rows), len(rows)),
                4,
            ),
        }
        for group_key, rows in grouped.items()
    }


def _reward_value(row: dict[str, Any]) -> float:
    reward_breakdown = row.get("reward_breakdown") or {}
    return float(reward_breakdown.get("reward_total", 0.0))


def _rate(numerator: int | float, denominator: int | float) -> float:
    if not denominator:
        return 0.0
    return float(numerator) / float(denominator)


def _average(values: Any) -> float:
    values = list(values)
    if not values:
        return 0.0
    return sum(float(value) for value in values) / len(values)
