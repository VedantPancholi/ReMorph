"""Deterministic reward function for Sprint 4 episodes."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RewardConfig:
    """Scoring constants."""

    success_reward: float = 1.0
    one_cycle_bonus: float = 0.2
    retry_penalty: float = -0.1
    wrong_route_penalty: float = -0.3
    hallucination_penalty: float = -0.5
    safe_abstention_bonus: float = 0.3
    unrecoverable_penalty: float = -1.0


@dataclass(frozen=True)
class RewardSignals:
    """Feature inputs for reward scoring."""

    repaired_success: bool
    fixed_in_one_cycle: bool
    extra_retries: int
    hallucinated_fields: bool
    wrong_route_candidate: bool
    final_recovery_failed: bool
    safe_abstained: bool = False
    unrecoverable: bool = False
    unsafe_hallucinated_repair: bool = False


@dataclass(frozen=True)
class RewardResult:
    """Reward output with explicit factor breakdown."""

    total_reward: float
    breakdown: dict[str, float]


class RewardFunction:
    """Deterministic rule-based reward function."""

    def __init__(self, config: RewardConfig | None = None) -> None:
        self._config = config or RewardConfig()

    def score(self, signals: RewardSignals) -> RewardResult:
        hallucination_penalty = (
            self._config.hallucination_penalty
            if signals.hallucinated_fields or signals.unsafe_hallucinated_repair
            else 0.0
        )
        unrecoverable_penalty = (
            self._config.unrecoverable_penalty
            if signals.final_recovery_failed and not signals.safe_abstained
            else 0.0
        )
        breakdown = {
            "success_reward": self._config.success_reward if signals.repaired_success else 0.0,
            "one_cycle_bonus": self._config.one_cycle_bonus
            if signals.fixed_in_one_cycle and signals.repaired_success
            else 0.0,
            "retry_penalty": self._config.retry_penalty * signals.extra_retries,
            "wrong_route_penalty": self._config.wrong_route_penalty
            if signals.wrong_route_candidate
            else 0.0,
            "hallucination_penalty": hallucination_penalty,
            "safe_abstention_bonus": self._config.safe_abstention_bonus
            if signals.safe_abstained
            else 0.0,
            "unrecoverable_penalty": unrecoverable_penalty,
        }
        breakdown["final_reward"] = round(
            breakdown["success_reward"]
            + breakdown["one_cycle_bonus"]
            + breakdown["retry_penalty"]
            + breakdown["wrong_route_penalty"]
            + breakdown["hallucination_penalty"]
            + breakdown["safe_abstention_bonus"]
            + breakdown["unrecoverable_penalty"],
            4,
        )
        breakdown.update(
            {
                "success_bonus": breakdown["success_reward"],
                "extra_retry_penalty": breakdown["retry_penalty"],
                "hallucinated_fields_penalty": breakdown["hallucination_penalty"],
                "final_failure_penalty": breakdown["unrecoverable_penalty"],
            }
        )
        return RewardResult(
            total_reward=breakdown["final_reward"],
            breakdown=breakdown,
        )
