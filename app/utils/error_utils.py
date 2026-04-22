"""Custom exceptions for the healing pipeline."""


class ReMorphError(Exception):
    """Base exception for project-specific failures."""


class DocumentationFetchError(ReMorphError):
    """Raised when the OpenAPI or docs source cannot be loaded."""


class SchemaExtractionError(ReMorphError):
    """Raised when the target route cannot be normalized from the spec."""


class LLMHealingError(ReMorphError):
    """Raised when the healing model fails or returns invalid output."""


class InvalidHealedResponseError(ReMorphError):
    """Reserved for downstream validation failures after model output."""


class AmbiguousRouteMatchError(SchemaExtractionError):
    """Raised when multiple routes are too close to pick confidently."""


class SchemaIncompleteError(ReMorphError):
    """Raised when the extracted schema is too incomplete to repair safely."""


class UnsupportedAuthSchemeError(ReMorphError):
    """Raised when the endpoint requires an auth mode ReMorph cannot repair."""


class NoRepairCandidateError(ReMorphError):
    """Raised when no repair candidate can be generated for the failure."""
