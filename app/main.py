"""Application entry point for trapped error processing."""

from typing import Any

from app.models.request_models import TrappedError
from app.models.response_models import HealedRequest
from app.services.healer import heal_request
from app.utils.error_utils import (
    AmbiguousRouteMatchError,
    DocumentationFetchError,
    LLMHealingError,
    NoRepairCandidateError,
    SchemaIncompleteError,
    SchemaExtractionError,
    UnsupportedAuthSchemeError,
)


def process_trapped_error(
    trapped_error_data: dict[str, Any],
    *,
    local_spec_path: str | None = None,
) -> dict[str, Any]:
    """Validate input, run the healing flow, and return JSON-safe output."""

    trapped_error = TrappedError.model_validate(trapped_error_data)
    healed_request = heal_request(trapped_error, local_spec_path=local_spec_path)
    return healed_request.model_dump(mode="json")


def process_trapped_error_safe(
    trapped_error_data: dict[str, Any],
    *,
    local_spec_path: str | None = None,
) -> tuple[HealedRequest | None, str | None]:
    """Run repair while converting known failures into stable failure reasons."""

    try:
        trapped_error = TrappedError.model_validate(trapped_error_data)
        healed_request = heal_request(trapped_error, local_spec_path=local_spec_path)
        return healed_request, None
    except DocumentationFetchError:
        return None, "docs_unavailable"
    except AmbiguousRouteMatchError:
        return None, "ambiguous_route_match"
    except SchemaIncompleteError:
        return None, "schema_incomplete"
    except UnsupportedAuthSchemeError:
        return None, "unsupported_auth_scheme"
    except NoRepairCandidateError:
        return None, "no_repair_candidate"
    except (LLMHealingError, SchemaExtractionError):
        return None, "unknown"
