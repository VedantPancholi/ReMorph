from types import SimpleNamespace

from sprint4.env.scenario_loader import load_contract_bundle
from sprint4.evaluation.benchmark_modes import BenchmarkRuntimeMode, run_benchmark_with_mode
from sprint4.training.trl_train_grpo import run_trl_training


def test_run_trl_training_writes_dataset_and_eval_summary(tmp_path, monkeypatch) -> None:
    monkeypatch.setitem(__import__("sys").modules, "trl", SimpleNamespace(__version__="0.test"))

    benchmark_dir = tmp_path / "benchmark"
    run_benchmark_with_mode(
        bundle=load_contract_bundle(),
        episodes_per_scenario=1,
        output_dir=str(benchmark_dir),
        mode=BenchmarkRuntimeMode(
            cache_mode="clear",
            telemetry_enabled=False,
            cache_path=str(tmp_path / "repair_cache.json"),
            telemetry_dir=str(tmp_path / "telemetry"),
        ),
    )

    summary = run_trl_training(
        episodes_path=str(benchmark_dir / "episodes.jsonl"),
        output_dir=str(tmp_path / "training"),
        eval_ratio=0.34,
        seed=3,
    )

    assert summary["trainer"] == "trl_grpo"
    assert summary["trl_version"] == "0.test"
    assert summary["sample_count"] == 3
    assert summary["train_sample_count"] + summary["eval_sample_count"] == 3
    assert summary["eval_summary"]["sample_count"] == summary["eval_sample_count"]
