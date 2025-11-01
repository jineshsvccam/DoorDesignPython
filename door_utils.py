def get_door_rectangles(df, fixed_params):
    """Build rectangles and door parameter dicts from an input DataFrame.

    For each row with `Run Required` == 'Y', construct a DoorDXFRequest using
    the per-row values and defaults overridden from `fixed_params`, call
    `prepare_dimensions` to compute derived measurements, and return a list of
    rectangles (outer_width, outer_height, file_name) and a list of
    door-parameter dicts that include the `request` object for downstream
    DXF generation.
    """
    import math
    from fastapi_app.schemas_input import DoorDXFRequest, DoorInfo, DimensionInfo, DefaultInfo
    from fastapi_app.schemas_output import Metadata as OutMeta
    from geometry.prepare_dimensions import prepare_dimensions

    def safe_num(val):
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return 0
        return val

    def safe_str(val, allow_empty=False):
        """Return a cleaned string or None.

        - If val is None or NaN, return None (or '' when allow_empty=True).
        - If val is an empty/whitespace string, return None (or '' when allow_empty=True).
        - Otherwise return str(val).
        """
        if val is None:
            return "" if allow_empty else None
        # pandas uses float('nan') for missing strings sometimes
        if isinstance(val, float) and math.isnan(val):
            return "" if allow_empty else None
        s = str(val).strip()
        if s == "":
            return "" if allow_empty else None
        return s

    rectangles = []
    door_params_list = []

    for idx, row in df.iterrows():
        if str(row.get("Run Required", "")).strip().upper() != "Y":
            # skip rows not marked for run
            continue

        # Map Excel columns to schema fields (use safe_num for numeric columns)
        door_name = str(row.get("Door Name") or f"door_{idx}")
        file_name = f"{door_name}.dxf"

        category = str(row.get("Door Type") or "Single")
        door_type = str(row.get("Door Sub Type") or row.get("Door Type") or "Normal")
        # Coerce NaN/empty values to None for optional fields
        option = safe_str(row.get("Fire Option"))
        hole_offset = safe_str(row.get("Hole Offset"), allow_empty=True) or ""

        width_measurement = float(safe_num(row.get("Frame Width")))
        height_measurement = float(safe_num(row.get("Frame Height")))
        left_side_allowance_width = float(safe_num(row.get("Left Margin Width")))
        right_side_allowance_width = float(safe_num(row.get("Right Margin Width")))
        top_side_allowance_height = float(safe_num(row.get("Top Marign Height")))
        bottom_side_allowance_height = float(safe_num(row.get("Bottom Margin Height")))

        # Build DefaultInfo and override values from fixed_params where provided
        defaults = DefaultInfo()
        try:
            if "door_minus_measurement_width" in fixed_params:
                defaults.door_minus_measurement_width = float(fixed_params["door_minus_measurement_width"])
            if "door_minus_measurement_height" in fixed_params:
                defaults.door_minus_measurement_height = float(fixed_params["door_minus_measurement_height"])
            if "bending_width" in fixed_params:
                defaults.bending_width = float(fixed_params["bending_width"])
            if "bending_height" in fixed_params:
                defaults.bending_height = float(fixed_params["bending_height"])
        except Exception:
            # If overrides fail, continue with defaults
            pass

        # Construct request model expected by prepare_dimensions and downstream code
        try:
            request = DoorDXFRequest(
                mode="batch",
                door=DoorInfo(
                    category=category,
                    type=door_type,
                    option=option,
                    hole_offset=hole_offset,
                    default_allowance="no",
                ),
                dimensions=DimensionInfo(
                    width_measurement=width_measurement,
                    height_measurement=height_measurement,
                    left_side_allowance_width=left_side_allowance_width,
                    right_side_allowance_width=right_side_allowance_width,
                    top_side_allowance_height=top_side_allowance_height,
                    bottom_side_allowance_height=bottom_side_allowance_height,
                ),
                metadata=OutMeta(label=door_name, file_name=file_name, width=0.0, height=0.0, rotated=False, is_annotation_required=True),
                defaults=defaults,
            )
        except Exception:
            # Fallback: if Pydantic validation fails for any reason, skip this row
            continue

        # Compute derived params using existing helper (keeps logic centralized)
        try:
            params = prepare_dimensions(request)
        except Exception:
            # If prepare_dimensions raises (e.g., invalid dims), skip this row
            continue

        # Compute outer bounding sizes for packing. For double doors use the
        # double-door bending width if provided.
        frame_total_width = width_measurement + left_side_allowance_width + right_side_allowance_width
        frame_total_height = height_measurement + top_side_allowance_height + bottom_side_allowance_height
        # inner_width/height already computed by prepare_dimensions and accounts for double-gap
        inner_width = float(params.get("inner_width", max(0.0, frame_total_width - defaults.door_minus_measurement_width)))
        inner_height = float(params.get("inner_height", max(0.0, frame_total_height - defaults.door_minus_measurement_height)))

        is_double = bool(params.get("is_double", False))
        bending_w = float(params.get("bending_width_double_door" if is_double else "bending_width", defaults.bending_width))
        bending_h = float(params.get("bending_height", defaults.bending_height))

        outer_width = inner_width + bending_w
        outer_height = inner_height + bending_h

        # Append rectangle for packing: (width, height, name)
        rectangles.append((outer_width, outer_height, file_name))

        # Prepare a door_params dict used by bin/door DXF generation. Include
        # the original request object so downstream code that expects a
        # DoorDXFRequest can use it directly.
        door_params = {
            "request": request,
            "width_measurement": width_measurement,
            "height_measurement": height_measurement,
            "left_side_allowance_width": left_side_allowance_width,
            "right_side_allowance_width": right_side_allowance_width,
            "left_side_allowance_height": top_side_allowance_height,
            "right_side_allowance_height": bottom_side_allowance_height,
            "door_minus_measurement_width": defaults.door_minus_measurement_width,
            "door_minus_measurement_height": defaults.door_minus_measurement_height,
            "bending_width": bending_w,
            "bending_height": bending_h,
            "outer_width": outer_width,
            "outer_height": outer_height,
            "file_name": file_name,
            "door_name": door_name,
        }

        door_params_list.append(door_params)

    return rectangles, door_params_list
