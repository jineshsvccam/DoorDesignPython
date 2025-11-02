from fastapi_app.schemas_output import Hole


def generate_holes(params, frames):
    """Generate top and bottom circular holes."""
    defaults = params["defaults"]
    # Derive inner area bounds from transformed/normalized inner frame
    inner_pts = frames.get("inner") or []
    if inner_pts:
        xs = [p[0] for p in inner_pts]
        ys = [p[1] for p in inner_pts]
        inner_offset_x, inner_offset_y = min(xs), min(ys)
        inner_width = max(xs) - inner_offset_x
        inner_height = max(ys) - inner_offset_y
    else:
        # fallback to params (legacy)
        inner_offset_x, inner_offset_y = frames.get("inner_offset", (0.0, 0.0))
        inner_width = params.get("inner_width", 0.0)
        inner_height = params.get("inner_height", 0.0)

    circle_center_x = inner_offset_x + defaults.left_circle_offset
    # The top hole should be offset down from the top edge by top_circle_offset
    # and adjusted by the bending offset in the opposite direction to the bottom hole.
    # Subtract bend_adjust for the top hole so top and bottom maintain symmetric gap.
    circle_center_y_top = inner_offset_y + (inner_height - defaults.top_circle_offset) - params.get("bend_adjust", 0.0)
    circle_center_y_bottom = inner_offset_y + defaults.top_circle_offset + params.get("bend_adjust", 0.0)

    holes = [
        Hole(name="hole_top", layer="CUT", center=(circle_center_x, circle_center_y_top), radius=defaults.circle_radius),
        Hole(name="hole_bottom", layer="CUT", center=(circle_center_x, circle_center_y_bottom), radius=defaults.circle_radius),
    ]
    return holes
