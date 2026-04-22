"""Minimal TRL GRPO training entrypoint for hackathon demos."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sprint4.training.episode_dataset import load_episode_jsonl, to_grpo_samples
from sprint4.training.policy_adapter import build_policy_batch


def run_trl_training(*, episodes_path: str, output_dir: str) -> dict[str, object]:
    """Run a tiny placeholder training flow and save metadata artifacts."""
    try:
        import trl  # type: ignore  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "TRL is not installed. Install optional dependencies before running training."
        ) from exc

    episodes = load_episode_jsonl(episodes_path)
    samples = to_grpo_samples(episodes)
    batch = build_policy_batch(samples)

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    summary = {
        "trainer": "trl_grpo",
        "sample_count": len(samples),
        "avg_reward": round(sum(batch.rewards) / max(1, len(batch.rewards)), 4),
        "note": "Placeholder flow: wire into your preferred GRPO trainer config.",
    }
    (output / "trl_training_summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run lightweight TRL GRPO demo flow.")
    parser.add_argument(
        "--episodes-path",
        default="runtime/sprint4/episodes.jsonl",
        help="Input Sprint 4 episode JSONL file.",
    )
    parser.add_argument(
        "--output-dir",
        default="runtime/sprint4/training",
        help="Directory to store training artifacts.",
    )
    args = parser.parse_args()
    summary = run_trl_training(episodes_path=args.episodes_path, output_dir=args.output_dir)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

