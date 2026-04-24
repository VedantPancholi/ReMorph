"""Minimal supervised warm-start training and offline replay evaluation."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sprint4.eval.compare_policies import compare_policy_runs, render_comparison_summary
from sprint4.eval.metrics import summarize_eval_run
from sprint4.training.benchmark_contract import BENCHMARK_CONTRACT_VERSION
from sprint4.training.dataset_schema import EvalResultRow, PolicyAction, PolicyState, TransitionOutcome
from sprint4.training.reward_model import is_abstain_action, score_transition
from sprint4.training.split_strategy import build_group_id

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_./:-]+")


def load_json(path: str) -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        return {}
    return json.loads(file_path.read_text(encoding="utf-8"))


def load_jsonl_rows(path: str) -> list[dict[str, Any]]:
    file_path = Path(path)
    if not file_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with file_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def train_supervised_warmstart(
    *,
    supervised_rows: list[dict[str, Any]],
    supervised_train_manifest: dict[str, Any],
    model_name: str = "prototype_knn_v1",
    seed: int = 42,
    balance_by_scenario: bool = False,
    top_k: int = 1,
    scenario_weight_overrides: dict[str, float] | None = None,
    action_weight_overrides: dict[str, float] | None = None,
    reward_priors_by_group: dict[str, float] | None = None,
    reward_priors_by_scenario: dict[str, float] | None = None,
    focus_scenarios: list[str] | None = None,
) -> dict[str, Any]:
    """Train a tiny prototype policy from canonical supervised rows."""

    allowed_groups = {
        str(descriptor.get("group_id"))
        for descriptor in supervised_train_manifest.get("row_descriptors", [])
    }
    training_rows = [
        row for row in supervised_rows
        if build_group_id(row) in allowed_groups
    ]
    scenario_counts = Counter(
        str(row.get("raw_scenario_type") or "unknown")
        for row in training_rows
    )
    max_scenario_count = max(scenario_counts.values(), default=1)
    examples = []
    label_distribution: Counter[str] = Counter()
    scenario_distribution: Counter[str] = Counter()
    for row in training_rows:
        action = PolicyAction.model_validate(row.get("target_action") or {})
        raw_scenario_type = str(row.get("raw_scenario_type") or "unknown")
        group_id = build_group_id(row)
        text = serialize_supervised_row(row)
        example_weight = _compute_example_weight(
            row=row,
            action=action,
            balance_by_scenario=balance_by_scenario,
            scenario_counts=scenario_counts,
            max_scenario_count=max_scenario_count,
            scenario_weight_overrides=scenario_weight_overrides or {},
            action_weight_overrides=action_weight_overrides or {},
            focus_scenarios=set(focus_scenarios or []),
        )
        reference_reward = _lookup_reference_reward(
            group_id=group_id,
            raw_scenario_type=raw_scenario_type,
            reward_priors_by_group=reward_priors_by_group or {},
            reward_priors_by_scenario=reward_priors_by_scenario or {},
        )
        example = {
            "group_id": group_id,
            "episode_id": row.get("episode_id"),
            "raw_scenario_type": raw_scenario_type,
            "benchmark_partition": row.get("benchmark_partition"),
            "target_action": action.model_dump(mode="json"),
            "serialized_input": text,
            "token_weights": _token_weights(text),
            "example_weight": example_weight,
            "reference_reward": reference_reward,
        }
        examples.append(example)
        label_distribution[action.action_type] += 1
        scenario_distribution[raw_scenario_type] += 1

    return {
        "model_kind": model_name,
        "contract_version": BENCHMARK_CONTRACT_VERSION,
        "manifest_id": supervised_train_manifest.get("manifest_id"),
        "seed": seed,
        "top_k": max(1, int(top_k)),
        "balance_by_scenario": balance_by_scenario,
        "scenario_weight_overrides": dict(scenario_weight_overrides or {}),
        "action_weight_overrides": dict(action_weight_overrides or {}),
        "focus_scenarios": list(focus_scenarios or []),
        "generation_timestamp": datetime.now(UTC).isoformat(),
        "training_row_count": len(training_rows),
        "label_distribution": dict(label_distribution),
        "scenario_distribution": dict(scenario_distribution),
        "examples": examples,
    }


def predict_action(
    model_artifact: dict[str, Any],
    state: PolicyState | dict[str, Any],
) -> PolicyAction:
    """Predict one structured action from a policy state."""

    return predict_action_with_confidence(model_artifact, state)["action"]


def predict_action_with_confidence(
    model_artifact: dict[str, Any],
    state: PolicyState | dict[str, Any],
) -> dict[str, Any]:
    """Predict one action plus lightweight confidence metadata."""

    top_prediction = predict_top_k_actions_with_confidence(
        model_artifact=model_artifact,
        state=state,
        k=_prediction_top_k_for_state(model_artifact, state),
    )
    if top_prediction["candidates"]:
        best_candidate = top_prediction["candidates"][0]
        return {
            "action": PolicyAction.model_validate(best_candidate["action"]),
            "confidence": float(best_candidate["confidence"]),
            "best_score": float(best_candidate["score"]),
            "runner_up_score": float(top_prediction["runner_up_score"]),
            "matched_example": best_candidate.get("matched_example"),
            "candidates": top_prediction["candidates"],
        }

    policy_state = state if isinstance(state, PolicyState) else PolicyState.model_validate(state)
    return {
        "action": PolicyAction(action_type="abstain", reason="No warm-start examples available."),
        "confidence": 0.0,
        "best_score": 0.0,
        "runner_up_score": 0.0,
        "matched_example": None,
        "candidates": [],
        "query_state": policy_state.model_dump(mode="json"),
    }


def predict_top_k_actions_with_confidence(
    model_artifact: dict[str, Any],
    state: PolicyState | dict[str, Any],
    *,
    k: int = 3,
) -> dict[str, Any]:
    """Predict the strongest candidate actions with aggregated prototype voting."""

    policy_state = state if isinstance(state, PolicyState) else PolicyState.model_validate(state)
    examples = model_artifact.get("examples", [])
    if not examples:
        return {
            "candidates": [],
            "runner_up_score": 0.0,
            "query_state": policy_state.model_dump(mode="json"),
        }

    query_text = serialize_policy_state(policy_state)
    query_weights = _token_weights(query_text)

    scored_examples: list[dict[str, Any]] = []
    for example in examples:
        raw_score = _similarity_score(policy_state, query_weights, example)
        adjusted_score = _apply_example_priors(raw_score, example)
        scored_examples.append(
            {
                "raw_score": float(raw_score),
                "adjusted_score": float(adjusted_score),
                "example": example,
            }
        )

    ranked_examples = sorted(
        scored_examples,
        key=lambda item: (
            item["adjusted_score"],
            item["raw_score"],
            float((item["example"].get("reference_reward") or 0.0)),
        ),
        reverse=True,
    )
    top_examples = ranked_examples[: max(1, int(k))]
    candidates = _aggregate_top_candidates(top_examples)
    runner_up_score = candidates[1]["score"] if len(candidates) > 1 else (candidates[0]["score"] if candidates else 0.0)
    for index, candidate in enumerate(candidates):
        candidate["confidence"] = _confidence_from_scores(
            float(candidate["score"]),
            float(runner_up_score if index == 0 else 0.0),
        )
    return {
        "candidates": candidates,
        "runner_up_score": float(runner_up_score),
        "query_state": policy_state.model_dump(mode="json"),
    }


def evaluate_warmstart_on_manifest(
    *,
    model_artifact: dict[str, Any],
    shared_eval_manifest: dict[str, Any],
    transition_rows: list[dict[str, Any]],
    policy_name: str = "warmstart",
) -> dict[str, Any]:
    """Offline replay evaluation of a supervised warm-start policy."""

    allowed_groups = {
        str(descriptor.get("group_id"))
        for descriptor in shared_eval_manifest.get("transition_row_descriptors", [])
    }
    manifest_id = str(shared_eval_manifest.get("manifest_id") or "")
    eval_rows: list[dict[str, Any]] = []
    for row in transition_rows:
        group_id = build_group_id(row)
        if group_id not in allowed_groups:
            continue

        state = PolicyState.model_validate(row.get("state") or {})
        outcome = TransitionOutcome.model_validate(row.get("outcome") or {})
        prediction = predict_action_with_confidence(model_artifact, state)
        predicted_action = prediction["action"]
        reference_action = PolicyAction.model_validate(row.get("action") or {})
        matched = actions_match(predicted_action, reference_action, state)
        replay = _offline_replay_result(
            state=state,
            predicted_action=predicted_action,
            reference_row=row,
            matched=matched,
        )
        eval_result = EvalResultRow(
            manifest_id=manifest_id,
            group_id=group_id,
            episode_id=str(row.get("episode_id") or group_id),
            policy_name=policy_name,
            scenario_type=state.scenario_type,
            raw_scenario_type=state.raw_scenario_type,
            benchmark_partition=state.benchmark_partition,
            contract_version=state.contract_version,
            source_name=str((row.get("provenance") or {}).get("source_name") or "benchmark_episode"),
            source_record_id=(row.get("provenance") or {}).get("source_record_id"),
            success=bool(replay["success"]),
            outcome_class=str(replay["outcome_class"]),
            retries_used=int(replay["retries_used"]),
            hallucination_detected=bool(replay["hallucination_detected"]),
            wrong_route_detected=bool(replay["wrong_route_detected"]),
            reward_breakdown=replay["reward_breakdown"],
        )
        eval_rows.append(eval_result.model_dump(mode="json"))

    return {
        "policy_name": policy_name,
        "manifest_id": manifest_id,
        "eval_rows": eval_rows,
        "summary": summarize_eval_run(eval_rows),
    }


def run_supervised_warmstart_pipeline(
    *,
    supervised_rows: list[dict[str, Any]],
    supervised_train_manifest: dict[str, Any],
    shared_eval_manifest: dict[str, Any],
    transition_rows: list[dict[str, Any]],
    output_dir: str,
    policy_name: str = "warmstart",
    model_name: str = "prototype_knn_v1",
    seed: int = 42,
    baseline_summary: dict[str, Any] | None = None,
    adaptive_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Train, evaluate, and persist one supervised warm-start run."""

    assert_no_manifest_overlap(
        supervised_train_manifest=supervised_train_manifest,
        shared_eval_manifest=shared_eval_manifest,
    )

    model_artifact = train_supervised_warmstart(
        supervised_rows=supervised_rows,
        supervised_train_manifest=supervised_train_manifest,
        model_name=model_name,
        seed=seed,
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
    run_results.append(eval_run)
    comparison = compare_policy_runs(run_results)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    artifacts = {
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
                "seed": seed,
            },
        ),
        "eval_on_shared_manifest": _write_json(output_path / "eval_on_shared_manifest.json", eval_run),
        "comparison_json": _write_json(output_path / "comparison_vs_pretraining.json", comparison),
        "comparison_markdown": _write_text(
            output_path / "comparison_vs_pretraining.md",
            render_comparison_summary(comparison),
        ),
    }

    return {
        "model_artifact": model_artifact,
        "eval_run": eval_run,
        "comparison": comparison,
        "artifacts": artifacts,
    }


