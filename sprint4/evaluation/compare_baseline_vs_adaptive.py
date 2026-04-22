"""Comparison utilities for baseline vs adaptive episode outcomes."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentAggregate:
    """Aggregate metrics for one agent mode."""

    success_rate: float
    avg_retries: float
    avg_latency_ms: float
    reward_average: float
    per_scenario_accuracy: dict[str, float]


def compare_agents(
    baseline: AgentAggregate,
    adaptive: AgentAggregate,
) -> dict[str, float]:
    """Return simple adaptive-minus-baseline deltas."""
    return {
        "success_rate_delta": round(adaptive.success_rate - baseline.success_rate, 4),
        "avg_retries_delta": round(adaptive.avg_retries - baseline.avg_retries, 4),
        "avg_latency_delta_ms": round(adaptive.avg_latency_ms - baseline.avg_latency_ms, 4),
        "reward_average_delta": round(adaptive.reward_average - baseline.reward_average, 4),
    }

