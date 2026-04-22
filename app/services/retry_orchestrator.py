"""Proxy-facing retry loop that uses Sprint 2 to repair and retry requests."""

from __future__ import annotations

from typing import Any, Callable

from app.main import process_trapped_error
from app.models.request_models import TrappedError
from app.models.response_models import (
    HealedRequest,
    ProxyWorkflowResult,
    RetryAttemptRecord,
    UpstreamExecutionResult,
)
from app.services.telemetry import record_workflow_event

RequestExecutor = Callable[[dict[str, Any]], dict[str, Any] | UpstreamExecutionResult]


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
        healed = HealedRequest.model_validate(
            process_trapped_error(
                current_error.model_dump(mode="json"),
                local_spec_path=local_spec_path,
            )
        )

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
                final_healed_request=healed,
                attempts=attempt,
                history=history,
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
        )

    result = ProxyWorkflowResult(
        status="failed",
        final_healed_request=history[-1].healed_request,
        attempts=len(history),
        history=history,
    )
    record_workflow_event(result)
    return result


def _normalize_execution_result(
    result: dict[str, Any] | UpstreamExecutionResult,
) -> UpstreamExecutionResult:
    if isinstance(result, UpstreamExecutionResult):
        return result
    return UpstreamExecutionResult.model_validate(result)
