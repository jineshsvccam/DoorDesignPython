import json
from pathlib import Path


# ===============================================================
# 🔧 GLOBAL CONFIGURATION / CONSTANTS
# ===============================================================
BENDING_WIDTH = 31.0
BENDING_HEIGHT = 24.0
BEND_ADJUST = 12.0
DOUBLE_DOOR_GAP = 3.0

KEYBOX_W = 70.0
KEYBOX_H = 40.0
KEYBOX_BOTTOM_OFFSET = 50.0

BOX_GAP = 30.0
BOX_WIDTH = 22.0
BOX_HEIGHT = 112.0

FIRE_GAP_LR = 190.0
FIRE_GAP_TOP = 170.0
FIRE_GAP_BOTTOM = 240.0


# ===============================================================
# 🧩 COMMON HELPER FUNCTIONS
# ===============================================================
def get_frame_bounds(frame):
    xs = [p[0] for p in frame["points"]]
    ys = [p[1] for p in frame["points"]]
    return min(xs), max(xs), min(ys), max(ys)


def get_dimensions(frame):
    left, right, bottom, top = get_frame_bounds(frame)
    return round(right - left, 2), round(top - bottom, 2)


def center_of(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def _collect_valid_flags(obj):
    """Recursively collect boolean flags named 'is_valid' or 'valid' from a nested result object."""
    flags = []

    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("is_valid", "valid") and isinstance(v, bool):
                flags.append(v)
            else:
                flags.extend(_collect_valid_flags(v))
    elif isinstance(obj, list):
        for item in obj:
            flags.extend(_collect_valid_flags(item))

    return flags


# ===============================================================
# 🧱 SINGLE DOOR VALIDATION
# ===============================================================
def validate_single_door(data):
    """Handles both normal and fire single door validation."""
    door_type = data.get("door_type", "")
    door_cat = data.get("door_category", "")
    option = str(data.get("option", "")).lower()

    if door_cat != "Single":
        return {"is_single_door": False}

    results = {}

    # --- Parse metadata and frames ---
    # NOTE: callers (for example `validate_schema`) are expected to
    # normalize rotated inputs by calling `adjust_for_rotation` once
    # before invoking this validator. This function assumes the
    # coordinate system is already non-rotated (Y is vertical).
    meta = data["metadata"]
    meta_w, meta_h = meta["width"], meta["height"]

    frames = data["geometry"]["frames"]
    outer = next(f for f in frames if f["name"] == "outer")
    inner = next(f for f in frames if f["name"] == "inner")

    outer_w, outer_h = get_dimensions(outer)
    inner_w, inner_h = get_dimensions(inner)

    outer_left, outer_right, outer_bottom, outer_top = get_frame_bounds(outer)
    inner_left, inner_right, inner_bottom, inner_top = get_frame_bounds(inner)

    # --- Frame validation ---
    top_gap = inner_top - outer_top
    bottom_gap = outer_bottom - inner_bottom
    left_gap = inner_left - outer_left
    right_gap = outer_right - inner_right

    expected_top_gap = expected_bottom_gap = BENDING_HEIGHT - BEND_ADJUST
    expected_left_gap = BENDING_WIDTH - BEND_ADJUST
    expected_right_gap = BENDING_WIDTH - expected_left_gap

    results["frame_gaps"] = dict(
        top=round(top_gap, 2),
        bottom=round(bottom_gap, 2),
        left=round(left_gap, 2),
        right=round(right_gap, 2),
        valid=(
            abs(top_gap - expected_top_gap) < 0.5
            and abs(bottom_gap - expected_bottom_gap) < 0.5
            and abs(left_gap - expected_left_gap) < 0.5
            and abs(right_gap - expected_right_gap) < 0.5
        ),
    )

    # --- Keyholes (position-based to handle rotation swaps) ---
    holes_list = data["geometry"].get("holes", [])
    hole_offset_str = meta.get("hole_offset", "150x40")
    top_bottom_offset, left_offset = map(float, hole_offset_str.lower().split("x"))

    # sort holes by Y (top first)
    holes_sorted = sorted(holes_list, key=lambda h: h["center"][1], reverse=True)

    for idx, h in enumerate(holes_sorted):
        name = h["name"]
        x, y = h["center"]

        # always measure horizontal offset from inner-left edge
        left_from_inner = x - inner_left

        # dynamically decide whether this is top or bottom hole
        if idx == 0:  # highest Y → top hole
            vertical_offset = outer_top - y
            hole_key = "hole_top"
        else:  # lowest Y → bottom hole
            vertical_offset = y - outer_bottom
            hole_key = "hole_bottom"

        valid = (
            abs(left_from_inner - left_offset) < 0.5
            and abs(vertical_offset - top_bottom_offset) < 0.5
        )

        results[hole_key] = {
            "reported_name": name,
            "left": round(left_from_inner, 2),
            "vertical": round(vertical_offset, 2),
            "is_valid": valid,
        }

    # --- Center handle cutout ---
    cutouts = {c["name"]: c["points"] for c in data["geometry"]["cutouts"]}
    if "center_handle" in cutouts:
        pts = cutouts["center_handle"]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        left, right, bottom, top = min(xs), max(xs), min(ys), max(ys)
        width, height = right - left, top - bottom
        top_gap = outer_top - top
        bottom_gap = bottom - outer_bottom
        centered = abs(top_gap - bottom_gap) < 0.5
        left_gap = left - inner_left

        results["center_handle"] = {
            "left_gap": round(left_gap, 2),
            "width": round(width, 2),
            "height": round(height, 2),
            "centered": centered,
            "is_valid": (
                abs(left_gap - BOX_GAP) < 0.5
                and abs(width - BOX_WIDTH) < 0.5
                and abs(height - BOX_HEIGHT) < 0.5
                and centered
            ),
        }

    # --- Fire door special validations ---
    if door_type == "Fire":
        cutouts = {c["name"]: c["points"] for c in data["geometry"]["cutouts"]}
        required = {"glass_cut", "keybox"}
        results["cutout_count_ok"] = required.issubset(cutouts.keys())

        # 🔹 Keybox check
        if "keybox" in cutouts:
            pts = cutouts["keybox"]
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            left, right, bottom, top = min(xs), max(xs), min(ys), max(ys)
            left_gap, right_gap = left - inner_left, inner_right - right
            bottom_gap = bottom - outer_bottom
            centered_lr = abs(left_gap - right_gap) < 0.5

            results["keybox"] = {
                "width": right - left,
                "height": top - bottom,
                "bottom_gap": bottom_gap,
                "centered_lr": centered_lr,
                "is_valid": (
                    abs(right - left - KEYBOX_W) < 0.5
                    and abs(top - bottom - KEYBOX_H) < 0.5
                    and abs(bottom_gap - KEYBOX_BOTTOM_OFFSET) < 0.5
                    and centered_lr
                ),
            }

        # 🔹 Glass cut validation
        if "glass_cut" in cutouts:
            pts = cutouts["glass_cut"]
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            left, right, bottom, top = min(xs), max(xs), min(ys), max(ys)

            left_gap = left - inner_left
            right_gap = inner_right - right
            top_gap = outer_top - top
            bottom_gap = bottom - outer_bottom
            center_y = (top + bottom) / 2
            outer_center_y = outer_h / 2


            if option == "option1":
                glass_ok = (
                    abs(left_gap - FIRE_GAP_LR) < 1
                    and abs(right_gap - FIRE_GAP_LR) < 1
                    and abs(top_gap - FIRE_GAP_TOP) < 1
                    and abs(bottom_gap - FIRE_GAP_BOTTOM) < 1
                )
            elif option == "option2":
                glass_ok = (
                    abs(left_gap - FIRE_GAP_LR) < 1
                    and abs(right_gap - FIRE_GAP_LR) < 1
                    and abs(top_gap - FIRE_GAP_TOP) < 1
                    and abs(bottom_gap - outer_center_y) < 1
                )
            elif option == "option3":
                glass_ok = (
                    abs(left_gap - FIRE_GAP_LR) < 1
                    and abs(right_gap - FIRE_GAP_LR) < 1
                    and abs(bottom_gap - FIRE_GAP_BOTTOM) < 1
                    and abs(top_gap - outer_center_y) < 1
                )
            else:
                glass_ok = False

            results["glass_cut"] = {
                "left_gap": left_gap,
                "right_gap": right_gap,
                "top_gap": top_gap,
                "bottom_gap": bottom_gap,
                "is_valid": glass_ok,
            }

    results["is_single_door"] = True
    return results


# ===============================================================
# 🚪 DOUBLE DOOR VALIDATION
# ===============================================================
def validate_double_door(data):
    if data.get("door_category") != "Double":
        return {"is_double_door": False}

    results = {"door_category": "Double", "is_valid": True}

    geometry = data["geometry"]
    frames = geometry.get("frames", [])
    cutouts = geometry.get("cutouts", [])
    holes = geometry.get("holes", [])
    cutout_names = {c["name"] for c in cutouts}

    # 1️⃣ 4 frame check
    results["frame_count_ok"] = len(frames) == 4
    if not results["frame_count_ok"]:
        results["is_valid"] = False

    # 2️⃣ gap between left and right door
    left_outer = next((f for f in frames if f["name"] == "left_outer"), None)
    right_outer = next((f for f in frames if f["name"] == "outer"), None)
    if left_outer and right_outer:
        left_right_gap = right_outer["points"][0][0] - left_outer["points"][1][0]
        results["double_door_gap_ok"] = abs(left_right_gap - DOUBLE_DOOR_GAP) < 0.5
    else:
        results["double_door_gap_ok"] = False

    # 3️⃣ keyhole/keybox on right door only
    hole_positions = [h["center"][0] for h in holes]
    if hole_positions and right_outer:
        avg_hole_x = sum(hole_positions) / len(hole_positions)
        right_center = right_outer["points"][0][0] + (right_outer["width"] / 2)
        results["keyhole_on_right_door"] = avg_hole_x > right_center - 100

    # 4️⃣ both handles should exist
    results["handles_ok"] = "left_handle" in cutout_names and "center_handle" in cutout_names

    # 5️⃣ fire double door glass validation
    if data.get("door_type") == "Fire":
        option = str(data.get("option", "")).lower()
        glass_cuts = [c for c in cutouts if "glass" in c["name"]]
        if option == "option4":
            results["glass_cut_valid"] = len(glass_cuts) == 2
        elif option == "option5":
            results["glass_cut_valid"] = len(glass_cuts) == 4
        else:
            results["glass_cut_valid"] = False

    results["is_double_door"] = True
    return results


# ===============================================================
# 🧮 MAIN ENTRY FUNCTION
# ===============================================================
def adjust_for_rotation(data):
    """Swaps X/Y meaning if metadata.rotated=True.

    This mutates the provided dict in-place and returns it. Call this
    before running geometry checks so the validators can assume a
    non-rotated coordinate system.
    """
    if not data.get("metadata", {}).get("rotated", False):
        return data  # No rotation

    geom = data["geometry"]
    for frame in geom.get("frames", []):
        frame["points"] = [(y, x) for (x, y) in frame["points"]]
    for cutout in geom.get("cutouts", []):
        cutout["points"] = [(y, x) for (x, y) in cutout["points"]]
    for hole in geom.get("holes", []):
        hole["center"] = (hole["center"][1], hole["center"][0])
    return data


def validate_schema(schema) -> bool:
    """
    Validate an in-memory schema object (either a dict matching the
    SchemasOutput contract or a Pydantic BaseModel instance) and return a
    boolean indicating pass (True) or fail (False).

    This wraps the existing dict-oriented validation functions so callers
    (for example the DXF generator) can validate a computed/received
    `SchemasOutput` object without writing it to disk.
    """
    # Convert Pydantic models to plain dict if necessary
    try:
        data = schema.dict() if hasattr(schema, "dict") else dict(schema)
    except Exception:
        # Fallback: assume already a dict-like
        data = schema

    # If the schema indicates it was rotated, adjust coordinates so the
    # downstream validators can operate in a consistent (unrotated)
    # coordinate system.
    try:
        data = adjust_for_rotation(data)
    except Exception:
        # If rotation adjustment fails, treat as validation failure and
        # print an error detail for callers.
        try:
            print(json.dumps({"validation": {"error": "rotation_adjustment_failed"}}, indent=2))
        except Exception:
            pass
        return False

    # Delegate to the correct validator based on door_category
    if isinstance(data, dict) and data.get("door_category") == "Double":
        result = validate_double_door(data)
    else:
        result = validate_single_door(data)

    # Determine pass/fail by collecting any explicit boolean validity flags
    flags = _collect_valid_flags(result)
    if flags:
        passed = all(flags)
    else:
        # Fallback: accept top-level indicators if present
        if result.get("is_single_door") is True or result.get("is_double_door") is True:
            passed = True
        else:
            passed = False

    # If validation fails, print the detailed result as JSON so callers
    # (for example the DXF generator) can report or persist it.
    if not passed:
        try:
            print(json.dumps({"validation": result}, indent=2))
        except Exception:
            # If printing fails for some reason, still return False
            pass

    return passed


def validate_geometry_auto(json_path: str):
    data = json.loads(Path(json_path).read_text())

    if data.get("door_category") == "Double":
        return validate_double_door(data)
    else:
        return validate_single_door(data)


# ===============================================================
# ▶️ RUN VALIDATION
# ===============================================================
if __name__ == "__main__":
    # Look for test-case files inside the repository's "Door TestCases" folder.
    # Use the script location to reliably find the project root, so this works
    # whether the script is run from the project root or elsewhere.
    base_dir = Path(__file__).resolve().parent.parent / "Door TestCases"
    files = [
        "SingleNormal_output.json",
        "SingleFireStandard_output.json",
        "SingleFireBottom_output.json",
        "SingleFireTop_output.json",
        "DoubleNormal_output.json",
        "DoubleStandard_output.json",
        "DoubleFourGlass_output.json",
    ]

    summary = {"files": {}, "missing": []}

    for file in files:
        file_path = base_dir / file
        if file_path.exists():
            print("\n==============================")
            print(f"🔍 Validating {file_path}")
            print("==============================")
            result = validate_geometry_auto(str(file_path))
            for k, v in result.items():
                print(f"{k}: {v}")
            # evaluate pass/fail: collect any 'is_valid'/'valid' flags and
            # consider the file passing only if all such flags are True.
            flags = _collect_valid_flags(result)
            if flags:
                passed = all(flags)
            else:
                # fallback: if there is an explicit top-level is_single_door /
                # is_double_door field use that; otherwise treat as fail.
                if result.get("is_single_door") is True or result.get("is_double_door") is True:
                    passed = True
                else:
                    passed = False

            status = "pass" if passed else "fail"

            # store result in summary
            summary["files"][file] = {
                "path": str(file_path),
                "result": result,
                "passed": passed,
                "status": status,
            }
        else:
            print(f"⚠️ Missing file: {file_path}")
            summary["missing"].append(str(file_path))

    # Add overall counts
    pass_count = sum(1 for f in summary["files"].values() if f.get("passed"))
    fail_count = sum(1 for f in summary["files"].values() if not f.get("passed"))

    summary["summary"] = {
        "validated_count": len(summary["files"]),
        "missing_count": len(summary["missing"]),
        "pass_count": pass_count,
        "fail_count": fail_count,
    }

    # Print JSON summary and write to file in the Door TestCases folder
    print("\n===== EXECUTION SUMMARY (JSON) =====")
    print(json.dumps(summary, indent=2))

    try:
        out_path = base_dir / "validation_summary.json"
        out_path.write_text(json.dumps(summary, indent=2))
        print(f"\nSaved summary to {out_path}")
    except Exception as e:
        print(f"⚠️ Failed to write summary: {e}")
