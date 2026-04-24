"""Shared-eval comparison harness for baseline, adaptive, and trained policies."""

from __future__ import annotations

from typing import Any

from sprint4.eval.metrics import summarize_eval_run
from sprint4.training.dataset_schema import EvalResultRow
from sprint4.training.split_strategy import build_group_id


def evaluate_policy_on_manifest(
    policy_name: str,
    manifest: dict[str, Any],
    transition_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Materialize eval result rows for one policy on a shared eval manifest."""

    manifest_id = str(manifest.get("manifest_id") or "")
    allowed_groups = {
        str(descriptor.get("group_id"))
        for descriptor in manifest.get("transition_row_descriptors", [])
    }
    eval_rows: list[dict[str, Any]] = []
    for row in transition_rows:
        group_id = build_group_id(row)
        if group_id not in allowed_groups:
            continue
        state = row.get("state") or {}
        provenance = row.get("provenance") or {}
        outcome = row.get("outcome") or {}
        eval_result = EvalResultRow(
            manifest_id=manifest_id,
            group_id=group_id,
            episode_id=str(row.get("episode_id") or group_id),
            policy_name=policy_name,
            scenario_type=str(state.get("scenario_type") or "unknown"),
            raw_scenario_type=str(row.get("raw_scenario_type") or state.get("raw_scenario_type") or "unknown"),
            benchmark_partition=str(row.get("benchmark_partition") or state.get("benchmark_partition") or "other"),
            contract_version=str(row.get("contract_version") or state.get("contract_version") or "unknown"),
            source_name=str(provenance.get("source_name") or "unknown"),
            source_record_id=provenance.get("source_record_id"),
            success=bool(row.get("success", False)),
            outcome_class=str(row.get("outcome_class") or "repair_failure"),
            retries_used=int(row.get("retries_used", outcome.get("retry_count", 0)) or 0),
            hallucination_detected=bool(
                row.get("hallucination_detected", outcome.get("used_hallucinated_auth", False))
            ),
            wrong_route_detected=bool(
                row.get("wrong_route_detected", not outcome.get("selected_route_correct", True))
            ),
            reward_breakdown=row.get("reward_breakdown") or {},
        )
        eval_rows.append(eval_result.model_dump(mode="json"))

    return {
        "policy_name": policy_name,
        "manifest_id": manifest_id,
        "eval_rows": eval_rows,
        "summary": summarize_eval_run(eval_rows),
    }


def compare_policy_runs(eval_run_results: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare multiple policy runs that used the same shared eval manifest."""

    comparison_rows: list[dict[str, Any]] = []
    manifest_ids = sorted({result.get("manifest_id") for result in eval_run_results if result.get("manifest_id")})
    for result in eval_run_results:
        summary = result.get("summary") or {}
        topline = summary.get("topline") or {}
        safety = summary.get("safety") or {}
        comparison_rows.append(
            {
                "policy_name": result.get("policy_name"),
                "manifest_id": result.get("manifest_id"),
                "overall_success": topline.get("success_rate", 0.0),
                "repairable_success": topline.get("repairable_success_rate", 0.0),
                "correct_abstention": topline.get("correct_abstention_rate", 0.0),
                "average_reward": topline.get("average_reward", 0.0),
                "average_retries": topline.get("average_retry_count", 0.0),
                "hallucination_rate": topline.get("hallucination_rate", 0.0),
                "wrong_route_rate": topline.get("wrong_route_rate", 0.0),
                "incorrect_abstain_rate": safety.get("incorrect_abstain_rate", 0.0),
            }
        )
    return {
        "manifest_ids": manifest_ids,
        "policies": comparison_rows,
    }


def render_comparison_summary(comparison: dict[str, Any]) -> str:
    """Render a concise human-readable comparison table."""

    rows = comparison.get("policies", [])
    if not rows:
        return "No policy runs available."
    header = (
        "Policy | Overall Success | Repairable Success | Correct Abstain | Avg Reward | Avg Retries | Hallucination Rate"
    )
    divider = "--- | --- | --- | --- | --- | --- | ---"
    lines = [header, divider]
    for row in rows:
        lines.append(
            " | ".join(
                [
                    str(row.get("policy_name")),
                    f"{float(row.get('overall_success', 0.0)):.4f}",
                    f"{float(row.get('repairable_success', 0.0)):.4f}",
                    f"{float(row.get('correct_abstention', 0.0)):.4f}",
                    f"{float(row.get('average_reward', 0.0)):.4f}",
                    f"{float(row.get('average_retries', 0.0)):.4f}",
                    f"{float(row.get('hallucination_rate', 0.0)):.4f}",
                ]
            )
        )
    return "\n".join(lines)
