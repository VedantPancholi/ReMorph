from app.models.request_models import TrappedError
from app.models.schema_models import EndpointSchema
from app.services.prompt_builder import build_healing_prompt


def test_build_healing_prompt_includes_failure_and_schema() -> None:
    trapped_error = TrappedError(
        target_url="https://mock.example.com/users",
        method="POST",
        failed_payload={"first_name": "John"},
        error_code=400,
        error_message="Invalid body",
    )
    schema = EndpointSchema(path="/users", method="POST", required_fields=["user"])

    prompt = build_healing_prompt(trapped_error, schema)

    assert "Invalid body" in prompt
    assert "\"required_fields\"" in prompt
