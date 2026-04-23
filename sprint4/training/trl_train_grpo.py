"""Minimal TRL GRPO training entrypoint for hackathon demos."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sprint4.training.episode_dataset import (
    generate_training_dataset,
    summarize_samples,
)
from sprint4.training.policy_adapter import build_policy_batch


def run_trl_training(
    *,
    episodes_path: str,
    output_dir: str,
    eval_ratio: float = 0.2,
    seed: int = 42,
) -> dict[str, object]:
    """Prepare TRL-ready train/eval artifacts and save lightweight summaries."""
    try:
        import trl  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "TRL is not installed. Install optional dependencies before running training."
        ) from exc

    dataset_manifest = generate_training_dataset(
        episodes_path=episodes_path,
        output_dir=output_dir,
        agent_type="adaptive",
        include_failed=False,
        eval_ratio=eval_ratio,
        seed=seed,
    )
    train_rows = _load_dataset_rows(dataset_manifest["train_path"])
    eval_rows = _load_dataset_rows(dataset_manifest["eval_path"])
    batch = build_policy_batch(train_rows)
    eval_summary = summarize_samples(eval_rows)

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    summary = {
        "trainer": "trl_grpo",
        "trl_version": getattr(trl, "__version__", "unknown"),
        "sample_count": dataset_manifest["sample_count"],
        "train_sample_count": dataset_manifest["train_sample_count"],
        "eval_sample_count": dataset_manifest["eval_sample_count"],
        "avg_reward": round(sum(batch.rewards) / max(1, len(batch.rewards)), 4),
        "dataset_artifacts": dataset_manifest,
        "eval_summary": eval_summary,
        "note": "Prepared TRL-ready prompt/completion datasets and offline eval summary.",
    }
    (output / "trl_training_summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    return summary


def _load_dataset_rows(path: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    file_path = Path(path)
    if not file_path.exists():
        return rows
    with file_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


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
    parser.add_argument("--eval-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    summary = run_trl_training(
        episodes_path=args.episodes_path,
        output_dir=args.output_dir,
        eval_ratio=args.eval_ratio,
        seed=args.seed,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
