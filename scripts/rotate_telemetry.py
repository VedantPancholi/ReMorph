"""Rotate telemetry JSONL files using the configured retention policy."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.services.telemetry import rotate_telemetry_logs


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Rotate telemetry JSONL files.")
    parser.add_argument("--telemetry-dir", default=settings.TELEMETRY_DIR)
    parser.add_argument("--max-bytes", type=int, default=settings.TELEMETRY_MAX_JSONL_BYTES)
    parser.add_argument("--max-rotated-files", type=int, default=settings.TELEMETRY_MAX_ROTATED_FILES)
    args = parser.parse_args()
    result = rotate_telemetry_logs(
        args.telemetry_dir,
        max_bytes=args.max_bytes,
        max_rotated_files=args.max_rotated_files,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
