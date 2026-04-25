"""Rebuild telemetry summaries from JSONL event files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.telemetry import rebuild_telemetry_summaries


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild telemetry summary JSON files from JSONL event history.")
    parser.add_argument("--telemetry-dir", default="runtime/telemetry")
    args = parser.parse_args()
    result = rebuild_telemetry_summaries(args.telemetry_dir)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
