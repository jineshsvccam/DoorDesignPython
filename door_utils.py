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
        # 5. Calculate Outer Bounding Box for Packing
        # ------------------------------------------------------------------------
        # Problem: Inner frame extends below outer frame by (bend_adjust - bending_h)
        #   Example: bend_adjust=12mm, bending_h=24mm → inner_offset_y = -12mm
        #   When apply_transform normalizes geometry to Y=0, it shifts everything up by 12mm
        #   So packing dimensions must account for this extra 12mm height
        #
        # Solution: Calculate adjustment = abs(min(0, inner_offset_y))
        #   Then multiply by 2 to handle rectpack rotation (width ↔ height swap)
        #
        # Formula breakdown:
        #   outer_width  = inner_width + bending_w + double_gap + adjustment + extra_spacing
        #   outer_height = inner_height + bending_h + adjustment + extra_spacing
        #
        # Where:
        #   - inner_width: Already accounts for double_door_gap subtraction (for leaf calc)
        #   - double_gap: Add back for double doors (3mm gap needs space in bounding box)
        #   - adjustment: Compensates for inner frame negative Y offset (24mm when doubled)
        #   - extra_spacing: Direct control of cutting clearance gap (5mm = 5mm gap)
        
        inner_offset_y = bend_adjust - bending_h
        adjustment = abs(min(0.0, inner_offset_y)) * 2
        extra_y_spacing = 5  # mm - controls gap between door cutting boundaries
        
        outer_width = inner_width + bending_w + double_gap + adjustment + extra_y_spacing
        outer_height = inner_height + bending_h + adjustment + extra_y_spacing

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
