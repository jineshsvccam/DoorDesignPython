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
from .add_labels import create_labels
from .generate_annotations import generate_annotations


def compute_door_geometry(request: DoorDXFRequest, rotated=False, offset=(0.0, 0.0)) -> SchemasOutput:
    """Main entrypoint — orchestrates all geometry generation."""
    params = prepare_dimensions(request)
    # Debug: print rotated flag and placement offset for tracing
    try:
        print(f"[DEBUG door_geometry] rotated={rotated}, offset={offset}")
    except Exception:
        # Keep function robust in environments where printing may fail
        pass
    frames = create_base_frames(params)
    handles = create_handles(params, frames)

    # Combine all point sets to compute a single global translation/rotation.
    # We'll keep a parallel `components` list so we can map transformed
    # point-sets back into the `frames` and `handles` structures.
    all_sets = []
    components = []  # list of tuples like ("frame", key) or ("handle", key)

    # required frames (outer/inner) — guard if missing
    for key in ("outer", "inner"):
        pts = frames.get(key)
        if pts:
            all_sets.append(pts)
            components.append(("frame", key))

    # handles may be None or empty lists
    rh = handles.get("right_handle") if isinstance(handles, dict) else None
    if rh:
        all_sets.append(rh)
        components.append(("handle", "right_handle"))

    lh = handles.get("left_handle") if isinstance(handles, dict) else None
    if lh:
        all_sets.append(lh)
        components.append(("handle", "left_handle"))

    # optional left-side frames for double doors
    if "left_outer" in frames and frames.get("left_outer"):
        all_sets.append(frames.get("left_outer"))
        components.append(("frame", "left_outer"))
    if "left_inner" in frames and frames.get("left_inner"):
        all_sets.append(frames.get("left_inner"))
        components.append(("frame", "left_inner"))

    # If for some reason no point sets are available, avoid calling apply_transform
    if not all_sets:
        transformed = []
        tx, ty = 0.0, 0.0
    else:
        transformed, (tx, ty) = apply_transform(all_sets, rotated, offset, frames["outer_height"])

        # Map transformed sets back to frames/handles according to `components` order
        for comp, pts in zip(components, transformed):
            typ, key = comp
            if typ == "frame":
                frames[key] = pts
            elif typ == "handle":
                # ensure handles dict exists and update
                if isinstance(handles, dict):
                    handles[key] = pts

        # Normalise all returned point sets so their minimum x/y is 0.0.
        # This makes the geometry's local origin equal to its bounding-box
        # bottom-left which simplifies placement: packer placement coordinates
        # can be used directly as offsets without extra negative corrections.
        all_x = []
        all_y = []
        for k in ("outer", "inner", "left_outer", "left_inner"):
            pts = frames.get(k)
            if pts:
                for p in pts:
                    all_x.append(p[0])
                    all_y.append(p[1])
        if isinstance(handles, dict):
            for hpts in handles.values():
                if hpts:
                    for p in hpts:
                        all_x.append(p[0])
                        all_y.append(p[1])

        if all_x and all_y:
            min_all_x = min(all_x)
            min_all_y = min(all_y)
            if min_all_x != 0.0 or min_all_y != 0.0:
                # shift all frames and handles so bbox min becomes (0,0)
                def shift_pts(pts, sx, sy):
                    return [(x - sx, y - sy) for (x, y) in pts]

                for k in ("outer", "inner", "left_outer", "left_inner"):
                    pts = frames.get(k)
                    if pts:
                        frames[k] = shift_pts(pts, min_all_x, min_all_y)

                if isinstance(handles, dict):
                    for hk, hpts in list(handles.items()):
                        if hpts:
                            handles[hk] = shift_pts(hpts, min_all_x, min_all_y)

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

    labels = create_labels(request)
    annotations = generate_annotations(frame_objs, cutouts, holes)

    geometry = Geometry(frames=frame_objs, cutouts=cutouts, holes=holes, annotations=annotations, labels=labels)

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
        # The frames returned by this function are normalized so their local
        # bounding-box minimum is (0,0). Therefore the placement offset used
        # for packing should be represented directly in metadata.offset.
        # Do NOT add the internal translation (tx,ty) here — that translation
        # was only used to make intermediate coordinates non-negative and was
        # reversed during normalization.
        offset=(offset[0], offset[1]),
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
