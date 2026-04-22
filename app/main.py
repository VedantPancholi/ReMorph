"""Application entry point for trapped error processing."""

from typing import Any

from app.models.request_models import TrappedError
from app.services.healer import heal_request


def process_trapped_error(
    trapped_error_data: dict[str, Any],
    *,
    local_spec_path: str | None = None,
) -> dict[str, Any]:
    """Validate input, run the healing flow, and return JSON-safe output."""

    trapped_error = TrappedError.model_validate(trapped_error_data)
    healed_request = heal_request(trapped_error, local_spec_path=local_spec_path)
    return healed_request.model_dump(mode="json")
