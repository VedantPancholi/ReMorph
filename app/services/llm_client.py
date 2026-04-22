"""LLM client wrapper for healing requests."""

from __future__ import annotations

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
        from litellm import completion
    except ImportError as exc:
        raise LLMHealingError("litellm is not installed") from exc

    try:
        response = completion(
            model=settings.LLM_MODEL,
            api_key=settings.GROQ_API_KEY,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
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
    payload = safe_load_json(cleaned)
    return HealedRequest.model_validate(payload)


def _strip_code_fences(content: str) -> str:
    cleaned = content.strip()
    if cleaned.startswith("```") and cleaned.endswith("```"):
        cleaned = "\n".join(cleaned.splitlines()[1:-1]).strip()
    return cleaned
