def create_handles(params, frames):
    """Create handle rectangles (and left handle for double doors)."""
    defaults = params["defaults"]
    inner_offset_x, inner_offset_y = frames["inner_offset"]
    inner_height = params["inner_height"]
    leaf_width = params["leaf_width"]
    shift_left = frames.get("shift_left", 0.0)
    is_double = params["is_double"]

    handle_gap = defaults.box_gap
    handle_width = defaults.box_width
    handle_height = defaults.box_height
    handle_bottom_y = inner_offset_y + ((inner_height + params["bending_height"] - handle_height) / 2.0)

    # Right or single door handle
    handle_left_x = inner_offset_x + handle_gap
    handle_pts = [
        (handle_left_x, handle_bottom_y),
        (handle_left_x + handle_width, handle_bottom_y),
        (handle_left_x + handle_width, handle_bottom_y + handle_height),
        (handle_left_x, handle_bottom_y + handle_height),
        (handle_left_x, handle_bottom_y),
    ]

    left_handle_pts = []
    if is_double:
        left_handle_left_x = inner_offset_x - shift_left + leaf_width - handle_gap - handle_width
        left_handle_pts = [
            (left_handle_left_x, handle_bottom_y),
            (left_handle_left_x + handle_width, handle_bottom_y),
            (left_handle_left_x + handle_width, handle_bottom_y + handle_height),
            (left_handle_left_x, handle_bottom_y + handle_height),
            (left_handle_left_x, handle_bottom_y),
        ]

    return {"right_handle": handle_pts, "left_handle": left_handle_pts}
