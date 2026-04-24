"""Reproducible evaluation runner for Sprint 4 shared-eval scoreboards."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sprint4.eval.compare_policies import (
    compare_policy_runs,
    evaluate_policy_on_manifest,
    render_comparison_summary,
)


def load_json(path: str) -> dict[str, Any]:
    """Load one JSON object from disk."""

    file_path = Path(path)
    if not file_path.exists():
        return {}
    return json.loads(file_path.read_text(encoding="utf-8"))


def load_jsonl_rows(path: str) -> list[dict[str, Any]]:
    """Load row-oriented JSONL records from disk."""

    file_path = Path(path)
    if not file_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with file_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def run_eval(
    *,
    policy_name: str,
    manifest: dict[str, Any],
    transition_rows: list[dict[str, Any]],
    output_dir: str | None = None,
) -> dict[str, Any]:
    """Run one policy against a shared eval manifest and optionally persist outputs."""

    run = evaluate_policy_on_manifest(
        policy_name=policy_name,
        manifest=manifest,
        transition_rows=transition_rows,
    )
    artifacts = {}
    if output_dir:
        artifacts = persist_eval_run(
            policy_name=policy_name,
            run_result=run,
            output_dir=output_dir,
        )
    return {
        "policy_name": policy_name,
        "manifest_id": run.get("manifest_id"),
        "eval_rows": run.get("eval_rows", []),
        "summary": run.get("summary", {}),
        "artifacts": artifacts,
    }


def run_eval_from_paths(
    *,
    policy_name: str,
    manifest_path: str,
    transition_rows_path: str,
    output_dir: str | None = None,
) -> dict[str, Any]:
    """Load manifest and rows from disk and run one policy evaluation."""

    manifest = load_json(manifest_path)
    transition_rows = load_jsonl_rows(transition_rows_path)
    return run_eval(
        policy_name=policy_name,
        manifest=manifest,
        transition_rows=transition_rows,
        output_dir=output_dir,
    )


def persist_eval_run(
    *,
    policy_name: str,
    run_result: dict[str, Any],
    output_dir: str,
) -> dict[str, str]:
    """Persist one evaluation run as machine-readable artifacts."""

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    eval_rows_path = output / "eval_results.jsonl"
    summary_path = output / "summary.json"
    topline_path = output / "topline.json"
    safety_path = output / "safety.json"
    scenario_path = output / "by_scenario.json"
    partition_path = output / "by_partition.json"
    source_path = output / "by_source.json"

    _write_jsonl(eval_rows_path, run_result.get("eval_rows", []))
    summary = run_result.get("summary", {})
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    topline_path.write_text(json.dumps(summary.get("topline", {}), indent=2, sort_keys=True), encoding="utf-8")
    safety_path.write_text(json.dumps(summary.get("safety", {}), indent=2, sort_keys=True), encoding="utf-8")
    scenario_path.write_text(json.dumps(summary.get("by_scenario", {}), indent=2, sort_keys=True), encoding="utf-8")
    partition_path.write_text(json.dumps(summary.get("by_partition", {}), indent=2, sort_keys=True), encoding="utf-8")
    source_path.write_text(json.dumps(summary.get("by_source", {}), indent=2, sort_keys=True), encoding="utf-8")
    return {
        "eval_results": str(eval_rows_path),
        "summary": str(summary_path),
        "topline": str(topline_path),
        "safety": str(safety_path),
        "by_scenario": str(scenario_path),
        "by_partition": str(partition_path),
        "by_source": str(source_path),
    }


def persist_comparison(
    *,
    run_results: list[dict[str, Any]],
    output_dir: str,
) -> dict[str, str]:
    """Persist a baseline-vs-adaptive style comparison artifact set."""

    comparison = compare_policy_runs(run_results)
    markdown = render_comparison_summary(comparison)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "comparison.json"
    md_path = output / "comparison.md"
    json_path.write_text(json.dumps(comparison, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")
    return {
        "comparison_json": str(json_path),
        "comparison_markdown": str(md_path),
    }


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=True))
            handle.write("\n")
