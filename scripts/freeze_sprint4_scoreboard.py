"""Freeze the first repo-native Sprint 4 pre-training scoreboard."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sprint4.eval.scoreboard_protocol import freeze_repo_native_scoreboard


def main() -> None:
    parser = argparse.ArgumentParser(description="Freeze the Sprint 4 repo-native pre-training scoreboard.")
    parser.add_argument(
        "--episodes-path",
        required=True,
        help="Benchmark episodes JSONL containing both baseline and adaptive rows.",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/sprint4/eval/pretraining_scoreboard",
        help="Directory to persist manifests, eval artifacts, and analysis outputs.",
    )
    parser.add_argument(
        "--benchmark-partition",
        choices=["repairable", "unrecoverable", "all"],
        default="all",
        help="Frozen benchmark slice used to derive transition rows and shared eval manifests.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Deterministic split seed for the shared eval manifest.",
    )
    parser.add_argument(
        "--eval-ratio",
        type=float,
        default=0.2,
        help="Eval ratio for the shared eval manifest.",
    )
    args = parser.parse_args()

    result = freeze_repo_native_scoreboard(
        episodes_path=args.episodes_path,
        output_dir=args.output_dir,
        benchmark_partition=args.benchmark_partition,
        split_seed=args.seed,
        eval_ratio=args.eval_ratio,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
