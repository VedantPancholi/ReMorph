"""Lightweight structured policy artifact learning and inference."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from typing import Any


def learn_structured_policy(samples: list[dict[str, Any]]) -> dict[str, Any]:
    """Learn a small majority-vote policy over raw and broad scenario types."""

    by_raw: dict[str, Counter[str]] = defaultdict(Counter)
    by_scenario: dict[str, Counter[str]] = defaultdict(Counter)
    by_recoverable: dict[str, Counter[str]] = defaultdict(Counter)
    overall: Counter[str] = Counter()

    for sample in samples:
        action = json.dumps(_target_action(sample), sort_keys=True, ensure_ascii=True)
        raw_scenario = str(sample.get("raw_scenario_type") or "unknown")
        scenario_type = str(sample.get("scenario_type") or "unknown")
        recoverable_key = "repairable" if bool(sample.get("recoverable", True)) else "unrecoverable"
        by_raw[raw_scenario][action] += 1
        by_scenario[scenario_type][action] += 1
        by_recoverable[recoverable_key][action] += 1
        overall[action] += 1

    return {
        "model_type": "structured_policy_memory",
        "default_action": _counter_top_json(overall),
        "by_raw_scenario_type": {
            key: _counter_top_json(counter) for key, counter in by_raw.items()
        },
        "by_scenario_type": {
            key: _counter_top_json(counter) for key, counter in by_scenario.items()
        },
        "by_recoverable_partition": {
            key: _counter_top_json(counter) for key, counter in by_recoverable.items()
        },
        "sample_count": len(samples),
    }


def predict_structured_policy(
    sample: dict[str, Any],
    policy_model: dict[str, Any],
) -> dict[str, Any]:
    """Predict a structured decision from the saved lightweight policy model."""

    raw_scenario = str(sample.get("raw_scenario_type") or "unknown")
    scenario_type = str(sample.get("scenario_type") or "unknown")
    recoverable_key = "repairable" if bool(sample.get("recoverable", True)) else "unrecoverable"
    for bucket_name, key in (
        ("by_raw_scenario_type", raw_scenario),
        ("by_scenario_type", scenario_type),
        ("by_recoverable_partition", recoverable_key),
    ):
        bucket = policy_model.get(bucket_name) or {}
        if isinstance(bucket, dict) and isinstance(bucket.get(key), dict):
            return dict(bucket[key])
    default_action = policy_model.get("default_action")
    if isinstance(default_action, dict):
        return dict(default_action)
    return {
        "action": "no_repair",
        "selected_endpoint": None,
        "method_rewrite": False,
        "payload_rewrite": False,
        "auth_rewrite": False,
        "safe_abstain": False,
    }


def _counter_top_json(counter: Counter[str]) -> dict[str, Any]:
    if not counter:
        return {
            "action": "no_repair",
            "selected_endpoint": None,
            "method_rewrite": False,
            "payload_rewrite": False,
            "auth_rewrite": False,
            "safe_abstain": False,
        }
    return json.loads(counter.most_common(1)[0][0])


def _target_action(sample: dict[str, Any]) -> dict[str, Any]:
    if isinstance(sample.get("target_action"), dict):
        return dict(sample["target_action"])
    target_json = sample.get("target_json")
    if isinstance(target_json, str):
        return json.loads(target_json)
    raise ValueError("Sample is missing target_action/target_json.")
