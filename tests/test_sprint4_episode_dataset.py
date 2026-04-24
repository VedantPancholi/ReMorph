from sprint4.env.scenario_loader import load_contract_bundle
from sprint4.evaluation.benchmark_modes import BenchmarkRuntimeMode, run_benchmark_with_mode
from sprint4.training.episode_dataset import (
    build_supervised_row_from_episode,
    build_transition_row_from_episode,
    generate_training_dataset,
    load_episode_jsonl,
)


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
    assert manifest["transition_sample_count"] >= 1
    assert manifest["contract_version"] == "v1"

    train_rows = load_episode_jsonl(manifest["train_path"], agent_type=None)
    assert train_rows
    sample = train_rows[0]
    assert "input_text" in sample
    assert "target_action" in sample
    assert sample["contract_version"] == "v1"
    assert sample["benchmark_partition"] == "repairable"


def test_generate_training_dataset_filters_to_repairable_partition(tmp_path) -> None:
    episodes_path = tmp_path / "episodes.jsonl"
    episodes_path.write_text(
        "\n".join(
            [
                '{"agent_type":"adaptive","success":true,"reward":1.2,"scenario_type":"payload_drift","raw_scenario_type":"schema_missing_key","original_request":{"method":"POST","url":"http://x","headers":{},"payload":{}},"healing_action":"payload_rewrite","healed_method":"POST","healed_url":"http://x","healed_headers":{},"healed_payload":{"currency":"USD"},"local_spec_path":"target_api/specs/openapi.json"}',
                '{"agent_type":"adaptive","success":false,"reward":-1.0,"scenario_type":"auth_drift","raw_scenario_type":"auth_missing_token","original_request":{"method":"GET","url":"http://y","headers":{},"payload":null},"healing_action":"no_change","healed_method":null,"healed_url":null,"healed_headers":null,"healed_payload":null,"local_spec_path":"target_api/specs/openapi.json"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    manifest = generate_training_dataset(
        episodes_path=str(episodes_path),
        output_dir=str(tmp_path / "dataset"),
        agent_type="adaptive",
        benchmark_partition="repairable",
        include_failed=True,
        eval_ratio=0.0,
        seed=7,
    )

    assert manifest["benchmark_partition"] == "repairable"
    assert manifest["sample_count"] == 1

    train_rows = load_episode_jsonl(manifest["train_path"], agent_type=None)
    assert len(train_rows) == 1
    assert train_rows[0]["raw_scenario_type"] == "schema_missing_key"
    assert train_rows[0]["benchmark_partition"] == "repairable"


def test_build_supervised_row_uses_abstain_for_unrecoverable_auth() -> None:
    episode = {
        "request_id": "ep-auth",
        "scenario_type": "auth_drift",
        "raw_scenario_type": "auth_missing_token",
        "original_request": {
            "method": "POST",
            "url": "http://127.0.0.1:8000/api/v1/payments/process",
            "headers": {},
            "payload": None,
        },
        "final_status_code": 401,
        "success": False,
    }

    row, reason = build_supervised_row_from_episode(episode)

    assert reason is None
    assert row is not None
    assert row.target_action.action_type == "abstain"
    assert row.benchmark_partition == "unrecoverable"


def test_build_transition_row_scores_correct_abstention_for_unrecoverable_auth() -> None:
    episode = {
        "request_id": "ep-auth",
        "scenario_type": "auth_drift",
        "raw_scenario_type": "auth_missing_token",
        "original_request": {
            "method": "POST",
            "url": "http://127.0.0.1:8000/api/v1/payments/process",
            "headers": {},
            "payload": None,
        },
        "final_status_code": 401,
        "success": False,
        "retries_used": 0,
    }

    row, reason = build_transition_row_from_episode(episode)

    assert reason is None
    assert row is not None
    assert row.action.action_type == "abstain"
    assert row.reward_breakdown.reward_abstention == 7.0
    assert row.reward_breakdown.reward_total == 8.0
    assert row.contract_version == "v1"


def test_build_transition_row_skips_missing_outcome_data() -> None:
    episode = {
        "request_id": "ep-missing",
        "scenario_type": "payload_drift",
        "raw_scenario_type": "schema_missing_key",
        "original_request": {
            "method": "POST",
            "url": "http://127.0.0.1:8000/api/v1/payments/process",
            "headers": {},
            "payload": {"amount": 100},
        },
        "success": False,
    }

    row, reason = build_transition_row_from_episode(episode)

    assert row is None
    assert reason == "missing_final_status_code"
