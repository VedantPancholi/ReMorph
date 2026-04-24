"""Run targeted reward-guided refinement for the Sprint 4 warm-start policy."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sprint4.training.targeted_refinement import run_targeted_refinement_from_paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Run targeted refinement on the Sprint 4 warm-start policy.")
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
        "--error-analysis-path",
        default="artifacts/sprint4/training/supervised_warmstart/error_analysis/warmstart_error_analysis.json",
        help="Warm-start error analysis JSON artifact.",
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
        "--warmstart-eval-path",
        default="artifacts/sprint4/training/supervised_warmstart/eval_on_shared_manifest.json",
        help="Warm-start eval JSON so the refinement comparison can include the current learned checkpoint.",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/sprint4/training/supervised_warmstart_refined",
        help="Directory to store refinement artifacts.",
    )
    parser.add_argument("--policy-name", default="warmstart_refined")
    parser.add_argument("--model-name", default="prototype_knn_refined_v1")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--top-k", type=int, default=0, help="Override candidate voting width. Zero uses the plan recommendation.")
    parser.add_argument(
        "--balance-by-scenario",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Balance training examples by raw scenario type before refinement weighting.",
    )
    args = parser.parse_args()

    result = run_targeted_refinement_from_paths(
        supervised_rows_path=args.supervised_rows_path,
        supervised_train_manifest_path=args.supervised_train_manifest_path,
        shared_eval_manifest_path=args.shared_eval_manifest_path,
        transition_rows_path=args.transition_rows_path,
        error_analysis_path=args.error_analysis_path,
        output_dir=args.output_dir,
        policy_name=args.policy_name,
        model_name=args.model_name,
        seed=args.seed,
        balance_by_scenario=args.balance_by_scenario,
        top_k=(args.top_k if args.top_k > 0 else None),
        baseline_summary_path=args.baseline_summary_path,
        adaptive_summary_path=args.adaptive_summary_path,
        warmstart_eval_path=args.warmstart_eval_path,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
