"""Optional Unsloth-oriented GRPO demo entrypoint."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sprint4.training.episode_dataset import load_episode_jsonl, to_grpo_samples


def run_unsloth_training(*, episodes_path: str, output_dir: str) -> dict[str, object]:
    """Run a lightweight Unsloth preparation flow for low-VRAM environments."""
    try:
        import unsloth  # type: ignore  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "Unsloth is not installed. Install optional dependencies before running training."
        ) from exc

    episodes = load_episode_jsonl(episodes_path)
    samples = to_grpo_samples(episodes)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    summary = {
        "trainer": "unsloth_grpo",
        "sample_count": len(samples),
        "avg_reward": round(
            sum(float(item["reward"]) for item in samples) / max(1, len(samples)),
            4,
        ),
        "note": "Placeholder flow: integrate with your Unsloth GRPO notebook/trainer.",
    }
    (output / "unsloth_training_summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    return summary


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
    args = parser.parse_args()
    summary = run_unsloth_training(
        episodes_path=args.episodes_path,
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

