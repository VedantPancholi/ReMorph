from app.models.response_models import HealedRequest
from app.services import healer
from app.testsupport.sample_errors import (
    SCENARIO_A_KEY_MUTATION,
    SCENARIO_B_ROUTE_DRIFT,
    SCENARIO_C_AUTH_DRIFT,
)


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
