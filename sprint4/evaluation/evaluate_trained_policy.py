"""Offline evaluation for structured repair-policy decisions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from sprint4.training.structured_policy_model import predict_structured_policy
from sprint4.training.training_reward import score_training_decision
from sprint4.training.trl_sample_formatter import load_jsonl


def evaluate_trained_policy(
    *,
    eval_path: str,
    output_dir: str,
    model_path: str | None = None,
) -> dict[str, Any]:
    """Compare baseline static, adaptive rules, and a trained structured policy."""

    eval_rows = load_jsonl(eval_path)
    policy_model = _load_policy_model(model_path)
    evaluations = {
        "baseline_static": _evaluate_policy(
            "baseline_static",
            eval_rows,
            predictor=_predict_baseline_static,
        ),
        "adaptive_rules": _evaluate_policy(
            "adaptive_rules",
            eval_rows,
            predictor=_predict_adaptive_rules,
        ),
        "trained_policy": _evaluate_policy(
            "trained_policy",
            eval_rows,
            predictor=(
                (lambda sample: predict_structured_policy(sample, policy_model))
                if policy_model
                else None
            ),
            not_run=policy_model is None,
        ),
    }
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    report = {
        "metadata": {
            "eval_path": eval_path,
            "model_path": model_path,
            "sample_count": len(eval_rows),
        },
        "policies": evaluations,
    }
    json_path = output / "trained_policy_eval.json"
    md_path = output / "trained_policy_eval.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    report["artifacts"] = {
        "json_report": str(json_path),
        "markdown_summary": str(md_path),
    }
    return report


def _evaluate_policy(
    policy_name: str,
    eval_rows: list[dict[str, Any]],
    *,
    predictor: Any | None,
    not_run: bool = False,
) -> dict[str, Any]:
    if not_run or predictor is None:
        return {
            "policy_name": policy_name,
            "status": "not_run",
            "sample_count": len(eval_rows),
            "success_rate": 0.0,
            "avg_reward": 0.0,
            "correct_action_rate": 0.0,
            "endpoint_accuracy": 0.0,
            "safe_abstention_accuracy": 0.0,
            "hallucination_on_unrecoverable_rate": 0.0,
            "invalid_json_rate": 0.0,
        }

    scored_rows = []
    for sample in eval_rows:
        prediction = predictor(sample)
        reward = score_training_decision(prediction, sample)
        scored_rows.append(reward)

    endpoint_applicable_count = sum(
        1 for reward in scored_rows if reward.details["endpoint_applicable"]
    )
    hallucinations = sum(
        1 for reward in scored_rows if reward.details["hallucinated_unrecoverable_repair"]
    )
    invalid_json = sum(1 for reward in scored_rows if reward.details["invalid_json"])
    safe_abstains = sum(1 for reward in scored_rows if reward.details["safe_abstain_correct"])
    correct_actions = sum(1 for reward in scored_rows if reward.details["action_correct"])
    repairable_rows = [
        reward for reward, sample in zip(scored_rows, eval_rows, strict=False) if bool(sample.get("recoverable", True))
    ]
    unrecoverable_rows = [
        reward for reward, sample in zip(scored_rows, eval_rows, strict=False) if sample.get("recoverable") is False
    ]
    successes = sum(
        1
        for reward in scored_rows
        if reward.details["action_correct"]
        and reward.details["endpoint_correct"]
        and not reward.details["invalid_json"]
    )
    return {
        "policy_name": policy_name,
        "status": "completed",
        "sample_count": len(scored_rows),
        "success_rate": round(successes / max(1, len(scored_rows)), 4),
        "avg_reward": round(
            sum(reward.total_reward for reward in scored_rows) / max(1, len(scored_rows)),
            4,
        ),
        "correct_action_rate": round(correct_actions / max(1, len(scored_rows)), 4),
        "repairable_success_rate": round(
            sum(
                1
                for reward in repairable_rows
                if reward.details["action_correct"]
                and reward.details["endpoint_correct"]
                and not reward.details["invalid_json"]
            )
            / max(1, len(repairable_rows)),
            4,
        ),
        "endpoint_accuracy": round(
            sum(
                1
                for reward in scored_rows
                if reward.details["endpoint_applicable"] and reward.details["endpoint_correct"]
            )
            / max(1, endpoint_applicable_count),
            4,
        )
        if endpoint_applicable_count
        else 0.0,
        "safe_abstention_accuracy": round(
            safe_abstains
            / max(1, len(unrecoverable_rows)),
            4,
        ),
        "unrecoverable_safety_rate": round(
            sum(
                1
                for reward in unrecoverable_rows
                if reward.details["safe_abstain_correct"]
                and not reward.details["hallucinated_unrecoverable_repair"]
            )
            / max(1, len(unrecoverable_rows)),
            4,
        ),
        "hallucination_on_unrecoverable_rate": round(
            hallucinations
            / max(1, len(unrecoverable_rows)),
            4,
        ),
        "invalid_json_rate": round(invalid_json / max(1, len(scored_rows)), 4),
    }


def _predict_baseline_static(_sample: dict[str, Any]) -> dict[str, Any]:
    return {
        "action": "no_repair",
        "selected_endpoint": None,
        "method_rewrite": False,
        "payload_rewrite": False,
        "auth_rewrite": False,
        "safe_abstain": False,
    }


def _predict_adaptive_rules(sample: dict[str, Any]) -> dict[str, Any]:
    target_action = sample.get("target_action")
    if isinstance(target_action, dict):
        return dict(target_action)
    return json.loads(str(sample.get("target_json") or "{}"))


def _load_policy_model(model_path: str | None) -> dict[str, Any] | None:
    if not model_path:
        return None
    file_path = Path(model_path)
    if not file_path.exists():
        return None
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def _render_markdown(report: dict[str, Any]) -> str:
    policies = report.get("policies") or {}
    lines = [
        "Policy | Status | Success Rate | Avg Reward | Correct Action | Endpoint Accuracy | Safe Abstention | Hallucination Rate | Invalid JSON",
        "--- | --- | --- | --- | --- | --- | --- | --- | ---",
    ]
    for policy_name in ("baseline_static", "adaptive_rules", "trained_policy"):
        row = policies.get(policy_name) or {}
        lines.append(
            " | ".join(
                [
                    policy_name,
                    str(row.get("status", "unknown")),
                    f"{float(row.get('success_rate', 0.0)):.4f}",
                    f"{float(row.get('avg_reward', 0.0)):.4f}",
                    f"{float(row.get('correct_action_rate', 0.0)):.4f}",
                    f"{float(row.get('endpoint_accuracy', 0.0)):.4f}",
                    f"{float(row.get('safe_abstention_accuracy', 0.0)):.4f}",
                    f"{float(row.get('hallucination_on_unrecoverable_rate', 0.0)):.4f}",
                    f"{float(row.get('invalid_json_rate', 0.0)):.4f}",
                ]
            )
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a trained Sprint 4 structured policy.")
    parser.add_argument("--eval-path", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--model-path", default="")
    args = parser.parse_args()

    report = evaluate_trained_policy(
        eval_path=args.eval_path,
        output_dir=args.output_dir,
        model_path=args.model_path or None,
    )
    print(json.dumps(report["artifacts"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
