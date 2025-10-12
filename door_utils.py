def get_door_rectangles(df, fixed_params):
    rectangles = []
    door_params_list = []
    import math
    def safe_num(val):
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return 0
        return val
    for idx, row in df.iterrows():
        if str(row.get("Run Required", "")).strip().upper() == "Y":
            width_measurement = safe_num(row["Frame Width"])
            height_measurement = safe_num(row["Frame Height"])
            left_side_allowance_width = safe_num(row["Left Margin Width"])
            right_side_allowance_width = safe_num(row["Right Margin Width"])
            left_side_allowance_height = safe_num(row["Top Marign Height"])
            right_side_allowance_height = safe_num(row["Bottom Margin Height"])
            door_minus_measurement_width = fixed_params["door_minus_measurement_width"]
            door_minus_measurement_height = fixed_params["door_minus_measurement_height"]
            bending_width = fixed_params["bending_width"]
            bending_height = fixed_params["bending_height"]
            file_name = f"{row['Door Name']}.dxf"

            frame_total_width = width_measurement + left_side_allowance_width + right_side_allowance_width
            frame_total_height = height_measurement + left_side_allowance_height + right_side_allowance_height
            inner_width = frame_total_width - door_minus_measurement_width
            inner_height = frame_total_height - door_minus_measurement_height
            outer_width = inner_width + bending_width
            outer_height = inner_height + bending_height

            rectangles.append((outer_width, outer_height, file_name))

            door_params = {
                "width_measurement": width_measurement,
                "height_measurement": height_measurement,
                "left_side_allowance_width": left_side_allowance_width,
                "right_side_allowance_width": right_side_allowance_width,
                "left_side_allowance_height": left_side_allowance_height,
                "right_side_allowance_height": right_side_allowance_height,
                "door_minus_measurement_width": door_minus_measurement_width,
                "door_minus_measurement_height": door_minus_measurement_height,
                "bending_width": bending_width,
                "bending_height": bending_height,
                "outer_width": outer_width,
                "outer_height": outer_height,
                "file_name": file_name,
                "door_name": row["Door Name"]
            }
            door_params_list.append(door_params)
    return rectangles, door_params_list
