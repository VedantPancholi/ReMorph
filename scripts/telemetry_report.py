"""Build a compact report comparing workflow outcomes by policy source and raw scenario."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.telemetry import build_telemetry_report


def _render_markdown(report: dict[str, object]) -> str:
    rows = report.get("rows") or []
    lines = [
        "# Telemetry Report",
        "",
        f"- generated_at: {report.get('generated_at')}",
        f"- workflow_event_count: {report.get('workflow_event_count')}",
        f"- healing_event_count: {report.get('healing_event_count')}",
        "",
        "| policy_source | raw_scenario_type | workflow_count | success_rate | average_processing_ms |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| {policy_source} | {raw_scenario_type} | {workflow_count} | {success_rate} | {average_processing_ms} |".format(
                policy_source=row.get("policy_source"),
                raw_scenario_type=row.get("raw_scenario_type"),
                workflow_count=row.get("workflow_count"),
                success_rate=row.get("success_rate"),
                average_processing_ms=row.get("average_processing_ms"),
            )
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a telemetry report grouped by policy source and raw scenario.")
    parser.add_argument("--telemetry-dir", default="runtime/telemetry")
    parser.add_argument("--output-dir", default="runtime/telemetry/report")
    args = parser.parse_args()

    report = build_telemetry_report(args.telemetry_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "telemetry_report.json"
    markdown_path = output_dir / "telemetry_report.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    markdown_path.write_text(_render_markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "json_report": str(json_path),
                "markdown_report": str(markdown_path),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
