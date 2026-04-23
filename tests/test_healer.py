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


def test_heal_request_uses_failure_signals_for_422_missing_fields(monkeypatch) -> None:
    monkeypatch.setattr(
        healer,
        "call_healing_model",
        lambda _system_prompt, _user_prompt: (_ for _ in ()).throw(
            healer.LLMHealingError("provider unavailable")
        ),
    )

    trapped_error = healer.TrappedError.model_validate(
        {
            "target_url": "http://127.0.0.1:8000/api/v1/payments/process",
            "method": "POST",
            "failed_payload": {
                "currency": "USD",
                "card_details": {
                    "card_number": "1234567812345678",
                    "cvv": "123",
                    "expiry": "12/26",
                },
                "billing_address": {
                    "street": "test_string",
                    "zip_code": "12345",
                    "iso_country": "US",
                },
            },
            "failed_headers": {
                "x-api-key": "secret",
                "x-vendor-id": "ven-123",
                "Authorization": "Bearer demo-token",
            },
            "error_code": 422,
            "error_message": "Field required",
            "failure_signals": {
                "missing_fields": ["amount"],
                "validation_paths": [["body", "amount"]],
            },
        }
    )
    result = healer.heal_request(
        trapped_error,
        local_spec_path="target_api/specs/openapi.json",
    )

    assert result.healing_action == "payload_rewrite"
    assert result.fixed_payload is not None
    assert result.fixed_payload["amount"] == 100


def test_heal_request_repairs_missing_required_header_from_live_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        healer,
        "call_healing_model",
        lambda _system_prompt, _user_prompt: (_ for _ in ()).throw(
            healer.LLMHealingError("provider unavailable")
        ),
    )

    trapped_error = healer.TrappedError.model_validate(
        {
            "target_url": "http://127.0.0.1:8000/api/v1/payments/process",
            "method": "POST",
            "failed_payload": {
                "amount": 100,
                "currency": "USD",
                "card_details": {
                    "card_number": "1234567812345678",
                    "cvv": "123",
                    "expiry": "12/26",
                },
                "billing_address": {
                    "street": "test_string",
                    "zip_code": "12345",
                    "iso_country": "US",
                },
            },
            "failed_headers": {
                "x-api-key": "secret",
                "Authorization": "Bearer demo-token",
            },
            "error_code": 422,
            "error_message": "Field required",
            "raw_scenario_type": "auth_missing_tenant",
            "failure_signals": {
                "missing_headers": ["x-vendor-id"],
                "validation_paths": [["header", "x-vendor-id"]],
            },
        }
    )
    result = healer.heal_request(
        trapped_error,
        local_spec_path="target_api/specs/openapi.json",
    )

    assert result.healing_action == "auth_rewrite"
    assert result.fixed_headers is not None
    assert result.fixed_headers["x-vendor-id"] == "ven-123"


def test_heal_request_corrects_method_spoof_on_exact_live_route(monkeypatch) -> None:
    monkeypatch.setattr(
        healer,
        "call_healing_model",
        lambda _system_prompt, _user_prompt: (_ for _ in ()).throw(
            healer.LLMHealingError("provider unavailable")
        ),
    )

    trapped_error = healer.TrappedError.model_validate(
        {
            "target_url": "http://127.0.0.1:8000/api/v1/payments/process",
            "method": "GET",
            "failed_payload": None,
            "failed_headers": {
                "x-api-key": "secret",
                "x-vendor-id": "ven-123",
                "Authorization": "Bearer demo-token",
            },
            "error_code": 405,
            "error_message": "Method not allowed",
        }
    )
    result = healer.heal_request(
        trapped_error,
        local_spec_path="target_api/specs/openapi.json",
    )

    assert result.healing_action == "route_rewrite"
    assert result.fixed_method == "POST"
    assert result.fixed_url == "http://127.0.0.1:8000/api/v1/payments/process"


def test_heal_request_fills_required_live_query_parameters(monkeypatch) -> None:
    monkeypatch.setattr(
        healer,
        "call_healing_model",
        lambda _system_prompt, _user_prompt: (_ for _ in ()).throw(
            healer.LLMHealingError("provider unavailable")
        ),
    )

    trapped_error = healer.TrappedError.model_validate(
        {
            "target_url": "http://127.0.0.1:8000/api/v1/ledger/transactions",
            "method": "GET",
            "failed_payload": None,
            "failed_headers": {
                "Authorization": "Bearer demo-token",
            },
            "error_code": 422,
            "error_message": "Field required; Field required",
            "failure_signals": {
                "validation_paths": [
                    ["query", "start_date"],
                    ["query", "end_date"],
                ],
            },
        }
    )
    result = healer.heal_request(
        trapped_error,
        local_spec_path="target_api/specs/openapi.json",
    )

    assert "start_date=2024-01-01T00%3A00%3A00Z" in result.fixed_url
    assert "end_date=2024-01-01T00%3A00%3A00Z" in result.fixed_url


