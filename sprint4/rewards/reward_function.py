"""Deterministic reward function for Sprint 4 episodes."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RewardConfig:
    """Scoring constants."""

    success_bonus: float = 1.0
    one_cycle_bonus: float = 0.2
    extra_retry_penalty: float = -0.1
    hallucinated_fields_penalty: float = -0.2
    wrong_route_penalty: float = -0.3
    final_failure_penalty: float = -1.0


@dataclass(frozen=True)
class RewardSignals:
    """Feature inputs for reward scoring."""

    repaired_success: bool
    fixed_in_one_cycle: bool
    extra_retries: int
    hallucinated_fields: bool
    wrong_route_candidate: bool
    final_recovery_failed: bool


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
        breakdown = {
            "success_bonus": self._config.success_bonus if signals.repaired_success else 0.0,
            "one_cycle_bonus": self._config.one_cycle_bonus
            if signals.fixed_in_one_cycle
            else 0.0,
            "extra_retry_penalty": self._config.extra_retry_penalty * signals.extra_retries,
            "hallucinated_fields_penalty": self._config.hallucinated_fields_penalty
            if signals.hallucinated_fields
            else 0.0,
            "wrong_route_penalty": self._config.wrong_route_penalty
            if signals.wrong_route_candidate
            else 0.0,
            "final_failure_penalty": self._config.final_failure_penalty
            if signals.final_recovery_failed
            else 0.0,
        }
        return RewardResult(
            total_reward=round(sum(breakdown.values()), 4),
            breakdown=breakdown,
        )

