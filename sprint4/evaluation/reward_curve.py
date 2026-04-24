"""Reward curve export from training metrics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def export_reward_curve(
    *,
    metrics_path: str,
    output_dir: str,
    require_plot: bool = True,
) -> dict[str, Any]:
    """Read training metrics and export JSON plus PNG reward curves."""

    metrics = _load_json(metrics_path)
    curve_rows = _normalize_curve_rows(metrics)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    reward_curve_json = output / "reward_curve.json"
    reward_curve_png = output / "reward_curve.png"
    reward_curve_json.write_text(
        json.dumps(
            {
                "source_metrics_path": metrics_path,
                "points": curve_rows,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    artifacts: dict[str, Any] = {
        "reward_curve_json": str(reward_curve_json),
        "reward_curve_png": str(reward_curve_png),
        "plot_generated": True,
    }
    try:
        _plot_curve(curve_rows, reward_curve_png)
    except RuntimeError as exc:
        if require_plot:
            raise
        artifacts["reward_curve_png"] = ""
        artifacts["plot_generated"] = False
        artifacts["plot_warning"] = str(exc)
    return artifacts


def _load_json(path: str) -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Training metrics file not found: {path}")
    return json.loads(file_path.read_text(encoding="utf-8"))


def _normalize_curve_rows(metrics: dict[str, Any]) -> list[dict[str, float | int]]:
    rows = metrics.get("metrics") or metrics.get("steps") or []
    normalized: list[dict[str, float | int]] = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            continue
        normalized.append(
            {
                "step": int(row.get("step", index)),
                "epoch": int(row.get("epoch", index)),
                "train_reward": float(row.get("train_reward", row.get("reward", 0.0)) or 0.0),
                "eval_reward": float(row.get("eval_reward", row.get("reward", 0.0)) or 0.0),
            }
        )
    if not normalized:
        raise ValueError("No reward metrics were found in the training metrics file.")
    return normalized


def _plot_curve(points: list[dict[str, float | int]], output_path: Path) -> None:
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "matplotlib is required to export reward curves. Install it with "
            "'.venv/bin/pip install matplotlib'."
        ) from exc

    steps = [int(point["step"]) for point in points]
    train_rewards = [float(point["train_reward"]) for point in points]
    eval_rewards = [float(point["eval_reward"]) for point in points]

    figure = plt.figure(figsize=(8, 4.5))
    axis = figure.add_subplot(111)
    axis.plot(steps, train_rewards, marker="o", linewidth=2, label="train_reward")
    axis.plot(steps, eval_rewards, marker="s", linewidth=2, label="eval_reward")
    axis.set_title("ReMorph Reward Curve")
    axis.set_xlabel("Training Step")
    axis.set_ylabel("Reward")
    axis.grid(alpha=0.3)
    axis.legend()
    figure.tight_layout()
    figure.savefig(output_path, dpi=150)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export reward curve artifacts from training metrics.")
    parser.add_argument("--metrics-path", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    artifacts = export_reward_curve(metrics_path=args.metrics_path, output_dir=args.output_dir)
    print(json.dumps(artifacts, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