def serialize_supervised_row(row: dict[str, Any]) -> str:
    return str(row.get("input_text") or "").strip()


def assert_no_manifest_overlap(
    *,
    supervised_train_manifest: dict[str, Any],
    shared_eval_manifest: dict[str, Any],
) -> None:
    """Raise if the supervised train manifest overlaps the frozen shared eval set."""

    train_groups = {
        str(descriptor.get("group_id"))
        for descriptor in supervised_train_manifest.get("row_descriptors", [])
        if descriptor.get("group_id")
    }
    eval_groups = {
        str(descriptor.get("group_id"))
        for descriptor in shared_eval_manifest.get("supervised_row_descriptors", [])
        if descriptor.get("group_id")
    }
    eval_groups.update(
        {
            str(descriptor.get("group_id"))
            for descriptor in shared_eval_manifest.get("transition_row_descriptors", [])
            if descriptor.get("group_id")
        }
    )
    overlap = sorted(train_groups & eval_groups)
    if overlap:
        raise ValueError(
            "Supervised train manifest overlaps the frozen shared eval manifest: "
            + ", ".join(overlap[:5])
        )


def serialize_policy_state(state: PolicyState | dict[str, Any]) -> str:
    policy_state = state if isinstance(state, PolicyState) else PolicyState.model_validate(state)
    lines = [
        "Repair the failed API request using the contract evidence.",
        f"scenario_type={policy_state.scenario_type}",
        f"raw_scenario_type={policy_state.raw_scenario_type}",
        f"benchmark_partition={policy_state.benchmark_partition}",
        f"error_code={policy_state.failure_code}",
        f"error_message={policy_state.failure_message}",
        f"retry_count={policy_state.retry_count}",
        "failed_request="
        + json.dumps(
            {
                "method": policy_state.request_method,
                "path": policy_state.request_path,
                "query": policy_state.request_query,
                "headers": policy_state.request_headers,
                "body": policy_state.request_body,
            },
            sort_keys=True,
            ensure_ascii=True,
        ),
        "contract_hints=" + json.dumps(policy_state.contract_hints, sort_keys=True, ensure_ascii=True),
    ]
    return "\n".join(lines)


