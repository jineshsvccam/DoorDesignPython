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

    # Door-minus values come from defaults (could alternatively be provided in dimensions)
    # For double doors include the configured gap between leaves when computing inner width
    door_minus_measurement_width = defaults.door_minus_measurement_width
    is_double = (door.category or "").strip().lower() == "double"
    if is_double:
        door_minus_measurement_width += defaults.double_door_gap

    inner_width = frame_total_width - door_minus_measurement_width
    inner_height = frame_total_height - defaults.door_minus_measurement_height

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
    # Parse hole_offset from the door input if provided. Expected format: "<left>x<top>" (e.g. "80x40").
    # If parsing succeeds, override the defaults on the DefaultInfo object so downstream
    # code (e.g. generate_holes) can continue to read offsets from defaults.
    hole_offset_raw = (door.hole_offset or "") if hasattr(door, "hole_offset") else ""
    try:
        if isinstance(hole_offset_raw, str) and hole_offset_raw.strip():
            parts = hole_offset_raw.lower().replace(" ", "").split("x")
            if len(parts) == 2:
                left_val = float(parts[1])
                top_val = float(parts[0])
                # Mutate the defaults object with parsed values
                try:
                    defaults.left_circle_offset = left_val
                    defaults.top_circle_offset = top_val
                except Exception:
                    # If defaults is not mutable for some reason, put them into params as fallback
                    params["left_circle_offset"] = left_val
                    params["top_circle_offset"] = top_val
    except Exception:
        # On any parse error, leave defaults unchanged (use configured defaults)
        pass
    return params
