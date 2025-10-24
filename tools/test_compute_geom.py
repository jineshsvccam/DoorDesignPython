import sys
from pathlib import Path

# Ensure project root is on sys.path so imports from fastapi_app work
sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi_app.schemas_input import DoorDXFRequest, DoorInfo, DimensionInfo, DefaultInfo
from fastapi_app.schemas_output import Metadata
from door_geometry import compute_door_geometry

# Construct the request based on the user's JSON
door_info = DoorInfo(category="Single", type="normal", option=None, hole_offset="80x40", default_allowance="yes")
dims = DimensionInfo(
    width_measurement=600,
    height_measurement=800,
    left_side_allowance_width=25,
    right_side_allowance_width=25,
    top_side_allowance_height=25,
    bottom_side_allowance_height=25,
)
metadata = Metadata(label="Single_door", file_name="Single_door.dxf", width=0, height=0)
defaults = DefaultInfo()

req = DoorDXFRequest(mode="generate", door=door_info, dimensions=dims, metadata=metadata, defaults=defaults)

out = compute_door_geometry(req)
print(out.model_dump_json(indent=2) if hasattr(out, 'model_dump_json') else out.json(indent=2))
