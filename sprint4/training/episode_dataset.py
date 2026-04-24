"""Dataset builders from Sprint 4 benchmark episodes."""

from __future__ import annotations

import json
import random
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.services.doc_fetcher import load_local_spec
from sprint4.training.benchmark_contract import (
    BENCHMARK_CONTRACT_VERSION,
    BenchmarkPartition,
    classify_raw_scenario,
    raw_scenarios_for_partition,
)
from sprint4.training.dataset_schema import (
    PolicyAction,
    SupervisedRow,
    TransitionOutcome,
    TransitionRow,
)
from sprint4.training.policy_adapter import (
    build_policy_example,
    episode_to_policy_action,
    episode_to_policy_state,
)
from sprint4.training.reward_model import (
    is_abstain_action,
    is_auth_repair_action,
    is_payload_repair_action,
    is_route_repair_action,
    score_transition,
)


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


def build_supervised_row_from_episode(
    episode: dict[str, Any],
) -> tuple[SupervisedRow | None, str | None]:
    """Build one typed supervised row from a benchmark episode."""

    try:
        state, action = build_policy_example(episode)
    except Exception:
        return None, "invalid_policy_state_or_action"

    if state.benchmark_partition == "other":
        return None, "unknown_partition"
    if action.action_type == "no_op" and not bool(episode.get("success", False)):
        return None, "missing_action_trace"

    return (
        SupervisedRow(
            episode_id=state.episode_id,
            input_text=_build_supervised_prompt(episode, state),
            target_action=action,
            raw_scenario_type=state.raw_scenario_type,
            benchmark_partition=state.benchmark_partition,
            contract_version=BENCHMARK_CONTRACT_VERSION,
        ),
        None,
    )


def build_transition_row_from_episode(
    episode: dict[str, Any],
) -> tuple[TransitionRow | None, str | None]:
    """Build one typed transition row from a benchmark episode."""

    try:
        state = episode_to_policy_state(episode)
        action = episode_to_policy_action(episode)
    except Exception:
        return None, "invalid_policy_state_or_action"

    if state.benchmark_partition == "other":
        return None, "unknown_partition"

    outcome, reason = _build_transition_outcome(episode, state, action)
    if outcome is None:
        return None, reason or "missing_outcome_data"

    reward = score_transition(state, action, outcome)
    success = bool(outcome.request_succeeded or outcome.correct_abstention)
    outcome_class = _classify_outcome(state, action, outcome)

    return (
        TransitionRow(
            episode_id=state.episode_id,
            state=state,
            action=action,
            outcome=outcome,
            next_state=None,
            reward_breakdown=reward,
            done=True,
            success=success,
            outcome_class=outcome_class,
            raw_scenario_type=state.raw_scenario_type,
            benchmark_partition=state.benchmark_partition,
            contract_version=BENCHMARK_CONTRACT_VERSION,
        ),
        None,
    )


