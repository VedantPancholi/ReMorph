"""Analyze warm-start vs adaptive errors on the frozen shared eval manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sprint4.eval.policy_error_analysis import analyze_from_paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze warm-start policy errors against adaptive.")
    parser.add_argument(
        "--model-artifact-path",
        default="artifacts/sprint4/training/supervised_warmstart/model_artifact.json",
        help="Warm-start model artifact JSON.",
    )
    parser.add_argument(
        "--supervised-train-manifest-path",
        default="artifacts/sprint4/eval/pretraining_scoreboard/manifests/supervised_train_manifest.json",
        help="Frozen supervised train manifest.",
    )
    parser.add_argument(
        "--shared-eval-manifest-path",
        default="artifacts/sprint4/eval/pretraining_scoreboard/manifests/shared_eval_manifest.json",
        help="Frozen shared eval manifest.",
    )
    parser.add_argument(
        "--transition-rows-path",
        default="artifacts/sprint4/eval/pretraining_scoreboard/data/adaptive_transition_rows.jsonl",
        help="Transition rows JSONL used for replay comparison.",
    )
    parser.add_argument(
        "--warmstart-eval-path",
        default="artifacts/sprint4/training/supervised_warmstart/eval_on_shared_manifest.json",
        help="Warm-start eval JSON.",
    )
    parser.add_argument(
        "--adaptive-eval-path",
        default="artifacts/sprint4/eval/pretraining_scoreboard/adaptive_real/eval_results.jsonl",
        help="Adaptive eval JSON or JSONL.",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/sprint4/training/supervised_warmstart/error_analysis",
        help="Directory for error-analysis artifacts.",
    )
    args = parser.parse_args()

    result = analyze_from_paths(
        model_artifact_path=args.model_artifact_path,
        supervised_train_manifest_path=args.supervised_train_manifest_path,
        shared_eval_manifest_path=args.shared_eval_manifest_path,
        transition_rows_path=args.transition_rows_path,
        warmstart_eval_path=args.warmstart_eval_path,
        adaptive_eval_path=args.adaptive_eval_path,
        output_dir=args.output_dir,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
