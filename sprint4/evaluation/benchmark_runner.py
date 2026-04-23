"""Benchmark harness for baseline vs adaptive Sprint 4 behavior."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from sprint4.env.factory import (
    EnvironmentMode,
    EnvironmentBackend,
    LiveEnvConfig,
    OpenEnvClientConfig,
    build_environment,
    resolve_backend,
)
from sprint4.env.scenario_loader import (
    ContractBundle,
    ScenarioRequest,
    default_live_scenarios,
    default_scenarios,
)
from sprint4.evaluation.compare_baseline_vs_adaptive import AgentAggregate, compare_agents
from sprint4.evaluation.metrics_report import write_json_report, write_markdown_summary
from sprint4.proxy.workflow_runner import WorkflowRunner


def run_benchmark(
    *,
    bundle: ContractBundle,
    scenarios: list[ScenarioRequest] | None = None,
    episodes_per_scenario: int = 1,
    output_dir: str = "runtime/sprint4",
    backend: EnvironmentBackend = "simulated",
    env_mode: EnvironmentMode | None = None,
    live_base_url: str = "http://127.0.0.1:8000",
    live_spec_path: str = "target_api/specs/openapi.json",
    live_dataset_path: str = "target_api/training_dataset.json",
    live_scenario_selection: str = "representative",
    live_raw_scenario_filter: str | None = None,
    openenv_config: OpenEnvClientConfig | None = None,
) -> dict[str, Any]:
    """Execute baseline and adaptive episodes and return aggregate report."""
    resolved_backend = resolve_backend(backend=backend, env_mode=env_mode)
    active_mode = env_mode or ("live" if resolved_backend == "live" else "local")
    scenario_list = scenarios or (
        default_live_scenarios(
            dataset_path=live_dataset_path,
            live_spec_path=live_spec_path,
            selection=live_scenario_selection,
            raw_scenario_filter=live_raw_scenario_filter,
        )
        if resolved_backend == "live"
        else default_scenarios()
    )
    env = build_environment(
        bundle=bundle,
        backend=resolved_backend,
        openenv_config=openenv_config,
        live_config=LiveEnvConfig(base_url=live_base_url, spec_path=live_spec_path)
        if resolved_backend == "live"
        else None,
    )
    runner = WorkflowRunner(
        env=env,
        episode_log_path=str(Path(output_dir) / "episodes.jsonl"),
        environment_mode=active_mode,
    )

    baseline_records: list[dict[str, Any]] = []
    adaptive_records: list[dict[str, Any]] = []

    for _ in range(episodes_per_scenario):
        for scenario in scenario_list:
            env.reset()
            env.apply_drift(scenario.drift_mode)
            request = {
                "method": scenario.method,
                "url": scenario.url,
                "headers": scenario.headers,
                "payload": scenario.payload,
                "raw_scenario_type": scenario.raw_scenario_type,
            }
            baseline_outcome = runner.run_episode(
                scenario_type=scenario.scenario_type,
                request=request,
                local_spec_path=scenario.local_spec_path or bundle.drift_paths[scenario.drift_mode],
                adaptive=False,
            )
            adaptive_outcome = runner.run_episode(
                scenario_type=scenario.scenario_type,
                request=request,
                local_spec_path=scenario.local_spec_path or bundle.drift_paths[scenario.drift_mode],
                adaptive=True,
            )
            baseline_records.append(asdict(baseline_outcome.record))
            adaptive_records.append(asdict(adaptive_outcome.record))

    baseline = _aggregate(baseline_records)
    adaptive = _aggregate(adaptive_records)
    deltas = compare_agents(
        AgentAggregate(
            success_rate=baseline["success_rate"],
            avg_retries=baseline["avg_retries"],
            avg_latency_ms=baseline["avg_latency_ms"],
            reward_average=baseline["reward_average"],
            per_scenario_accuracy=baseline["per_scenario_accuracy"],
        ),
        AgentAggregate(
            success_rate=adaptive["success_rate"],
            avg_retries=adaptive["avg_retries"],
            avg_latency_ms=adaptive["avg_latency_ms"],
            reward_average=adaptive["reward_average"],
            per_scenario_accuracy=adaptive["per_scenario_accuracy"],
        ),
    )

    report = {
        "metadata": {
            "episodes_per_scenario": episodes_per_scenario,
            "scenario_count": len(scenario_list),
            "environment_mode": active_mode,
            "backend": resolved_backend,
            "live_dataset_path": live_dataset_path if resolved_backend == "live" else None,
            "live_scenario_selection": live_scenario_selection if resolved_backend == "live" else None,
            "live_raw_scenario_filter": live_raw_scenario_filter if resolved_backend == "live" else None,
        },
        "baseline": baseline,
        "adaptive": adaptive,
        "deltas": deltas,
        "records": {
            "baseline": baseline_records,
            "adaptive": adaptive_records,
        },
    }

    json_path = write_json_report(report, str(Path(output_dir) / "benchmark_report.json"))
    markdown_path = write_markdown_summary(
        report,
        str(Path(output_dir) / "benchmark_summary.md"),
    )
    report["artifacts"] = {
        "json_report": json_path,
        "markdown_summary": markdown_path,
    }
    return report


def _aggregate(records: list[dict[str, Any]]) -> dict[str, Any]:
    count = max(1, len(records))
    success_count = sum(1 for record in records if record["success"])
    avg_retries = sum(record["retries_used"] for record in records) / count
    avg_latency = sum(record["latency_ms"] for record in records) / count
    avg_reward = sum(record["reward"] for record in records) / count

    per_scenario_counts: dict[str, int] = {}
    per_scenario_success: dict[str, int] = {}
    per_raw_scenario_counts: dict[str, int] = {}
    per_raw_scenario_success: dict[str, int] = {}
    for record in records:
        scenario = record["scenario_type"]
        per_scenario_counts[scenario] = per_scenario_counts.get(scenario, 0) + 1
        if record["success"]:
            per_scenario_success[scenario] = per_scenario_success.get(scenario, 0) + 1
        raw_scenario = str(record.get("raw_scenario_type") or "unknown")
        per_raw_scenario_counts[raw_scenario] = per_raw_scenario_counts.get(raw_scenario, 0) + 1
        if record["success"]:
            per_raw_scenario_success[raw_scenario] = per_raw_scenario_success.get(raw_scenario, 0) + 1
    per_scenario_accuracy = {
        scenario: round(per_scenario_success.get(scenario, 0) / total, 4)
        for scenario, total in per_scenario_counts.items()
    }
    per_raw_scenario_accuracy = {
        scenario: round(per_raw_scenario_success.get(scenario, 0) / total, 4)
        for scenario, total in per_raw_scenario_counts.items()
    }

    return {
        "success_rate": round(success_count / count, 4),
        "avg_retries": round(avg_retries, 4),
        "avg_latency_ms": round(avg_latency, 4),
        "reward_average": round(avg_reward, 4),
        "per_scenario_accuracy": per_scenario_accuracy,
        "per_raw_scenario_accuracy": per_raw_scenario_accuracy,
    }
