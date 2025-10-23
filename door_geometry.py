from typing import Tuple, Optional, List
from pathlib import Path

from fastapi_app.schemas_output import (
    SchemasOutput,
    Metadata,
    Geometry,
    Frame,
    Cutout,
    Hole,
    Label,
)
from fastapi_app.schemas_input import DoorDXFRequest, DefaultInfo


def compute_door_geometry(request: DoorDXFRequest, rotated: bool = False, offset: Tuple[float, float] = (0.0, 0.0)) -> SchemasOutput:
    """Compute door geometry points and return a SchemasOutput object.

    This extracts the geometry calculation logic from DoorDrawingGenerator.generate_door_dxf
    and returns structured data representing frames, cutouts, holes, and labels.
    """

    # Extract values from request and merge with defaults
    door = request.door
    dims = request.dimensions
    defaults: DefaultInfo = request.defaults

    # DimensionInfo now contains width/height and allowances
    width_measurement = dims.width_measurement
    height_measurement = dims.height_measurement

    left_side_allowance_width = dims.left_side_allowance_width
    right_side_allowance_width = dims.right_side_allowance_width
    # DimensionInfo uses top/bottom naming for height allowances
    left_side_allowance_height = dims.top_side_allowance_height
    right_side_allowance_height = dims.bottom_side_allowance_height

    # Door-minus and bending values come from defaults (or could be added to dimensions)
    door_minus_measurement_width = defaults.door_minus_measurement_width
    door_minus_measurement_height = defaults.door_minus_measurement_height
    bending_width = defaults.bending_width
    bending_height = defaults.bending_height

    label_name = request.metadata.label if hasattr(request.metadata, 'label') else None
    file_name = request.metadata.file_name if hasattr(request.metadata, 'file_name') else None

    # Basic validation
    if width_measurement <= 0 or height_measurement <= 0:
        raise ValueError("Width and height must be positive numbers.")

    # Calculate geometry same as in DoorDrawingGenerator
    frame_total_width = width_measurement + left_side_allowance_width + right_side_allowance_width
    frame_total_height = height_measurement + left_side_allowance_height + right_side_allowance_height
    inner_width = frame_total_width - door_minus_measurement_width
    inner_height = frame_total_height - door_minus_measurement_height
    outer_width = inner_width + bending_width
    outer_height = inner_height + bending_height
    bend_adjust = defaults.bend_adjust
    inner_offset_x = bending_width - bend_adjust
    inner_offset_y = bend_adjust - bending_height

    # Local points (before translation/rotation)
    outer_pts = [
        (0, 0),
        (outer_width, 0),
        (outer_width, inner_height),
        (0, inner_height),
        (0, 0),
    ]


    inner_pts = [
        (inner_offset_x, inner_offset_y),
        (inner_offset_x + inner_width, inner_offset_y),
        (inner_offset_x + inner_width, inner_offset_y + outer_height),
        (inner_offset_x, inner_offset_y + outer_height),
        (inner_offset_x, inner_offset_y),
    ]

    # center box
    box_gap = defaults.box_gap
    box_width = defaults.box_width
    box_height = defaults.box_height
    box_left_x = inner_offset_x + box_gap
    box_bottom_y = inner_offset_y + ((inner_height + bending_height - box_height) / 2.0)
    box_pts = [
        (box_left_x, box_bottom_y),
        (box_left_x + box_width, box_bottom_y),
        (box_left_x + box_width, box_bottom_y + box_height),
        (box_left_x, box_bottom_y + box_height),
        (box_left_x, box_bottom_y),
    ]

    # circles
    left_circle_offset = defaults.left_circle_offset
    top_circle_offset = defaults.top_circle_offset
    circle_center_x = inner_offset_x + left_circle_offset
    circle_center_y_top = inner_height - top_circle_offset + inner_offset_y + bend_adjust
    circle_center_y_bottom = top_circle_offset + inner_offset_y + bend_adjust

    # compute translation to keep all coords non-negative (same logic)
    all_x = [p[0] for p in outer_pts + inner_pts + box_pts + [(circle_center_x, circle_center_y_top), (circle_center_x, circle_center_y_bottom)]]
    all_y = [p[1] for p in outer_pts + inner_pts + box_pts + [(circle_center_x, circle_center_y_top), (circle_center_x, circle_center_y_bottom)]]
    min_x = min(all_x)
    min_y = min(all_y)
    worst_negative_dim_offset = -5 
    margin_y = abs(worst_negative_dim_offset) if worst_negative_dim_offset < 0 else 0
    translate_x = max(0.0, -min_x)
    translate_y = max(0.0, -min_y + margin_y)

    # Apply translation and optional rotation
    def transform_point(pt):
        x, y = pt   
        if not rotated:
            return (offset[0] + translate_x + x, offset[1] + translate_y + y)
        # rotated 90deg CCW: (x,y)->(outer_height - y, x) then translate
        return (offset[0] + translate_x + (outer_height - y), offset[1] + translate_y + x)

    outer_trans = [transform_point(p) for p in outer_pts]
    inner_trans = [transform_point(p) for p in inner_pts]
    box_trans = [transform_point(p) for p in box_pts]
    circle_top = transform_point((circle_center_x, circle_center_y_top))
    circle_bottom = transform_point((circle_center_x, circle_center_y_bottom))

    outer_w, outer_h = compute_frame_dimensions(outer_trans)
    inner_w, inner_h = compute_frame_dimensions(inner_trans)

    # Build output models
    metadata = Metadata(
        label=label_name or file_name or "",
        file_name=Path(file_name).name if file_name else (label_name or "") + ".dxf",
        width=outer_width,
        height=outer_height,
        rotated=rotated,
        is_annotation_required=True,
        offset=(offset[0] + translate_x, offset[1] + translate_y),
    )

    frames=[
        Frame(name="outer", layer="CUT", points=outer_trans, width=outer_w, height=outer_h),
        Frame(name="inner", layer="CUT", points=inner_trans, width=inner_w, height=inner_h)
    ]
    cutouts = [Cutout(name="center_box", layer="CUT", points=box_trans)]
    holes = [
        Hole(name="hole_top", layer="CUT", center=circle_top, radius=defaults.circle_radius),
        Hole(name="hole_bottom", layer="CUT", center=circle_bottom, radius=defaults.circle_radius),
    ]
    labels = [Label(type="center_label", text=label_name or file_name or "", position="center")]

    geometry = Geometry(frames=frames, cutouts=cutouts, holes=holes, annotations=[], labels=labels)

    output = SchemasOutput(
        door_category="Single",
        door_type="Normal",
        option=None,
        metadata=metadata,
        geometry=geometry,
    )

    return output

