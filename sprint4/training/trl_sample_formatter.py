"""Convert benchmark episodes into compact TRL-ready prompt/target rows."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sprint4.training.episode_dataset import load_episode_jsonl, split_samples, write_jsonl_rows
from sprint4.training.policy_adapter import episode_to_policy_state, episode_to_rl_transition


def format_trl_dataset(
    *,
    episodes_path: str,
    output_dir: str,
    eval_ratio: float = 0.2,
    seed: int = 42,
    agent_type: str | None = "adaptive",
) -> dict[str, Any]:
    """Export train/eval prompt datasets for TRL-style policy learning."""

    episodes = load_episode_jsonl(episodes_path, agent_type=agent_type)
    if not episodes:
        raise ValueError(
            f"No episodes were found at {episodes_path}. Generate episodes before formatting the TRL dataset."
        )
    samples = [episode_to_trl_sample(episode) for episode in episodes]
    if not samples:
        raise ValueError(
            f"No TRL samples could be derived from {episodes_path}. Check the episode generator output and agent filter."
        )
    train_rows, eval_rows = split_samples(samples, eval_ratio=eval_ratio, seed=seed)

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    train_path = write_jsonl_rows(str(output / "train_prompts.jsonl"), train_rows)
    eval_path = write_jsonl_rows(str(output / "eval_prompts.jsonl"), eval_rows)
    summary = _summarize_trl_rows(
        samples=samples,
        episodes_path=episodes_path,
        train_path=train_path,
        eval_path=eval_path,
        eval_ratio=eval_ratio,
        seed=seed,
        agent_type=agent_type,
    )
    (output / "trl_dataset_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return summary


def episode_to_trl_sample(episode: dict[str, Any]) -> dict[str, Any]:
    """Project one benchmark episode into a TRL-ready prompt and target JSON."""

    state = episode_to_policy_state(episode)
    transition = episode_to_rl_transition(episode)
    target_action = episode_to_target_decision(episode)
    return {
        "prompt": _build_prompt(episode, state),
        "target_json": json.dumps(target_action, sort_keys=True, ensure_ascii=True),
        "target_action": target_action,
        "reward": float(transition.get("reward", 0.0)),
        "scenario_type": state.scenario_type,
        "raw_scenario_type": state.raw_scenario_type,
        "recoverable": episode.get("recoverable") is not False,
        "metadata": {
            "request_id": state.episode_id,
            "agent_type": episode.get("agent_type"),
            "retry_count": state.retry_count,
            "final_status_code": episode.get("final_status_code"),
        },
    }


def episode_to_target_decision(episode: dict[str, Any]) -> dict[str, Any]:
    """Build the canonical structured repair decision target for one episode."""

    transition = episode_to_rl_transition(episode)
    action = dict(transition.get("action") or {})
    decision = {
        "action": str(episode.get("healing_action") or action.get("repair_type") or "no_repair"),
        "selected_endpoint": episode.get("selected_endpoint_path"),
        "method_rewrite": bool(action.get("method_rewrite", False)),
        "payload_rewrite": bool(action.get("payload_rewrite", False)),
        "auth_rewrite": bool(action.get("auth_rewrite", False)),
        "safe_abstain": bool(action.get("safe_abstain", False)),
    }
    if decision["safe_abstain"]:
        decision["unrecoverable_reason"] = str(
            episode.get("unrecoverable_reason") or "missing_or_invalid_credential_material"
        )
    return decision


def _build_prompt(episode: dict[str, Any], state: Any) -> str:
    failed_request = {
        "method": state.request_method,
        "path": state.request_path,
        "headers": state.request_headers,
        "query": state.request_query,
        "body": state.request_body,
    }
    contract_summary = {
        "request_path": state.request_path,
        "candidate_methods": sorted(
            {
                candidate.method
                for candidate in state.candidate_routes
                if candidate.method
            }
        ),
        "contract_hints": state.contract_hints,
    }
    candidate_endpoints = [
        {
            "path": candidate.path,
            "method": candidate.method,
            "confidence": candidate.confidence,
        }
        for candidate in state.candidate_routes[:3]
    ]
    instructions = (
        "Return strict JSON only with keys: action, selected_endpoint, "
        "method_rewrite, payload_rewrite, auth_rewrite, safe_abstain, "
        "and unrecoverable_reason when safe_abstain is true."
    )
    return "\n".join(
        [
            "Choose the safest repair decision for this failed API request.",
            instructions,
            f"scenario_type={state.scenario_type}",
            f"raw_scenario_type={state.raw_scenario_type}",
            f"recoverable={str(episode.get('recoverable') is not False).lower()}",
            f"error_code={state.failure_code}",
            f"error_message={state.failure_message}",
            "failed_request="
            + json.dumps(failed_request, sort_keys=True, ensure_ascii=True, separators=(",", ":")),
            "contract_summary="
            + json.dumps(contract_summary, sort_keys=True, ensure_ascii=True, separators=(",", ":")),
            "candidate_endpoints="
            + json.dumps(candidate_endpoints, sort_keys=True, ensure_ascii=True, separators=(",", ":")),
        ]
    )


def _summarize_trl_rows(
    *,
    samples: list[dict[str, Any]],
    episodes_path: str,
    train_path: str,
    eval_path: str,
    eval_ratio: float,
    seed: int,
    agent_type: str | None,
) -> dict[str, Any]:
    scenario_distribution = Counter(sample["scenario_type"] for sample in samples)
    raw_scenario_distribution = Counter(sample["raw_scenario_type"] for sample in samples)
    return {
        "episodes_path": episodes_path,
        "agent_type": agent_type,
        "generation_timestamp": datetime.now(UTC).isoformat(),
        "eval_ratio": eval_ratio,
        "seed": seed,
        "sample_count": len(samples),
        "train_count": len(load_jsonl(train_path)),
        "eval_count": len(load_jsonl(eval_path)),
        "repairable_count": sum(1 for sample in samples if bool(sample.get("recoverable", True))),
        "unrecoverable_count": sum(1 for sample in samples if sample.get("recoverable") is False),
        "avg_reward": round(
            sum(float(sample.get("reward", 0.0)) for sample in samples) / max(1, len(samples)),
            4,
        ),
        "scenario_distribution": dict(scenario_distribution),
        "raw_scenario_distribution": dict(raw_scenario_distribution),
        "train_path": train_path,
        "eval_path": eval_path,
    }


def load_jsonl(path: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    file_path = Path(path)
    if not file_path.exists():
        return rows
    with file_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Format Sprint 4 episodes into TRL prompt datasets.")
    parser.add_argument("--episodes-path", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--eval-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--agent-type", default="adaptive")
    args = parser.parse_args()

    summary = format_trl_dataset(
        episodes_path=args.episodes_path,
        output_dir=args.output_dir,
        eval_ratio=args.eval_ratio,
        seed=args.seed,
        agent_type=args.agent_type or None,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
