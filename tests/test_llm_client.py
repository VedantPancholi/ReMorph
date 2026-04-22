from app.services.llm_client import parse_healing_response


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
