"""JSON serialization helpers."""

import json
from typing import Any


def safe_load_json(raw_json: str) -> dict[str, Any]:
    """Parse JSON into a dictionary with a clear error path."""

    payload = json.loads(raw_json)
    if not isinstance(payload, dict):
        raise ValueError("Expected JSON object at top level")
    return payload


def safe_dump_json(payload: Any) -> str:
    """Serialize a Python object into stable pretty JSON."""

    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True)


def pretty_print_json(payload: Any) -> str:
    """Alias used by callers that want explicitly formatted JSON output."""

    return safe_dump_json(payload)