def compute_frame_dimensions(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    width = max(xs) - min(xs)
    height = max(ys) - min(ys)
    return width, height

def main() -> None:
    """Simple test harness for compute_door_geometry.

    Constructs a sample DoorDXFRequest with reasonable defaults, calls
    compute_door_geometry and prints the resulting SchemasOutput as JSON.
    """
    from fastapi_app.schemas_input import DoorDXFRequest, DoorInfo, DimensionInfo, DefaultInfo

    # Build a sample request
    door_info = DoorInfo(category="Single", type="Normal", hole_offset="center", default_allowance="standard")
    dims = DimensionInfo(
        width_measurement=600.0,
        height_measurement=1105.0,
        left_side_allowance_width=25.0,
        right_side_allowance_width=25.0,
        top_side_allowance_height=25.0,
        bottom_side_allowance_height=0.0,
    )
    metadata = Metadata(label="TestDoor", file_name="test_door.dxf", width=0.0, height=0.0)
    defaults = DefaultInfo()

    request = DoorDXFRequest(mode="generate", door=door_info, dimensions=dims, metadata=metadata, defaults=defaults)

    # Compute geometry
    result = compute_door_geometry(request)

    # Print JSON (use Pydantic v2 API)
    try:
        print(result.model_dump_json(indent=2))
    except AttributeError:
        # Fallback for older Pydantic versions
        print(result.json(indent=2))


if __name__ == "__main__":
    main()