def actions_match(
    predicted_action: PolicyAction | dict[str, Any],
    reference_action: PolicyAction | dict[str, Any],
    state: PolicyState | dict[str, Any] | None = None,
) -> bool:
    predicted = predicted_action if isinstance(predicted_action, PolicyAction) else PolicyAction.model_validate(predicted_action)
    reference = reference_action if isinstance(reference_action, PolicyAction) else PolicyAction.model_validate(reference_action)
    policy_state = state if isinstance(state, PolicyState) or state is None else PolicyState.model_validate(state)

    if predicted.action_type != reference.action_type:
        return False
    if predicted.action_type == "abstain":
        return True
    if predicted.action_type == "repair_route":
        return (
            (predicted.target_method or "").upper() == (reference.target_method or "").upper()
            and str(predicted.target_path or "") == str(reference.target_path or "")
        )
    if predicted.action_type == "repair_payload":
        return _normalize_json(predicted.body_patch) == _normalize_json(reference.body_patch)
    if predicted.action_type == "repair_auth":
        predicted_patch = dict(predicted.header_patch or {})
        reference_patch = dict(reference.header_patch or {})
        if policy_state and policy_state.benchmark_partition == "unrecoverable":
            return False
        return predicted_patch == reference_patch
    return True


def _offline_replay_result(
    *,
    state: PolicyState,
    predicted_action: PolicyAction,
    reference_row: dict[str, Any],
    matched: bool,
) -> dict[str, Any]:
    reference_outcome = TransitionOutcome.model_validate(reference_row.get("outcome") or {})
    if matched:
        return {
            "success": bool(reference_row.get("success", False)),
            "outcome_class": str(reference_row.get("outcome_class") or "repair_success"),
            "retries_used": int(reference_outcome.retry_count),
            "hallucination_detected": bool(reference_outcome.used_hallucinated_auth),
            "wrong_route_detected": not bool(reference_outcome.selected_route_correct),
            "reward_breakdown": dict(reference_row.get("reward_breakdown") or {}),
        }

    failure_outcome = TransitionOutcome(
        request_succeeded=False,
        http_status=reference_outcome.http_status,
        retry_count=reference_outcome.retry_count,
        selected_route_correct=not (predicted_action.action_type == "repair_route"),
        payload_valid=False,
        used_hallucinated_auth=bool(
            state.benchmark_partition == "unrecoverable"
            and predicted_action.action_type == "repair_auth"
        ),
        abstained=is_abstain_action(predicted_action),
        correct_abstention=bool(
            state.benchmark_partition == "unrecoverable" and is_abstain_action(predicted_action)
        ),
        max_retries_exceeded=bool(reference_outcome.max_retries_exceeded),
    )
    reward = score_transition(state, predicted_action, failure_outcome)
    if failure_outcome.used_hallucinated_auth:
        outcome_class = "unsafe_hallucination"
    elif failure_outcome.correct_abstention:
        outcome_class = "correct_abstain"
    elif is_abstain_action(predicted_action) and state.benchmark_partition == "repairable":
        outcome_class = "incorrect_abstain"
    elif state.benchmark_partition == "unrecoverable":
        outcome_class = "unrecoverable_failure"
    else:
        outcome_class = "repair_failure"

    return {
        "success": bool(failure_outcome.correct_abstention),
        "outcome_class": outcome_class,
        "retries_used": int(failure_outcome.retry_count),
        "hallucination_detected": bool(failure_outcome.used_hallucinated_auth),
        "wrong_route_detected": not bool(failure_outcome.selected_route_correct),
        "reward_breakdown": reward.model_dump(mode="json"),
    }


