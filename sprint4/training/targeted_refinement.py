"""Targeted reward-guided refinement for the prototype warm-start policy."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from sprint4.eval.compare_policies import compare_policy_runs, render_comparison_summary
from sprint4.training.supervised_warmstart import (
    assert_no_manifest_overlap,
    evaluate_warmstart_on_manifest,
    load_json,
    load_jsonl_rows,
    train_supervised_warmstart,
)


def build_refinement_plan(
    *,
    error_analysis: dict[str, Any],
    transition_rows: list[dict[str, Any]],
    max_focus_scenarios: int = 5,
) -> dict[str, Any]:
    """Translate warm-start misses into deterministic refinement weights."""

    missed_by_scenario = {
        str(key): int(value)
        for key, value in (error_analysis.get("missed_by_scenario") or {}).items()
    }
    wrong_route_repairs = {
        str(key): int(value)
        for key, value in (error_analysis.get("wrong_route_repairs") or {}).items()
    }
    payload_failures = {
        str(key): int(value)
        for key, value in (error_analysis.get("payload_repair_failures") or {}).items()
    }
    scenario_gap_values: defaultdict[str, list[float]] = defaultdict(list)
    for row in error_analysis.get("analysis_rows", []):
        raw_scenario_type = str(row.get("raw_scenario_type") or "unknown")
        scenario_gap_values[raw_scenario_type].append(float(row.get("reward_gap_vs_adaptive", 0.0) or 0.0))

    ranked_focus_scenarios = sorted(
        missed_by_scenario,
        key=lambda scenario: (
            missed_by_scenario.get(scenario, 0),
            _average(scenario_gap_values.get(scenario, [])),
        ),
        reverse=True,
    )[:max_focus_scenarios]

    scenario_weight_overrides: dict[str, float] = {}
    for scenario in ranked_focus_scenarios:
        missed = missed_by_scenario.get(scenario, 0)
        wrong_route = wrong_route_repairs.get(scenario, 0)
        payload_failure = payload_failures.get(scenario, 0)
        average_gap = _average(scenario_gap_values.get(scenario, []))
        weight = 1.0 + (0.5 * missed) + (0.35 * wrong_route) + (0.25 * payload_failure)
        weight += min(1.25, average_gap / 20.0)
        scenario_weight_overrides[scenario] = round(weight, 4)

    action_weight_overrides: dict[str, float] = {}
    confusion = error_analysis.get("action_confusion") or {}
    for target_action_type, predicted_counts in confusion.items():
        target_action = str(target_action_type)
        off_diagonal = sum(
            int(count)
            for predicted_action, count in (predicted_counts or {}).items()
            if str(predicted_action) != target_action
        )
        if off_diagonal:
            action_weight_overrides[target_action] = round(1.0 + (0.25 * off_diagonal), 4)

    reward_priors_by_group, reward_priors_by_scenario = collect_reward_priors(transition_rows)
    recommended_top_k = 3 if action_weight_overrides else 1

    return {
        "focus_scenarios": ranked_focus_scenarios,
        "scenario_weight_overrides": scenario_weight_overrides,
        "action_weight_overrides": action_weight_overrides,
        "reward_priors_by_group": reward_priors_by_group,
        "reward_priors_by_scenario": reward_priors_by_scenario,
        "recommended_top_k": recommended_top_k,
    }


def collect_reward_priors(
    transition_rows: list[dict[str, Any]],
) -> tuple[dict[str, float], dict[str, float]]:
    """Derive replay reward priors from canonical transition rows."""

    reward_priors_by_group: dict[str, float] = {}
    reward_values_by_scenario: defaultdict[str, list[float]] = defaultdict(list)
    for row in transition_rows:
        group_id = str(row.get("group_id") or row.get("episode_id") or "")
        raw_scenario_type = str(row.get("raw_scenario_type") or "unknown")
        reward_total = float((row.get("reward_breakdown") or {}).get("reward_total", 0.0) or 0.0)
        if group_id:
            reward_priors_by_group[group_id] = reward_total
        reward_values_by_scenario[raw_scenario_type].append(reward_total)
    reward_priors_by_scenario = {
        scenario: round(_average(values), 4)
        for scenario, values in reward_values_by_scenario.items()
    }
    return reward_priors_by_group, reward_priors_by_scenario


def run_targeted_refinement_pipeline(
    *,
    supervised_rows: list[dict[str, Any]],
    supervised_train_manifest: dict[str, Any],
    shared_eval_manifest: dict[str, Any],
    transition_rows: list[dict[str, Any]],
    error_analysis: dict[str, Any],
    output_dir: str,
    policy_name: str = "warmstart_refined",
    model_name: str = "prototype_knn_refined_v1",
    seed: int = 42,
    balance_by_scenario: bool = True,
    top_k: int | None = None,
    baseline_summary: dict[str, Any] | None = None,
    adaptive_summary: dict[str, Any] | None = None,
    warmstart_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Train and evaluate a refinement pass on the frozen shared eval manifest."""

    assert_no_manifest_overlap(
        supervised_train_manifest=supervised_train_manifest,
        shared_eval_manifest=shared_eval_manifest,
    )

    refinement_plan = build_refinement_plan(
        error_analysis=error_analysis,
        transition_rows=transition_rows,
    )
    model_artifact = train_supervised_warmstart(
        supervised_rows=supervised_rows,
        supervised_train_manifest=supervised_train_manifest,
        model_name=model_name,
        seed=seed,
        balance_by_scenario=balance_by_scenario,
        top_k=top_k or int(refinement_plan.get("recommended_top_k", 1) or 1),
        scenario_weight_overrides=refinement_plan.get("scenario_weight_overrides") or {},
        action_weight_overrides=refinement_plan.get("action_weight_overrides") or {},
        reward_priors_by_group=refinement_plan.get("reward_priors_by_group") or {},
        reward_priors_by_scenario=refinement_plan.get("reward_priors_by_scenario") or {},
        focus_scenarios=list(refinement_plan.get("focus_scenarios") or []),
    )
    eval_run = evaluate_warmstart_on_manifest(
        model_artifact=model_artifact,
        shared_eval_manifest=shared_eval_manifest,
        transition_rows=transition_rows,
        policy_name=policy_name,
    )

    run_results = []
    if baseline_summary:
        run_results.append(
            {
                "policy_name": "baseline",
                "manifest_id": shared_eval_manifest.get("manifest_id"),
                "summary": baseline_summary,
            }
        )
    if adaptive_summary:
        run_results.append(
            {
                "policy_name": "adaptive",
                "manifest_id": shared_eval_manifest.get("manifest_id"),
                "summary": adaptive_summary,
            }
        )
    if warmstart_summary:
        run_results.append(
            {
                "policy_name": "warmstart",
                "manifest_id": shared_eval_manifest.get("manifest_id"),
                "summary": warmstart_summary,
            }
        )
    run_results.append(eval_run)
    comparison = compare_policy_runs(run_results)
    adoption_decision = assess_refinement_candidate(
        warmstart_summary=warmstart_summary,
        refined_summary=eval_run.get("summary") or {},
    )

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "refinement_plan": _write_json(output_path / "refinement_plan.json", refinement_plan),
        "model_artifact": _write_json(output_path / "model_artifact.json", model_artifact),
        "training_summary": _write_json(
            output_path / "training_summary.json",
            {
                "model_kind": model_artifact.get("model_kind"),
                "manifest_id": model_artifact.get("manifest_id"),
                "contract_version": model_artifact.get("contract_version"),
                "training_row_count": model_artifact.get("training_row_count"),
                "label_distribution": model_artifact.get("label_distribution"),
                "scenario_distribution": model_artifact.get("scenario_distribution"),
                "balance_by_scenario": model_artifact.get("balance_by_scenario"),
                "top_k": model_artifact.get("top_k"),
                "scenario_weight_overrides": model_artifact.get("scenario_weight_overrides"),
                "action_weight_overrides": model_artifact.get("action_weight_overrides"),
                "seed": seed,
            },
        ),
        "eval_on_shared_manifest": _write_json(output_path / "eval_on_shared_manifest.json", eval_run),
        "comparison_json": _write_json(output_path / "comparison_vs_warmstart.json", comparison),
        "comparison_markdown": _write_text(
            output_path / "comparison_vs_warmstart.md",
            render_comparison_summary(comparison),
        ),
        "adoption_decision": _write_json(output_path / "adoption_decision.json", adoption_decision),
    }
    return {
        "refinement_plan": refinement_plan,
        "model_artifact": model_artifact,
        "eval_run": eval_run,
        "comparison": comparison,
        "adoption_decision": adoption_decision,
        "artifacts": artifacts,
    }


