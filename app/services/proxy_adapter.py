"""Direct adapter contract for Jenish's proxy layer."""

from __future__ import annotations

from typing import Any

from app.main import process_trapped_error_safe
from app.models.response_models import ProxyFailureEnvelope
from app.services.retry_orchestrator import RequestExecutor, heal_and_retry


def handle_proxy_failure(
    trapped_error_data: dict[str, Any],
    *,
    local_spec_path: str | None = None,
) -> dict[str, Any]:
    """Return a stable response envelope for the external proxy."""

    healed_request, failure_reason = process_trapped_error_safe(
        trapped_error_data,
        local_spec_path=local_spec_path,
    )
    if healed_request is None:
        return ProxyFailureEnvelope(
            contract_version="remorph.proxy.v1",
            status="unrepairable",
            failure_reason=failure_reason or "unknown",
            message="ReMorph could not safely generate a repair.",
        ).model_dump(mode="json")

    return ProxyFailureEnvelope(
        contract_version="remorph.proxy.v1",
        status="healed",
        healed_request=healed_request,
    ).model_dump(mode="json")


def handle_proxy_failure_with_retry(
    trapped_error_data: dict[str, Any],
    execute_request: RequestExecutor,
    *,
    local_spec_path: str | None = None,
    max_retries: int = 1,
) -> dict[str, Any]:
    """Repair the request and run the retry loop through an injected executor."""

    workflow = heal_and_retry(
        trapped_error_data,
        execute_request,
        local_spec_path=local_spec_path,
        max_retries=max_retries,
    )
    return {
        "contract_version": "remorph.proxy.v1",
        "status": workflow.status,
        "workflow_result": workflow.model_dump(mode="json"),
    }
