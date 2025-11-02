"""
door_geometry_service.py

Refactored, modular version of compute_door_geometry() for improved maintainability.
Performs full geometry pipeline:
- base frame + handle creation
- cutouts & holes generation
- unified transformation (rotate + translate)
- coordinate normalization
- metadata & final output
"""

from typing import Tuple, List, Optional, Literal, cast
from fastapi_app.schemas_output import SchemasOutput, Metadata, Geometry, Frame, Cutout, Hole
from fastapi_app.schemas_input import DoorDXFRequest
from .prepare_dimensions import prepare_dimensions
from .create_base_frames import create_base_frames
from .apply_transform import apply_transform
from .create_handles import create_handles
from .generate_cutouts import generate_cutouts
from .generate_holes import generate_holes
from .add_labels import create_labels
from .generate_annotations import generate_annotations
from .utilis import compute_frame_dimensions


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def build_geometry_sets(frames, handles, cutouts, holes):
    """Collect all frame, handle, cutout, and hole point sets for transformation."""
    all_sets, components = [], []

    def add(key, pts, typ="frame"):
        if pts:
            all_sets.append(pts)
            components.append((typ, key))

    # Frames
    for key in ("outer", "inner", "left_outer", "left_inner"):
        add(key, frames.get(key), "frame")

    # Handles
    if isinstance(handles, dict):
        for key in ("right_handle", "left_handle"):
            add(key, handles.get(key), "handle")

    # Cutouts & holes
    for i, c in enumerate(cutouts):
        add(i, c.points, "cutout")
    for i, h in enumerate(holes):
        add(i, [h.center], "hole")

    return all_sets, components


def map_transformed_sets(frames, handles, cutouts, holes, components, transformed):
    """Map transformed point sets back into respective geometry structures."""
    for comp, pts in zip(components, transformed):
        typ, key = comp
        if typ == "frame":
            frames[key] = pts
        elif typ == "handle" and isinstance(handles, dict):
            handles[key] = pts
        elif typ == "cutout":
            cutouts[key].points = pts
        elif typ == "hole":
            holes[key].center = pts[0]


def transform_offsets(frames, tx, ty, rotated):
    """Apply translation & rotation to stored offset tuples (inner_offset, etc.)."""
    def _transform(pt):
        x, y = pt
        if not rotated:
            return (tx + x, ty + y)
        return (tx + (frames.get("outer_height", 0.0) - y), ty + x)

    for off_key in ("inner_offset", "inner_offset_left"):
        val = frames.get(off_key)
        if isinstance(val, (tuple, list)) and len(val) == 2:
            try:
                frames[off_key] = _transform((float(val[0]), float(val[1])))
            except Exception:
                pass


def normalize_geometry(frames, handles, cutouts, holes):
    """Shift all coordinates so min(x,y)=0 for consistent placement."""
    all_x, all_y = [], []

    def collect(pts):
        for x, y in pts:
            all_x.append(x)
            all_y.append(y)

    for key in ("outer", "inner", "left_outer", "left_inner"):
        if frames.get(key):
            collect(frames[key])
    if isinstance(handles, dict):
        for v in handles.values():
            if v:
                collect(v)
    for c in cutouts:
        collect(c.points)
    for h in holes:
        all_x.append(h.center[0])
        all_y.append(h.center[1])

    if not all_x or not all_y:
        return

    min_x, min_y = min(all_x), min(all_y)
    if min_x == 0.0 and min_y == 0.0:
        return

    def shift(pts): return [(x - min_x, y - min_y) for x, y in pts]

    for k in ("outer", "inner", "left_outer", "left_inner"):
        if frames.get(k):
            frames[k] = shift(frames[k])
    if isinstance(handles, dict):
        for k, pts in handles.items():
            if pts:
                handles[k] = shift(pts)
    for c in cutouts:
        c.points = shift(c.points)
    for h in holes:
        cx, cy = h.center
        h.center = (cx - min_x, cy - min_y)

    for off_key in ("inner_offset", "inner_offset_left"):
        v = frames.get(off_key)
        if isinstance(v, (tuple, list)) and len(v) == 2:
            frames[off_key] = (v[0] - min_x, v[1] - min_y)


