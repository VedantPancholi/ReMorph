"""Output models for healed requests."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.constants import HEALING_ACTIONS, SUPPORTED_HTTP_METHODS

HealingAction = Literal[
    "payload_rewrite",
    "route_rewrite",
    "auth_rewrite",
    "combined_rewrite",
    "no_change",
]

RepairStrategy = Literal["deterministic", "llm", "merged", "cache"]
RepairStatus = Literal["healed", "unrepairable"]
FailureReason = Literal[
    "docs_unavailable",
    "ambiguous_route_match",
    "schema_incomplete",
    "invalid_llm_output",
    "unsupported_auth_scheme",
    "no_repair_candidate",
    "unknown",
]


class RepairDiagnostics(BaseModel):
    """Operational metadata used by proxy integration and Sprint 4 evaluation."""

    original_error_code: int
    selected_endpoint_path: str
    docs_source: str
    repair_strategy: RepairStrategy
    docs_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    spec_hash: str | None = None
    spec_version: str | None = None
    scenario_type: str | None = None
    llm_attempted: bool = False
    llm_succeeded: bool = False
    fallback_used: bool = False
    processing_ms: int | None = Field(default=None, ge=0)
    request_id: str | None = None
    source_component: str | None = None
    retry_count: int = Field(default=0, ge=0)
    retry_succeeded: bool | None = None
    total_recovery_steps: int | None = Field(default=None, ge=0)
    final_reward: float | None = None
    failure_reason: FailureReason | None = None


class HealedRequest(BaseModel):
    """Validated request repair emitted by the reasoning layer."""

    model_config = ConfigDict(extra="forbid")

    reasoning: str
    fixed_url: str
    fixed_method: str
    fixed_payload: dict[str, Any] | None = None
    fixed_headers: dict[str, str] | None = None
    schema_summary: dict[str, Any] | None = None
    healing_action: HealingAction = "no_change"
    status: RepairStatus = "healed"
    failure_reason: FailureReason | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    diagnostics: RepairDiagnostics | None = None

    @field_validator("fixed_method")
    @classmethod
    def normalize_method(cls, value: str) -> str:
        method = value.upper()
        if method not in SUPPORTED_HTTP_METHODS:
            raise ValueError(f"Unsupported fixed method: {value}")
        return method

    @field_validator("healing_action")
    @classmethod
    def validate_action(cls, value: str) -> str:
        if value not in HEALING_ACTIONS:
            raise ValueError(f"Unsupported healing action: {value}")
        return value


class UpstreamExecutionResult(BaseModel):
    """Normalized result returned by a proxy or request executor."""

    success: bool
    status_code: int
    response_body: dict[str, Any] | None = None
    error_message: str | None = None


class RetryAttemptRecord(BaseModel):
    """One repair and retry attempt inside the orchestrated loop."""

    attempt_number: int
    healed_request: HealedRequest
    execution_result: UpstreamExecutionResult


class ProxyWorkflowResult(BaseModel):
    """Full response returned to an external orchestrator such as Jenish's proxy."""

    status: Literal["success", "failed"]
    final_healed_request: HealedRequest
    attempts: int = Field(ge=1)
    history: list[RetryAttemptRecord] = Field(default_factory=list)


class ProxyFailureEnvelope(BaseModel):
    """Stable external contract returned when repair succeeds or fails."""

    contract_version: str
    status: RepairStatus
    healed_request: HealedRequest | None = None
    failure_reason: FailureReason | None = None
    message: str | None = None
