"""End-to-end healing orchestration."""

from time import perf_counter

from app.models.request_models import TrappedError
from app.models.response_models import HealedRequest, RepairDiagnostics
from app.services.deterministic_repair import build_deterministic_repair
from app.services.doc_fetcher import fetch_openapi_spec_with_source
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

    started_at = perf_counter()
    logger.info("Received trapped error for %s %s", trapped_error.method, trapped_error.target_url)

    spec, docs_source = fetch_openapi_spec_with_source(
        trapped_error.target_url,
        local_spec_path=local_spec_path,
    )
    logger.info("Documentation loaded successfully from %s", docs_source)

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
        merged_repair = _merge_repairs(deterministic_repair, healed_request)
        return _attach_diagnostics(
            merged_repair,
            trapped_error=trapped_error,
            endpoint_path=endpoint_schema.path,
            docs_source=docs_source,
            repair_strategy="merged",
            llm_attempted=True,
            llm_succeeded=True,
            fallback_used=False,
            processing_ms=_elapsed_ms(started_at),
        )
    except LLMHealingError as exc:
        logger.warning(
            "Falling back to deterministic repair because model healing failed: %s",
            exc,
        )
        return _attach_diagnostics(
            deterministic_repair,
            trapped_error=trapped_error,
            endpoint_path=endpoint_schema.path,
            docs_source=docs_source,
            repair_strategy="deterministic",
            llm_attempted=True,
            llm_succeeded=False,
            fallback_used=True,
            processing_ms=_elapsed_ms(started_at),
        )


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


def _attach_diagnostics(
    healed_request: HealedRequest,
    *,
    trapped_error: TrappedError,
    endpoint_path: str,
    docs_source: str,
    repair_strategy: str,
    llm_attempted: bool,
    llm_succeeded: bool,
    fallback_used: bool,
    processing_ms: int,
) -> HealedRequest:
    """Attach runtime diagnostics needed by the proxy and training loop."""

    return healed_request.model_copy(
        update={
            "diagnostics": RepairDiagnostics(
                original_error_code=trapped_error.error_code,
                selected_endpoint_path=endpoint_path,
                docs_source=docs_source,
                repair_strategy=repair_strategy,
                llm_attempted=llm_attempted,
                llm_succeeded=llm_succeeded,
                fallback_used=fallback_used,
                processing_ms=processing_ms,
                request_id=trapped_error.request_id,
                source_component=trapped_error.source_component,
                retry_count=trapped_error.retry_count,
            )
        }
    )


def _elapsed_ms(started_at: float) -> int:
    """Convert elapsed perf-counter time to integer milliseconds."""

    return int((perf_counter() - started_at) * 1000)