def run_targeted_refinement_from_paths(
    *,
    supervised_rows_path: str,
    supervised_train_manifest_path: str,
    shared_eval_manifest_path: str,
    transition_rows_path: str,
    error_analysis_path: str,
    output_dir: str,
    policy_name: str = "warmstart_refined",
    model_name: str = "prototype_knn_refined_v1",
    seed: int = 42,
    balance_by_scenario: bool = True,
    top_k: int | None = None,
    baseline_summary_path: str | None = None,
    adaptive_summary_path: str | None = None,
    warmstart_eval_path: str | None = None,
) -> dict[str, Any]:
    """Convenience wrapper for the refinement CLI."""

    warmstart_eval = load_json(warmstart_eval_path) if warmstart_eval_path else {}
    return run_targeted_refinement_pipeline(
        supervised_rows=load_jsonl_rows(supervised_rows_path),
        supervised_train_manifest=load_json(supervised_train_manifest_path),
        shared_eval_manifest=load_json(shared_eval_manifest_path),
        transition_rows=load_jsonl_rows(transition_rows_path),
        error_analysis=load_json(error_analysis_path),
        output_dir=output_dir,
        policy_name=policy_name,
        model_name=model_name,
        seed=seed,
        balance_by_scenario=balance_by_scenario,
        top_k=top_k,
        baseline_summary=load_json(baseline_summary_path) if baseline_summary_path else None,
        adaptive_summary=load_json(adaptive_summary_path) if adaptive_summary_path else None,
        warmstart_summary=(warmstart_eval.get("summary") if warmstart_eval else None),
    )


