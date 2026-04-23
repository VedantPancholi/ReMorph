"""Lightweight policy adapter abstraction for Sprint 4 training demos."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PolicyBatch:
    """Minimal policy training batch format."""

    prompts: list[str]
    completions: list[str]
    rewards: list[float]
    metadata: list[dict[str, Any]]


def build_policy_batch(samples: list[dict[str, Any]]) -> PolicyBatch:
    """Create a policy batch from GRPO-style samples."""
    return PolicyBatch(
        prompts=[str(sample["prompt"]) for sample in samples],
        completions=[str(sample["completion"]) for sample in samples],
        rewards=[float(sample["reward"]) for sample in samples],
        metadata=[
            {
                "scenario_type": sample.get("scenario_type"),
                "success": sample.get("success"),
                "reward": sample.get("reward"),
            }
            for sample in samples
        ],
    )
