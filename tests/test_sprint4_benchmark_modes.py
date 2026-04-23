from sprint4.env.scenario_loader import load_contract_bundle
from sprint4.evaluation.benchmark_modes import BenchmarkRuntimeMode, run_benchmark_with_mode


def test_benchmark_runtime_modes_control_cache_behavior(tmp_path) -> None:
    bundle = load_contract_bundle()
    cache_path = tmp_path / "repair_cache.json"
    telemetry_dir = tmp_path / "telemetry"

    clear_report = run_benchmark_with_mode(
        bundle=bundle,
        episodes_per_scenario=1,
        output_dir=str(tmp_path / "clear"),
        mode=BenchmarkRuntimeMode(
            cache_mode="clear",
            telemetry_enabled=False,
            cache_path=str(cache_path),
            telemetry_dir=str(telemetry_dir),
        ),
    )
    assert clear_report["metadata"]["runtime_mode"]["cache_mode"] == "clear"
    assert {row["repair_strategy"] for row in clear_report["records"]["adaptive"]} == {
        "deterministic"
    }
    assert cache_path.exists()

    reuse_report = run_benchmark_with_mode(
        bundle=bundle,
        episodes_per_scenario=1,
        output_dir=str(tmp_path / "reuse"),
        mode=BenchmarkRuntimeMode(
            cache_mode="reuse",
            telemetry_enabled=False,
            cache_path=str(cache_path),
            telemetry_dir=str(telemetry_dir),
        ),
    )
    assert {row["repair_strategy"] for row in reuse_report["records"]["adaptive"]} == {"cache"}

    disable_report = run_benchmark_with_mode(
        bundle=bundle,
        episodes_per_scenario=1,
        output_dir=str(tmp_path / "disable"),
        mode=BenchmarkRuntimeMode(
            cache_mode="disable",
            telemetry_enabled=False,
            cache_path=str(cache_path),
            telemetry_dir=str(telemetry_dir),
        ),
    )
    assert {row["repair_strategy"] for row in disable_report["records"]["adaptive"]} == {
        "deterministic"
    }
