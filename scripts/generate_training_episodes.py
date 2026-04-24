"""Generate large Sprint 4 training episodes for repair-policy learning."""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sprint4.env.factory import LiveEnvConfig, build_environment, resolve_backend
from sprint4.env.scenario_loader import ContractBundle, ScenarioRequest, load_contract_bundle
from sprint4.evaluation.benchmark_modes import BenchmarkRuntimeMode, benchmark_runtime_mode
from sprint4.proxy.workflow_runner import WorkflowRunner
from sprint4.training.benchmark_contract import (
    REPAIRABLE_RAW_SCENARIOS,
    UNRECOVERABLE_RAW_SCENARIOS,
)


def generate_training_episodes(
    *,
    episodes: int,
    output_path: str,
    cache_mode: str = "disable",
    include_repairable: bool = False,
    include_unrecoverable: bool = False,
    seed: int = 42,
    backend: str = "simulated",
    env_mode: str = "local",
    append: bool = False,
    live_base_url: str = "http://127.0.0.1:8000",
    telemetry_enabled: bool = False,
) -> dict[str, Any]:
    """Generate many adaptive episodes using the existing Sprint 4 workflow runner."""

    bundle = load_contract_bundle()
    output_file = Path(output_path)
    summary_path = output_file.with_name("episode_generation_summary.json")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    if not append:
        output_file.unlink(missing_ok=True)
        summary_path.unlink(missing_ok=True)

    selected_raw_scenarios = _selected_raw_scenarios(
        include_repairable=include_repairable,
        include_unrecoverable=include_unrecoverable,
    )
    if not selected_raw_scenarios:
        raise ValueError("No scenarios were selected for generation.")

    resolved_backend = resolve_backend(backend=backend, env_mode=env_mode)
    env = build_environment(
        bundle=bundle,
        backend=resolved_backend,
        live_config=LiveEnvConfig(base_url=live_base_url)
        if resolved_backend == "live"
        else None,
    )
    runner = WorkflowRunner(
        env=env,
        episode_log_path=str(output_file),
        environment_mode=env_mode,
    )

    rng = random.Random(seed)
    scenario_schedule = _scenario_schedule(
        raw_scenarios=selected_raw_scenarios,
        total_episodes=episodes,
        seed=seed,
    )

    mode = BenchmarkRuntimeMode(
        cache_mode=cache_mode, telemetry_enabled=telemetry_enabled
    )
    generated_records: list[dict[str, Any]] = []
    with benchmark_runtime_mode(mode):
        for episode_index, raw_scenario_type in enumerate(scenario_schedule):
            scenario = _build_training_scenario(
                bundle=bundle,
                raw_scenario_type=raw_scenario_type,
                episode_index=episode_index,
                rng=rng,
            )
            env.reset()
            env.apply_drift(scenario.drift_mode)
            result = runner.run_episode(
                scenario_type=scenario.scenario_type,
                request={
                    "method": scenario.method,
                    "url": scenario.url,
                    "headers": scenario.headers,
                    "payload": scenario.payload,
                    "raw_scenario_type": scenario.raw_scenario_type,
                },
                local_spec_path=scenario.local_spec_path or bundle.drift_paths[scenario.drift_mode],
                adaptive=True,
            )
            generated_records.append(asdict(result.record))

    summary = _summarize_generated_records(
        generated_records,
        output_path=str(output_file),
        summary_path=str(summary_path),
        cache_mode=cache_mode,
        backend=resolved_backend,
        env_mode=env_mode,
        seed=seed,
    )
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return summary


def _selected_raw_scenarios(
    *,
    include_repairable: bool,
    include_unrecoverable: bool,
) -> list[str]:
    if not include_repairable and not include_unrecoverable:
        include_repairable = True
        include_unrecoverable = True

    selected: list[str] = []
    if include_repairable:
        selected.extend(REPAIRABLE_RAW_SCENARIOS)
    if include_unrecoverable:
        selected.extend(UNRECOVERABLE_RAW_SCENARIOS)
    return selected


def _scenario_schedule(
    *,
    raw_scenarios: list[str],
    total_episodes: int,
    seed: int,
) -> list[str]:
    ordered = [raw_scenarios[index % len(raw_scenarios)] for index in range(total_episodes)]
    random.Random(seed).shuffle(ordered)
    return ordered


