"""Run a concise Sprint 4 baseline-vs-adaptive demo episode."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import cast

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sprint4.config import get_sprint4_settings
from sprint4.env.factory import (
    EnvironmentBackend,
    LiveEnvConfig,
    OpenEnvClientConfig,
    build_environment,
    resolve_backend,
)
from sprint4.env.scenario_loader import default_live_scenarios, default_scenarios, load_contract_bundle
from sprint4.proxy.workflow_runner import WorkflowRunner


def main() -> None:
    settings = get_sprint4_settings()
    backend = cast(
        EnvironmentBackend,
        resolve_backend(
            backend=cast(EnvironmentBackend, settings.ENV_BACKEND.strip().lower()),
            env_mode=cast(str, settings.ENV_MODE.strip().lower()),
        ),
    )
    bundle = load_contract_bundle()
    scenario = (
        next(item for item in default_live_scenarios() if item.drift_mode == "route")
        if backend == "live"
        else next(item for item in default_scenarios() if item.drift_mode == "route")
    )
    openenv_cfg = OpenEnvClientConfig(
        module=settings.OPENENV_CLIENT_MODULE,
        class_name=settings.OPENENV_CLIENT_CLASS,
        base_url=settings.OPENENV_BASE_URL or None,
        strict=settings.OPENENV_STRICT,
    )
    env = build_environment(
        bundle=bundle,
        backend=backend,
        openenv_config=openenv_cfg if backend == "openenv" else None,
        live_config=LiveEnvConfig(
            base_url=settings.LIVE_BASE_URL,
            spec_path=settings.LIVE_SPEC_PATH,
        )
        if backend == "live"
        else None,
    )
    env.apply_drift(scenario.drift_mode)
    runner = WorkflowRunner(
        env=env,
        episode_log_path=settings.EPISODE_LOG_PATH,
        max_repair_cycles=settings.MAX_REPAIR_CYCLES,
        environment_mode="live" if backend == "live" else "local",
    )

    request = {
        "method": scenario.method,
        "url": scenario.url,
        "headers": scenario.headers,
        "payload": scenario.payload,
        "raw_scenario_type": scenario.raw_scenario_type,
    }
    baseline = runner.run_episode(
        scenario_type=scenario.scenario_type,
        request=request,
        local_spec_path=scenario.local_spec_path or bundle.drift_paths[scenario.drift_mode],
        adaptive=False,
    )
    adaptive = runner.run_episode(
        scenario_type=scenario.scenario_type,
        request=request,
        local_spec_path=scenario.local_spec_path or bundle.drift_paths[scenario.drift_mode],
        adaptive=True,
    )

    print("=== Sprint 4 Demo ===")
    print(f"Env Backend: {backend}")
    print(f"Drift Type: {scenario.drift_mode}")
    print("Baseline:")
    print(
        json.dumps(
            {
                "status_code": baseline.final_result.status_code,
                "success": baseline.final_result.success,
                "reward": baseline.reward.total_reward,
            },
            indent=2,
        )
    )
    print("Adaptive:")
    print(
        json.dumps(
            {
                "initial_status": adaptive.initial_result.status_code,
                "final_status": adaptive.final_result.status_code,
                "success": adaptive.final_result.success,
                "healed_request": adaptive.healed_request.model_dump(mode="json")
                if adaptive.healed_request
                else None,
                "reward": adaptive.reward.total_reward,
                "reward_breakdown": adaptive.reward.breakdown,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
