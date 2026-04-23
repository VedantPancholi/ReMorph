"""Dataset builders from Sprint 4 JSONL episodes."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from app.services.doc_fetcher import load_local_spec


def load_episode_jsonl(
    path: str,
    *,
    agent_type: str | None = None,
) -> list[dict[str, Any]]:
    """Load JSONL episodes into memory, optionally filtering by agent type."""
    episodes: list[dict[str, Any]] = []
    file_path = Path(path)
    if not file_path.exists():
        return episodes
    with file_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            item = json.loads(line)
            if agent_type and item.get("agent_type") != agent_type:
                continue
            episodes.append(item)
    return episodes


def to_grpo_samples(
    episodes: list[dict[str, Any]],
    *,
    agent_type: str | None = "adaptive",
    include_failed: bool = False,
) -> list[dict[str, Any]]:
    """Convert episodes into structured policy-learning samples."""
    rows: list[dict[str, Any]] = []
    for item in episodes:
        if agent_type and item.get("agent_type") != agent_type:
            continue
        if not include_failed and not bool(item.get("success", False)):
            continue
        training_episode = format_training_episode(item)
        rows.append(
            {
                "prompt": _build_prompt(training_episode),
                "completion": json.dumps(
                    training_episode["action"],
                    sort_keys=True,
                    ensure_ascii=True,
                ),
                "reward": float(item.get("reward", 0.0)),
                "success": bool(item.get("success", False)),
                "scenario_type": item.get("scenario_type", "unknown"),
                "state": training_episode["state"],
                "action": training_episode["action"],
                "metadata": training_episode["metadata"],
            }
        )
    return rows


def format_training_episode(item: dict[str, Any]) -> dict[str, Any]:
    """Project one benchmark episode into a training-facing state/action record."""
    trapped_error = item.get("trapped_error") or {}
    original_request = item.get("original_request") or {}
    method = (
        item.get("healed_method")
        or original_request.get("method")
        or trapped_error.get("method")
        or "GET"
    )
    selected_endpoint = item.get("selected_endpoint_path")
    local_spec_path = item.get("local_spec_path")
    state = {
        "failed_request": original_request,
        "error_code": item.get("error_code") or trapped_error.get("error_code"),
        "error_message": item.get("error_message") or trapped_error.get("error_message"),
        "retry_count": (trapped_error or {}).get("retry_count", 0),
        "selected_endpoint_path": selected_endpoint,
        "route_match_confidence": item.get("route_match_confidence"),
        "available_contract": _extract_contract_slice(
            local_spec_path=local_spec_path,
            endpoint_path=selected_endpoint,
            method=method,
        ),
    }
    action = {
        "repair_type": item.get("healing_action") or _infer_repair_type(item),
        "selected_endpoint": selected_endpoint,
        "fixed_method": item.get("healed_method"),
        "fixed_url": item.get("healed_url"),
        "fixed_headers": item.get("healed_headers"),
        "fixed_payload": item.get("healed_payload"),
        "reasoning": item.get("reasoning"),
    }
    metadata = {
        "request_id": item.get("request_id"),
        "scenario_type": item.get("scenario_type"),
        "reward": float(item.get("reward", 0.0)),
        "success": bool(item.get("success", False)),
        "agent_type": item.get("agent_type"),
        "repair_strategy": item.get("repair_strategy"),
        "cache_hit": bool(item.get("cache_hit", False)),
        "llm_attempted": bool(item.get("llm_attempted", False)),
        "llm_succeeded": bool(item.get("llm_succeeded", False)),
        "local_spec_path": local_spec_path,
    }
    return {
        "state": state,
        "action": action,
        "reward": metadata["reward"],
        "success": metadata["success"],
        "metadata": metadata,
    }


def split_samples(
    samples: list[dict[str, Any]],
    *,
    eval_ratio: float = 0.2,
    seed: int = 42,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Deterministically split samples into train and eval partitions."""
    if not samples:
        return [], []
    shuffled = list(samples)
    random.Random(seed).shuffle(shuffled)
    eval_count = min(len(shuffled) - 1, max(1, int(round(len(shuffled) * eval_ratio))))
    if len(shuffled) == 1:
        eval_count = 0
    train_count = max(1, len(shuffled) - eval_count)
    train = shuffled[:train_count]
    eval_rows = shuffled[train_count:]
    return train, eval_rows


