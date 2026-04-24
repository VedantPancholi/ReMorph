"""Train and evaluate a supervised warm-start policy on the frozen Sprint 4 protocol."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sprint4.training.supervised_warmstart import (
    load_json,
    load_jsonl_rows,
    run_supervised_warmstart_pipeline,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a Sprint 4 supervised warm-start policy.")
    parser.add_argument(
        "--supervised-rows-path",
        default="artifacts/sprint4/eval/pretraining_scoreboard/data/supervised_rows.jsonl",
        help="Canonical supervised rows JSONL.",
    )
    parser.add_argument(
        "--supervised-train-manifest-path",
        default="artifacts/sprint4/eval/pretraining_scoreboard/manifests/supervised_train_manifest.json",
        help="Frozen supervised train manifest JSON.",
    )
    parser.add_argument(
        "--shared-eval-manifest-path",
        default="artifacts/sprint4/eval/pretraining_scoreboard/manifests/shared_eval_manifest.json",
        help="Frozen shared eval manifest JSON.",
    )
    parser.add_argument(
        "--transition-rows-path",
        default="artifacts/sprint4/eval/pretraining_scoreboard/data/adaptive_transition_rows.jsonl",
        help="Canonical transition rows JSONL used for offline replay evaluation.",
    )
    parser.add_argument(
        "--baseline-summary-path",
        default="artifacts/sprint4/eval/pretraining_scoreboard/baseline_real/summary.json",
        help="Optional baseline summary for comparison output.",
    )
    parser.add_argument(
        "--adaptive-summary-path",
        default="artifacts/sprint4/eval/pretraining_scoreboard/adaptive_real/summary.json",
        help="Optional adaptive summary for comparison output.",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/sprint4/training/supervised_warmstart",
        help="Directory to store warm-start artifacts.",
    )
    parser.add_argument("--policy-name", default="warmstart")
    parser.add_argument("--model-name", default="prototype_knn_v1")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    result = run_supervised_warmstart_pipeline(
        supervised_rows=load_jsonl_rows(args.supervised_rows_path),
        supervised_train_manifest=load_json(args.supervised_train_manifest_path),
        shared_eval_manifest=load_json(args.shared_eval_manifest_path),
        transition_rows=load_jsonl_rows(args.transition_rows_path),
        output_dir=args.output_dir,
        policy_name=args.policy_name,
        model_name=args.model_name,
        seed=args.seed,
        baseline_summary=load_json(args.baseline_summary_path),
        adaptive_summary=load_json(args.adaptive_summary_path),
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
