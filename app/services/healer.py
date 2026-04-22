"""End-to-end healing orchestration."""

from time import perf_counter

from app.models.request_models import TrappedError
from app.models.response_models import HealedRequest, RepairDiagnostics
from app.services.repair_cache import (
    build_repair_cache_key,
    get_cached_repair,
    store_cached_repair,
)
from app.services.deterministic_repair import build_deterministic_repair
from app.services.doc_fetcher import fetch_openapi_spec_bundle
from app.services.llm_client import call_healing_model
from app.services.prompt_builder import build_healing_prompt, build_system_prompt
from app.services.schema_extractor import extract_schema_for_route
from app.services.telemetry import record_healing_event
from app.services.url_utils import extract_path
from app.utils.error_utils import (
    LLMHealingError,
    NoRepairCandidateError,
    SchemaIncompleteError,
    UnsupportedAuthSchemeError,
)
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

    spec, spec_metadata = fetch_openapi_spec_bundle(
        trapped_error.target_url,
        local_spec_path=local_spec_path,
    )
    docs_source = spec_metadata.source
    logger.info("Documentation loaded successfully from %s", docs_source)

    endpoint_schema = extract_schema_for_route(
        spec,
        extract_path(trapped_error.target_url),
        trapped_error.method,
    )
    logger.info("Endpoint schema extracted for %s", endpoint_schema.path)

    if "contains_unsupported_auth_scheme" in endpoint_schema.completeness_flags:
        raise UnsupportedAuthSchemeError(
            f"Unsupported auth scheme for {trapped_error.method} {trapped_error.target_url}"
        )
    if endpoint_schema.docs_confidence < 0.35:
        raise SchemaIncompleteError(
            f"Documentation confidence too low for {trapped_error.method} {trapped_error.target_url}"
        )

    cache_key = build_repair_cache_key(
        trapped_error,
        endpoint_schema,
        spec_hash=spec_metadata.spec_hash,
        spec_version=spec_metadata.spec_version,
    )
    cached_repair = get_cached_repair(cache_key)
    if cached_repair is not None:
        logger.info("Using cached repair for %s %s", trapped_error.method, trapped_error.target_url)
        cached_result = _attach_diagnostics(
            cached_repair,
            trapped_error=trapped_error,
            endpoint_path=endpoint_schema.path,
            docs_source=docs_source,
            endpoint_schema=endpoint_schema,
            spec_metadata=spec_metadata,
            repair_strategy="cache",
            llm_attempted=False,
            llm_succeeded=False,
            fallback_used=False,
            processing_ms=_elapsed_ms(started_at),
            failure_reason=None,
        )
        record_healing_event(trapped_error, cached_result)
        return cached_result

    system_prompt = build_system_prompt()
    user_prompt = build_healing_prompt(trapped_error, endpoint_schema)
    logger.info("Healing prompt constructed")

    deterministic_repair = build_deterministic_repair(trapped_error, endpoint_schema)
    logger.info("Deterministic repair prepared with action %s", deterministic_repair.healing_action)
    if deterministic_repair.healing_action == "no_change":
        raise NoRepairCandidateError(
            f"No repair candidate found for {trapped_error.method} {trapped_error.target_url}"
        )

    try:
        healed_request = call_healing_model(system_prompt, user_prompt)
        logger.info("Healing response validated through the model provider")
        merged_repair = _merge_repairs(deterministic_repair, healed_request)
        final_result = _attach_diagnostics(
            merged_repair,
            trapped_error=trapped_error,
            endpoint_path=endpoint_schema.path,
            docs_source=docs_source,
            endpoint_schema=endpoint_schema,
            spec_metadata=spec_metadata,
            repair_strategy="merged",
            llm_attempted=True,
            llm_succeeded=True,
            fallback_used=False,
            processing_ms=_elapsed_ms(started_at),
            failure_reason=None,
        )
        store_cached_repair(cache_key, final_result)
        record_healing_event(trapped_error, final_result)
        return final_result
    except LLMHealingError as exc:
        logger.warning(
            "Falling back to deterministic repair because model healing failed: %s",
            exc,
        )
        final_result = _attach_diagnostics(
            deterministic_repair,
            trapped_error=trapped_error,
            endpoint_path=endpoint_schema.path,
            docs_source=docs_source,
            endpoint_schema=endpoint_schema,
            spec_metadata=spec_metadata,
            repair_strategy="deterministic",
            llm_attempted=True,
            llm_succeeded=False,
            fallback_used=True,
            processing_ms=_elapsed_ms(started_at),
            failure_reason="invalid_llm_output",
        )
        store_cached_repair(cache_key, final_result)
        record_healing_event(trapped_error, final_result)
        return final_result


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
    endpoint_schema,
    spec_metadata,
    repair_strategy: str,
    llm_attempted: bool,
    llm_succeeded: bool,
    fallback_used: bool,
    processing_ms: int,
    failure_reason: str | None,
) -> HealedRequest:
    """Attach runtime diagnostics needed by the proxy and training loop."""

    return healed_request.model_copy(
        update={
            "diagnostics": RepairDiagnostics(
                original_error_code=trapped_error.error_code,
                selected_endpoint_path=endpoint_path,
                docs_source=docs_source,
                repair_strategy=repair_strategy,
                docs_confidence=endpoint_schema.docs_confidence,
                spec_hash=spec_metadata.spec_hash,
                spec_version=spec_metadata.spec_version,
                scenario_type=_infer_scenario_type(trapped_error.error_code),
                llm_attempted=llm_attempted,
                llm_succeeded=llm_succeeded,
                fallback_used=fallback_used,
                processing_ms=processing_ms,
                request_id=trapped_error.request_id,
                source_component=trapped_error.source_component,
                retry_count=trapped_error.retry_count,
                total_recovery_steps=1,
                failure_reason=failure_reason,
            )
        }
    )


def _elapsed_ms(started_at: float) -> int:
    """Convert elapsed perf-counter time to integer milliseconds."""

    return int((perf_counter() - started_at) * 1000)


def _infer_scenario_type(error_code: int) -> str:
    if error_code == 400:
        return "payload_drift"
    if error_code == 401:
        return "auth_drift"
    if error_code == 404:
        return "route_drift"
    return "unknown"
