from typing import Tuple, List, Optional
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
    try:
        print(f"[DEBUG door_geometry] rotated={rotated}, offset={offset}")
    except Exception:
        pass

    frames = create_base_frames(params)
    handles = create_handles(params, frames)

    # ✅ Generate cutouts and holes before transformation
    pre_cutouts = generate_cutouts(params, frames, handles)
    pre_holes = generate_holes(params, frames)

    # Convert to simple point sets
    cutout_pointsets = [c.points for c in pre_cutouts if c.points]
    hole_pointsets = [[h.center] for h in pre_holes if h.center]

    # Build all_sets and components (frames + handles + cutouts + holes)
    all_sets = []
    components = []  # ("type", key)

    # Required frames
    for key in ("outer", "inner"):
        pts = frames.get(key)
        if pts:
            all_sets.append(pts)
            components.append(("frame", key))

    # Handles
    rh = handles.get("right_handle") if isinstance(handles, dict) else None
    if rh:
        all_sets.append(rh)
        components.append(("handle", "right_handle"))

    lh = handles.get("left_handle") if isinstance(handles, dict) else None
    if lh:
        all_sets.append(lh)
        components.append(("handle", "left_handle"))

    # Left frames (for double doors)
    if "left_outer" in frames and frames.get("left_outer"):
        all_sets.append(frames.get("left_outer"))
        components.append(("frame", "left_outer"))
    if "left_inner" in frames and frames.get("left_inner"):
        all_sets.append(frames.get("left_inner"))
        components.append(("frame", "left_inner"))

    # ✅ Append cutouts & holes
    for i, pts in enumerate(cutout_pointsets):
        all_sets.append(pts)
        components.append(("cutout", i))
    for i, pts in enumerate(hole_pointsets):
        all_sets.append(pts)
        components.append(("hole", i))

    # If no sets, skip transform
    if not all_sets:
        transformed = []
        tx, ty = 0.0, 0.0
    else:
        transformed, (tx, ty) = apply_transform(all_sets, rotated, offset, frames["outer_height"])

        # Map transformed data back
        # typed as Optional to reflect initial None placeholders that will
        # be replaced with lists/tuples after transformation
        transformed_cutouts: List[Optional[List[Tuple[float, float]]]] = [None] * len(cutout_pointsets)
        transformed_holes: List[Optional[Tuple[float, float]]] = [None] * len(hole_pointsets)

        for comp, pts in zip(components, transformed):
            typ, key = comp
            if typ == "frame":
                frames[key] = pts
            elif typ == "handle":
                if isinstance(handles, dict):
                    handles[key] = pts
            elif typ == "cutout":
                transformed_cutouts[key] = pts
            elif typ == "hole":
                transformed_holes[key] = pts[0]  # single center point

        # ✅ Update transformed cutouts & holes
        cutouts = []
        for i, cpts in enumerate(transformed_cutouts):
            if cpts:
                base = pre_cutouts[i]
                cutouts.append(Cutout(name=base.name, layer=base.layer, points=cpts))

        holes = []
        for i, center in enumerate(transformed_holes):
            if center:
                base = pre_holes[i]
                holes.append(Hole(name=base.name, layer=base.layer, center=center, radius=base.radius))

        # ✅ Transform offsets (inner_offset, etc.)
        def _transform_offset(pt):
            x, y = pt
            if not rotated:
                return (tx + x, ty + y)
            return (tx + (frames.get("outer_height", 0.0) - y), ty + x)

        for off_key in ("inner_offset", "inner_offset_left"):
            val = frames.get(off_key)
            if isinstance(val, (tuple, list)) and len(val) == 2:
                try:
                    frames[off_key] = _transform_offset((float(val[0]), float(val[1])))
                except Exception:
                    pass

        # ✅ Normalize all coordinates (min x/y → 0)
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
        for c in cutouts:
            for p in c.points:
                all_x.append(p[0])
                all_y.append(p[1])
        for h in holes:
            all_x.append(h.center[0])
            all_y.append(h.center[1])

        if all_x and all_y:
            min_all_x = min(all_x)
            min_all_y = min(all_y)
            if min_all_x != 0.0 or min_all_y != 0.0:
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
                for c in cutouts:
                    c.points = shift_pts(c.points, min_all_x, min_all_y)
                for h in holes:
                    cx, cy = h.center
                    h.center = (cx - min_all_x, cy - min_all_y)

                def shift_offset_if_present(key):
                    v = frames.get(key)
                    if isinstance(v, (tuple, list)) and len(v) == 2 and isinstance(v[0], (int, float)):
                        frames[key] = (v[0] - min_all_x, v[1] - min_all_y)
                shift_offset_if_present("inner_offset")
                shift_offset_if_present("inner_offset_left")
    # end of transform section

    # Build Frame objects
    frame_objs = []
    for key in ("outer", "inner"):
        pts = frames.get(key)
        if not pts:
            continue
        w, h = compute_frame_dimensions(pts)
        frame_objs.append(Frame(name=key, layer="CUT", points=pts, width=w, height=h))

    if "left_outer" in frames or "left_inner" in frames:
        for key in ("left_outer", "left_inner"):
            pts = frames.get(key)
            if not pts:
                continue
            w, h = compute_frame_dimensions(pts)
            frame_objs.append(Frame(name=key, layer="CUT", points=pts, width=w, height=h))

    # Labels + annotations
    labels = create_labels(request)
    annotations = generate_annotations(frame_objs, cutouts, holes)

    geometry = Geometry(frames=frame_objs, cutouts=cutouts, holes=holes, annotations=annotations, labels=labels)

    # Metadata
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
        offset=(offset[0], offset[1]),
    )

    raw_type = (params["door"].type or "").strip().lower()
    door_type_normalized = "Fire" if raw_type == "fire" else "Normal"

    raw_option = params["door"].option
    from typing import Literal, cast
    normalized_option: Literal['Option1', 'Option2', 'Option3', 'Option4', 'Option5'] | None = None
    if raw_option:
        o = str(raw_option).strip().lower()
        if o in ("standard", "standard_double", "standard-double", "standarddouble"):
            normalized_option = "Option4"
        elif o in ("fourglass", "four_glass", "four-glass"):
            normalized_option = "Option5"
        elif o.startswith("option") and o[6:].isdigit():
            num = int(o[6:])
            if 1 <= num <= 5:
                normalized_option = cast(Literal['Option1', 'Option2', 'Option3', 'Option4', 'Option5'], f"Option{num}")

    return SchemasOutput(
        door_category=params["door"].category,
        door_type=door_type_normalized,
        option=normalized_option,
        metadata=metadata,
        geometry=geometry,
    )
