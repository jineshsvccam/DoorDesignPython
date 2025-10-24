from fastapi_app.schemas_input import DoorDXFRequest, DefaultInfo


def prepare_dimensions(request: DoorDXFRequest):
    """Extract and compute all key measurements, flags, and derived values."""
    door = request.door
    dims = request.dimensions
    defaults: DefaultInfo = request.defaults

    width_measurement = dims.width_measurement
    height_measurement = dims.height_measurement
    if width_measurement <= 0 or height_measurement <= 0:
        raise ValueError("Width and height must be positive numbers.")

    # Allowances
    frame_total_width = width_measurement + dims.left_side_allowance_width + dims.right_side_allowance_width
    frame_total_height = height_measurement + dims.top_side_allowance_height + dims.bottom_side_allowance_height

    inner_width = frame_total_width - defaults.door_minus_measurement_width
    inner_height = frame_total_height - defaults.door_minus_measurement_height

    is_double = (door.category or "").strip().lower() == "double"
    double_gap = defaults.double_door_gap if is_double else 0.0

    if is_double:
        leaf_width = inner_width / 2.0
        gap = double_gap
    else:
        leaf_width = inner_width
        gap = 0.0

    params = {
        "door": door,
        "defaults": defaults,
        "inner_width": inner_width,
        "inner_height": inner_height,
        "leaf_width": leaf_width,
        "gap": gap,
        "is_double": is_double,
        "bending_width": defaults.bending_width,
        "bending_height": defaults.bending_height,
        "bending_width_double_door": defaults.bending_width_double_door,
        "bend_adjust": defaults.bend_adjust,
    }
    return params
