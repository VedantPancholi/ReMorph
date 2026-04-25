"""Proxy-facing retry loop that uses Sprint 2 to repair and retry requests."""

from __future__ import annotations

from typing import Any, Callable

from app.main import process_trapped_error_safe
from app.models.request_models import TrappedError
from app.models.response_models import (
    HealedRequest,
    ProxyWorkflowResult,
    RetryAttemptRecord,
    UpstreamExecutionResult,
)
from app.services.telemetry import record_workflow_event

RequestExecutor = Callable[[dict[str, Any]], dict[str, Any] | UpstreamExecutionResult]

_REPAIRABLE_RAW_SCENARIOS = {
    "schema_missing_key",
    "schema_type_coercion",
    "schema_extra_key",
    "schema_null_injection",
    "route_regression",
    "route_method_spoof",
    "route_invalid_path",
    "auth_missing_tenant",
}

_UNRECOVERABLE_RAW_SCENARIOS = {
    "auth_missing_token",
    "auth_malformed_jwt",
}


def heal_and_retry(
    trapped_error_data: dict[str, Any],
    execute_request: RequestExecutor,
    *,
    local_spec_path: str | None = None,
    max_retries: int = 1,
) -> ProxyWorkflowResult:
    """Run the repair loop and retry execution using an injected executor."""

    current_error = TrappedError.model_validate(trapped_error_data)
    history: list[RetryAttemptRecord] = []

    for attempt in range(1, max_retries + 2):
        healed, failure_reason = process_trapped_error_safe(
            current_error.model_dump(mode="json"),
            local_spec_path=local_spec_path,
        )
        if healed is None:
            unrepairable = HealedRequest(
                reasoning="ReMorph could not produce a safe repair.",
                fixed_url=current_error.target_url,
                fixed_method=current_error.method,
                fixed_payload=current_error.failed_payload,
                fixed_headers=current_error.failed_headers,
                healing_action="no_change",
                status="unrepairable",
                failure_reason=failure_reason or "unknown",
            )
            result = ProxyWorkflowResult(
                status="failed",
                final_healed_request=_enrich_diagnostics(
                    unrepairable,
                    retry_succeeded=False,
                    total_recovery_steps=attempt,
                    final_reward=_estimate_reward(success=False, attempts=attempt, fallback_used=True),
                ),
                attempts=max(1, attempt),
                history=history,
                request_id=current_error.request_id,
                raw_scenario_type=current_error.raw_scenario_type,
                benchmark_partition=_classify_benchmark_partition(current_error.raw_scenario_type),
            )
            record_workflow_event(result)
            return result

        execution_result = _normalize_execution_result(
            execute_request(
                {
                    "url": healed.fixed_url,
                    "method": healed.fixed_method,
                    "payload": healed.fixed_payload,
                    "headers": healed.fixed_headers,
                    "request_id": current_error.request_id,
                    "attempt_number": attempt,
                }
            )
        )

        history.append(
            RetryAttemptRecord(
                attempt_number=attempt,
                healed_request=healed,
                execution_result=execution_result,
            )
        )

        if execution_result.success:
            result = ProxyWorkflowResult(
                status="success",
                final_healed_request=_enrich_diagnostics(
                    healed,
                    retry_succeeded=True,
                    total_recovery_steps=attempt,
                    final_reward=_estimate_reward(
                        success=True,
                        attempts=attempt,
                        fallback_used=bool(
                            healed.diagnostics and healed.diagnostics.fallback_used
                        ),
                    ),
                ),
                attempts=attempt,
                history=history,
                request_id=current_error.request_id,
                raw_scenario_type=current_error.raw_scenario_type,
                benchmark_partition=_classify_benchmark_partition(current_error.raw_scenario_type),
                policy_name=healed.diagnostics.policy_name if healed.diagnostics else None,
                policy_version=healed.diagnostics.policy_version if healed.diagnostics else None,
                policy_source=healed.diagnostics.policy_source if healed.diagnostics else None,
                policy_run_id=healed.diagnostics.policy_run_id if healed.diagnostics else None,
            )
            record_workflow_event(result)
            return result

        current_error = TrappedError(
            target_url=healed.fixed_url,
            method=healed.fixed_method,
            failed_payload=healed.fixed_payload,
            failed_headers=healed.fixed_headers,
            error_code=execution_result.status_code,
            error_message=execution_result.error_message or "Retry execution failed",
            request_id=current_error.request_id,
            source_component=current_error.source_component or "proxy",
            retry_count=current_error.retry_count + 1,
            raw_scenario_type=current_error.raw_scenario_type,
            failure_signals=current_error.failure_signals,
        )

    result = ProxyWorkflowResult(
        status="failed",
        final_healed_request=_enrich_diagnostics(
            history[-1].healed_request,
            retry_succeeded=False,
            total_recovery_steps=len(history),
            final_reward=_estimate_reward(
                success=False,
                attempts=len(history),
                fallback_used=bool(
                    history[-1].healed_request.diagnostics
                    and history[-1].healed_request.diagnostics.fallback_used
                ),
            ),
        ),
        attempts=len(history),
        history=history,
        request_id=current_error.request_id,
        raw_scenario_type=current_error.raw_scenario_type,
        benchmark_partition=_classify_benchmark_partition(current_error.raw_scenario_type),
        policy_name=history[-1].healed_request.diagnostics.policy_name if history[-1].healed_request.diagnostics else None,
        policy_version=history[-1].healed_request.diagnostics.policy_version if history[-1].healed_request.diagnostics else None,
        policy_source=history[-1].healed_request.diagnostics.policy_source if history[-1].healed_request.diagnostics else None,
        policy_run_id=history[-1].healed_request.diagnostics.policy_run_id if history[-1].healed_request.diagnostics else None,
    )
    record_workflow_event(result)
    return result


def _normalize_execution_result(
    result: dict[str, Any] | UpstreamExecutionResult,
) -> UpstreamExecutionResult:
    if isinstance(result, UpstreamExecutionResult):
        return result
    return UpstreamExecutionResult.model_validate(result)


def _enrich_diagnostics(
    healed_request: HealedRequest,
    *,
    retry_succeeded: bool,
    total_recovery_steps: int,
    final_reward: float,
) -> HealedRequest:
    if healed_request.diagnostics is None:
        return healed_request
    return healed_request.model_copy(
        update={
            "diagnostics": healed_request.diagnostics.model_copy(
                update={
                    "retry_succeeded": retry_succeeded,
                    "total_recovery_steps": total_recovery_steps,
                    "final_reward": final_reward,
                }
            )
        }
    )


def _estimate_reward(*, success: bool, attempts: int, fallback_used: bool) -> float:
    reward = 1.0 if success else -0.5
    if attempts == 1 and success:
        reward += 0.2
    reward -= 0.1 * max(0, attempts - 1)
    if fallback_used:
        reward -= 0.2
    return round(reward, 2)


def _classify_benchmark_partition(raw_scenario_type: str | None) -> str | None:
    if raw_scenario_type in _REPAIRABLE_RAW_SCENARIOS:
        return "repairable"
    if raw_scenario_type in _UNRECOVERABLE_RAW_SCENARIOS:
        return "unrecoverable"
    return "other" if raw_scenario_type else None
