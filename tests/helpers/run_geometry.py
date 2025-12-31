import sys
import json
from pathlib import Path

# Ensure repository root is on sys.path so imports like `fastapi_app` resolve
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from fastapi_app.schemas_input import DoorDXFRequest
from geometry.door_geometry import compute_door_geometry


def parse_model(data: dict) -> DoorDXFRequest:
    if hasattr(DoorDXFRequest, "model_validate"):
        return DoorDXFRequest.model_validate(data)
    return DoorDXFRequest.parse_obj(data)


def compute_output(input_json: dict) -> dict:
    req = parse_model(input_json)
    output = compute_door_geometry(req)

    if hasattr(output, "model_dump"):
        return output.model_dump()
    return json.loads(output.json())
