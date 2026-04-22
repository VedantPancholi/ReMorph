from sprint4.env.mutable_api_env import MutableAPIEnvironment
from sprint4.env.scenario_loader import default_scenarios, load_contract_bundle
from sprint4.proxy.workflow_runner import WorkflowRunner


def test_workflow_runner_adaptive_success_path(tmp_path) -> None:
    bundle = load_contract_bundle()
    scenario = next(item for item in default_scenarios() if item.drift_mode == "payload")
    env = MutableAPIEnvironment(
        baseline_contract=bundle.baseline_contract,
        drift_contracts=bundle.drift_contracts,
    )
    env.apply_drift(scenario.drift_mode)
    runner = WorkflowRunner(
        env=env,
        episode_log_path=str(tmp_path / "episodes.jsonl"),
        max_repair_cycles=2,
    )
    result = runner.run_episode(
        scenario_type=scenario.scenario_type,
        request={
            "method": scenario.method,
            "url": scenario.url,
            "headers": scenario.headers,
            "payload": scenario.payload,
        },
        local_spec_path=bundle.drift_paths[scenario.drift_mode],
        adaptive=True,
    )
    assert result.initial_result.success is False
    assert result.final_result.success is True
    assert result.record.retries_used >= 1
    assert result.record.reward > 0


def test_workflow_runner_failure_when_repair_contract_missing(tmp_path) -> None:
    bundle = load_contract_bundle()
    scenario = next(item for item in default_scenarios() if item.drift_mode == "route")
    env = MutableAPIEnvironment(
        baseline_contract=bundle.baseline_contract,
        drift_contracts=bundle.drift_contracts,
    )
    env.apply_drift(scenario.drift_mode)
    runner = WorkflowRunner(
        env=env,
        episode_log_path=str(tmp_path / "episodes.jsonl"),
        max_repair_cycles=1,
    )
    result = runner.run_episode(
        scenario_type=scenario.scenario_type,
        request={
            "method": scenario.method,
            "url": scenario.url,
            "headers": scenario.headers,
            "payload": scenario.payload,
        },
        local_spec_path="sprint4/env/contracts/does_not_exist.json",
        adaptive=True,
    )
    assert result.initial_result.success is False
    assert result.final_result.success is False
    assert result.record.reward < 0

