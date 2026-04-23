from sprint4.env.scenario_loader import load_contract_bundle
from sprint4.evaluation.benchmark_modes import BenchmarkRuntimeMode, run_benchmark_with_mode
from sprint4.training.episode_dataset import generate_training_dataset, load_episode_jsonl


def test_generate_training_dataset_creates_structured_samples(tmp_path) -> None:
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

    manifest = generate_training_dataset(
        episodes_path=str(benchmark_dir / "episodes.jsonl"),
        output_dir=str(tmp_path / "dataset"),
        agent_type="adaptive",
        eval_ratio=0.34,
        seed=7,
    )

    assert manifest["sample_count"] == 3
    assert manifest["train_sample_count"] + manifest["eval_sample_count"] == 3

    train_rows = load_episode_jsonl(manifest["train_path"], agent_type=None)
    assert train_rows
    sample = train_rows[0]
    assert "state" in sample
    assert "action" in sample
    assert "prompt" in sample
    assert "completion" in sample
    assert sample["state"]["available_contract"]["path"] in {"/users", "/api/v2/finance/ledger"}
    assert sample["action"]["repair_type"] in {
        "payload_rewrite",
        "route_rewrite",
        "auth_rewrite",
        "combined_rewrite",
    }