def create_metadata(request, frames, offset, rotated):
    """Build metadata safely based on frame geometry."""
    outer_pts = frames.get("outer") or []
    left_outer_pts = frames.get("left_outer") or []
    all_pts = outer_pts + left_outer_pts
    w, h = compute_frame_dimensions(all_pts) if all_pts else (0.0, frames.get("outer_height", 0.0))
    return Metadata(
        label=request.metadata.label,
        file_name=request.metadata.file_name,
        width=w,
        height=frames["outer_height"],
        rotated=rotated,
        is_annotation_required=True,
        offset=offset,
    )


def normalize_door_type_and_option(params) -> Tuple[Literal['Normal', 'Fire'], Optional[Literal['Option1', 'Option2', 'Option3', 'Option4', 'Option5']]]:
    """Standardize door type and option values."""
    raw_type = (params["door"].type or "").strip().lower()
    door_type = cast(Literal['Normal', 'Fire'], ("Fire" if raw_type == "fire" else "Normal"))

    raw_option = (params["door"].option or "").strip().lower()
    mapping = {
        "standard": "Option4",
        "standard_double": "Option4",
        "standard-double": "Option4",
        "standarddouble": "Option4",
        "fourglass": "Option5",
        "four_glass": "Option5",
        "four-glass": "Option5"
    }

    normalized_option: Optional[Literal['Option1', 'Option2', 'Option3', 'Option4', 'Option5']] = None
    if raw_option in mapping:        
        normalized_option = cast(Optional[Literal['Option1', 'Option2', 'Option3', 'Option4', 'Option5']], mapping[raw_option])
    elif raw_option.startswith("option") and raw_option[6:].isdigit():
        num = int(raw_option[6:])
        if 1 <= num <= 5:
            normalized_option = cast(Literal['Option1','Option2','Option3','Option4','Option5'], f"Option{num}")

    return door_type, normalized_option


# ---------------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------------

def compute_door_geometry(request: DoorDXFRequest, rotated=False, offset=(0.0, 0.0)) -> SchemasOutput:
    """Main entrypoint — orchestrates geometry creation, transformation, and output."""
    params = prepare_dimensions(request)
    print(f"[DEBUG] rotated={rotated}, offset={offset}")

    # --- Base geometry creation ---
    frames = create_base_frames(params)
    handles = create_handles(params, frames)
    pre_cutouts = generate_cutouts(params, frames, handles)
    pre_holes = generate_holes(params, frames)

    # --- Unified transformation ---
    all_sets, components = build_geometry_sets(frames, handles, pre_cutouts, pre_holes)
    if all_sets:
        transformed, (tx, ty) = apply_transform(all_sets, rotated, offset, frames["outer_height"])
        map_transformed_sets(frames, handles, pre_cutouts, pre_holes, components, transformed)
        transform_offsets(frames, tx, ty, rotated)
        normalize_geometry(frames, handles, pre_cutouts, pre_holes)

    # --- Frame assembly ---
    frame_objs = []
    for key in ("outer", "inner", "left_outer", "left_inner"):
        pts = frames.get(key)
        if pts:
            w, h = compute_frame_dimensions(pts)
            frame_objs.append(Frame(name=key, layer="CUT", points=pts, width=w, height=h))

    # --- Labels & annotations ---
    labels = create_labels(request)
    annotations = generate_annotations(frame_objs, pre_cutouts, pre_holes)
    geometry = Geometry(
        frames=frame_objs,
        cutouts=pre_cutouts,
        holes=pre_holes,
        annotations=annotations,
        labels=labels,
    )

    # --- Metadata & final output ---
    metadata = create_metadata(request, frames, offset, rotated)
    door_type, normalized_option = normalize_door_type_and_option(params)

    return SchemasOutput(
        door_category=params["door"].category,
        door_type=door_type,
        option=normalized_option,
        metadata=metadata,
        geometry=geometry,
    )