def write_jsonl_rows(path: str, rows: list[dict[str, Any]]) -> str:
    """Persist row-oriented training or evaluation data as JSONL."""
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=True))
            handle.write("\n")
    return str(file_path)


def generate_training_dataset(
    *,
    episodes_path: str,
    output_dir: str,
    agent_type: str = "adaptive",
    include_failed: bool = False,
    eval_ratio: float = 0.2,
    seed: int = 42,
) -> dict[str, Any]:
    """Build train/eval JSONL files from benchmark episodes and return a manifest."""
    episodes = load_episode_jsonl(episodes_path, agent_type=agent_type)
    samples = to_grpo_samples(
        episodes,
        agent_type=None,
        include_failed=include_failed,
    )
    train_rows, eval_rows = split_samples(samples, eval_ratio=eval_ratio, seed=seed)

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    train_path = write_jsonl_rows(str(output / "train.jsonl"), train_rows)
    eval_path = write_jsonl_rows(str(output / "eval.jsonl"), eval_rows)
    manifest = {
        "episodes_path": episodes_path,
        "agent_type": agent_type,
        "include_failed": include_failed,
        "eval_ratio": eval_ratio,
        "seed": seed,
        "sample_count": len(samples),
        "train_sample_count": len(train_rows),
        "eval_sample_count": len(eval_rows),
        "train_path": train_path,
        "eval_path": eval_path,
    }
    (output / "dataset_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return manifest


def summarize_samples(samples: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute lightweight training/eval summary statistics."""
    if not samples:
        return {
            "sample_count": 0,
            "avg_reward": 0.0,
            "success_rate": 0.0,
            "scenario_distribution": {},
        }

    scenario_distribution: dict[str, int] = {}
    success_count = 0
    total_reward = 0.0
    for sample in samples:
        scenario = str(sample.get("scenario_type", "unknown"))
        scenario_distribution[scenario] = scenario_distribution.get(scenario, 0) + 1
        success_count += int(bool(sample.get("success", False)))
        total_reward += float(sample.get("reward", 0.0))
    return {
        "sample_count": len(samples),
        "avg_reward": round(total_reward / len(samples), 4),
        "success_rate": round(success_count / len(samples), 4),
        "scenario_distribution": scenario_distribution,
    }


def _build_prompt(training_episode: dict[str, Any]) -> str:
    state = training_episode["state"]
    metadata = training_episode["metadata"]
    return "\n".join(
        [
            "Repair the failed API request using the contract evidence.",
            f"scenario_type={metadata['scenario_type']}",
            f"error_code={state['error_code']}",
            f"error_message={state['error_message']}",
            f"retry_count={state['retry_count']}",
            "failed_request="
            + json.dumps(state["failed_request"], sort_keys=True, ensure_ascii=True),
            "available_contract="
            + json.dumps(state["available_contract"], sort_keys=True, ensure_ascii=True),
        ]
    )


def _extract_contract_slice(
    *,
    local_spec_path: str | None,
    endpoint_path: str | None,
    method: str | None,
) -> dict[str, Any] | None:
    if not local_spec_path or not endpoint_path or not method:
        return None
    try:
        spec = load_local_spec(local_spec_path)
    except Exception:  # noqa: BLE001 - dataset generation should tolerate old records
        return None

    operation = (
        spec.get("paths", {})
        .get(endpoint_path, {})
        .get(str(method).lower())
    )
    if not isinstance(operation, dict):
        return None
    return {
        "path": endpoint_path,
        "method": str(method).upper(),
        "operation": operation,
    }


def _infer_repair_type(item: dict[str, Any]) -> str:
    scenario_type = str(item.get("scenario_type", ""))
    if "payload" in scenario_type:
        return "payload_rewrite"
    if "route" in scenario_type:
        return "route_rewrite"
    if "auth" in scenario_type:
        return "auth_rewrite"
    return "no_change"
