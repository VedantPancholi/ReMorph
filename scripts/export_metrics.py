"""Export markdown summary from an existing benchmark JSON report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sprint4.evaluation.metrics_report import write_markdown_summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Export Sprint 4 benchmark markdown.")
    parser.add_argument(
        "--report-json",
        default="runtime/sprint4/benchmark_report.json",
        help="Path to benchmark JSON report.",
    )
    parser.add_argument(
        "--output-md",
        default="runtime/sprint4/benchmark_summary.md",
        help="Path to markdown summary output.",
    )
    args = parser.parse_args()

    report = json.loads(Path(args.report_json).read_text(encoding="utf-8"))
    out = write_markdown_summary(report, args.output_md)
    print(out)


if __name__ == "__main__":
    main()
