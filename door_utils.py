def get_door_rectangles(df, fixed_params):
    """Build rectangles and door parameter dicts from an input DataFrame.

    Processes Excel rows marked with 'Run Required' = 'Y', computes dimensions
    for packing, and prepares door parameters for DXF generation.

    Args:
        df: pandas DataFrame containing door specifications from Excel
        fixed_params: dict of default parameters (bending, door_minus, etc.)

    Returns:
        tuple: (rectangles, door_params_list)
            - rectangles: list of (width, height, filename) tuples for packing
            - door_params_list: list of dicts containing door parameters and request objects
    """
    import math
    from fastapi_app.schemas_input import DoorDXFRequest, DoorInfo, DimensionInfo, DefaultInfo
    from fastapi_app.schemas_output import Metadata as OutMeta
    from geometry.prepare_dimensions import prepare_dimensions

    # ============================================================================
    # Helper Functions
    # ============================================================================
    
    def safe_num(val):
        """Convert value to number, return 0 for None/NaN."""
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return 0
        return val

    def safe_str(val, allow_empty=False):
        """Convert value to string, return None/empty for missing values."""
        if val is None:
            return "" if allow_empty else None
        if isinstance(val, float) and math.isnan(val):
            return "" if allow_empty else None
        s = str(val).strip()
        if s == "":
            return "" if allow_empty else None
        return s

    rectangles = []
    door_params_list = []

    # ============================================================================
    # Process Each Row
    # ============================================================================
    
    for idx, row in df.iterrows():
        # Skip rows not marked for generation
        if str(row.get("Run Required", "")).strip().upper() != "Y":
            continue

        # ------------------------------------------------------------------------
        # 1. Extract Excel Data
        # ------------------------------------------------------------------------
        door_name = str(row.get("Door Name") or f"door_{idx}")
        file_name = f"{door_name}.dxf"
        category = str(row.get("Door Type") or "Single")
        door_type = str(row.get("Door Sub Type") or row.get("Door Type") or "Normal")
        option = safe_str(row.get("Fire Option"))
        hole_offset = safe_str(row.get("Hole Offset"), allow_empty=True) or ""

        width_measurement = float(safe_num(row.get("Frame Width")))
        height_measurement = float(safe_num(row.get("Frame Height")))
        left_side_allowance_width = float(safe_num(row.get("Left Margin Width")))
        right_side_allowance_width = float(safe_num(row.get("Right Margin Width")))
        top_side_allowance_height = float(safe_num(row.get("Top Marign Height")))
        bottom_side_allowance_height = float(safe_num(row.get("Bottom Margin Height")))

        # ------------------------------------------------------------------------
        # 2. Build Default Parameters (override with fixed_params)
        # ------------------------------------------------------------------------
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
            pass

        # ------------------------------------------------------------------------
        # 3. Build DoorDXFRequest Schema
        # ------------------------------------------------------------------------
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
            continue  # Skip invalid rows

        # ------------------------------------------------------------------------
        # 4. Compute Derived Dimensions (inner_width, bending, etc.)
        # ------------------------------------------------------------------------
        try:
            params = prepare_dimensions(request)
        except Exception:
            continue  # Skip if dimensions are invalid

        inner_width = float(params["inner_width"]) 
        inner_height = float(params["inner_height"]) 
        is_double = bool(params["is_double"]) 
        bending_w = float(params["bending_width_double_door"] if is_double else params["bending_width"]) 
        bending_h = float(params["bending_height"]) 
        bend_adjust = float(params["bend_adjust"]) 
        double_gap = float(params.get("gap", 0.0))  # 3mm for double doors, 0 for single

        # ------------------------------------------------------------------------
        # 5. Calculate bounding box used for packing
        # ------------------------------------------------------------------------
        # Compute the rectangle size used by the packer from the actual
        # frame geometry so placements match the drawn DXF. The algorithm:
        #  - Determine `extra_spacing` (gap) from, in order: request.defaults,
        #    fixed_params, or fallback to 5.0 mm.
        #  - Build the base frames using `create_base_frames(params)` and
        #    compute the tight bounding box with `compute_frame_dimensions(..)`.
        #  - Include both outer/inner and left_outer/left_inner polygons so
        #    any inner-frame extension is accounted for.
        #  - If geometry helpers fail, fall back to the previous heuristic.
        #  - Finally add `extra_spacing` to width/height to produce
        #    `outer_width`/`outer_height` used by the packer.

        # determine extra spacing safely
        try:
            val = getattr(request.defaults, "extra_spacing", None)
            if val is not None:
                extra_spacing = float(val)
            else:
                fp_val = fixed_params.get("extra_spacing", None)
                extra_spacing = float(fp_val) if fp_val is not None else 5.0
        except Exception:
            extra_spacing = 5.0

        # compute bbox from frame geometry
        try:
            from geometry.create_base_frames import create_base_frames
            from geometry.utilis import compute_frame_dimensions

            frames_for_bbox = create_base_frames(params)
            pts = []
            for key in ("outer", "inner", "left_outer", "left_inner"):
                poly = frames_for_bbox.get(key)
                if isinstance(poly, (list, tuple)):
                    pts.extend(poly)

            if pts:
                bbox_w, bbox_h = compute_frame_dimensions(pts)
            else:
                # heuristic fallback
                bbox_w = inner_width + bending_w + double_gap
                bbox_h = inner_height + bending_h
        except Exception:
            bbox_w = inner_width + bending_w + double_gap
            bbox_h = inner_height + bending_h

        outer_width = bbox_w + extra_spacing
        outer_height = bbox_h + extra_spacing

        rectangles.append((outer_width, outer_height, file_name))

        # ------------------------------------------------------------------------
        # 6. Build Door Parameters Dict for DXF Generation
        # ------------------------------------------------------------------------
        door_params = {
            "request": request,  # Original DoorDXFRequest for downstream processing
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
