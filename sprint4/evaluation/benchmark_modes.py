"""Benchmark runtime wrappers for cache- and telemetry-controlled runs."""

from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterator, Literal

from app.config import get_settings
from sprint4.evaluation.benchmark_runner import run_benchmark
from sprint4.evaluation.metrics_report import write_json_report, write_markdown_summary

CacheMode = Literal["reuse", "clear", "disable"]


@dataclass(frozen=True)
class BenchmarkRuntimeMode:
    """Runtime controls layered on top of the benchmark runner."""

    cache_mode: CacheMode = "reuse"
    telemetry_enabled: bool = True
    cache_path: str | None = None
    telemetry_dir: str | None = None


@contextmanager
def benchmark_runtime_mode(mode: BenchmarkRuntimeMode) -> Iterator[None]:
    """Temporarily apply cache and telemetry settings for one benchmark run."""

    previous = {
        "REMORPH_ENABLE_REPAIR_CACHE": os.environ.get("REMORPH_ENABLE_REPAIR_CACHE"),
        "REMORPH_ENABLE_TELEMETRY": os.environ.get("REMORPH_ENABLE_TELEMETRY"),
        "REMORPH_REPAIR_CACHE_PATH": os.environ.get("REMORPH_REPAIR_CACHE_PATH"),
        "REMORPH_TELEMETRY_DIR": os.environ.get("REMORPH_TELEMETRY_DIR"),
    }
    try:
        os.environ["REMORPH_ENABLE_REPAIR_CACHE"] = (
            "false" if mode.cache_mode == "disable" else "true"
        )
        os.environ["REMORPH_ENABLE_TELEMETRY"] = "true" if mode.telemetry_enabled else "false"
        if mode.cache_path:
            os.environ["REMORPH_REPAIR_CACHE_PATH"] = mode.cache_path
        if mode.telemetry_dir:
            os.environ["REMORPH_TELEMETRY_DIR"] = mode.telemetry_dir

        get_settings.cache_clear()
        settings = get_settings()
        if mode.cache_mode == "clear":
            cache_path = Path(settings.REPAIR_CACHE_PATH)
            if cache_path.exists():
                cache_path.unlink()
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def run_benchmark_with_mode(
    *,
    mode: BenchmarkRuntimeMode | None = None,
    **benchmark_kwargs: Any,
) -> dict[str, Any]:
    """Run the existing benchmark under one cache/telemetry mode."""

    active_mode = mode or BenchmarkRuntimeMode()
    with benchmark_runtime_mode(active_mode):
        report = run_benchmark(**benchmark_kwargs)

    metadata = report.setdefault("metadata", {})
    metadata["runtime_mode"] = asdict(active_mode)

    artifacts = report.get("artifacts", {})
    json_path = artifacts.get("json_report")
    markdown_path = artifacts.get("markdown_summary")
    if isinstance(json_path, str):
        write_json_report(report, json_path)
    if isinstance(markdown_path, str):
        write_markdown_summary(report, markdown_path)
    return report
