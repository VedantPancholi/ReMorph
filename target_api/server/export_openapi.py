import json
from pathlib import Path

from target_api.server.main import app

if __name__ == "__main__":
    output_path = Path(__file__).resolve().parents[1] / "specs" / "openapi.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    schema = app.openapi()
    output_path.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    print(
        "✅ Exported highly complex FastAPI spec "
        f"({len(schema['paths'])} routes) to {output_path}"
    )
