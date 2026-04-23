import json

from sprint4.training.phase1_dataset_adapter import (
    normalize_phase1_dataset,
    summarize_phase1_dataset,
)


def test_phase1_dataset_adapter_normalizes_records(tmp_path) -> None:
    dataset_path = tmp_path / "training_dataset.json"
    dataset_path.write_text(
        json.dumps(
            [
                {
                    "target_url": "http://127.0.0.1:8000/api/v1/payments/process",
                    "method": "POST",
                    "actual_server_response": '{"detail":[{"type":"missing","loc":["body","currency"],"msg":"Field required"}]}',
                    "request_id": "req-123",
                    "source_component": "api_proxy",
                    "scenario_type": "schema_missing_key",
                    "failed_payload": {"amount": 100},
                    "failed_headers": {"x-api-key": "secret"},
                    "error_code": 422,
                }
            ]
        ),
        encoding="utf-8",
    )

    rows = normalize_phase1_dataset(str(dataset_path))
    assert len(rows) == 1
    row = rows[0]
    assert row["environment_mode"] == "live"
    assert row["scenario_type"] == "payload_drift"
    assert row["raw_scenario_type"] == "schema_missing_key"
    assert row["response"]["failure_signals"]["missing_fields"] == ["currency"]

    summary = summarize_phase1_dataset(str(dataset_path))
    assert summary["sample_count"] == 1
    assert summary["failure_count"] == 1
    assert summary["scenario_distribution"] == {"payload_drift": 1}
