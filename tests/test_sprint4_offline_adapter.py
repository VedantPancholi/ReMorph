import json

from sprint4.training.offline_adapter import (
    adapt_benchmark_trace_dataset,
    adapt_offline_sources,
    adapt_phase1_dataset,
)


def test_offline_adapter_adapts_full_fidelity_benchmark_record(tmp_path) -> None:
    episodes_path = tmp_path / "episodes.jsonl"
    episodes_path.write_text(
        json.dumps(
            {
                "request_id": "ep-1",
                "scenario_type": "route_drift",
                "raw_scenario_type": "route_regression",
                "original_request": {
                    "method": "GET",
                    "url": "http://127.0.0.1:8000/api/v0/ledger/transactions?limit=100",
                    "headers": {"Authorization": "Bearer demo-token"},
                    "payload": None,
                },
                "selected_endpoint_path": "/api/v1/ledger/transactions",
                "route_match_confidence": 0.75,
                "healing_action": "route_rewrite",
                "healed_method": "GET",
                "healed_url": "http://127.0.0.1:8000/api/v1/ledger/transactions?limit=100",
                "final_status_code": 200,
                "success": True,
                "retries_used": 0,
                "reward_breakdown": {"wrong_route_penalty": 0.0},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = adapt_benchmark_trace_dataset(str(episodes_path))

    assert len(result["supervised_rows"]) == 1
    assert len(result["transition_rows"]) == 1
    assert result["supervised_rows"][0]["provenance"]["source_name"] == "benchmark_episode"
    assert result["transition_rows"][0]["reward_breakdown"]["reward_total"] == 15.0


def test_offline_adapter_downgrades_to_supervised_when_outcome_missing(tmp_path) -> None:
    episodes_path = tmp_path / "episodes.jsonl"
    episodes_path.write_text(
        json.dumps(
            {
                "request_id": "ep-2",
                "scenario_type": "payload_drift",
                "raw_scenario_type": "schema_missing_key",
                "original_request": {
                    "method": "POST",
                    "url": "http://127.0.0.1:8000/api/v1/payments/process",
                    "headers": {},
                    "payload": {"amount": 100},
                },
                "healing_action": "payload_rewrite",
                "healed_method": "POST",
                "healed_url": "http://127.0.0.1:8000/api/v1/payments/process",
                "healed_payload": {"amount": 100, "currency": "USD"},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = adapt_benchmark_trace_dataset(str(episodes_path))

    assert len(result["supervised_rows"]) == 1
    assert len(result["transition_rows"]) == 0
    assert result["manifest"]["downgraded_to_supervised_only_count"] == 1
    assert result["manifest"]["skipped_rows_by_reason"]["transition_unavailable"] == 1


def test_offline_adapter_skips_when_action_target_missing(tmp_path) -> None:
    episodes_path = tmp_path / "episodes.jsonl"
    episodes_path.write_text(
        json.dumps(
            {
                "request_id": "ep-3",
                "scenario_type": "payload_drift",
                "raw_scenario_type": "schema_missing_key",
                "original_request": {
                    "method": "POST",
                    "url": "http://127.0.0.1:8000/api/v1/payments/process",
                    "headers": {},
                    "payload": {"amount": 100},
                },
                "success": False,
                "final_status_code": 422,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = adapt_benchmark_trace_dataset(str(episodes_path))

    assert len(result["supervised_rows"]) == 0
    assert len(result["transition_rows"]) == 0
    assert result["manifest"]["skipped_rows_by_reason"]["missing_action_trace"] == 1
    assert result["manifest"]["skipped_rows_by_reason"]["transition_unavailable"] == 1


def test_offline_adapter_phase1_unrecoverable_auth_becomes_abstention(tmp_path) -> None:
    dataset_path = tmp_path / "training_dataset.json"
    dataset_path.write_text(
        json.dumps(
            [
                {
                    "target_url": "http://127.0.0.1:8000/api/v1/payments/process",
                    "method": "POST",
                    "actual_server_response": '{"detail":"Authentication failed: Missing bearer token."}',
                    "request_id": "req-1",
                    "source_component": "api_proxy",
                    "scenario_type": "auth_missing_token",
                    "failed_payload": None,
                    "failed_headers": {},
                    "error_code": 401,
                }
            ]
        ),
        encoding="utf-8",
    )

    result = adapt_phase1_dataset(str(dataset_path))

    assert len(result["supervised_rows"]) == 1
    assert result["supervised_rows"][0]["target_action"]["action_type"] == "abstain"
    assert len(result["transition_rows"]) == 1
    assert result["transition_rows"][0]["reward_breakdown"]["reward_abstention"] == 7.0


def test_offline_adapter_flags_contract_mismatch() -> None:
    candidate = {
        "environment_mode": "live",
        "scenario_type": "payload_drift",
        "raw_scenario_type": "schema_missing_key",
        "request": {"method": "POST", "url": "http://x", "headers": {}, "payload": {"amount": 100}},
        "response": {"success": False, "status_code": 422, "error_message": "Field required", "failure_signals": {}},
        "metadata": {"request_id": "mismatch", "source_component": "api_proxy", "benchmark_partition": "unrecoverable"},
    }

    from sprint4.training.offline_adapter import _phase1_row_to_candidate

    normalized = _phase1_row_to_candidate(candidate, 0)
    result = adapt_offline_sources([normalized])

    assert "contract_partition_mismatch" in result["manifest"]["skipped_rows_by_reason"]
    assert result["supervised_rows"][0]["benchmark_partition"] == "repairable"


def test_offline_adapter_manifest_counts_match_rows(tmp_path) -> None:
    episodes_path = tmp_path / "episodes.jsonl"
    episodes_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "request_id": "ep-1",
                        "scenario_type": "route_drift",
                        "raw_scenario_type": "route_regression",
                        "original_request": {"method": "GET", "url": "http://x", "headers": {}, "payload": None},
                        "selected_endpoint_path": "/api/v1/ledger/transactions",
                        "healing_action": "route_rewrite",
                        "healed_method": "GET",
                        "healed_url": "http://x",
                        "final_status_code": 200,
                        "success": True,
                        "retries_used": 0,
                        "reward_breakdown": {"wrong_route_penalty": 0.0},
                    }
                ),
                json.dumps(
                    {
                        "request_id": "ep-2",
                        "scenario_type": "auth_drift",
                        "raw_scenario_type": "auth_missing_token",
                        "original_request": {"method": "POST", "url": "http://y", "headers": {}, "payload": None},
                        "final_status_code": 401,
                        "success": False,
                        "retries_used": 0,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = adapt_benchmark_trace_dataset(str(episodes_path))

    assert result["manifest"]["supervised_rows_emitted"] == len(result["supervised_rows"])
    assert result["manifest"]["transition_rows_emitted"] == len(result["transition_rows"])
