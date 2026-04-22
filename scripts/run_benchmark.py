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
from sprint4.evaluation.benchmark_runner import run_benchmark


def main() -> None:
    settings = get_sprint4_settings()
    parser = argparse.ArgumentParser(description="Run Sprint 4 benchmark.")
    parser.add_argument("--episodes-per-scenario", type=int, default=1)
    parser.add_argument("--output-dir", default=settings.BENCHMARK_OUTPUT_DIR)
    parser.add_argument("--backend", choices=["simulated", "openenv"], default=settings.ENV_BACKEND)
    parser.add_argument("--openenv-client-module", default=settings.OPENENV_CLIENT_MODULE)
    parser.add_argument("--openenv-client-class", default=settings.OPENENV_CLIENT_CLASS)
    parser.add_argument("--openenv-base-url", default=settings.OPENENV_BASE_URL)
    parser.add_argument("--openenv-strict", action="store_true", default=settings.OPENENV_STRICT)
    args = parser.parse_args()

    openenv_config = OpenEnvClientConfig(
        module=args.openenv_client_module,
        class_name=args.openenv_client_class,
        base_url=args.openenv_base_url or None,
        strict=bool(args.openenv_strict),
    )
    report = run_benchmark(
        bundle=load_contract_bundle(),
        episodes_per_scenario=args.episodes_per_scenario,
        output_dir=args.output_dir,
        backend=args.backend,
        openenv_config=openenv_config if args.backend == "openenv" else None,
    )
    print(json.dumps(report["artifacts"], indent=2))


if __name__ == "__main__":
    main()
