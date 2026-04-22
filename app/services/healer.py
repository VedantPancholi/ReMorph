"""End-to-end healing orchestration."""

from app.models.request_models import TrappedError
from app.models.response_models import HealedRequest
from app.services.deterministic_repair import build_deterministic_repair
from app.services.doc_fetcher import fetch_openapi_spec
from app.services.llm_client import call_healing_model
from app.services.prompt_builder import build_healing_prompt, build_system_prompt
from app.services.schema_extractor import extract_schema_for_route
from app.services.url_utils import extract_path
from app.utils.error_utils import LLMHealingError
from app.utils.logger import get_logger

logger = get_logger(__name__)


def heal_request(
    trapped_error: TrappedError,
    *,
    local_spec_path: str | None = None,
) -> HealedRequest:
    """Run the healing pipeline for a trapped request failure."""

    logger.info("Received trapped error for %s %s", trapped_error.method, trapped_error.target_url)

    spec = fetch_openapi_spec(
        trapped_error.target_url,
        local_spec_path=local_spec_path,
    )
    logger.info("Documentation loaded successfully")

    endpoint_schema = extract_schema_for_route(
        spec,
        extract_path(trapped_error.target_url),
        trapped_error.method,
    )
    logger.info("Endpoint schema extracted for %s", endpoint_schema.path)

    system_prompt = build_system_prompt()
    user_prompt = build_healing_prompt(trapped_error, endpoint_schema)
    logger.info("Healing prompt constructed")

    deterministic_repair = build_deterministic_repair(trapped_error, endpoint_schema)
    logger.info("Deterministic repair prepared with action %s", deterministic_repair.healing_action)

    try:
        healed_request = call_healing_model(system_prompt, user_prompt)
        logger.info("Healing response validated through the model provider")
        return _merge_repairs(deterministic_repair, healed_request)
    except LLMHealingError as exc:
        logger.warning(
            "Falling back to deterministic repair because model healing failed: %s",
            exc,
        )
        return deterministic_repair


def _merge_repairs(
    deterministic_repair: HealedRequest,
    llm_repair: HealedRequest,
) -> HealedRequest:
    """Prefer validated LLM output while preserving deterministic coverage."""

    return HealedRequest(
        reasoning=llm_repair.reasoning or deterministic_repair.reasoning,
        fixed_url=llm_repair.fixed_url or deterministic_repair.fixed_url,
        fixed_method=llm_repair.fixed_method or deterministic_repair.fixed_method,
        fixed_payload=llm_repair.fixed_payload
        if llm_repair.fixed_payload is not None
        else deterministic_repair.fixed_payload,
        fixed_headers=llm_repair.fixed_headers
        if llm_repair.fixed_headers is not None
        else deterministic_repair.fixed_headers,
        schema_summary=llm_repair.schema_summary or deterministic_repair.schema_summary,
        healing_action=llm_repair.healing_action or deterministic_repair.healing_action,
        confidence=llm_repair.confidence or deterministic_repair.confidence,
    )
