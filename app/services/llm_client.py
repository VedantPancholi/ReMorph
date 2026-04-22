"""LLM client wrapper for healing requests."""

from __future__ import annotations

import json
import logging

from pydantic import ValidationError

from app.config import get_settings
from app.models.response_models import HealedRequest
from app.utils.error_utils import LLMHealingError
from app.utils.json_utils import safe_load_json


def call_healing_model(system_prompt: str, user_prompt: str) -> HealedRequest:
    """Call the configured model and return a validated healed response."""

    settings = get_settings()
    if not settings.GROQ_API_KEY:
        raise LLMHealingError("GROQ_API_KEY is not configured")

    try:
        import litellm
        from litellm import completion
    except ImportError as exc:
        raise LLMHealingError("litellm is not installed") from exc

    _configure_litellm_runtime(litellm)

    try:
        response = completion(
            model=settings.LLM_MODEL,
            api_key=settings.GROQ_API_KEY,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format=_build_response_format(settings.LLM_MODEL),
            temperature=0,
        )
        content = response.choices[0].message.content
    except Exception as exc:  # pragma: no cover - provider errors are runtime specific
        raise LLMHealingError("Healing model invocation failed") from exc

    return parse_healing_response(content)


def parse_healing_response(content: str) -> HealedRequest:
    """Parse model output into the strict healed request model."""

    if not content:
        raise LLMHealingError("Healing model returned an empty response")

    cleaned = _strip_code_fences(content)
    candidate = _extract_json_object(cleaned)

    try:
        payload = safe_load_json(candidate)
        return HealedRequest.model_validate(payload)
    except (ValueError, json.JSONDecodeError, ValidationError) as exc:
        raise LLMHealingError(
            "Healing model returned invalid structured output"
        ) from exc


def _strip_code_fences(content: str) -> str:
    cleaned = content.strip()
    if cleaned.startswith("```") and cleaned.endswith("```"):
        cleaned = "\n".join(cleaned.splitlines()[1:-1]).strip()
    return cleaned


def _extract_json_object(content: str) -> str:
    """Extract the first top-level JSON object from provider output."""

    stripped = content.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped

    start = stripped.find("{")
    if start == -1:
        return stripped

    depth = 0
    in_string = False
    escape_next = False

    for index in range(start, len(stripped)):
        char = stripped[index]

        if escape_next:
            escape_next = False
            continue

        if char == "\\" and in_string:
            escape_next = True
            continue

        if char == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return stripped[start : index + 1]

    return stripped


def _build_response_format(model_name: str) -> dict[str, object]:
    """Choose the strongest structured output mode supported by the model."""

    normalized = model_name.lower()
    if "gpt-oss-20b" in normalized or "gpt-oss-120b" in normalized:
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "healed_request",
                "strict": False,
                "schema": HealedRequest.model_json_schema(),
            },
        }

    return {"type": "json_object"}


def _configure_litellm_runtime(litellm_module: object) -> None:
    """Reduce noisy provider logs during local runs and demos."""

    setattr(litellm_module, "suppress_debug_info", True)
    logging.getLogger("LiteLLM").setLevel(logging.WARNING)
