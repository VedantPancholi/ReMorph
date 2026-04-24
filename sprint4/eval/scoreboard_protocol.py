"""Freeze a repo-native Sprint 4 pre-training scoreboard on real benchmark rows."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sprint4.eval.compare_policies import compare_policy_runs, render_comparison_summary
from sprint4.eval.eval_runner import persist_comparison, run_eval
from sprint4.training.benchmark_contract import BENCHMARK_CONTRACT_VERSION, BenchmarkPartition
from sprint4.training.episode_dataset import (
    build_supervised_dataset,
    build_transition_dataset,
    load_episode_jsonl,
)
from sprint4.training.manifests import build_experiment_manifests
from sprint4.training.split_strategy import build_group_id


def freeze_repo_native_scoreboard(
    *,
    episodes_path: str,
    output_dir: str,
    benchmark_partition: BenchmarkPartition = "all",
    split_seed: int = 42,
    eval_ratio: float = 0.2,
) -> dict[str, Any]:
    """Freeze one official baseline-vs-adaptive scoreboard from benchmark episodes."""

    baseline_episodes = load_episode_jsonl(episodes_path, agent_type="baseline")
    adaptive_episodes = load_episode_jsonl(episodes_path, agent_type="adaptive")

    baseline_rows, baseline_summary = build_transition_dataset(
        baseline_episodes,
        benchmark_partition=benchmark_partition,
    )
    supervised_rows, supervised_summary = build_supervised_dataset(
        adaptive_episodes,
        benchmark_partition=benchmark_partition,
    )
    adaptive_rows, adaptive_summary = build_transition_dataset(
        adaptive_episodes,
        benchmark_partition=benchmark_partition,
    )

    baseline_rows = _attach_benchmark_provenance(baseline_rows, policy_name="baseline")
    adaptive_rows = _attach_benchmark_provenance(adaptive_rows, policy_name="adaptive")
    adaptive_group_map = {
        str(row.get("episode_id")): build_group_id(row)
        for row in adaptive_rows
    }
    supervised_rows = _attach_benchmark_provenance(
        supervised_rows,
        policy_name="adaptive",
        group_id_by_episode_id=adaptive_group_map,
    )
    canonical_rows = _canonical_manifest_rows(adaptive_rows, baseline_rows)
    manifests = build_experiment_manifests(
        supervised_rows=supervised_rows,
        transition_rows=canonical_rows,
        split_seed=split_seed,
        eval_ratio=eval_ratio,
    )
    shared_eval_manifest = manifests["shared_eval"]

    output_path = Path(output_dir)
    manifests_dir = output_path / "manifests"
    data_dir = output_path / "data"
    checkpoint_dir = output_path / "checkpoint"
    manifests_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    manifest_paths = {
        "supervised_train": _write_json(manifests_dir / "supervised_train_manifest.json", manifests["supervised_train"]),
        "transition_train": _write_json(manifests_dir / "transition_train_manifest.json", manifests["transition_train"]),
        "shared_eval": _write_json(manifests_dir / "shared_eval_manifest.json", shared_eval_manifest),
    }
    data_paths = {
        "supervised_rows": _write_jsonl(data_dir / "supervised_rows.jsonl", supervised_rows),
        "baseline_transition_rows": _write_jsonl(data_dir / "baseline_transition_rows.jsonl", baseline_rows),
        "adaptive_transition_rows": _write_jsonl(data_dir / "adaptive_transition_rows.jsonl", adaptive_rows),
        "canonical_transition_rows": _write_jsonl(data_dir / "canonical_transition_rows.jsonl", canonical_rows),
    }

    baseline_run = run_eval(
        policy_name="baseline",
        manifest=shared_eval_manifest,
        transition_rows=baseline_rows,
        output_dir=str(output_path / "baseline_real"),
    )
    adaptive_run = run_eval(
        policy_name="adaptive",
        manifest=shared_eval_manifest,
        transition_rows=adaptive_rows,
        output_dir=str(output_path / "adaptive_real"),
    )
    comparison_artifacts = persist_comparison(
        run_results=[baseline_run, adaptive_run],
        output_dir=str(output_path / "comparisons"),
    )
    comparison = compare_policy_runs([baseline_run, adaptive_run])

    checkpoint_summary = _build_checkpoint_summary(
        episodes_path=episodes_path,
        benchmark_partition=benchmark_partition,
        split_seed=split_seed,
        eval_ratio=eval_ratio,
        shared_eval_manifest=shared_eval_manifest,
        baseline_summary=baseline_run["summary"],
        adaptive_summary=adaptive_run["summary"],
        supervised_summary_raw=supervised_summary,
        baseline_summary_raw=baseline_summary,
        adaptive_summary_raw=adaptive_summary,
        comparison=comparison,
        manifest_paths=manifest_paths,
        data_paths=data_paths,
        run_artifacts={
            "baseline": baseline_run.get("artifacts", {}),
            "adaptive": adaptive_run.get("artifacts", {}),
            "comparison": comparison_artifacts,
        },
    )
    checkpoint_paths = {
        "checkpoint_json": _write_json(checkpoint_dir / "scoreboard_checkpoint.json", checkpoint_summary),
        "checkpoint_markdown": _write_text(
            checkpoint_dir / "pretraining_scoreboard.md",
            _render_checkpoint_markdown(checkpoint_summary),
        ),
    }

    failure_analysis = _build_failure_analysis(
        manifest_id=str(shared_eval_manifest.get("manifest_id") or ""),
        baseline_summary=baseline_run["summary"],
        adaptive_summary=adaptive_run["summary"],
    )
    analysis_paths = {
        "analysis_json": _write_json(checkpoint_dir / "failure_analysis.json", failure_analysis),
        "analysis_markdown": _write_text(
            checkpoint_dir / "failure_analysis.md",
            _render_failure_analysis_markdown(failure_analysis),
        ),
    }

    return {
        "episodes_path": episodes_path,
        "benchmark_partition": benchmark_partition,
        "contract_version": BENCHMARK_CONTRACT_VERSION,
        "manifest_paths": manifest_paths,
        "data_paths": data_paths,
        "baseline_run": baseline_run,
        "adaptive_run": adaptive_run,
        "comparison": comparison,
        "checkpoint_paths": checkpoint_paths,
        "analysis_paths": analysis_paths,
    }


def _attach_benchmark_provenance(
    rows: list[dict[str, Any]],
    *,
    policy_name: str,
    group_id_by_episode_id: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for row in rows:
        row_copy = dict(row)
        row_copy["provenance"] = {
            "source_name": "benchmark_episode",
            "source_record_id": row.get("episode_id"),
            "policy_name": policy_name,
        }
        if group_id_by_episode_id is not None:
            episode_id = str(row.get("episode_id") or "")
            if episode_id in group_id_by_episode_id:
                row_copy["group_id"] = group_id_by_episode_id[episode_id]
        enriched.append(row_copy)
    return enriched


def _canonical_manifest_rows(*row_sets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    canonical: dict[str, dict[str, Any]] = {}
    for rows in row_sets:
        for row in rows:
            canonical.setdefault(build_group_id(row), row)
    return list(canonical.values())


def _build_checkpoint_summary(
    *,
    episodes_path: str,
    benchmark_partition: str,
    split_seed: int,
    eval_ratio: float,
    shared_eval_manifest: dict[str, Any],
    baseline_summary: dict[str, Any],
    adaptive_summary: dict[str, Any],
    supervised_summary_raw: dict[str, Any],
    baseline_summary_raw: dict[str, Any],
    adaptive_summary_raw: dict[str, Any],
    comparison: dict[str, Any],
    manifest_paths: dict[str, str],
    data_paths: dict[str, str],
    run_artifacts: dict[str, Any],
) -> dict[str, Any]:
    return {
        "checkpoint_name": "sprint4_pretraining_scoreboard",
        "generation_timestamp": datetime.now(UTC).isoformat(),
        "episodes_path": episodes_path,
        "benchmark_partition": benchmark_partition,
        "contract_version": BENCHMARK_CONTRACT_VERSION,
        "manifest_id": shared_eval_manifest.get("manifest_id"),
        "split_seed": split_seed,
        "eval_ratio": eval_ratio,
        "row_counts": {
            "supervised_rows": int(supervised_summary_raw.get("exported_row_count", 0)),
            "shared_eval_transition_rows": len(shared_eval_manifest.get("transition_row_descriptors", [])),
            "baseline_transition_rows": int(baseline_summary_raw.get("exported_row_count", 0)),
            "adaptive_transition_rows": int(adaptive_summary_raw.get("exported_row_count", 0)),
        },
        "baseline_summary": baseline_summary,
        "adaptive_summary": adaptive_summary,
        "comparison": comparison,
        "artifacts": {
            "manifests": manifest_paths,
            "data": data_paths,
            "runs": run_artifacts,
        },
    }


def _build_failure_analysis(
    *,
    manifest_id: str,
    baseline_summary: dict[str, Any],
    adaptive_summary: dict[str, Any],
) -> dict[str, Any]:
    baseline_scenarios = baseline_summary.get("by_scenario", {})
    adaptive_scenarios = adaptive_summary.get("by_scenario", {})
    scenario_rows: list[dict[str, Any]] = []
    for raw_scenario_type in sorted(set(baseline_scenarios) | set(adaptive_scenarios)):
        baseline_metrics = baseline_scenarios.get(raw_scenario_type, {})
        adaptive_metrics = adaptive_scenarios.get(raw_scenario_type, {})
        scenario_rows.append(
            {
                "raw_scenario_type": raw_scenario_type,
                "baseline_success_rate": float(baseline_metrics.get("success_rate", 0.0)),
                "adaptive_success_rate": float(adaptive_metrics.get("success_rate", 0.0)),
                "adaptive_average_reward": float(adaptive_metrics.get("average_reward", 0.0)),
                "delta_success_rate": round(
                    float(adaptive_metrics.get("success_rate", 0.0))
                    - float(baseline_metrics.get("success_rate", 0.0)),
                    4,
                ),
            }
        )

    strongest = sorted(
        scenario_rows,
        key=lambda row: (row["adaptive_success_rate"], row["delta_success_rate"]),
        reverse=True,
    )[:3]
    weakest = sorted(
        scenario_rows,
        key=lambda row: (row["adaptive_success_rate"], row["delta_success_rate"]),
    )[:3]

    adaptive_topline = adaptive_summary.get("topline", {})
    adaptive_safety = adaptive_summary.get("safety", {})
    training_focus = [
        row["raw_scenario_type"]
        for row in scenario_rows
        if row["adaptive_success_rate"] < 1.0
    ]
    if not training_focus:
        training_focus = ["safety_calibration", "retry_efficiency"]

    return {
        "manifest_id": manifest_id,
        "generation_timestamp": datetime.now(UTC).isoformat(),
        "strongest_scenarios": strongest,
        "weakest_scenarios": weakest,
        "safety_behavior": {
            "correct_abstention_rate": adaptive_topline.get("correct_abstention_rate", 0.0),
            "hallucination_rate": adaptive_topline.get("hallucination_rate", 0.0),
            "incorrect_abstain_rate": adaptive_safety.get("incorrect_abstain_rate", 0.0),
            "max_retry_exhaustion_rate": adaptive_safety.get("max_retry_exhaustion_rate", 0.0),
        },
        "training_opportunity_summary": {
            "priority_scenarios": training_focus,
            "recommended_focus": _recommended_focus(training_focus),
        },
        "scenario_rows": scenario_rows,
    }


def _recommended_focus(training_focus: list[str]) -> list[str]:
    recommendations: list[str] = []
    if any(name.startswith("route_") for name in training_focus):
        recommendations.append("route_repair_accuracy")
    if any(name.startswith("schema_") for name in training_focus):
        recommendations.append("payload_repair_accuracy")
    if any(name.startswith("auth_") for name in training_focus):
        recommendations.append("abstention_and_auth_safety")
    if not recommendations:
        recommendations.append("retry_efficiency")
    return recommendations


def _render_checkpoint_markdown(summary: dict[str, Any]) -> str:
    baseline = summary.get("baseline_summary", {}).get("topline", {})
    adaptive = summary.get("adaptive_summary", {}).get("topline", {})
    comparison_table = render_comparison_summary(summary.get("comparison", {}))
    return "\n".join(
        [
            "# Sprint 4 Pre-Training Scoreboard",
            "",
            f"- Manifest id: `{summary.get('manifest_id')}`",
            f"- Contract version: `{summary.get('contract_version')}`",
            f"- Split seed: `{summary.get('split_seed')}`",
            f"- Eval ratio: `{summary.get('eval_ratio')}`",
            f"- Shared eval rows: `{summary.get('row_counts', {}).get('shared_eval_transition_rows', 0)}`",
            "",
            "## Topline",
            "",
            f"- Baseline success rate: `{baseline.get('success_rate', 0.0)}`",
            f"- Adaptive success rate: `{adaptive.get('success_rate', 0.0)}`",
            f"- Baseline average reward: `{baseline.get('average_reward', 0.0)}`",
            f"- Adaptive average reward: `{adaptive.get('average_reward', 0.0)}`",
            "",
            "## Comparison",
            "",
            comparison_table,
            "",
        ]
    )


def _render_failure_analysis_markdown(analysis: dict[str, Any]) -> str:
    strongest = analysis.get("strongest_scenarios", [])
    weakest = analysis.get("weakest_scenarios", [])
    lines = [
        "# Sprint 4 Failure Analysis",
        "",
        f"- Manifest id: `{analysis.get('manifest_id')}`",
        "",
        "## Strongest Scenarios",
        "",
    ]
    for row in strongest:
        lines.append(
            f"- `{row['raw_scenario_type']}` adaptive success `{row['adaptive_success_rate']}` "
            f"(delta `{row['delta_success_rate']}`)"
        )
    lines.extend(["", "## Weakest Scenarios", ""])
    for row in weakest:
        lines.append(
            f"- `{row['raw_scenario_type']}` adaptive success `{row['adaptive_success_rate']}` "
            f"(delta `{row['delta_success_rate']}`)"
        )
    lines.extend(
        [
            "",
            "## Training Focus",
            "",
            f"- Priority scenarios: `{', '.join(analysis.get('training_opportunity_summary', {}).get('priority_scenarios', []))}`",
            f"- Recommended focus: `{', '.join(analysis.get('training_opportunity_summary', {}).get('recommended_focus', []))}`",
            "",
        ]
    )
    return "\n".join(lines)


def _write_json(path: Path, payload: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return str(path)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, ensure_ascii=True))
            handle.write("\n")
    return str(path)


def _write_text(path: Path, content: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)
