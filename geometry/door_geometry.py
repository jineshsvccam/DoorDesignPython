from typing import Tuple, List
from fastapi_app.schemas_output import SchemasOutput, Metadata, Geometry, Frame, Cutout, Hole, Label
from fastapi_app.schemas_input import DoorDXFRequest, DefaultInfo
from .utilis import compute_frame_dimensions, create_rounded_box, create_rounded_rect, dedupe_consecutive_points
from .prepare_dimensions import prepare_dimensions
from .create_base_frames import create_base_frames
from .apply_transform import apply_transform
from .create_handles import create_handles
from .generate_cutouts import generate_cutouts
from .generate_holes import generate_holes
from .add_labels import add_labels


def compute_door_geometry(request: DoorDXFRequest, rotated=False, offset=(0.0, 0.0)) -> SchemasOutput:
    """Main entrypoint — orchestrates all geometry generation."""
    params = prepare_dimensions(request)
    frames = create_base_frames(params)
    handles = create_handles(params, frames)

    # Combine all point sets to compute translation. Filter out None or empty sets
    all_sets = []
    # required frames (outer/inner) — guard if missing
    for key in ("outer", "inner"):
        pts = frames.get(key)
        if pts:
            all_sets.append(pts)

    # handles may be None or empty lists
    rh = handles.get("right_handle") if isinstance(handles, dict) else None
    if rh:
        all_sets.append(rh)

    lh = handles.get("left_handle") if isinstance(handles, dict) else None
    if lh:
        all_sets.append(lh)

    # optional left-side frames for double doors
    if "left_outer" in frames and frames.get("left_outer"):
        all_sets.append(frames.get("left_outer"))
    if "left_inner" in frames and frames.get("left_inner"):
        all_sets.append(frames.get("left_inner"))

    # If for some reason no point sets are available, avoid calling apply_transform
    if not all_sets:
        transformed = []
        tx, ty = 0.0, 0.0
    else:
        transformed, (tx, ty) = apply_transform(all_sets, rotated, offset, frames["outer_height"])

    # Frame objects (include left frames for double doors)
    frame_objs = []
    for key in ("outer", "inner"):
        pts = frames.get(key)
        if not pts:
            # skip missing or None frames
            continue
        w, h = compute_frame_dimensions(pts)
        frame_objs.append(Frame(name=key, layer="CUT", points=pts, width=w, height=h))

    # If double door, also expose left-side frames so both leaves are present in the output
    if "left_outer" in frames or "left_inner" in frames:
        for key in ("left_outer", "left_inner"):
            pts = frames.get(key)
            if not pts:
                continue
            w, h = compute_frame_dimensions(pts)
            frame_objs.append(Frame(name=key, layer="CUT", points=pts, width=w, height=h))

    cutouts = generate_cutouts(params, frames, handles)
    holes = generate_holes(params, frames)
    labels = add_labels(request)

    geometry = Geometry(frames=frame_objs, cutouts=cutouts, holes=holes, annotations=[], labels=labels)

    # Compute overall width/height from the available frame polygons so metadata reflects
    # single- or double-door bounding box correctly.
    outer_pts = frames.get("outer") or []
    all_frame_points = list(outer_pts)
    if "left_outer" in frames:
        left_outer_pts = frames.get("left_outer") or []
        all_frame_points += list(left_outer_pts)
    overall_w, overall_h = compute_frame_dimensions(all_frame_points) if all_frame_points else (0.0, frames.get("outer_height", 0.0))

    metadata = Metadata(
        label=request.metadata.label,
        file_name=request.metadata.file_name,
        width=overall_w,
        height=frames["outer_height"],
        rotated=rotated,
        is_annotation_required=True,
        offset=(offset[0] + tx, offset[1] + ty),
    )

    # Normalize door_type to match the SchemasOutput literal requirement
    # SchemasOutput expects exactly 'Normal' or 'Fire' (case-sensitive).
    raw_type = (params["door"].type or "").strip().lower()
    door_type_normalized = "Fire" if raw_type == "fire" else "Normal"

    # Normalize option to one of the allowed literal values (Option1..Option5) or None.
    # Map known UI tokens to the OptionX tokens used by SchemasOutput.
    raw_option = params["door"].option
    from typing import Literal, cast

    normalized_option: Literal['Option1', 'Option2', 'Option3', 'Option4', 'Option5'] | None = None
    if raw_option:
        o = str(raw_option).strip().lower()
        # Mapping heuristics
        if o in ("standard", "standard_double", "standard-double", "standarddouble"):
            normalized_option = "Option4"
        elif o in ("fourglass", "four_glass", "four-glass"):
            normalized_option = "Option5"
        else:
            # If already in OptionX form, accept it; else fallback to None to avoid validation errors
            if o.startswith("option") and o[6:].isdigit():
                # Ensure it's Option1..Option5
                num = int(o[6:])
                if 1 <= num <= 5:
                    normalized_option = cast(Literal['Option1', 'Option2', 'Option3', 'Option4', 'Option5'], f"Option{num}")
            else:
                normalized_option = None

    return SchemasOutput(
        door_category=params["door"].category,
        door_type=door_type_normalized,
        option=normalized_option,
        metadata=metadata,
        geometry=geometry,
    )
