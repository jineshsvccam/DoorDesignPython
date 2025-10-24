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

    # Combine all point sets to compute translation
    all_sets = [frames["outer"], frames["inner"], handles["right_handle"]]
    if handles["left_handle"]:
        all_sets.append(handles["left_handle"])
    if "left_outer" in frames:
        all_sets += [frames["left_outer"], frames["left_inner"]]

    transformed, (tx, ty) = apply_transform(all_sets, rotated, offset, frames["outer_height"])

    # Frame objects (simplified mapping for now)
    frame_objs = []
    for pts, name in zip([frames["outer"], frames["inner"]], ["outer", "inner"]):
        w, h = compute_frame_dimensions(pts)
        frame_objs.append(Frame(name=name, layer="CUT", points=pts, width=w, height=h))

    cutouts = generate_cutouts(params, frames, handles)
    holes = generate_holes(params, frames)
    labels = add_labels(request)

    geometry = Geometry(frames=frame_objs, cutouts=cutouts, holes=holes, annotations=[], labels=labels)

    metadata = Metadata(
        label=request.metadata.label,
        file_name=request.metadata.file_name,
        width=frames["inner_offset"][0] + params["leaf_width"],
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
