"""Typed dataset contracts for Sprint 4 Phase 2 training and evaluation."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

OutcomeClass = Literal[
    "repair_success",
    "repair_failure",
    "correct_abstain",
    "incorrect_abstain",
    "unsafe_hallucination",
    "unrecoverable_failure",
]

ActionType = Literal[
    "repair_route",
    "repair_payload",
    "repair_auth",
    "abstain",
    "no_op",
]


class CandidateRoute(BaseModel):
    """One route candidate exposed to the policy."""

    path: str
    method: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    source: str = "episode"


class PolicyState(BaseModel):
    """Normalized policy input derived from a benchmark episode."""

    model_config = ConfigDict(extra="forbid")

    episode_id: str
    scenario_type: str
    raw_scenario_type: str
    benchmark_partition: str
    contract_version: str
    request_method: str
    request_path: str
    request_headers: dict[str, str] = Field(default_factory=dict)
    request_query: dict[str, Any] = Field(default_factory=dict)
    request_body: dict[str, Any] | None = None
    failure_code: int | None = None
    failure_message: str | None = None
    failure_signals: dict[str, Any] = Field(default_factory=dict)
    candidate_routes: list[CandidateRoute] = Field(default_factory=list)
    contract_hints: dict[str, Any] = Field(default_factory=dict)
    retry_count: int = Field(default=0, ge=0)


class PolicyAction(BaseModel):
    """Structured action emitted by a policy or heuristic adapter."""

    model_config = ConfigDict(extra="forbid")

    action_type: ActionType
    target_method: str | None = None
    target_path: str | None = None
    header_patch: dict[str, str] | None = None
    query_patch: dict[str, Any] | None = None
    body_patch: dict[str, Any] | None = None
    reason: str | None = None


class RewardBreakdown(BaseModel):
    """Structured reward terms for one transition."""

    model_config = ConfigDict(extra="forbid")

    reward_total: float = 0.0
    reward_success: float = 0.0
    reward_efficiency: float = 0.0
    reward_route_accuracy: float = 0.0
    reward_payload_accuracy: float = 0.0
    reward_auth_safety: float = 0.0
    reward_abstention: float = 0.0
    reward_penalty_retries: float = 0.0
    reward_penalty_hallucination: float = 0.0


class TransitionOutcome(BaseModel):
    """Typed environment feedback after one policy action."""

    model_config = ConfigDict(extra="forbid")

    request_succeeded: bool
    http_status: int | None = None
    retry_count: int = Field(default=0, ge=0)
    selected_route_correct: bool = False
    payload_valid: bool = False
    used_hallucinated_auth: bool = False
    abstained: bool = False
    correct_abstention: bool = False
    max_retries_exceeded: bool = False


class TransitionRow(BaseModel):
    """One RL-style transition row."""

    model_config = ConfigDict(extra="forbid")

    episode_id: str
    state: PolicyState
    action: PolicyAction
    outcome: TransitionOutcome
    next_state: PolicyState | None = None
    reward_breakdown: RewardBreakdown
    done: bool = True
    success: bool
    outcome_class: OutcomeClass
    raw_scenario_type: str
    benchmark_partition: str
    contract_version: str


class SupervisedRow(BaseModel):
    """One supervised warm-start row."""

    model_config = ConfigDict(extra="forbid")

    episode_id: str
    input_text: str
    target_action: PolicyAction
    raw_scenario_type: str
    benchmark_partition: str
    contract_version: str


class EvalResultRow(BaseModel):
    """One normalized evaluation result row."""

    model_config = ConfigDict(extra="forbid")

    manifest_id: str
    group_id: str
    episode_id: str
    policy_name: str
    scenario_type: str
    raw_scenario_type: str
    benchmark_partition: str
    contract_version: str
    source_name: str = "unknown"
    source_record_id: str | None = None
    success: bool
    outcome_class: OutcomeClass
    retries_used: int = Field(default=0, ge=0)
    hallucination_detected: bool = False
    wrong_route_detected: bool = False
    reward_breakdown: RewardBreakdown