def _similarity_score(
    state: PolicyState,
    query_weights: dict[str, float],
    example: dict[str, Any],
) -> float:
    example_weights = example.get("token_weights") or {}
    shared = set(query_weights) & set(example_weights)
    score = sum(min(query_weights[token], example_weights[token]) for token in shared)
    if state.raw_scenario_type == example.get("raw_scenario_type"):
        score += 10.0
    if state.benchmark_partition == example.get("benchmark_partition"):
        score += 3.0
    if state.scenario_type and state.scenario_type in example.get("serialized_input", ""):
        score += 1.0
    return score


def _apply_example_priors(raw_score: float, example: dict[str, Any]) -> float:
    example_weight = max(0.1, float(example.get("example_weight", 1.0) or 1.0))
    reference_reward = float(example.get("reference_reward", 0.0) or 0.0)
    reward_multiplier = 1.0 + max(-0.1, min(0.3, reference_reward / 60.0))
    return float(raw_score) * example_weight * reward_multiplier


def _aggregate_top_candidates(scored_examples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    aggregated: dict[str, dict[str, Any]] = {}
    for item in scored_examples:
        example = item["example"]
        action = PolicyAction.model_validate(example.get("target_action") or {})
        if action.reason is None:
            action.reason = f"Prototype warm-start matched {example.get('raw_scenario_type')}."
        signature = _action_signature(action)
        candidate = aggregated.setdefault(
            signature,
            {
                "action": action.model_dump(mode="json"),
                "score": 0.0,
                "support_count": 0,
                "matched_example": {
                    "group_id": example.get("group_id"),
                    "episode_id": example.get("episode_id"),
                    "raw_scenario_type": example.get("raw_scenario_type"),
                    "benchmark_partition": example.get("benchmark_partition"),
                    "target_action_type": (example.get("target_action") or {}).get("action_type"),
                },
            },
        )
        candidate["score"] = round(float(candidate["score"]) + float(item["adjusted_score"]), 6)
        candidate["support_count"] = int(candidate["support_count"]) + 1
    return sorted(
        aggregated.values(),
        key=lambda candidate: (float(candidate["score"]), int(candidate["support_count"])),
        reverse=True,
    )


def _action_signature(action: PolicyAction) -> str:
    return json.dumps(
        {
            "action_type": action.action_type,
            "target_method": action.target_method,
            "target_path": action.target_path,
            "body_patch": action.body_patch,
            "header_patch": action.header_patch,
            "query_patch": action.query_patch,
        },
        sort_keys=True,
        ensure_ascii=True,
    )


def _token_weights(text: str) -> dict[str, float]:
    counts: Counter[str] = Counter(token.lower() for token in TOKEN_PATTERN.findall(text))
    return {token: 1.0 + math.log1p(count) for token, count in counts.items()}


def _confidence_from_scores(best_score: float, runner_up_score: float) -> float:
    if best_score <= 0.0:
        return 0.0
    margin = max(0.0, best_score - max(0.0, runner_up_score))
    confidence = margin / max(best_score, 1.0)
    return round(min(1.0, max(0.0, confidence)), 4)


def _normalize_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True)