def test_heal_request_fills_unresolved_live_path_parameter(monkeypatch) -> None:
    monkeypatch.setattr(
        healer,
        "call_healing_model",
        lambda _system_prompt, _user_prompt: (_ for _ in ()).throw(
            healer.LLMHealingError("provider unavailable")
        ),
    )

    trapped_error = healer.TrappedError.model_validate(
        {
            "target_url": "http://127.0.0.1:8000/api/v1/payments/{trx_id}",
            "method": "DELETE",
            "failed_payload": None,
            "failed_headers": {
                "x-api-key": "secret",
                "x-vendor-id": "ven-123",
                "Authorization": "Bearer demo-token",
            },
            "error_code": 422,
            "error_message": "Input should be a valid UUID",
            "failure_signals": {
                "validation_paths": [["path", "trx_id"]],
            },
        }
    )
    result = healer.heal_request(
        trapped_error,
        local_spec_path="target_api/specs/openapi.json",
    )

    assert result.fixed_url == "http://127.0.0.1:8000/api/v1/payments/123e4567-e89b-12d3-a456-426614174000"


def test_heal_request_builds_body_after_method_correction(monkeypatch) -> None:
    monkeypatch.setattr(
        healer,
        "call_healing_model",
        lambda _system_prompt, _user_prompt: (_ for _ in ()).throw(
            healer.LLMHealingError("provider unavailable")
        ),
    )

    trapped_error = healer.TrappedError.model_validate(
        {
            "target_url": "http://127.0.0.1:8000/api/v1/payments/process",
            "method": "POST",
            "failed_payload": None,
            "failed_headers": {
                "x-api-key": "secret",
                "x-vendor-id": "ven-123",
                "Authorization": "Bearer demo-token",
            },
            "error_code": 422,
            "error_message": "Field required",
            "failure_signals": {
                "validation_paths": [["body"]],
            },
        }
    )
    result = healer.heal_request(
        trapped_error,
        local_spec_path="target_api/specs/openapi.json",
    )

    assert result.healing_action == "payload_rewrite"
    assert result.fixed_payload is not None
    assert result.fixed_payload["amount"] == 100
    assert result.fixed_payload["currency"] == "USD"


def test_heal_request_replaces_invalid_live_query_parameter(monkeypatch) -> None:
    monkeypatch.setattr(
        healer,
        "call_healing_model",
        lambda _system_prompt, _user_prompt: (_ for _ in ()).throw(
            healer.LLMHealingError("provider unavailable")
        ),
    )

    trapped_error = healer.TrappedError.model_validate(
        {
            "target_url": "http://127.0.0.1:8000/api/v1/ledger/transactions?start_date=2024-01-01T00:00:00Z&end_date=2024-01-02T00:00:00Z&limit=100/invalid_path_404",
            "method": "GET",
            "failed_payload": None,
            "failed_headers": {
                "Authorization": "Bearer demo-token",
            },
            "error_code": 422,
            "error_message": "Input should be a valid integer",
            "failure_signals": {
                "validation_paths": [["query", "limit"]],
            },
        }
    )
    result = healer.heal_request(
        trapped_error,
        local_spec_path="target_api/specs/openapi.json",
    )

    assert "limit=100" in result.fixed_url
    assert "100%2Finvalid_path_404" not in result.fixed_url


def test_heal_request_uses_pattern_aware_defaults_for_live_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        healer,
        "call_healing_model",
        lambda _system_prompt, _user_prompt: (_ for _ in ()).throw(
            healer.LLMHealingError("provider unavailable")
        ),
    )

    trapped_error = healer.TrappedError.model_validate(
        {
            "target_url": "http://127.0.0.1:8000/api/v1/clients/onboard",
            "method": "POST",
            "failed_payload": {
                "contact_email": "test@example.com",
                "company_name": "Acme Corp",
                "registration_code": None,
            },
            "failed_headers": {
                "Authorization": "Bearer demo-token",
            },
            "error_code": 422,
            "error_message": "Input should be a valid string",
            "failure_signals": {
                "missing_fields": ["registration_code"],
                "validation_paths": [["body", "registration_code"]],
            },
        }
    )
    result = healer.heal_request(
        trapped_error,
        local_spec_path="target_api/specs/openapi.json",
    )

    assert result.fixed_payload is not None
    assert result.fixed_payload["registration_code"] == "ABCD12345XYZ"