def _average(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(float(value) for value in values) / len(values)


def assess_refinement_candidate(
    *,
    warmstart_summary: dict[str, Any] | None,
    refined_summary: dict[str, Any],
) -> dict[str, Any]:
    """Decide whether a refinement candidate is safe to promote."""

    if not warmstart_summary:
        return {
            "recommended_policy": "warmstart_refined",
            "promote_candidate": True,
            "reason": "No warm-start summary was provided, so the candidate cannot be compared against the prior checkpoint.",
        }

    warmstart_topline = warmstart_summary.get("topline") or {}
    warmstart_safety = warmstart_summary.get("safety") or {}
    refined_topline = refined_summary.get("topline") or {}
    refined_safety = refined_summary.get("safety") or {}

    success_delta = round(
        float(refined_topline.get("success_rate", 0.0))
        - float(warmstart_topline.get("success_rate", 0.0)),
        4,
    )
    reward_delta = round(
        float(refined_topline.get("average_reward", 0.0))
        - float(warmstart_topline.get("average_reward", 0.0)),
        4,
    )
    abstention_delta = round(
        float(refined_topline.get("correct_abstention_rate", 0.0))
        - float(warmstart_topline.get("correct_abstention_rate", 0.0)),
        4,
    )
    hallucination_delta = round(
        float(refined_topline.get("hallucination_rate", 0.0))
        - float(warmstart_topline.get("hallucination_rate", 0.0)),
        4,
    )
    incorrect_abstain_delta = round(
        float(refined_safety.get("incorrect_abstain_rate", 0.0))
        - float(warmstart_safety.get("incorrect_abstain_rate", 0.0)),
        4,
    )

    promote_candidate = (
        success_delta > 0.0
        and abstention_delta >= 0.0
        and hallucination_delta <= 0.0
        and incorrect_abstain_delta <= 0.0
        and reward_delta >= 0.0
    )
    reason = (
        "Candidate improves overall success without regressing abstention safety."
        if promote_candidate
        else "Candidate is not promoted because it does not beat the frozen warm-start checkpoint on the shared eval contract."
    )
    return {
        "recommended_policy": "warmstart_refined" if promote_candidate else "warmstart",
        "promote_candidate": promote_candidate,
        "reason": reason,
        "deltas": {
            "success_rate": success_delta,
            "average_reward": reward_delta,
            "correct_abstention_rate": abstention_delta,
            "hallucination_rate": hallucination_delta,
            "incorrect_abstain_rate": incorrect_abstain_delta,
        },
    }


def _write_json(path: Path, payload: dict[str, Any]) -> str:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return str(path)


def _write_text(path: Path, content: str) -> str:
    path.write_text(content, encoding="utf-8")
    return str(path)
