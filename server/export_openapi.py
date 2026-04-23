import json
import os
from server.main import app

if __name__ == "__main__":
    os.makedirs("specs", exist_ok=True)
    schema = app.openapi()
    with open("specs/openapi.json", "w") as f:
        json.dump(schema, f, indent=2)
    print(f"✅ Exported highly complex FastAPI spec ({len(schema['paths'])} routes) to specs/openapi.json")
