"""Prompt construction for the healing model."""

from app.models.request_models import TrappedError
from app.models.schema_models import EndpointSchema
from app.utils.json_utils import safe_dump_json


def build_system_prompt() -> str:
    """Return the system prompt used for request repair."""

    return (
        "You are an autonomous API repair agent.\n"
        "A request failed and must be repaired using the latest API schema.\n"
        "Rules:\n"
        "1. Do not hallucinate fields.\n"
        "2. Only use fields present in the provided schema.\n"
        "3. Repair payload, route, or auth only when required.\n"
        "4. Return strict JSON matching the expected healed request model.\n"
    )


def build_healing_prompt(trapped_error: TrappedError, schema: EndpointSchema) -> str:
    """Render the user prompt with failure and schema context."""

    return "\n".join(
        [
            "Failed request context:",
            safe_dump_json(trapped_error.model_dump(mode="json")),
            "",
            "Normalized endpoint schema:",
            safe_dump_json(schema.model_dump(mode="json")),
            "",
            "Return a strict JSON object with:",
            "- reasoning",
            "- fixed_url",
            "- fixed_method",
            "- fixed_payload",
            "- fixed_headers",
            "- schema_summary",
            "- healing_action",
            "- confidence",
        ]
    )
