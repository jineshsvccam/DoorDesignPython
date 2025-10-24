from fastapi_app.schemas_output import Hole


def generate_holes(params, frames):
    """Generate top and bottom circular holes."""
    defaults = params["defaults"]
    inner_offset_x, inner_offset_y = frames["inner_offset"]

    circle_center_x = inner_offset_x + defaults.left_circle_offset
    circle_center_y_top = params["inner_height"] - defaults.top_circle_offset + inner_offset_y + params["bend_adjust"]
    circle_center_y_bottom = defaults.top_circle_offset + inner_offset_y + params["bend_adjust"]

    holes = [
        Hole(name="hole_top", layer="CUT", center=(circle_center_x, circle_center_y_top), radius=defaults.circle_radius),
        Hole(name="hole_bottom", layer="CUT", center=(circle_center_x, circle_center_y_bottom), radius=defaults.circle_radius),
    ]
    return holes
