"""Generate train/eval datasets from Sprint 4 benchmark episodes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sprint4.training.episode_dataset import generate_training_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Sprint 4 training dataset.")
    parser.add_argument(
        "--episodes-path",
        default="runtime/sprint4/episodes.jsonl",
        help="Input episode JSONL file.",
    )
    parser.add_argument(
        "--output-dir",
        default="runtime/sprint4/dataset",
        help="Directory for generated train/eval datasets.",
    )
    parser.add_argument("--agent-type", default="adaptive")
    parser.add_argument("--include-failed", action="store_true")
    parser.add_argument("--eval-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    manifest = generate_training_dataset(
        episodes_path=args.episodes_path,
        output_dir=args.output_dir,
        agent_type=args.agent_type,
        include_failed=args.include_failed,
        eval_ratio=args.eval_ratio,
        seed=args.seed,
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
