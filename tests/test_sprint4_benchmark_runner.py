from sprint4.env.scenario_loader import load_contract_bundle
from sprint4.evaluation.benchmark_runner import run_benchmark


def test_benchmark_output_shape(tmp_path) -> None:
    report = run_benchmark(
        bundle=load_contract_bundle(),
        episodes_per_scenario=1,
        output_dir=str(tmp_path),
    )
    assert "baseline" in report
    assert "adaptive" in report
    assert "deltas" in report
    assert "artifacts" in report
    assert set(report["adaptive"].keys()) >= {
        "success_rate",
        "avg_retries",
        "avg_latency_ms",
        "reward_average",
        "per_scenario_accuracy",
    }

