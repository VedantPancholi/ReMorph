import json

from sprint4.env.scenario_loader import default_live_scenarios


def test_default_live_scenarios_can_select_all_and_filter(tmp_path) -> None:
    dataset_path = tmp_path / "training_dataset.json"
    dataset_path.write_text(
        json.dumps(
            [
                {
                    "target_url": "http://127.0.0.1:8000/api/v1/payments/process",
                    "method": "POST",
                    "scenario_type": "schema_missing_key",
                    "failed_payload": {"currency": "USD"},
                    "failed_headers": {"x-api-key": "secret"},
                    "error_code": 422,
                    "actual_server_response": '{"detail":[{"type":"missing","loc":["body","amount"],"msg":"Field required"}]}',
                },
                {
                    "target_url": "http://127.0.0.1:8000/api/v0/payments/process",
                    "method": "POST",
                    "scenario_type": "route_regression",
                    "failed_payload": {"amount": 100},
                    "failed_headers": {"x-api-key": "secret"},
                    "error_code": 404,
                    "actual_server_response": '{"detail":"Route not found"}',
                },
                {
                    "target_url": "http://127.0.0.1:8000/api/v1/payments/process",
                    "method": "POST",
                    "scenario_type": "auth_missing_token",
                    "failed_payload": {"amount": 100},
                    "failed_headers": {"x-api-key": "secret"},
                    "error_code": 401,
                    "actual_server_response": '{"detail":"Not authenticated"}',
                },
            ]
        ),
        encoding="utf-8",
    )

    all_rows = default_live_scenarios(
        dataset_path=str(dataset_path),
        selection="all",
    )
    assert len(all_rows) == 3
    assert {row.raw_scenario_type for row in all_rows} == {
        "schema_missing_key",
        "route_regression",
        "auth_missing_token",
    }

    filtered = default_live_scenarios(
        dataset_path=str(dataset_path),
        raw_scenario_filter="route_regression",
    )
    assert len(filtered) == 1
    assert filtered[0].scenario_type == "route_drift"


def test_default_live_scenarios_prefers_repairable_auth_representative(tmp_path) -> None:
    dataset_path = tmp_path / "training_dataset.json"
    dataset_path.write_text(
        json.dumps(
            [
                {
                    "target_url": "http://127.0.0.1:8000/api/v1/payments/process",
                    "method": "POST",
                    "scenario_type": "auth_missing_token",
                    "failed_payload": {"amount": 100},
                    "failed_headers": {"x-api-key": "secret"},
                    "error_code": 401,
                    "actual_server_response": '{"detail":"Not authenticated"}',
                },
                {
                    "target_url": "http://127.0.0.1:8000/api/v1/payments/process",
                    "method": "POST",
                    "scenario_type": "auth_missing_tenant",
                    "failed_payload": {"amount": 100},
                    "failed_headers": {
                        "x-api-key": "secret",
                        "Authorization": "Bearer valid-token",
                    },
                    "error_code": 422,
                    "actual_server_response": '{"detail":[{"type":"missing","loc":["header","x-vendor-id"],"msg":"Field required"}]}',
                },
            ]
        ),
        encoding="utf-8",
    )

    selected = default_live_scenarios(dataset_path=str(dataset_path))
    auth_row = next(row for row in selected if row.scenario_type == "auth_drift")
    assert auth_row.raw_scenario_type == "auth_missing_tenant"
