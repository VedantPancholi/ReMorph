"""Warm-start vs adaptive policy error analysis on the frozen shared eval manifest."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from sprint4.training.dataset_schema import PolicyAction, PolicyState
from sprint4.training.supervised_warmstart import (
    actions_match,
    assert_no_manifest_overlap,
    load_json,
    load_jsonl_rows,
    predict_action_with_confidence,
)
from sprint4.training.split_strategy import build_group_id


def analyze_warmstart_vs_adaptive(
    *,
    model_artifact: dict[str, Any],
    supervised_train_manifest: dict[str, Any],
    shared_eval_manifest: dict[str, Any],
    transition_rows: list[dict[str, Any]],
    warmstart_eval_rows: list[dict[str, Any]],
    adaptive_eval_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compare warm-start behavior against adaptive on the frozen eval set."""

    assert_no_manifest_overlap(
        supervised_train_manifest=supervised_train_manifest,
        shared_eval_manifest=shared_eval_manifest,
    )

    allowed_groups = {
        str(descriptor.get("group_id"))
        for descriptor in shared_eval_manifest.get("transition_row_descriptors", [])
        if descriptor.get("group_id")
    }
    transition_by_group = {
        build_group_id(row): row
        for row in transition_rows
        if build_group_id(row) in allowed_groups
    }
    warmstart_by_group = {
        str(row.get("group_id")): row
        for row in warmstart_eval_rows
    }
    adaptive_by_group = {
        str(row.get("group_id")): row
        for row in adaptive_eval_rows
    }

    analysis_rows: list[dict[str, Any]] = []
    missed_by_scenario: Counter[str] = Counter()
    scenario_support: Counter[str] = Counter()
    false_abstentions_by_scenario: Counter[str] = Counter()
    payload_failures_by_scenario: Counter[str] = Counter()
    wrong_route_by_scenario: Counter[str] = Counter()
    unsafe_auth_by_scenario: Counter[str] = Counter()
    confusion: Counter[tuple[str, str]] = Counter()
    confidence_buckets: Counter[str] = Counter()

    for group_id in sorted(allowed_groups):
        transition_row = transition_by_group.get(group_id)
        warmstart_row = warmstart_by_group.get(group_id)
        adaptive_row = adaptive_by_group.get(group_id)
        if transition_row is None or warmstart_row is None or adaptive_row is None:
            continue

        state = PolicyState.model_validate(transition_row.get("state") or {})
        reference_action = PolicyAction.model_validate(transition_row.get("action") or {})
        prediction = predict_action_with_confidence(model_artifact, state)
        predicted_action = prediction["action"]
        matched = actions_match(predicted_action, reference_action, state)

        raw_scenario_type = state.raw_scenario_type
        scenario_support[raw_scenario_type] += 1
        confusion[(reference_action.action_type, predicted_action.action_type)] += 1
        confidence_buckets[_confidence_bucket(float(prediction["confidence"]))] += 1

        row = {
            "group_id": group_id,
            "episode_id": transition_row.get("episode_id"),
            "raw_scenario_type": raw_scenario_type,
            "scenario_type": state.scenario_type,
            "benchmark_partition": state.benchmark_partition,
            "support_count_for_scenario": scenario_support[raw_scenario_type],
            "warmstart_success": bool(warmstart_row.get("success", False)),
            "adaptive_success": bool(adaptive_row.get("success", False)),
            "warmstart_outcome_class": warmstart_row.get("outcome_class"),
            "adaptive_outcome_class": adaptive_row.get("outcome_class"),
            "target_action_type": reference_action.action_type,
            "predicted_action_type": predicted_action.action_type,
            "predicted_action": predicted_action.model_dump(mode="json"),
            "matched_target_action": matched,
            "action_confidence": prediction["confidence"],
            "confidence_best_score": prediction["best_score"],
            "confidence_runner_up_score": prediction["runner_up_score"],
            "matched_example": prediction["matched_example"],
            "reward_gap_vs_adaptive": round(
                float((adaptive_row.get("reward_breakdown") or {}).get("reward_total", 0.0))
                - float((warmstart_row.get("reward_breakdown") or {}).get("reward_total", 0.0)),
                4,
            ),
            "warmstart_reward": float((warmstart_row.get("reward_breakdown") or {}).get("reward_total", 0.0)),
            "adaptive_reward": float((adaptive_row.get("reward_breakdown") or {}).get("reward_total", 0.0)),
            "repairable_false_abstention": bool(
                state.benchmark_partition == "repairable"
                and predicted_action.action_type == "abstain"
                and not bool(warmstart_row.get("success", False))
            ),
            "wrong_route_repair": bool(warmstart_row.get("wrong_route_detected", False)),
            "payload_repair_failure": bool(
                reference_action.action_type == "repair_payload"
                and not bool(warmstart_row.get("success", False))
            ),
            "unsafe_auth_action": bool(
                state.benchmark_partition == "unrecoverable"
                and predicted_action.action_type == "repair_auth"
            ),
        }
        analysis_rows.append(row)

        if not row["warmstart_success"]:
            missed_by_scenario[raw_scenario_type] += 1
        if row["repairable_false_abstention"]:
            false_abstentions_by_scenario[raw_scenario_type] += 1
        if row["payload_repair_failure"]:
            payload_failures_by_scenario[raw_scenario_type] += 1
        if row["wrong_route_repair"]:
            wrong_route_by_scenario[raw_scenario_type] += 1
        if row["unsafe_auth_action"]:
            unsafe_auth_by_scenario[raw_scenario_type] += 1

    missed_rows = [row for row in analysis_rows if not row["warmstart_success"]]
    missed_rows_sorted = sorted(
        missed_rows,
        key=lambda row: (row["reward_gap_vs_adaptive"], row["action_confidence"]),
        reverse=True,
    )

    return {
        "manifest_id": str(shared_eval_manifest.get("manifest_id") or ""),
        "row_count": len(analysis_rows),
        "scenario_support": dict(scenario_support),
        "missed_by_scenario": dict(missed_by_scenario),
        "repairable_false_abstentions": dict(false_abstentions_by_scenario),
        "wrong_route_repairs": dict(wrong_route_by_scenario),
        "payload_repair_failures": dict(payload_failures_by_scenario),
        "unsafe_auth_actions": dict(unsafe_auth_by_scenario),
        "action_confusion": _format_confusion(confusion),
        "confidence_distribution": dict(confidence_buckets),
        "largest_reward_gaps": missed_rows_sorted[:5],
        "analysis_rows": analysis_rows,
    }


