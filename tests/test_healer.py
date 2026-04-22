import pytest

from app.config import get_settings
from app.models.response_models import HealedRequest
from app.services import healer
from app.testsupport.sample_errors import (
    SCENARIO_A_KEY_MUTATION,
    SCENARIO_B_ROUTE_DRIFT,
    SCENARIO_C_AUTH_DRIFT,
)


@pytest.fixture(autouse=True)
def isolate_runtime(monkeypatch, tmp_path):
    monkeypatch.setenv("REMORPH_ENABLE_REPAIR_CACHE", "false")
    monkeypatch.setenv("REMORPH_ENABLE_TELEMETRY", "false")
    monkeypatch.setenv("REMORPH_REPAIR_CACHE_PATH", str(tmp_path / "repair_cache.json"))
    monkeypatch.setenv("REMORPH_TELEMETRY_DIR", str(tmp_path / "telemetry"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_heal_request_uses_pipeline_and_returns_model(monkeypatch) -> None:
    monkeypatch.setattr(
        healer,
        "call_healing_model",
        lambda _system_prompt, _user_prompt: HealedRequest(
            reasoning="Schema changed to nested user payload.",
            fixed_url="https://mock.example.com/users",
            fixed_method="POST",
            fixed_payload={"user": {"f_name": "John", "l_name": "Doe"}},
            fixed_headers=None,
            schema_summary={"required_fields": ["user"]},
            healing_action="payload_rewrite",
            confidence=0.95,
        ),
    )

    trapped_error = healer.TrappedError.model_validate(SCENARIO_A_KEY_MUTATION)
    result = healer.heal_request(
        trapped_error,
        local_spec_path="app/testsupport/sample_openapi.json",
    )

    assert result.fixed_payload == {"user": {"f_name": "John", "l_name": "Doe"}}
    assert result.diagnostics is not None
    assert result.diagnostics.repair_strategy == "merged"
    assert result.diagnostics.docs_source == "local:app/testsupport/sample_openapi.json"


def test_heal_request_falls_back_to_deterministic_payload_repair(monkeypatch) -> None:
    monkeypatch.setattr(
        healer,
        "call_healing_model",
        lambda _system_prompt, _user_prompt: (_ for _ in ()).throw(
            healer.LLMHealingError("provider unavailable")
        ),
    )

    trapped_error = healer.TrappedError.model_validate(SCENARIO_A_KEY_MUTATION)
    result = healer.heal_request(
        trapped_error,
        local_spec_path="app/testsupport/sample_openapi.json",
    )

    assert result.healing_action == "payload_rewrite"
    assert result.fixed_payload == {"user": {"f_name": "John", "l_name": "Doe"}}
    assert result.diagnostics is not None
    assert result.diagnostics.fallback_used is True
    assert result.diagnostics.request_id == "req-scenario-a"


def test_heal_request_falls_back_to_deterministic_route_repair(monkeypatch) -> None:
    monkeypatch.setattr(
        healer,
        "call_healing_model",
        lambda _system_prompt, _user_prompt: (_ for _ in ()).throw(
            healer.LLMHealingError("provider unavailable")
        ),
    )

    trapped_error = healer.TrappedError.model_validate(SCENARIO_B_ROUTE_DRIFT)
    result = healer.heal_request(
        trapped_error,
        local_spec_path="app/testsupport/sample_openapi.json",
    )

    assert result.healing_action == "combined_rewrite"
    assert result.fixed_url == "https://mock.example.com/api/v2/finance/ledger"
    assert result.fixed_headers == {"x-api-key": "demo-token"}
    assert result.diagnostics is not None
    assert result.diagnostics.selected_endpoint_path == "/api/v2/finance/ledger"


def test_heal_request_falls_back_to_deterministic_auth_repair(monkeypatch) -> None:
    monkeypatch.setattr(
        healer,
        "call_healing_model",
        lambda _system_prompt, _user_prompt: (_ for _ in ()).throw(
            healer.LLMHealingError("provider unavailable")
        ),
    )

    trapped_error = healer.TrappedError.model_validate(SCENARIO_C_AUTH_DRIFT)
    result = healer.heal_request(
        trapped_error,
        local_spec_path="app/testsupport/sample_openapi.json",
    )

    assert result.healing_action == "auth_rewrite"
    assert result.fixed_headers == {"x-api-key": "demo-token"}
    assert result.diagnostics is not None
    assert result.diagnostics.retry_count == 1
