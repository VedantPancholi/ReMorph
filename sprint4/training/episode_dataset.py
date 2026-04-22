"""Dataset builders from Sprint 4 JSONL episodes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_episode_jsonl(path: str) -> list[dict[str, Any]]:
    """Load JSONL episodes into memory."""
    episodes: list[dict[str, Any]] = []
    file_path = Path(path)
    if not file_path.exists():
        return episodes
    with file_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                episodes.append(json.loads(line))
    return episodes


def to_grpo_samples(episodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert episodes to a tiny prompt/reward schema usable by demo trainers."""
    rows: list[dict[str, Any]] = []
    for item in episodes:
        trapped_error = item.get("trapped_error") or {}
        prompt = (
            f"error_code={trapped_error.get('error_code')} "
            f"method={trapped_error.get('method')} "
            f"url={trapped_error.get('target_url')} "
            f"message={trapped_error.get('error_message')}"
        )
        rows.append(
            {
                "prompt": prompt,
                "reward": float(item.get("reward", 0.0)),
                "success": bool(item.get("success", False)),
                "scenario_type": item.get("scenario_type", "unknown"),
            }
        )
    return rows

