import pytest
import json

from app.config import get_settings
from app.services.proxy_adapter import handle_proxy_failure
from app.services.retry_orchestrator import heal_and_retry
from app.testsupport.sample_errors import (
    SCENARIO_A_KEY_MUTATION,
    SCENARIO_B_ROUTE_DRIFT,
)


@pytest.fixture(autouse=True)
def isolate_runtime(monkeypatch, tmp_path):
    monkeypatch.setenv("REMORPH_ENABLE_REPAIR_CACHE", "false")
    monkeypatch.setenv("REMORPH_ENABLE_TELEMETRY", "false")
    monkeypatch.setenv("REMORPH_GROQ_API_KEY", "")
    monkeypatch.setenv("REMORPH_REPAIR_CACHE_PATH", str(tmp_path / "repair_cache.json"))
    monkeypatch.setenv("REMORPH_TELEMETRY_DIR", str(tmp_path / "telemetry"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_handle_proxy_failure_returns_contract_envelope() -> None:
    response = handle_proxy_failure(
        SCENARIO_A_KEY_MUTATION,
        local_spec_path="app/testsupport/sample_openapi.json",
    )

    assert response["contract_version"] == "remorph.proxy.v1"
    assert response["status"] == "healed"
    assert response["healed_request"]["healing_action"] == "payload_rewrite"


def test_handle_proxy_failure_returns_explicit_unrepairable_state() -> None:
    response = handle_proxy_failure(
        SCENARIO_A_KEY_MUTATION,
        local_spec_path="app/testsupport/missing.json",
    )

    assert response["contract_version"] == "remorph.proxy.v1"
    assert response["status"] == "unrepairable"
    assert response["failure_reason"] == "docs_unavailable"


def test_heal_and_retry_returns_successful_workflow() -> None:
    def execute_request(request: dict) -> dict:
        if request["url"].endswith("/api/v2/finance/ledger") and request["headers"] == {
            "x-api-key": "demo-token"
        }:
            return {"success": True, "status_code": 200, "response_body": {"ok": True}}
        return {"success": False, "status_code": 400, "error_message": "still broken"}

    workflow = heal_and_retry(
        SCENARIO_B_ROUTE_DRIFT,
        execute_request,
        local_spec_path="app/testsupport/sample_openapi.json",
        max_retries=1,
    )

    assert workflow.status == "success"
    assert workflow.attempts == 1
    assert workflow.final_healed_request.fixed_url.endswith("/api/v2/finance/ledger")
    assert workflow.final_healed_request.diagnostics.retry_succeeded is True
    assert workflow.policy_name == "adaptive_rules"
    assert workflow.policy_source == "deterministic_fallback"


def test_workflow_telemetry_records_policy_and_summary(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("REMORPH_ENABLE_TELEMETRY", "true")
    monkeypatch.setenv("REMORPH_TELEMETRY_DIR", str(tmp_path / "telemetry"))
    get_settings.cache_clear()

    def execute_request(request: dict) -> dict:
        if request["url"].endswith("/api/v2/finance/ledger") and request["headers"] == {
            "x-api-key": "demo-token"
        }:
            return {"success": True, "status_code": 200, "response_body": {"ok": True}}
        return {"success": False, "status_code": 400, "error_message": "still broken"}

    workflow = heal_and_retry(
        {
            **SCENARIO_B_ROUTE_DRIFT,
            "raw_scenario_type": "route_regression",
        },
        execute_request,
        local_spec_path="app/testsupport/sample_openapi.json",
        max_retries=1,
    )

    assert workflow.status == "success"

    events_path = tmp_path / "telemetry" / "workflow_events.jsonl"
    summary_path = tmp_path / "telemetry" / "workflow_summary.json"
    event = json.loads(events_path.read_text(encoding="utf-8").strip().splitlines()[-1])
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    assert event["event_schema_version"] == 2
    assert event["workflow_id"].startswith("workflow:")
    assert event["raw_scenario_type"] == "route_regression"
    assert event["benchmark_partition"] == "repairable"
    assert event["policy_name"] == "adaptive_rules"
    assert event["policy_source"] == "deterministic_fallback"
    assert event["final_status_code"] == 200
    assert event["healing_action_sequence"] == ["combined_rewrite"]
    assert event["attempt_status_codes"] == [200]

    assert summary["status_counts"]["success"] == 1
    assert summary["success_rate"] == 1.0
    assert summary["raw_scenario_type_counts"]["route_regression"] == 1
    assert summary["benchmark_partition_counts"]["repairable"] == 1
    assert summary["policy_name_counts"]["adaptive_rules"] == 1
    assert summary["policy_source_counts"]["deterministic_fallback"] == 1
