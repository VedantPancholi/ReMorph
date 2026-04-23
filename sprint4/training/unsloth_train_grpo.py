"""Optional Unsloth-oriented GRPO demo entrypoint."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sprint4.training.episode_dataset import (
    generate_training_dataset,
    summarize_samples,
)


def run_unsloth_training(
    *,
    episodes_path: str,
    output_dir: str,
    eval_ratio: float = 0.2,
    seed: int = 42,
) -> dict[str, object]:
    """Run a lightweight Unsloth preparation flow for low-VRAM environments."""
    try:
        import unsloth  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "Unsloth is not installed. Install optional dependencies before running training."
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
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    summary = {
        "trainer": "unsloth_grpo",
        "unsloth_version": getattr(unsloth, "__version__", "unknown"),
        "sample_count": dataset_manifest["sample_count"],
        "train_sample_count": dataset_manifest["train_sample_count"],
        "eval_sample_count": dataset_manifest["eval_sample_count"],
        "avg_reward": round(
            sum(float(item["reward"]) for item in train_rows) / max(1, len(train_rows)),
            4,
        ),
        "dataset_artifacts": dataset_manifest,
        "eval_summary": summarize_samples(eval_rows),
        "note": "Prepared Unsloth-ready prompt/completion datasets and offline eval summary.",
    }
    (output / "unsloth_training_summary.json").write_text(
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
    parser = argparse.ArgumentParser(description="Run lightweight Unsloth GRPO demo flow.")
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
    summary = run_unsloth_training(
        episodes_path=args.episodes_path,
        output_dir=args.output_dir,
        eval_ratio=args.eval_ratio,
        seed=args.seed,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
