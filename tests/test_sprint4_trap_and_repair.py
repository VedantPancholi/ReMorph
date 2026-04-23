from sprint4.proxy.request_executor import RequestExecutionResult
from sprint4.proxy.trap_and_repair import package_trapped_error


def test_package_trapped_error_maps_422_into_payload_drift() -> None:
    trapped = package_trapped_error(
        method="POST",
        url="http://127.0.0.1:8000/api/v1/payments/process",
        payload={"amount": 100},
        headers={"x-api-key": "secret"},
        execution_result=RequestExecutionResult(
            success=False,
            status_code=422,
            error_message="Field required",
            raw_response_text='{"detail":[{"type":"missing","loc":["body","currency"],"msg":"Field required"}]}',
            parsed_error={"detail": [{"type": "missing", "loc": ["body", "currency"], "msg": "Field required"}]},
            metadata={"source_component": "api_proxy"},
        ),
        scenario_type="payload_drift",
        raw_scenario_type="schema_missing_key",
        retry_count=0,
    )

    assert trapped["scenario_type"] == "payload_drift"
    assert trapped["raw_scenario_type"] == "schema_missing_key"
    assert trapped["failure_signals"]["missing_fields"] == ["currency"]


def test_package_trapped_error_extracts_query_and_path_context() -> None:
    trapped = package_trapped_error(
        method="GET",
        url="http://127.0.0.1:8000/api/v1/payments/{trx_id}?start_date=2024-01-01T00:00:00Z",
        payload=None,
        headers={"Authorization": "Bearer demo-token"},
        execution_result=RequestExecutionResult(
            success=False,
            status_code=422,
            error_message="Field required",
            raw_response_text='{"detail":[{"type":"missing","loc":["query","end_date"],"msg":"Field required"},{"type":"uuid_parsing","loc":["path","trx_id"],"msg":"Invalid UUID"}]}',
            parsed_error={
                "detail": [
                    {"type": "missing", "loc": ["query", "end_date"], "msg": "Field required"},
                    {"type": "uuid_parsing", "loc": ["path", "trx_id"], "msg": "Invalid UUID"},
                ]
            },
            metadata={"source_component": "api_proxy"},
        ),
        scenario_type="route_drift",
        raw_scenario_type="route_invalid_path",
        retry_count=1,
    )

    assert trapped["query_params"] == {"start_date": "2024-01-01T00:00:00Z"}
    assert trapped["path_params"] == {"trx_id": "{trx_id}"}
