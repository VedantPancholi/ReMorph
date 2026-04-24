"""Training-time reward scoring for structured repair decisions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TrainingRewardResult:
    """Structured reward result for one predicted decision."""

    total_reward: float
    reward_breakdown: dict[str, float]
    details: dict[str, Any]


def score_training_decision(
    prediction: str | dict[str, Any],
    reference: dict[str, Any],
) -> TrainingRewardResult:
    """Score one model-generated JSON decision against the episode ground truth."""

    analysis = analyze_training_decision(prediction, reference)
    breakdown = {
        "correct_action_reward": 0.0,
        "selected_endpoint_reward": 0.0,
        "safe_abstain_reward": 0.0,
        "hallucinated_repair_penalty": 0.0,
        "invalid_json_penalty": 0.0,
        "wrong_action_penalty": 0.0,
        "unnecessary_repair_flag_penalty": 0.0,
    }

    if analysis["invalid_json"]:
        breakdown["invalid_json_penalty"] = -0.3
    else:
        if analysis["recoverable"]:
            if analysis["action_correct"]:
                breakdown["correct_action_reward"] = 1.0
            else:
                breakdown["wrong_action_penalty"] = -0.2
            if analysis["endpoint_applicable"] and analysis["endpoint_correct"]:
                breakdown["selected_endpoint_reward"] = 0.5
        else:
            if analysis["safe_abstain_correct"]:
                breakdown["safe_abstain_reward"] = 0.5
            elif analysis["hallucinated_unrecoverable_repair"]:
                breakdown["hallucinated_repair_penalty"] = -0.7
            else:
                breakdown["wrong_action_penalty"] = -0.2

        breakdown["unnecessary_repair_flag_penalty"] = round(
            -0.1 * analysis["unnecessary_repair_flags"],
            4,
        )

    total_reward = round(sum(breakdown.values()), 4)
    breakdown["total_reward"] = total_reward
    return TrainingRewardResult(
        total_reward=total_reward,
        reward_breakdown=breakdown,
        details=analysis,
    )


def analyze_training_decision(
    prediction: str | dict[str, Any],
    reference: dict[str, Any],
) -> dict[str, Any]:
    """Return the normalized decision analysis used by training and offline eval."""

    parsed_prediction, invalid_json = _parse_prediction(prediction)
    target = _reference_target(reference)
    recoverable = bool(reference.get("recoverable", True))

    predicted_action = str(parsed_prediction.get("action") or "") if parsed_prediction else ""
    target_action = str(target.get("action") or "")
    endpoint_applicable = target.get("selected_endpoint") is not None
    endpoint_correct = (
        not endpoint_applicable
        or (
            parsed_prediction is not None
            and parsed_prediction.get("selected_endpoint") == target.get("selected_endpoint")
        )
    )
    safe_abstain_correct = bool(
        not invalid_json
        and (
            bool(parsed_prediction.get("safe_abstain"))
            or predicted_action == "safe_abstain"
        )
        and target_action == "safe_abstain"
    )
    hallucinated_unrecoverable_repair = bool(
        not recoverable
        and not invalid_json
        and not safe_abstain_correct
        and predicted_action not in {"", "no_repair", "noop", "safe_abstain"}
    )

    unnecessary_repair_flags = 0
    for flag in ("method_rewrite", "payload_rewrite", "auth_rewrite"):
        if parsed_prediction and bool(parsed_prediction.get(flag)) and not bool(target.get(flag)):
            unnecessary_repair_flags += 1

    return {
        "invalid_json": invalid_json,
        "recoverable": recoverable,
        "predicted_action": predicted_action,
        "target_action": target_action,
        "action_correct": not invalid_json and predicted_action == target_action,
        "endpoint_applicable": endpoint_applicable,
        "endpoint_correct": endpoint_correct,
        "safe_abstain_correct": safe_abstain_correct,
        "hallucinated_unrecoverable_repair": hallucinated_unrecoverable_repair,
        "unnecessary_repair_flags": unnecessary_repair_flags,
        "prediction": parsed_prediction,
        "target": target,
    }


def _reference_target(reference: dict[str, Any]) -> dict[str, Any]:
    if isinstance(reference.get("target_action"), dict):
        return dict(reference["target_action"])
    target_json = reference.get("target_json")
    if isinstance(target_json, str):
        return json.loads(target_json)
    raise ValueError("Reference sample is missing target_action/target_json.")


def _parse_prediction(prediction: str | dict[str, Any]) -> tuple[dict[str, Any] | None, bool]:
    if isinstance(prediction, dict):
        return prediction, False
    try:
        parsed = json.loads(prediction)
    except Exception:  # noqa: BLE001
        return None, True
    if not isinstance(parsed, dict):
        return None, True
    return parsed, False