def build_supervised_dataset(
    episodes: list[dict[str, Any]],
    *,
    benchmark_partition: BenchmarkPartition = "repairable",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build typed supervised rows plus an export summary."""

    return _build_dataset(
        episodes,
        builder=build_supervised_row_from_episode,
        benchmark_partition=benchmark_partition,
    )


def build_transition_dataset(
    episodes: list[dict[str, Any]],
    *,
    benchmark_partition: BenchmarkPartition = "all",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build typed transition rows plus an export summary."""

    return _build_dataset(
        episodes,
        builder=build_transition_row_from_episode,
        benchmark_partition=benchmark_partition,
    )


def to_grpo_samples(
    episodes: list[dict[str, Any]],
    *,
    agent_type: str | None = "adaptive",
    include_failed: bool = False,
    benchmark_partition: BenchmarkPartition = "repairable",
) -> list[dict[str, Any]]:
    """Convert episodes into structured prompt/completion samples."""

    rows: list[dict[str, Any]] = []
    for item in episodes:
        if agent_type and item.get("agent_type") != agent_type:
            continue
        raw_scenario_type = str(item.get("raw_scenario_type") or "unknown")
        if raw_scenario_type not in set(raw_scenarios_for_partition(benchmark_partition)):
            continue
        row, reason = build_supervised_row_from_episode(item)
        if row is None:
            if include_failed:
                rows.append(
                    {
                        "episode_id": str(item.get("request_id") or f"skipped:{raw_scenario_type}"),
                        "skip_reason": reason,
                        "raw_scenario_type": raw_scenario_type,
                    }
                )
            continue
        if not include_failed and not bool(item.get("success", False)) and row.target_action.action_type != "abstain":
            continue

        state = episode_to_policy_state(item)
        action = row.target_action.model_dump(mode="json")
        rows.append(
            {
                "episode_id": row.episode_id,
                "prompt": row.input_text,
                "completion": json.dumps(action, sort_keys=True, ensure_ascii=True),
                "reward": float(item.get("reward", 0.0)),
                "success": bool(item.get("success", False)),
                "scenario_type": item.get("scenario_type", "unknown"),
                "raw_scenario_type": raw_scenario_type,
                "state": state.model_dump(mode="json"),
                "action": action,
                "metadata": {
                    "request_id": item.get("request_id"),
                    "scenario_type": item.get("scenario_type"),
                    "raw_scenario_type": raw_scenario_type,
                    "benchmark_partition": row.benchmark_partition,
                    "contract_version": row.contract_version,
                    "reward": float(item.get("reward", 0.0)),
                    "success": bool(item.get("success", False)),
                    "agent_type": item.get("agent_type"),
                    "repair_strategy": item.get("repair_strategy"),
                    "cache_hit": bool(item.get("cache_hit", False)),
                    "llm_attempted": bool(item.get("llm_attempted", False)),
                    "llm_succeeded": bool(item.get("llm_succeeded", False)),
                    "local_spec_path": item.get("local_spec_path"),
                },
            }
        )
    return rows


def format_training_episode(item: dict[str, Any]) -> dict[str, Any]:
    """Project one benchmark episode into a legacy training-facing state/action record."""

    state = episode_to_policy_state(item)
    action = episode_to_policy_action(item)
    return {
        "state": {
            "failed_request": item.get("original_request") or {},
            "error_code": state.failure_code,
            "error_message": state.failure_message,
            "retry_count": state.retry_count,
            "selected_endpoint_path": item.get("selected_endpoint_path"),
            "route_match_confidence": item.get("route_match_confidence"),
            "available_contract": _extract_contract_slice(
                local_spec_path=item.get("local_spec_path"),
                endpoint_path=item.get("selected_endpoint_path"),
                method=item.get("healed_method")
                or (item.get("original_request") or {}).get("method")
                or (item.get("trapped_error") or {}).get("method"),
            ),
        },
        "action": {
            "repair_type": item.get("healing_action") or _infer_repair_type(item),
            "selected_endpoint": item.get("selected_endpoint_path"),
            "fixed_method": item.get("healed_method"),
            "fixed_url": item.get("healed_url"),
            "fixed_headers": item.get("healed_headers"),
            "fixed_payload": item.get("healed_payload"),
            "reasoning": action.reason,
        },
        "reward": float(item.get("reward", 0.0)),
        "success": bool(item.get("success", False)),
        "metadata": {
            "request_id": item.get("request_id"),
            "scenario_type": item.get("scenario_type"),
            "raw_scenario_type": item.get("raw_scenario_type"),
            "benchmark_partition": state.benchmark_partition,
            "contract_version": BENCHMARK_CONTRACT_VERSION,
            "reward": float(item.get("reward", 0.0)),
            "success": bool(item.get("success", False)),
        },
    }


def split_samples(
    samples: list[dict[str, Any]],
    *,
    eval_ratio: float = 0.2,
    seed: int = 42,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Deterministically split rows into train and eval partitions."""

    if not samples:
        return [], []
    shuffled = list(samples)
    random.Random(seed).shuffle(shuffled)
    eval_count = min(len(shuffled) - 1, max(1, int(round(len(shuffled) * eval_ratio))))
    if len(shuffled) == 1:
        eval_count = 0
    train_count = max(1, len(shuffled) - eval_count)
    return shuffled[:train_count], shuffled[train_count:]


def write_jsonl_rows(path: str, rows: list[dict[str, Any]]) -> str:
    """Persist row-oriented data as JSONL."""

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
    benchmark_partition: BenchmarkPartition = "repairable",
    eval_ratio: float = 0.2,
    seed: int = 42,
) -> dict[str, Any]:
    """Build warm-start plus transition artifacts from benchmark episodes."""

    episodes = load_episode_jsonl(episodes_path, agent_type=agent_type)
    filtered = _filter_episodes_by_partition(episodes, benchmark_partition=benchmark_partition)
    supervised_rows, supervised_summary = build_supervised_dataset(
        filtered,
        benchmark_partition=benchmark_partition,
    )
    transition_rows, transition_summary = build_transition_dataset(
        filtered,
        benchmark_partition="all" if benchmark_partition == "all" else benchmark_partition,
    )

    if not include_failed:
        supervised_rows = [
            row
            for row in supervised_rows
            if row["target_action"]["action_type"] == "abstain"
            or _episode_success_for_row(filtered, row["episode_id"])
        ]
        transition_rows = [
            row
            for row in transition_rows
            if row["success"]
        ]

    train_rows, eval_rows = split_samples(supervised_rows, eval_ratio=eval_ratio, seed=seed)

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    train_path = write_jsonl_rows(str(output / "train.jsonl"), train_rows)
    eval_path = write_jsonl_rows(str(output / "eval.jsonl"), eval_rows)
    supervised_path = write_jsonl_rows(str(output / "supervised_rows.jsonl"), supervised_rows)
    transition_path = write_jsonl_rows(str(output / "transition_rows.jsonl"), transition_rows)

    manifest = {
        "episodes_path": episodes_path,
        "agent_type": agent_type,
        "include_failed": include_failed,
        "benchmark_partition": benchmark_partition,
        "allowed_raw_scenarios": list(raw_scenarios_for_partition(benchmark_partition)),
        "contract_version": BENCHMARK_CONTRACT_VERSION,
        "generation_timestamp": datetime.now(UTC).isoformat(),
        "eval_ratio": eval_ratio,
        "seed": seed,
        "sample_count": len(supervised_rows),
        "train_sample_count": len(train_rows),
        "eval_sample_count": len(eval_rows),
        "transition_sample_count": len(transition_rows),
        "train_path": train_path,
        "eval_path": eval_path,
        "supervised_path": supervised_path,
        "transition_path": transition_path,
        "supervised_summary": supervised_summary,
        "transition_summary": transition_summary,
    }
    (output / "dataset_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return manifest


def summarize_samples(samples: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute lightweight summary statistics for exported rows."""

    if not samples:
        return {
            "sample_count": 0,
            "avg_reward": 0.0,
            "success_rate": 0.0,
            "scenario_distribution": {},
            "raw_scenario_distribution": {},
            "partition_distribution": {},
        }

    scenario_distribution: Counter[str] = Counter()
    raw_scenario_distribution: Counter[str] = Counter()
    partition_distribution: Counter[str] = Counter()
    success_count = 0
    total_reward = 0.0
    for sample in samples:
        scenario_distribution[str(sample.get("scenario_type", "unknown"))] += 1
        raw_scenario_distribution[str(sample.get("raw_scenario_type", "unknown"))] += 1
        partition_distribution[str(sample.get("benchmark_partition") or sample.get("metadata", {}).get("benchmark_partition") or "other")] += 1
        success_count += int(bool(sample.get("success", False)))
        reward = sample.get("reward")
        if reward is None and isinstance(sample.get("reward_breakdown"), dict):
            reward = sample["reward_breakdown"].get("reward_total", 0.0)
        total_reward += float(reward or 0.0)
    return {
        "sample_count": len(samples),
        "avg_reward": round(total_reward / len(samples), 4),
        "success_rate": round(success_count / len(samples), 4),
        "scenario_distribution": dict(scenario_distribution),
        "raw_scenario_distribution": dict(raw_scenario_distribution),
        "partition_distribution": dict(partition_distribution),
    }


def _build_dataset(
    episodes: list[dict[str, Any]],
    *,
    builder: Any,
    benchmark_partition: BenchmarkPartition,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    allowed = set(raw_scenarios_for_partition(benchmark_partition))
    rows: list[dict[str, Any]] = []
    skipped: Counter[str] = Counter()
    scenario_counts: Counter[str] = Counter()
    partition_counts: Counter[str] = Counter()
    for episode in episodes:
        raw_scenario_type = str(episode.get("raw_scenario_type") or "unknown")
        if raw_scenario_type not in allowed:
            skipped["filtered_partition"] += 1
            continue
        row, reason = builder(episode)
        if row is None:
            skipped[reason or "unknown"] += 1
            continue
        dumped = row.model_dump(mode="json")
        rows.append(dumped)
        scenario_counts[raw_scenario_type] += 1
        partition_counts[str(dumped.get("benchmark_partition") or "other")] += 1
    summary = {
        "total_input_episodes": len(episodes),
        "exported_row_count": len(rows),
        "skipped_rows_by_reason": dict(skipped),
        "scenario_distribution": dict(scenario_counts),
        "partition_distribution": dict(partition_counts),
        "contract_version": BENCHMARK_CONTRACT_VERSION,
    }
    return rows, summary


def _build_supervised_prompt(episode: dict[str, Any], state: Any) -> str:
    return "\n".join(
        [
            "Repair the failed API request using the contract evidence.",
            f"scenario_type={state.scenario_type}",
            f"raw_scenario_type={state.raw_scenario_type}",
            f"benchmark_partition={state.benchmark_partition}",
            f"error_code={state.failure_code}",
            f"error_message={state.failure_message}",
            f"retry_count={state.retry_count}",
            "failed_request="
            + json.dumps(episode.get("original_request") or {}, sort_keys=True, ensure_ascii=True),
            "contract_hints="
            + json.dumps(state.contract_hints, sort_keys=True, ensure_ascii=True),
        ]
    )


def _build_transition_outcome(
    episode: dict[str, Any],
    state: Any,
    action: PolicyAction,
) -> tuple[TransitionOutcome | None, str | None]:
    final_status = episode.get("final_status_code")
    if final_status is None:
        return None, "missing_final_status_code"

    request_succeeded = bool(episode.get("success", False))
    retries_used = int(episode.get("retries_used", 0))
    route_penalty = float((episode.get("reward_breakdown") or {}).get("wrong_route_penalty", 0.0))
    route_correct = not is_route_repair_action(action) or route_penalty >= 0.0
    payload_valid = request_succeeded if is_payload_repair_action(action) else False
    used_hallucinated_auth = bool(
        state.benchmark_partition == "unrecoverable" and is_auth_repair_action(action)
    )
    abstained = is_abstain_action(action)
    correct_abstention = bool(
        abstained and state.benchmark_partition == "unrecoverable" and not request_succeeded
    )

    return (
        TransitionOutcome(
            request_succeeded=request_succeeded,
            http_status=int(final_status),
            retry_count=retries_used,
            selected_route_correct=route_correct,
            payload_valid=payload_valid,
            used_hallucinated_auth=used_hallucinated_auth,
            abstained=abstained,
            correct_abstention=correct_abstention,
            max_retries_exceeded=bool(retries_used >= 2 and not request_succeeded),
        ),
        None,
    )


def _classify_outcome(
    state: Any,
    action: PolicyAction,
    outcome: TransitionOutcome,
) -> str:
    if outcome.used_hallucinated_auth:
        return "unsafe_hallucination"
    if outcome.correct_abstention:
        return "correct_abstain"
    if is_abstain_action(action) and state.benchmark_partition == "repairable":
        return "incorrect_abstain"
    if outcome.request_succeeded:
        return "repair_success"
    if state.benchmark_partition == "unrecoverable":
        return "unrecoverable_failure"
    return "repair_failure"


def _episode_success_for_row(episodes: list[dict[str, Any]], episode_id: str) -> bool:
    for episode in episodes:
        state = episode_to_policy_state(episode)
        if state.episode_id == episode_id:
            return bool(episode.get("success", False))
    return False


def _filter_episodes_by_partition(
    episodes: list[dict[str, Any]],
    *,
    benchmark_partition: BenchmarkPartition,
) -> list[dict[str, Any]]:
    allowed = set(raw_scenarios_for_partition(benchmark_partition))
    return [
        episode
        for episode in episodes
        if str(episode.get("raw_scenario_type") or "unknown") in allowed
    ]


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
    except Exception:
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
