"""Run Sprint 4 benchmark and emit JSON + markdown artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sprint4.config import get_sprint4_settings
from sprint4.env.factory import OpenEnvClientConfig
from sprint4.env.scenario_loader import load_contract_bundle
from sprint4.evaluation.benchmark_modes import BenchmarkRuntimeMode, run_benchmark_with_mode


def main() -> None:
    settings = get_sprint4_settings()
    parser = argparse.ArgumentParser(description="Run Sprint 4 benchmark.")
    parser.add_argument("--episodes-per-scenario", type=int, default=1)
    parser.add_argument("--output-dir", default=settings.BENCHMARK_OUTPUT_DIR)
    parser.add_argument("--env-mode", choices=["local", "live"], default=settings.ENV_MODE)
    parser.add_argument("--backend", choices=["simulated", "live", "openenv"], default=settings.ENV_BACKEND)
    parser.add_argument("--live-base-url", default=settings.LIVE_BASE_URL)
    parser.add_argument("--live-spec-path", default=settings.LIVE_SPEC_PATH)
    parser.add_argument("--live-dataset-path", default=settings.LIVE_DATASET_PATH)
    parser.add_argument("--live-scenario-selection", choices=["representative", "all"], default="representative")
    parser.add_argument("--live-raw-scenario", default="")
    parser.add_argument("--openenv-client-module", default=settings.OPENENV_CLIENT_MODULE)
    parser.add_argument("--openenv-client-class", default=settings.OPENENV_CLIENT_CLASS)
    parser.add_argument("--openenv-base-url", default=settings.OPENENV_BASE_URL)
    parser.add_argument("--openenv-strict", action="store_true", default=settings.OPENENV_STRICT)
    parser.add_argument("--cache-mode", choices=["reuse", "clear", "disable"], default="reuse")
    parser.add_argument("--disable-telemetry", action="store_true")
    parser.add_argument("--cache-path", default="")
    parser.add_argument("--telemetry-dir", default="")
    args = parser.parse_args()

    openenv_config = OpenEnvClientConfig(
        module=args.openenv_client_module,
        class_name=args.openenv_client_class,
        base_url=args.openenv_base_url or None,
        strict=bool(args.openenv_strict),
    )
    report = run_benchmark_with_mode(
        bundle=load_contract_bundle(),
        episodes_per_scenario=args.episodes_per_scenario,
        output_dir=args.output_dir,
        backend=args.backend,
        env_mode=args.env_mode,
        live_base_url=args.live_base_url,
        live_spec_path=args.live_spec_path,
        live_dataset_path=args.live_dataset_path,
        live_scenario_selection=args.live_scenario_selection,
        live_raw_scenario_filter=args.live_raw_scenario or None,
        openenv_config=openenv_config if args.backend == "openenv" else None,
        mode=BenchmarkRuntimeMode(
            cache_mode=args.cache_mode,
            telemetry_enabled=not args.disable_telemetry,
            cache_path=args.cache_path or None,
            telemetry_dir=args.telemetry_dir or None,
        ),
    )
    print(json.dumps(report["artifacts"], indent=2))


if __name__ == "__main__":
    main()