def _build_training_scenario(
    *,
    bundle: ContractBundle,
    raw_scenario_type: str,
    episode_index: int,
    rng: random.Random,
) -> ScenarioRequest:
    if raw_scenario_type.startswith("schema_"):
        return ScenarioRequest(
            scenario_type="payload_drift",
            raw_scenario_type=raw_scenario_type,
            drift_mode="payload",
            method="POST",
            url="https://mock.example.com/users",
            headers={
                "Authorization": "Bearer demo-token",
                "X-Trace-Id": f"payload-{episode_index:05d}",
            },
            payload={
                "first_name": f"User{episode_index}",
                "last_name": f"Case{rng.randint(10, 999)}",
            },
            local_spec_path=bundle.drift_paths["payload"],
        )
    if raw_scenario_type.startswith("route_"):
        return ScenarioRequest(
            scenario_type="route_drift",
            raw_scenario_type=raw_scenario_type,
            drift_mode="route",
            method="GET",
            url=(
                "https://mock.example.com/api/v1/transactions"
                f"?page={(episode_index % 5) + 1}&limit={20 + (episode_index % 3) * 10}"
            ),
            headers={
                "Authorization": "Bearer demo-token",
                "X-Trace-Id": f"route-{episode_index:05d}",
            },
            payload=None,
            local_spec_path=bundle.drift_paths["route"],
        )
    if raw_scenario_type == "auth_missing_tenant":
        return ScenarioRequest(
            scenario_type="auth_drift",
            raw_scenario_type=raw_scenario_type,
            drift_mode="auth",
            method="GET",
            url="https://mock.example.com/api/v2/finance/ledger",
            headers={
                "Authorization": "Bearer demo-token",
                "X-Trace-Id": f"auth-{episode_index:05d}",
            },
            payload=None,
            local_spec_path=bundle.drift_paths["auth"],
        )
    if raw_scenario_type == "auth_missing_token":
        return ScenarioRequest(
            scenario_type="auth_drift",
            raw_scenario_type=raw_scenario_type,
            drift_mode="auth",
            method="GET",
            url="https://mock.example.com/api/v2/finance/ledger",
            headers={"X-Trace-Id": f"auth-missing-token-{episode_index:05d}"},
            payload=None,
            local_spec_path=bundle.drift_paths["auth"],
        )
    if raw_scenario_type == "auth_malformed_jwt":
        return ScenarioRequest(
            scenario_type="auth_drift",
            raw_scenario_type=raw_scenario_type,
            drift_mode="auth",
            method="GET",
            url="https://mock.example.com/api/v2/finance/ledger",
            headers={
                "Authorization": "Bearer malformed.jwt.token",
                "X-Trace-Id": f"auth-malformed-{episode_index:05d}",
            },
            payload=None,
            local_spec_path=bundle.drift_paths["auth"],
        )
    raise ValueError(f"Unsupported raw scenario type: {raw_scenario_type}")


def _summarize_generated_records(
    records: list[dict[str, Any]],
    *,
    output_path: str,
    summary_path: str,
    cache_mode: str,
    backend: str,
    env_mode: str,
    seed: int,
) -> dict[str, Any]:
    total = len(records)
    scenario_distribution = Counter(
        str(record.get("raw_scenario_type") or "unknown") for record in records
    )
    safe_abstention_count = sum(
        1 for record in records if record.get("healing_action") == "safe_abstain"
    )
    cache_usage_count = sum(1 for record in records if bool(record.get("cache_hit")))
    success_count = sum(1 for record in records if bool(record.get("success")))
    avg_reward = round(
        sum(float(record.get("reward", 0.0)) for record in records) / max(1, total),
        4,
    )
    return {
        "output_path": output_path,
        "summary_path": summary_path,
        "backend": backend,
        "env_mode": env_mode,
        "cache_mode": cache_mode,
        "seed": seed,
        "total_episodes": total,
        "repairable_count": sum(1 for record in records if record.get("recoverable") is not False),
        "unrecoverable_count": sum(1 for record in records if record.get("recoverable") is False),
        "scenario_distribution": dict(scenario_distribution),
        "success_rate": round(success_count / max(1, total), 4),
        "avg_reward": avg_reward,
        "safe_abstention_count": safe_abstention_count,
        "cache_usage_count": cache_usage_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate large Sprint 4 training episodes.")
    parser.add_argument("--episodes", type=int, default=1000)
    parser.add_argument("--output", required=True)
    parser.add_argument("--cache-mode", default="disable")
    parser.add_argument("--include-repairable", action="store_true")
    parser.add_argument("--include-unrecoverable", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--backend", default="simulated")
    parser.add_argument("--env-mode", default="local")
    parser.add_argument("--append", action="store_true")
    parser.add_argument("--live-base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    summary = generate_training_episodes(
        episodes=args.episodes,
        output_path=args.output,
        cache_mode=args.cache_mode,
        include_repairable=args.include_repairable,
        include_unrecoverable=args.include_unrecoverable,
        seed=args.seed,
        backend=args.backend,
        env_mode=args.env_mode,
        append=args.append,
        live_base_url=args.live_base_url,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
