"""Generate PNG plot artifacts for the clean submission repo without extra dependencies."""

from __future__ import annotations

import json
from pathlib import Path
import struct
import sys
import zlib

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

WIDTH = 720
HEIGHT = 480
WHITE = (255, 255, 255)
BLACK = (20, 24, 28)
BLUE = (52, 120, 246)
GREEN = (40, 167, 69)
RED = (220, 53, 69)
ORANGE = (255, 159, 67)
GRAY = (220, 225, 232)


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _blank_canvas(width: int = WIDTH, height: int = HEIGHT) -> list[list[tuple[int, int, int]]]:
    return [[WHITE for _ in range(width)] for _ in range(height)]


def _set_pixel(canvas, x: int, y: int, color) -> None:
    if 0 <= x < WIDTH and 0 <= y < HEIGHT:
        canvas[y][x] = color


def _draw_line(canvas, x1: int, y1: int, x2: int, y2: int, color) -> None:
    dx = abs(x2 - x1)
    dy = -abs(y2 - y1)
    sx = 1 if x1 < x2 else -1
    sy = 1 if y1 < y2 else -1
    err = dx + dy
    while True:
        for offset_x in range(-1, 2):
            for offset_y in range(-1, 2):
                _set_pixel(canvas, x1 + offset_x, y1 + offset_y, color)
        if x1 == x2 and y1 == y2:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x1 += sx
        if e2 <= dx:
            err += dx
            y1 += sy


def _draw_rect(canvas, x: int, y: int, width: int, height: int, color) -> None:
    for yy in range(y, y + height):
        for xx in range(x, x + width):
            _set_pixel(canvas, xx, yy, color)


def _draw_axes(canvas) -> None:
    _draw_line(canvas, 60, 40, 60, 420, BLACK)
    _draw_line(canvas, 60, 420, 680, 420, BLACK)
    for y in range(80, 421, 68):
        _draw_line(canvas, 60, y, 680, y, GRAY)


def _value_to_y(value: float, max_value: float) -> int:
    usable_height = 320
    if max_value <= 0:
        return 420
    normalized = min(max(value / max_value, 0.0), 1.0)
    return int(420 - normalized * usable_height)


def _save_png(path: Path, canvas) -> None:
    raw = b"".join(
        b"\x00" + b"".join(bytes(pixel) for pixel in row)
        for row in canvas
    )

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack("!I", len(data))
            + tag
            + data
            + struct.pack("!I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack("!2I5B", WIDTH, HEIGHT, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, level=9))
    png += chunk(b"IEND", b"")
    path.write_bytes(png)


def _line_chart(values: list[float], path: Path, color) -> None:
    canvas = _blank_canvas()
    _draw_axes(canvas)
    if not values:
        _save_png(path, canvas)
        return
    max_value = max(values) if max(values) > 0 else 1.0
    step = 620 // max(1, len(values) - 1)
    points = [(60 + index * step, _value_to_y(value, max_value)) for index, value in enumerate(values)]
    for first, second in zip(points, points[1:]):
        _draw_line(canvas, first[0], first[1], second[0], second[1], color)
    for point in points:
        _draw_rect(canvas, point[0] - 3, point[1] - 3, 7, 7, color)
    _save_png(path, canvas)


def _bar_chart(values: list[float], path: Path, colors: list[tuple[int, int, int]]) -> None:
    canvas = _blank_canvas()
    _draw_axes(canvas)
    max_value = max(values) if values and max(values) > 0 else 1.0
    bar_width = 100
    gap = 35
    start_x = 90
    for index, value in enumerate(values):
        height = max(1, int((value / max_value) * 300))
        x = start_x + index * (bar_width + gap)
        y = 420 - height
        _draw_rect(canvas, x, y, bar_width, height, colors[index % len(colors)])
    _save_png(path, canvas)


def main() -> None:
    training_dir = REPO_ROOT / "artifacts" / "submission" / "training_run"
    plots_dir = REPO_ROOT / "artifacts" / "submission" / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    loss_history = _load_json(training_dir / "loss_history.json")
    reward_history = _load_json(training_dir / "reward_history.json")
    eval_summary = _load_json(training_dir / "eval_summary.json")

    mismatches = [row["mismatch_rate"] for row in loss_history]
    avg_rewards = [row["average_normalized_reward"] for row in reward_history]

    labels = ["baseline", "replay", "supervised", "oracle"]
    success_values = [eval_summary[label]["success_rate"] for label in labels]
    reward_values = [eval_summary[label]["average_episode_normalized_return_capped"] for label in labels]
    train_eval_labels = [
        ("baseline_train", next((row["success_rate"] for row in reward_history if row["policy_name"] == "baseline" and row["split"] == "train"), 0.0)),
        ("baseline_eval", next((row["success_rate"] for row in reward_history if row["policy_name"] == "baseline" and row["split"] == "eval"), 0.0)),
        ("supervised_train", next((row["success_rate"] for row in reward_history if row["policy_name"] == "supervised" and row["split"] == "train"), 0.0)),
        ("supervised_eval", next((row["success_rate"] for row in reward_history if row["policy_name"] == "supervised" and row["split"] == "eval"), 0.0)),
    ]
    train_eval_reward_values = [
        next((row["average_raw_reward"] for row in reward_history if row["policy_name"] == "baseline" and row["split"] == "train"), 0.0),
        next((row["average_raw_reward"] for row in reward_history if row["policy_name"] == "baseline" and row["split"] == "eval"), 0.0),
        next((row["average_raw_reward"] for row in reward_history if row["policy_name"] == "supervised" and row["split"] == "train"), 0.0),
        next((row["average_raw_reward"] for row in reward_history if row["policy_name"] == "supervised" and row["split"] == "eval"), 0.0),
    ]

    _line_chart(mismatches, plots_dir / "loss_curve.png", BLUE)
    _line_chart(avg_rewards, plots_dir / "reward_curve.png", GREEN)
    _bar_chart(success_values, plots_dir / "success_rate_comparison.png", [BLUE, ORANGE, GREEN, RED])
    _bar_chart(reward_values, plots_dir / "avg_reward_comparison.png", [BLUE, ORANGE, GREEN, RED])
    _bar_chart([value for _, value in train_eval_labels], plots_dir / "train_eval_success_comparison.png", [BLUE, ORANGE, GREEN, RED])
    _bar_chart(train_eval_reward_values, plots_dir / "train_eval_raw_reward_comparison.png", [BLUE, ORANGE, GREEN, RED])

    print(json.dumps({"status": "ok", "plots_dir": str(plots_dir)}, indent=2))


if __name__ == "__main__":
    main()