def persist_error_analysis(
    *,
    analysis: dict[str, Any],
    output_dir: str,
) -> dict[str, str]:
    """Persist machine-readable and markdown error-analysis artifacts."""

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    json_path = output_path / "warmstart_error_analysis.json"
    md_path = output_path / "warmstart_error_analysis.md"
    missed_path = output_path / "missed_by_scenario.json"
    confusion_path = output_path / "action_confusion.json"

    json_path.write_text(json.dumps(analysis, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(_render_error_analysis_markdown(analysis), encoding="utf-8")
    missed_path.write_text(json.dumps(analysis.get("missed_by_scenario", {}), indent=2, sort_keys=True), encoding="utf-8")
    confusion_path.write_text(json.dumps(analysis.get("action_confusion", {}), indent=2, sort_keys=True), encoding="utf-8")
    return {
        "error_analysis_json": str(json_path),
        "error_analysis_markdown": str(md_path),
        "missed_by_scenario": str(missed_path),
        "action_confusion": str(confusion_path),
    }


def analyze_from_paths(
    *,
    model_artifact_path: str,
    supervised_train_manifest_path: str,
    shared_eval_manifest_path: str,
    transition_rows_path: str,
    warmstart_eval_path: str,
    adaptive_eval_path: str,
    output_dir: str,
) -> dict[str, Any]:
    """Convenience wrapper for the CLI."""

    analysis = analyze_warmstart_vs_adaptive(
        model_artifact=load_json(model_artifact_path),
        supervised_train_manifest=load_json(supervised_train_manifest_path),
        shared_eval_manifest=load_json(shared_eval_manifest_path),
        transition_rows=load_jsonl_rows(transition_rows_path),
        warmstart_eval_rows=_load_eval_rows(warmstart_eval_path),
        adaptive_eval_rows=_load_eval_rows(adaptive_eval_path),
    )
    artifacts = persist_error_analysis(analysis=analysis, output_dir=output_dir)
    return {
        "analysis": analysis,
        "artifacts": artifacts,
    }


def _load_eval_rows(path: str) -> list[dict[str, Any]]:
    try:
        data = load_json(path)
    except json.JSONDecodeError:
        return load_jsonl_rows(path)
    if "eval_rows" in data:
        return list(data.get("eval_rows") or [])
    return load_jsonl_rows(path)


def _format_confusion(confusion: Counter[tuple[str, str]]) -> dict[str, dict[str, int]]:
    matrix: dict[str, dict[str, int]] = {}
    for (target_action, predicted_action), count in sorted(confusion.items()):
        matrix.setdefault(target_action, {})[predicted_action] = int(count)
    return matrix


def _confidence_bucket(confidence: float) -> str:
    if confidence >= 0.75:
        return "high"
    if confidence >= 0.4:
        return "medium"
    return "low"


def _render_error_analysis_markdown(analysis: dict[str, Any]) -> str:
    lines = [
        "# Warm-Start Error Analysis",
        "",
        f"- Manifest id: `{analysis.get('manifest_id')}`",
        f"- Row count: `{analysis.get('row_count')}`",
        "",
        "## Missed By Scenario",
        "",
    ]
    for scenario, count in sorted((analysis.get("missed_by_scenario") or {}).items()):
        support = (analysis.get("scenario_support") or {}).get(scenario, 0)
        lines.append(f"- `{scenario}` missed `{count}` of `{support}`")
    lines.extend(["", "## Action Confusion", ""])
    for target_action, predicted_counts in sorted((analysis.get("action_confusion") or {}).items()):
        rendered = ", ".join(
            f"{predicted_action}={count}"
            for predicted_action, count in sorted(predicted_counts.items())
        )
        lines.append(f"- `{target_action}` -> {rendered}")
    lines.extend(["", "## Largest Reward Gaps", ""])
    for row in analysis.get("largest_reward_gaps", []):
        lines.append(
            f"- `{row['raw_scenario_type']}` predicted `{row['predicted_action_type']}` "
            f"vs target `{row['target_action_type']}`, reward gap `{row['reward_gap_vs_adaptive']}`"
        )
    return "\n".join(lines)
