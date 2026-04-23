"""Write machine-readable and markdown benchmark reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_json_report(report: dict[str, Any], output_path: str) -> str:
    """Persist benchmark report as pretty JSON."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return str(path)


def write_markdown_summary(report: dict[str, Any], output_path: str) -> str:
    """Persist concise markdown summary for demo-readability."""
    baseline = report["baseline"]
    adaptive = report["adaptive"]
    deltas = report["deltas"]
    lines = [
        "# Sprint 4 Benchmark Summary",
        "",
        "## Baseline",
        f"- Success rate: {baseline['success_rate']:.2%}",
        f"- Avg retries: {baseline['avg_retries']:.2f}",
        f"- Avg latency (ms): {baseline['avg_latency_ms']:.2f}",
        f"- Avg reward: {baseline['reward_average']:.3f}",
        "",
        "## Adaptive ReMorph",
        f"- Success rate: {adaptive['success_rate']:.2%}",
        f"- Avg retries: {adaptive['avg_retries']:.2f}",
        f"- Avg latency (ms): {adaptive['avg_latency_ms']:.2f}",
        f"- Avg reward: {adaptive['reward_average']:.3f}",
        "",
        "## Delta (Adaptive - Baseline)",
        f"- Success rate delta: {deltas['success_rate_delta']:.3f}",
        f"- Avg retries delta: {deltas['avg_retries_delta']:.3f}",
        f"- Avg latency delta (ms): {deltas['avg_latency_delta_ms']:.3f}",
        f"- Reward delta: {deltas['reward_average_delta']:.3f}",
        "",
        "## Per Scenario Accuracy (Adaptive)",
    ]
    for scenario, accuracy in adaptive["per_scenario_accuracy"].items():
        lines.append(f"- {scenario}: {accuracy:.2%}")
    raw_accuracy = adaptive.get("per_raw_scenario_accuracy", {})
    if raw_accuracy:
        lines.extend(
            [
                "",
                "## Per Raw Scenario Accuracy (Adaptive)",
            ]
        )
        for scenario, accuracy in raw_accuracy.items():
            lines.append(f"- {scenario}: {accuracy:.2%}")

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)
