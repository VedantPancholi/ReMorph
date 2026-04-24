"""Run one or more Sprint 4 shared-eval policy evaluations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sprint4.eval.eval_runner import persist_comparison, run_eval_from_paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Sprint 4 eval on a shared eval manifest.")
    parser.add_argument(
        "--manifest-path",
        required=True,
        help="Path to the shared eval manifest JSON.",
    )
    parser.add_argument(
        "--policy",
        action="append",
        dest="policies",
        required=True,
        help="Policy name. Provide once per transition rows input.",
    )
    parser.add_argument(
        "--transition-rows-path",
        action="append",
        dest="transition_rows_paths",
        required=True,
        help="Path to transition rows JSONL for the matching policy.",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/sprint4/eval",
        help="Directory to store evaluation artifacts.",
    )
    args = parser.parse_args()

    if len(args.policies) != len(args.transition_rows_paths):
        raise SystemExit("Number of --policy and --transition-rows-path arguments must match.")

    run_results = []
    artifacts: dict[str, object] = {}
    for policy_name, transition_rows_path in zip(args.policies, args.transition_rows_paths, strict=True):
        policy_output_dir = str(Path(args.output_dir) / policy_name)
        result = run_eval_from_paths(
            policy_name=policy_name,
            manifest_path=args.manifest_path,
            transition_rows_path=transition_rows_path,
            output_dir=policy_output_dir,
        )
        run_results.append(result)
        artifacts[policy_name] = result.get("artifacts", {})

    if len(run_results) > 1:
        comparison_artifacts = persist_comparison(
            run_results=run_results,
            output_dir=str(Path(args.output_dir) / "comparisons"),
        )
        artifacts["comparison"] = comparison_artifacts

    print(json.dumps(artifacts, indent=2))


if __name__ == "__main__":
    main()
