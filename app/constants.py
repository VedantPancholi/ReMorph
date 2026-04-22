"""Shared constants used across the healing engine."""

SUPPORTED_HTTP_METHODS = {
    "GET",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
    "OPTIONS",
    "HEAD",
}

SUPPORTED_ERROR_CODES = {400, 401, 404}

HEALING_ACTIONS = (
    "payload_rewrite",
    "route_rewrite",
    "auth_rewrite",
    "combined_rewrite",
    "no_change",
)

LOG_PREFIX = "[ReMorph]"
