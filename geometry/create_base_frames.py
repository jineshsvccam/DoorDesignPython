from typing import Dict, List, Tuple, Any


def create_base_frames(params) -> Dict[str, Any]:
    """Create outer and inner frame polygons for single or double door."""
    leaf_width = params["leaf_width"]
    inner_height = params["inner_height"]
    bending_width = params["bending_width"]
    bending_height = params["bending_height"]
    bending_width_double_door = params["bending_width_double_door"]
    bend_adjust = params["bend_adjust"]
    is_double = params["is_double"]
    gap = params["gap"]

    outer_width = leaf_width + bending_width
    outer_width_left = leaf_width + bending_width_double_door
    outer_height = inner_height + bending_height

    inner_offset_x = bending_width - bend_adjust
    inner_offset_y = bend_adjust - bending_height
    shift_left = outer_width_left + gap
    # allow callers to override the left inner x-offset (useful for double-door configs)
    # if not provided, fall back to the same adjust value
    inner_offset_x_left = params.get("inner_offset_x_left", bend_adjust)

    outer_pts = [(0, 0),
                (outer_width, 0),
                (outer_width, inner_height),
                (0, inner_height), (0, 0)]
    
    inner_pts = [
        (inner_offset_x, inner_offset_y),
        (inner_offset_x + leaf_width, inner_offset_y),
        (inner_offset_x + leaf_width, inner_offset_y + outer_height),
        (inner_offset_x, inner_offset_y + outer_height),
        (inner_offset_x, inner_offset_y),
    ]

    frames = {"outer": outer_pts, "inner": inner_pts, "outer_height": outer_height, "inner_offset": (inner_offset_x, inner_offset_y)}

    if is_double:
        # Build left-local polygons anchored at (0,0) for easier debugging.
        # These represent the left leaf geometry before being placed to the left of
        # the right leaf. After construction we create shifted versions by
        # subtracting `shift_left` from x coordinates.

        # left-local outer (starts at x=0)
        left_outer_local = [
            (0, 0),
            (outer_width_left, 0),
            (outer_width_left, inner_height),
            (0, inner_height),
            (0, 0),
        ]

        # left-local inner uses left-specific inner_offset_x_left (relative to left-local origin)
        left_inner_local = [
            (inner_offset_x_left, inner_offset_y),
            (inner_offset_x_left + leaf_width, inner_offset_y),
            (inner_offset_x_left + leaf_width, inner_offset_y + outer_height),
            (inner_offset_x_left, inner_offset_y + outer_height),
            (inner_offset_x_left, inner_offset_y),
        ]

        # Now shift local coordinates left by shift_left to place the left leaf next to the right leaf
        left_outer_pts = [(x - shift_left, y) for (x, y) in left_outer_local]
        left_inner_pts = [(x - shift_left, y) for (x, y) in left_inner_local]

    # Store only the shifted (placed) left polygons and metadata in the
    # returned `frames` dict when this is a double-door configuration.
    # For single doors we don't expose left-specific polygons; set the
    # keys to None so callers can always expect these keys to exist.
    if is_double:
        frames["left_outer"] = left_outer_pts
        frames["left_inner"] = left_inner_pts
        frames["shift_left"] = shift_left
        frames["inner_offset_left"] = (inner_offset_x_left, inner_offset_y)
    else:
        frames["left_outer"] = None
        frames["left_inner"] = None
        frames["shift_left"] = None
        frames["inner_offset_left"] = None

    return frames
