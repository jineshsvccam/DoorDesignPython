from typing import Tuple, Optional, List
from pathlib import Path
import math

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

    # center handle defaults (rectangle). 
    handle_gap = defaults.box_gap
    handle_width = defaults.box_width
    handle_height = defaults.box_height
    handle_left_x = inner_offset_x + handle_gap
    handle_bottom_y = inner_offset_y + ((inner_height + bending_height - handle_height) / 2.0)
    # Simple rectangle points (fallback)
    handle_pts = [
        (handle_left_x, handle_bottom_y),
        (handle_left_x + handle_width, handle_bottom_y),
        (handle_left_x + handle_width, handle_bottom_y + handle_height),
        (handle_left_x, handle_bottom_y + handle_height),
        (handle_left_x, handle_bottom_y),
    ]

    # circles
    left_circle_offset = defaults.left_circle_offset
    top_circle_offset = defaults.top_circle_offset
    circle_center_x = inner_offset_x + left_circle_offset
    circle_center_y_top = inner_height - top_circle_offset + inner_offset_y + bend_adjust
    circle_center_y_bottom = top_circle_offset + inner_offset_y + bend_adjust

    # compute translation to keep all coords non-negative (same logic)
    all_x = [p[0] for p in outer_pts + inner_pts + handle_pts + [(circle_center_x, circle_center_y_top), (circle_center_x, circle_center_y_bottom)]]
    all_y = [p[1] for p in outer_pts + inner_pts + handle_pts + [(circle_center_x, circle_center_y_top), (circle_center_x, circle_center_y_bottom)]]
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
    handle_trans = [transform_point(p) for p in handle_pts]
    circle_top = transform_point((circle_center_x, circle_center_y_top))
    circle_bottom = transform_point((circle_center_x, circle_center_y_bottom))

    outer_w, outer_h = compute_frame_dimensions(outer_trans)
    inner_w, inner_h = compute_frame_dimensions(inner_trans)
 

    frames=[
        Frame(name="outer", layer="CUT", points=outer_trans, width=outer_w, height=outer_h),
        Frame(name="inner", layer="CUT", points=inner_trans, width=inner_w, height=inner_h)
    ]

    # Determine final cutout(s) based on door info options
    door_info = door
    # Normalize option text to match schema Option1/Option2/Option3 where applicable
    option_in = (door_info.option or "").strip()
    opt_normalized = None
    if option_in:
        lower = option_in.lower()
        if "option1" in lower or lower == "option 1" or lower == "1" or "standard" in lower:
            opt_normalized = "Option1"
        elif "option2" in lower or lower == "option 2" or lower == "2" or "topfixed" in lower:
            opt_normalized = "Option2"
        elif "option3" in lower or lower == "option 3" or lower == "3" or "bottomfixed" in lower:
            opt_normalized = "Option3"

    cutouts = []

    # Default rounded radius guess
    rounded_radius = min(defaults.box_height / 2.0, defaults.box_width / 2.0)

    # Helper to normalize strings safely
    def _eq_str(a, b):
        return (a or "").strip().lower() == (b or "").strip().lower()

    # If Single Fire door, apply the user's margin rules for Option1/2/3
    pts_box = None
    if _eq_str(door_info.category, "single") and _eq_str(door_info.type, "fire"):
        # Per-request margins (use configurable defaults)
        left_margin = right_margin = defaults.fire_glass_lr_margin
        top_margin = defaults.fire_glass_top_margin
        bottom_margin = defaults.fire_glass_bottom_margin

        if opt_normalized == "Option1":
            # use configured defaults (explicit for clarity)
            left_margin = right_margin = defaults.fire_glass_lr_margin
            top_margin = defaults.fire_glass_top_margin
            bottom_margin = defaults.fire_glass_bottom_margin
        elif opt_normalized == "Option2":
            left_margin = right_margin = defaults.fire_glass_lr_margin
            top_margin = defaults.fire_glass_top_margin
            # extend the glass down to the centerline of the inner panel
            bottom_margin = inner_height / 2.0
        elif opt_normalized == "Option3":
            left_margin = right_margin = defaults.fire_glass_lr_margin
            bottom_margin = defaults.fire_glass_bottom_margin
            # extend the glass up to the centerline of the inner panel
            top_margin = inner_height / 2.0

        # Compute glass rectangle in inner-local coordinates (0..inner_width, 0..inner_height)
        glass_left_local = left_margin
        glass_right_local = inner_width - right_margin
        glass_bottom_local = bottom_margin
        glass_top_local = inner_height - top_margin

        # validate using local coordinates and fallback to centered default in local coords
        if glass_right_local <= glass_left_local or glass_top_local <= glass_bottom_local:
            # fallback to centered default box (local coords)
            glass_w = defaults.box_width
            glass_h = defaults.box_height
            glass_left_local = (inner_width - glass_w) / 2.0
            glass_bottom_local = (inner_height - glass_h) / 2.0
            glass_right_local = glass_left_local + glass_w
            glass_top_local = glass_bottom_local + glass_h
        else:
            glass_w = glass_right_local - glass_left_local
            glass_h = glass_top_local - glass_bottom_local

        # convert local coords to absolute (inner) coords by adding inner offsets
        glass_left = inner_offset_x + glass_left_local
        glass_right = inner_offset_x + glass_right_local
        glass_bottom = inner_offset_y + glass_bottom_local
        glass_top = inner_offset_y + glass_top_local

        # Shift glass up by the bend adjustment so the visible glass is moved above the bend
        # (this raises both bottom and top by bend_adjust, typically 12)
        glass_bottom += bend_adjust
        glass_top += bend_adjust

        # pick a small corner radius from defaults (rounded rectangle) and create rounded rect
        radius = min(defaults.glass_corner_radius, glass_w / 2.0 if glass_w else 0.0, glass_h / 2.0 if glass_h else 0.0)
        pts_box = create_rounded_rect(glass_left, glass_bottom, glass_w, glass_h, radius, segments=defaults.glass_segments)
        # remove consecutive duplicates for a cleaner polygon
        pts_box = dedupe_consecutive_points(pts_box)

    else:
        # keep existing behavior for other categories and options
        if _eq_str(door_info.category, "single"):
            if _eq_str(door_info.type, "fire"):
                # previously handled above; but if not matched, fallback
                pts_box = handle_pts
            else:
                if opt_normalized == "Option1":
                    pts_box = create_rounded_box(handle_left_x, handle_bottom_y, handle_width, handle_height, rounded_radius)
                else:
                    pts_box = handle_pts
        elif _eq_str(door_info.category, "double"):
            if _eq_str(door_info.type, "fire"):
                if opt_normalized == "Option1":
                    mid_x = inner_offset_x + inner_width / 2.0
                    gap = 6.0
                    left_box = create_rounded_box(mid_x - gap - handle_width, handle_bottom_y, handle_width, handle_height, rounded_radius)
                    right_box = create_rounded_box(mid_x + gap, handle_bottom_y, handle_width, handle_height, rounded_radius)
                    pts_box = left_box + right_box
                elif opt_normalized == "Option2":
                    pts_box = create_rounded_box(inner_offset_x + handle_gap, handle_bottom_y, inner_width - handle_gap * 2.0, handle_height, rounded_radius)
                else:
                    pts_box = handle_pts
            else:
                pts_box = handle_pts
        else:
            pts_box = handle_pts

    # Transform calculated glass/handle points
    if pts_box is None:
        pts_box = handle_pts
    glass_trans = [transform_point(p) for p in pts_box]

    # Add keybox (fire doors only) - centered at bottom, offset above inner bottom by default
    keybox_cutout = None
    if _eq_str(door_info.type, "fire"):
        kb_w = defaults.keybox_width
        kb_h = defaults.keybox_height
        kb_offset = defaults.keybox_bottom_offset
        # compute local center bottom within inner local coords then convert to absolute
        kb_center_x_local = inner_width / 2.0
        kb_left_local = kb_center_x_local - kb_w / 2.0
        kb_bottom_local = kb_offset
        kb_left = inner_offset_x + kb_left_local
        kb_bottom = inner_offset_y + kb_bottom_local
        # shift up by bend_adjust so keybox sits above the bend like glass
        kb_bottom += bend_adjust
        kb_pts = [
            (kb_left, kb_bottom),
            (kb_left + kb_w, kb_bottom),
            (kb_left + kb_w, kb_bottom + kb_h),
            (kb_left, kb_bottom + kb_h),
            (kb_left, kb_bottom),
        ]
        keybox_cutout = Cutout(name="keybox", layer="CUT", points=[transform_point(p) for p in kb_pts])

    # Always add the center handle cutout from the handle default geometry
    cutouts.append(Cutout(name="center_handle", layer="CUT", points=handle_trans))
    # Add the glass cutout separately (may be same as handle when using defaults)
    cutouts.append(Cutout(name="glass_cut", layer="CUT", points=glass_trans))
    # Append keybox if created
    if keybox_cutout is not None:
        cutouts.append(keybox_cutout)
   
    holes = [
        Hole(name="hole_top", layer="CUT", center=circle_top, radius=defaults.circle_radius),
        Hole(name="hole_bottom", layer="CUT", center=circle_bottom, radius=defaults.circle_radius),
    ]
    labels = [Label(type="center_label", text=label_name or file_name or "", position="center")]

    geometry = Geometry(frames=frames, cutouts=cutouts, holes=holes, annotations=[], labels=labels)

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

    output = SchemasOutput(
        door_category=door_info.category if door_info.category in ("Single", "Double") else "Single",
        door_type=door_info.type if door_info.type in ("Normal", "Fire") else "Normal",
        option=opt_normalized,
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


def create_rounded_box(left_x, bottom_y, width, height, radius, segments=12):
    """Return list of points approximating a rectangle with semicircular ends (rounded box/capsule).

    The shape is a capsule oriented horizontally: semicircle at left and right, connected by straight edges.
    """
    cx_left = left_x + radius
    cx_right = left_x + width - radius
    top = bottom_y + height
    # If radius is larger than half of height, clamp it
    radius = min(radius, height / 2.0)

    pts = []
    # top edge from left to right (excluding corners)
    pts.append((cx_left, top))
    pts.append((cx_right, top))

    # right semicircle (top->bottom)
    for i in range(segments + 1):
        theta = (i / segments) * math.pi  # 0..pi
        x = cx_right + radius * math.cos(theta)
        y = bottom_y + height / 2.0 + radius * math.sin(theta)
        pts.append((x, y))

    # bottom edge from right to left
    pts.append((cx_left, bottom_y))

    # left semicircle (bottom->top)
    for i in range(segments + 1):
        theta = math.pi + (i / segments) * math.pi  # pi..2pi
        x = cx_left + radius * math.cos(theta)
        y = bottom_y + height / 2.0 + radius * math.sin(theta)
        pts.append((x, y))

    # close
    pts.append(pts[0])
    return pts


def create_rounded_rect(left_x, bottom_y, width, height, radius, segments=8):
    """Create a rounded-rectangle polygon (clockwise) with quarter-circle corners.

    Constructed in clockwise order: top edge left->right, top-right arc, right edge,
    bottom-right arc, bottom edge, bottom-left arc, left edge, top-left arc.
    """
    right = left_x + width
    top = bottom_y + height
    r = min(radius, width / 2.0, height / 2.0)

    # corner centers
    tl_c = (left_x + r, top - r)
    tr_c = (right - r, top - r)
    br_c = (right - r, bottom_y + r)
    bl_c = (left_x + r, bottom_y + r)

    pts = []

    # top edge tangents (exact coordinates)
    pts.append((left_x + r, top))
    pts.append((right - r, top))

    # helper to sample arc between start_angle -> end_angle (exclude endpoints)
    def sample_arc(center, start_ang, end_ang, segs):
        cx, cy = center
        arc_pts = []
        if segs > 1:
            for i in range(1, segs):
                t = i / segs
                theta = start_ang + (end_ang - start_ang) * t
                arc_pts.append((cx + r * math.cos(theta), cy + r * math.sin(theta)))
        return arc_pts

    # top-right arc: 90deg -> 0deg
    pts += sample_arc(tr_c, math.pi / 2.0, 0.0, segments)
    # right edge tangents
    pts.append((right, top - r))
    pts.append((right, bottom_y + r))

    # bottom-right arc: 0 -> -90deg
    pts += sample_arc(br_c, 0.0, -math.pi / 2.0, segments)
    # bottom edge tangents
    pts.append((right - r, bottom_y))
    pts.append((left_x + r, bottom_y))

    # bottom-left arc: -90 -> -180deg
    pts += sample_arc(bl_c, -math.pi / 2.0, -math.pi, segments)
    # left edge tangents
    pts.append((left_x, bottom_y + r))
    pts.append((left_x, top - r))

    # top-left arc: pi -> pi/2 (i.e. 180deg -> 90deg)
    pts += sample_arc(tl_c, math.pi, math.pi / 2.0, segments)

    # Snap points very close to exact tangent coordinates to avoid floating-point micro-gaps
    tangents = [
        (left_x + r, top),         # top-left tangent
        (right - r, top),          # top-right tangent
        (right, top - r),          # right-top
        (right, bottom_y + r),     # right-bottom
        (right - r, bottom_y),     # bottom-right
        (left_x + r, bottom_y),    # bottom-left
        (left_x, bottom_y + r),    # left-bottom
        (left_x, top - r),         # left-top
    ]
    eps = 1e-6
    snapped = []
    for x, y in pts:
        snapped_point = (x, y)
        for tx, ty in tangents:
            if (abs(x - tx) <= eps) and (abs(y - ty) <= eps):
                snapped_point = (tx, ty)
                break
        snapped.append(snapped_point)

    # close and dedupe
    pts = dedupe_consecutive_points(snapped)
    return pts


def dedupe_consecutive_points(points, eps=1e-6):
    if not points:
        return points
    out = [points[0]]
    for p in points[1:]:
        if abs(p[0] - out[-1][0]) > eps or abs(p[1] - out[-1][1]) > eps:
            out.append(p)
    # If closed, ensure explicit close
    if out[0] != out[-1]:
        out.append(out[0])
    return out

def main() -> None:
    """Simple test harness for compute_door_geometry.

    Constructs a sample DoorDXFRequest with reasonable defaults, calls
    compute_door_geometry and prints the resulting SchemasOutput as JSON.
    """
    from fastapi_app.schemas_input import DoorDXFRequest, DoorInfo, DimensionInfo, DefaultInfo

    # Build a sample request
    door_info = DoorInfo(category="Single", type="Fire", option="standard", hole_offset="center", default_allowance="standard")
    dims = DimensionInfo(
        width_measurement=895.0,
        height_measurement=1765.0,
        left_side_allowance_width=25.0,
        right_side_allowance_width=25.0,
        top_side_allowance_height=25.0,
        bottom_side_allowance_height=25.0,
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
