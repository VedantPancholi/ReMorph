"""Compare baseline, adaptive rules, and trained-policy artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from sprint4.training.episode_dataset import load_episode_jsonl
from sprint4.training.policy_adapter import episode_to_rl_transition
from sprint4.training.training_reward import score_training_decision


def compare_trained_vs_untrained(
    *,
    baseline_records: list[dict[str, Any]],
    adaptive_records: list[dict[str, Any]],
    trained_policy_records: list[dict[str, Any]] | None = None,
    trained_policy_summary: dict[str, Any] | None = None,
    trained_policy_eval: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare baseline, adaptive rules, and an optional trained policy."""

    policies = [
        _summarize_policy("baseline", baseline_records),
        _summarize_policy("adaptive_rules", adaptive_records),
        _summarize_trained_policy(
            trained_policy_records=trained_policy_records,
            trained_policy_summary=trained_policy_summary,
            trained_policy_eval=trained_policy_eval,
        ),
    ]
    return {
        "policies": policies,
        "notes": _comparison_notes(policies),
    }


def _summarize_policy(policy_name: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    normalized = [_normalize_row(row) for row in rows]
    repairable = [row for row in normalized if row.get("info", {}).get("recoverable") is not False]
    unrecoverable = [row for row in normalized if row.get("info", {}).get("recoverable") is False]
    explicit_safe_abstains = [
        row for row in unrecoverable if bool(row.get("action", {}).get("safe_abstain"))
    ]
    safe_unrecoverable = [
        row
        for row in unrecoverable
        if not bool(row.get("action", {}).get("auth_rewrite"))
        and not bool(_reward_breakdown(row).get("hallucination_penalty", 0.0) < 0.0)
    ]
    return {
        "policy_name": policy_name,
        "status": "completed",
        "placeholder_used": False,
        "episode_count": len(normalized),
        "success_rate": _rate(
            sum(bool(row.get("info", {}).get("success")) for row in normalized),
            len(normalized),
        ),
        "avg_reward": _average(float(row.get("reward", 0.0)) for row in normalized),
        "avg_retries": _average(
            int(row.get("info", {}).get("retries_used", 0) or 0) for row in normalized
        ),
        "repairable_success_rate": _rate(
            sum(bool(row.get("info", {}).get("success")) for row in repairable),
            len(repairable),
        ),
        "unrecoverable_safety_rate": _rate(len(safe_unrecoverable), len(unrecoverable)),
        "safe_abstention_accuracy": _rate(len(explicit_safe_abstains), len(unrecoverable)),
    }


def _summarize_trained_policy(
    *,
    trained_policy_records: list[dict[str, Any]] | None,
    trained_policy_summary: dict[str, Any] | None,
    trained_policy_eval: dict[str, Any] | None,
) -> dict[str, Any]:
    if trained_policy_eval:
        trained_row = dict((trained_policy_eval.get("policies") or {}).get("trained_policy") or {})
        trained_row.setdefault("policy_name", "trained_policy")
        trained_row.setdefault("placeholder_used", False)
        trained_row.setdefault("episode_count", int(trained_row.get("sample_count", 0)))
        return trained_row
    if trained_policy_summary:
        metrics = dict(trained_policy_summary.get("policy_metrics") or {})
        return {
            "policy_name": "trained_policy",
            "status": str(trained_policy_summary.get("status") or "completed"),
            "placeholder_used": bool(trained_policy_summary.get("placeholder", False)),
            "episode_count": int(
                trained_policy_summary.get("eval_summary", {}).get(
                    "sample_count",
                    len(trained_policy_records or []),
                )
            ),
            "success_rate": float(metrics.get("success_rate", 0.0)),
            "avg_reward": float(metrics.get("avg_reward", 0.0)),
            "avg_retries": float(metrics.get("avg_retries", 0.0)),
            "repairable_success_rate": float(metrics.get("repairable_success_rate", 0.0)),
            "unrecoverable_safety_rate": float(metrics.get("unrecoverable_safety_rate", 0.0)),
            "safe_abstention_accuracy": float(metrics.get("safe_abstention_accuracy", 0.0)),
            "summary_path": trained_policy_summary.get("summary_path"),
        }
    if trained_policy_records:
        summary = _summarize_policy("trained_policy", trained_policy_records)
        summary["status"] = "completed"
        return summary
    return {
        "policy_name": "trained_policy",
        "status": "not_run",
        "placeholder_used": True,
        "episode_count": 0,
        "success_rate": 0.0,
        "avg_reward": 0.0,
        "avg_retries": 0.0,
        "repairable_success_rate": 0.0,
        "unrecoverable_safety_rate": 0.0,
        "safe_abstention_accuracy": 0.0,
    }


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    if {"observation", "action", "reward", "done", "info"} <= set(row):
        return row
    return episode_to_rl_transition(row)


def _reward_breakdown(row: dict[str, Any]) -> dict[str, Any]:
    return dict((row.get("info") or {}).get("reward_breakdown") or {})


def _average(values: Any) -> float:
    values = list(values)
    if not values:
        return 0.0
    return round(sum(float(value) for value in values) / len(values), 4)


def _rate(numerator: int | float, denominator: int | float) -> float:
    if not denominator:
        return 0.0
    return round(float(numerator) / float(denominator), 4)


def _load_rows_from_input_dir(input_dir: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    base = Path(input_dir)
    rows: list[dict[str, Any]] = []
    for filename in ("train.jsonl", "eval.jsonl", "train_prompts.jsonl", "eval_prompts.jsonl"):
        rows.extend(load_episode_jsonl(str(base / filename), agent_type=None))
    if rows and "prompt" in rows[0] and "target_json" in rows[0]:
        baseline = [_trl_prompt_row_to_comparison_row(row, policy_name="baseline") for row in rows]
        adaptive = [_trl_prompt_row_to_comparison_row(row, policy_name="adaptive_rules") for row in rows]
        return baseline, adaptive
    baseline = [row for row in rows if str((row.get("info") or {}).get("agent_type") or "") == "baseline"]
    adaptive = [row for row in rows if str((row.get("info") or {}).get("agent_type") or "") == "adaptive"]
    return baseline, adaptive


def _trl_prompt_row_to_comparison_row(row: dict[str, Any], *, policy_name: str) -> dict[str, Any]:
    if policy_name == "adaptive_rules":
        prediction = dict(row.get("target_action") or json.loads(str(row.get("target_json") or "{}")))
    else:
        prediction = {
            "action": "no_repair",
            "selected_endpoint": None,
            "method_rewrite": False,
            "payload_rewrite": False,
            "auth_rewrite": False,
            "safe_abstain": False,
        }
    reward = score_training_decision(prediction, row)
    success = bool(
        reward.details["action_correct"]
        and reward.details["endpoint_correct"]
        and not reward.details["invalid_json"]
    )
    recoverable = bool(row.get("recoverable", True))
    return {
        "observation": {
            "scenario_type": row.get("scenario_type", "unknown"),
        },
        "action": {
            "safe_abstain": bool(prediction.get("safe_abstain", False)),
            "auth_rewrite": bool(prediction.get("auth_rewrite", False)),
        },
        "reward": reward.total_reward,
        "done": True,
        "info": {
            "success": success,
            "final_status_code": 200 if success else 400,
            "retries_used": 0,
            "reward_breakdown": {
                "hallucination_penalty": reward.reward_breakdown.get("hallucinated_repair_penalty", 0.0),
                "final_reward": reward.total_reward,
            },
            "recoverable": recoverable,
            "unrecoverable_reason": prediction.get("unrecoverable_reason"),
            "raw_scenario_type": row.get("raw_scenario_type"),
            "agent_type": policy_name,
        },
    }


def _resolve_trained_policy_summary(
    *,
    input_dir: str,
    trained_policy_summary_path: str | None,
) -> dict[str, Any] | None:
    candidates = []
    if trained_policy_summary_path:
        candidates.append(Path(trained_policy_summary_path))
    input_path = Path(input_dir)
    candidates.extend(
        [
            input_path / "trained_policy_summary.json",
            input_path.parent / "trl_training" / "trained_policy_summary.json",
            input_path.parent / "training" / "trained_policy_summary.json",
        ]
    )
    for path in candidates:
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                payload["summary_path"] = str(path)
                return payload
    return None


def _resolve_trained_policy_eval(
    *,
    input_dir: str,
) -> dict[str, Any] | None:
    input_path = Path(input_dir)
    candidates = [
        input_path / "trained_policy_eval.json",
        input_path.parent / "trl_training" / "trained_policy_eval.json",
        input_path.parent / "training" / "trained_policy_eval.json",
    ]
    for path in candidates:
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                payload["eval_path"] = str(path)
                return payload
    return None


def _comparison_notes(policies: list[dict[str, Any]]) -> list[str]:
    by_name = {policy["policy_name"]: policy for policy in policies}
    adaptive = by_name.get("adaptive_rules") or {}
    trained = by_name.get("trained_policy") or {}
    if str(trained.get("status")) == "not_run":
        return ["trained_policy has not been run yet; no learned-policy lift is claimed."]

    delta_success = round(
        float(trained.get("success_rate", 0.0)) - float(adaptive.get("success_rate", 0.0)),
        4,
    )
    delta_reward = round(
        float(trained.get("avg_reward", 0.0)) - float(adaptive.get("avg_reward", 0.0)),
        4,
    )
    if delta_success > 0.0 or delta_reward > 0.0:
        return [
            f"trained_policy improves over adaptive_rules by success_delta={delta_success:.4f} and reward_delta={delta_reward:.4f}."
        ]
    if delta_success == 0.0 and delta_reward == 0.0:
        return [
            "trained_policy matches adaptive_rules on the available eval slice; no improvement is fabricated."
        ]
    return [
        f"trained_policy underperforms adaptive_rules by success_delta={delta_success:.4f} and reward_delta={delta_reward:.4f}."
    ]


def _render_markdown(comparison: dict[str, Any]) -> str:
    rows = comparison.get("policies", [])
    header = (
        "Policy | Status | Success Rate | Avg Reward | Avg Retries | Repairable Success | "
        "Unrecoverable Safety | Safe Abstention Accuracy"
    )
    divider = "--- | --- | --- | --- | --- | --- | --- | ---"
    lines = [header, divider]
    for row in rows:
        lines.append(
            " | ".join(
                [
                    str(row.get("policy_name")),
                    str(row.get("status", "unknown")),
                    f"{float(row.get('success_rate', 0.0)):.4f}",
                    f"{float(row.get('avg_reward', 0.0)):.4f}",
                    f"{float(row.get('avg_retries', 0.0)):.4f}",
                    f"{float(row.get('repairable_success_rate', 0.0)):.4f}",
                    f"{float(row.get('unrecoverable_safety_rate', 0.0)):.4f}",
                    f"{float(row.get('safe_abstention_accuracy', 0.0)):.4f}",
                ]
            )
        )
    notes = comparison.get("notes") or []
    if notes:
        lines.append("")
        lines.append("Notes")
        lines.append("---")
        lines.extend(f"- {note}" for note in notes)
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare baseline, adaptive, and trained policy artifacts.")
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--trained-policy-summary-path", default="")
    args = parser.parse_args()

    baseline, adaptive = _load_rows_from_input_dir(args.input_dir)
    trained_summary = _resolve_trained_policy_summary(
        input_dir=args.input_dir,
        trained_policy_summary_path=args.trained_policy_summary_path or None,
    )
    trained_eval = _resolve_trained_policy_eval(input_dir=args.input_dir)
    comparison = compare_trained_vs_untrained(
        baseline_records=baseline,
        adaptive_records=adaptive,
        trained_policy_summary=trained_summary,
        trained_policy_eval=trained_eval,
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "comparison.json"
    md_path = output_dir / "comparison.md"
    json_path.write_text(json.dumps(comparison, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(_render_markdown(comparison), encoding="utf-8")
    print(json.dumps({"json_report": str(json_path), "markdown_summary": str(md_path)}, indent=2))


if __name__ == "__main__":
    main()
