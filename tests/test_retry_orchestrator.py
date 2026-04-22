import pytest

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
