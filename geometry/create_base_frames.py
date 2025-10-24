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
    shift_left = leaf_width + gap
    inner_offset_x_left = bend_adjust

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
        left_outer_pts = [(x - shift_left, y) for (x, y) in outer_pts]
        left_inner_pts = [(x - shift_left, y) for (x, y) in inner_pts]
        frames["left_outer"] = left_outer_pts
        frames["left_inner"] = left_inner_pts
        frames["shift_left"] = shift_left

    return frames
