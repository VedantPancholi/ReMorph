import pytest

from app.services.llm_client import _build_response_format, parse_healing_response
from app.utils.error_utils import LLMHealingError


def test_parse_healing_response_handles_json_payload() -> None:
    healed = parse_healing_response(
        """
        {
          "reasoning": "Schema requires nested user object.",
          "fixed_url": "https://mock.example.com/users",
          "fixed_method": "POST",
          "fixed_payload": {"user": {"f_name": "John", "l_name": "Doe"}},
          "fixed_headers": null,
          "schema_summary": {"required_fields": ["user"]},
          "healing_action": "payload_rewrite",
          "confidence": 0.91
        }
        """
    )

    assert healed.healing_action == "payload_rewrite"
    assert healed.confidence == 0.91


def test_parse_healing_response_extracts_json_from_wrapped_text() -> None:
    healed = parse_healing_response(
        """
        Here is the repaired request:
        ```json
        {
          "reasoning": "Route changed in docs.",
          "fixed_url": "https://mock.example.com/api/v2/finance/ledger",
          "fixed_method": "GET",
          "fixed_payload": null,
          "fixed_headers": {"x-api-key": "demo-token"},
          "schema_summary": {"required_fields": []},
          "healing_action": "combined_rewrite",
          "confidence": 0.88
        }
        ```
        """
    )

    assert healed.fixed_url.endswith("/api/v2/finance/ledger")
    assert healed.healing_action == "combined_rewrite"


def test_parse_healing_response_raises_structured_error_for_bad_output() -> None:
    with pytest.raises(LLMHealingError):
        parse_healing_response("I think the payload should probably be changed.")


def test_build_response_format_uses_json_schema_for_supported_groq_models() -> None:
    response_format = _build_response_format("groq/openai/gpt-oss-20b")

    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["name"] == "healed_request"


def test_build_response_format_uses_json_object_for_other_models() -> None:
    response_format = _build_response_format("groq/llama-3.1-8b-instant")

    assert response_format == {"type": "json_object"}