def _compute_example_weight(
    *,
    row: dict[str, Any],
    action: PolicyAction,
    balance_by_scenario: bool,
    scenario_counts: Counter[str],
    max_scenario_count: int,
    scenario_weight_overrides: dict[str, float],
    action_weight_overrides: dict[str, float],
    focus_scenarios: set[str],
) -> float:
    raw_scenario_type = str(row.get("raw_scenario_type") or "unknown")
    weight = 1.0
    if balance_by_scenario:
        scenario_count = max(1, int(scenario_counts.get(raw_scenario_type, 1)))
        weight *= float(max_scenario_count) / float(scenario_count)
    if not focus_scenarios or raw_scenario_type in focus_scenarios:
        weight *= float(scenario_weight_overrides.get(raw_scenario_type, 1.0) or 1.0)
        weight *= float(action_weight_overrides.get(action.action_type, 1.0) or 1.0)
    return round(min(4.0, max(0.1, weight)), 4)


def _lookup_reference_reward(
    *,
    group_id: str,
    raw_scenario_type: str,
    reward_priors_by_group: dict[str, float],
    reward_priors_by_scenario: dict[str, float],
) -> float:
    if group_id in reward_priors_by_group:
        return float(reward_priors_by_group[group_id])
    if raw_scenario_type in reward_priors_by_scenario:
        return float(reward_priors_by_scenario[raw_scenario_type])
    return 0.0


def _prediction_top_k_for_state(
    model_artifact: dict[str, Any],
    state: PolicyState | dict[str, Any],
) -> int:
    policy_state = state if isinstance(state, PolicyState) else PolicyState.model_validate(state)
    focus_scenarios = {
        str(raw_scenario_type)
        for raw_scenario_type in (model_artifact.get("focus_scenarios") or [])
    }
    if focus_scenarios and policy_state.raw_scenario_type not in focus_scenarios:
        return 1
    return max(1, int(model_artifact.get("top_k", 1) or 1))


def _write_json(path: Path, payload: dict[str, Any]) -> str:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return str(path)


def _write_text(path: Path, content: str) -> str:
    path.write_text(content, encoding="utf-8")
    return str(path)
