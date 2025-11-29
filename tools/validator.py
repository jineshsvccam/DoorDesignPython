import json
import sys
from pathlib import Path
from typing import Any, Dict

# Add parent directory to path so we can import fastapi_app
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Import default values from schemas to avoid duplication
from fastapi_app.schemas_input import DefaultInfo

# Create a default instance to use as fallback values
_DEFAULTS = DefaultInfo()

# Expose constants for backward compatibility and easy access
BENDING_WIDTH = _DEFAULTS.bending_width
BENDING_HEIGHT = _DEFAULTS.bending_height
BEND_ADJUST = _DEFAULTS.bend_adjust
DOUBLE_DOOR_GAP = _DEFAULTS.double_door_gap
DOOR_MINUS_W = _DEFAULTS.door_minus_measurement_width
DOOR_MINUS_H = _DEFAULTS.door_minus_measurement_height
BENDING_W_DOUBLE = _DEFAULTS.bending_width_double_door

KEYBOX_W = _DEFAULTS.keybox_width
KEYBOX_H = _DEFAULTS.keybox_height
KEYBOX_BOTTOM_OFFSET = _DEFAULTS.keybox_bottom_offset

BOX_GAP = _DEFAULTS.box_gap
BOX_WIDTH = _DEFAULTS.box_width
BOX_HEIGHT = _DEFAULTS.box_height

FIRE_GAP_LR = _DEFAULTS.fire_glass_lr_margin
FIRE_GAP_TOP = _DEFAULTS.fire_glass_top_margin
FIRE_GAP_TOP_DOUBLE = _DEFAULTS.fire_glass_top_margin_double
FIRE_GAP_BOTTOM = _DEFAULTS.fire_glass_bottom_margin

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
def _validate_frame_dimensions(outer, inner, meta, door_width_meas, door_height_meas, bending_width_override=None, is_double_door=False):
    """Validate frame dimensions for a single door (or one side of double door)."""
    outer_w, outer_h = get_dimensions(outer)
    inner_w, inner_h = get_dimensions(inner)
    
    dims = meta.get("dimensions", {})
    left_allow = dims.get("left_side_allowance_width", 0)
    right_allow = dims.get("right_side_allowance_width", 0)
    top_allow = dims.get("top_side_allowance_height", 0)
    bottom_allow = dims.get("bottom_side_allowance_height", 0)

    # Use override bending width for double doors, otherwise use default
    bending_w = bending_width_override if bending_width_override is not None else BENDING_WIDTH
    
    # For double doors, door_width_meas is already the inner width per door
    # For single doors, we need to calculate it
    if is_double_door:
        expected_inner_w = door_width_meas
        expected_outer_w = expected_inner_w + bending_w
    else:
        expected_outer_w = door_width_meas + left_allow + right_allow - DOOR_MINUS_W + BENDING_WIDTH
        expected_inner_w = expected_outer_w - BENDING_WIDTH

    # Height calculation is same for both
    expected_outer_h = door_height_meas + top_allow + bottom_allow - DOOR_MINUS_H + BENDING_HEIGHT
    expected_inner_h = expected_outer_h - BENDING_HEIGHT

    return {
        "outer_frame": {
            "actual_width": round(outer_w, 2),
            "actual_height": round(outer_h, 2),
            "expected_width": round(expected_outer_w, 2),
            "expected_height": round(expected_inner_h, 2),
            "width_valid": abs(outer_w - expected_outer_w) < 0.5,
            "height_valid": abs(outer_h - expected_inner_h) < 0.5,
        },
        "inner_frame": {
            "actual_width": round(inner_w, 2),
            "actual_height": round(inner_h, 2),
            "expected_width": round(expected_inner_w, 2),
            "expected_height": round(expected_outer_h, 2),
            "width_valid": abs(inner_w - expected_inner_w) < 0.5,
            "height_valid": abs(inner_h - expected_outer_h) < 0.5,
        },
        "is_valid": (
            abs(outer_w - expected_outer_w) < 0.5
            and abs(outer_h - expected_inner_h) < 0.5
            and abs(inner_w - expected_inner_w) < 0.5
            and abs(inner_h - expected_outer_h) < 0.5
        ),
    }


def _validate_frame_gaps(outer, inner, bending_width_override=None):
    """Validate gaps between outer and inner frames.
    
    For left door in double door setup, use BENDING_W_DOUBLE instead of BENDING_WIDTH.
    """
    outer_left, outer_right, outer_bottom, outer_top = get_frame_bounds(outer)
    inner_left, inner_right, inner_bottom, inner_top = get_frame_bounds(inner)
    
    top_gap = inner_top - outer_top
    bottom_gap = outer_bottom - inner_bottom
    left_gap = inner_left - outer_left
    right_gap = outer_right - inner_right

    # Use override bending width for double doors left door, otherwise use default
    bending_w = bending_width_override if bending_width_override is not None else BENDING_WIDTH
    
    expected_top_gap = expected_bottom_gap = BENDING_HEIGHT - BEND_ADJUST
    # For left door (with bending_w=43), left_gap should be BEND_ADJUST (12)
    # For right door (with bending_w=31), left_gap should be bending_w - BEND_ADJUST (19)
    if bending_width_override == BENDING_W_DOUBLE:
        # Left door in double door setup
        expected_left_gap = BEND_ADJUST
        expected_right_gap = bending_w - BEND_ADJUST
    else:
        # Right door or single door
        expected_left_gap = bending_w - BEND_ADJUST
        expected_right_gap = BEND_ADJUST

    return {
        "top": round(top_gap, 2),
        "bottom": round(bottom_gap, 2),
        "left": round(left_gap, 2),
        "right": round(right_gap, 2),
        "valid": (
            abs(top_gap - expected_top_gap) < 0.5
            and abs(bottom_gap - expected_bottom_gap) < 0.5
            and abs(left_gap - expected_left_gap) < 0.5
            and abs(right_gap - expected_right_gap) < 0.5
        ),
    }


def _validate_holes(holes_list, outer, inner, meta):
    """Validate keyhole positions."""
    outer_left, outer_right, outer_bottom, outer_top = get_frame_bounds(outer)
    inner_left, inner_right, inner_bottom, inner_top = get_frame_bounds(inner)
    
    hole_offset_str = meta.get("hole_offset", "150x40")
    top_bottom_offset, left_offset = map(float, hole_offset_str.lower().split("x"))

    # sort holes by Y (top first)
    holes_sorted = sorted(holes_list, key=lambda h: h["center"][1], reverse=True)

    results = {}
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
    
    return results


def _validate_handle(cutout_points, outer, inner, handle_name="center_handle", is_left_door=False):
    """Validate handle cutout dimensions and position.
    
    For left door handles, measure gap from right edge of inner frame.
    For right door handles, measure gap from left edge of inner frame.
    """
    outer_left, outer_right, outer_bottom, outer_top = get_frame_bounds(outer)
    inner_left, inner_right, inner_bottom, inner_top = get_frame_bounds(inner)
    
    xs = [p[0] for p in cutout_points]
    ys = [p[1] for p in cutout_points]
    left, right, bottom, top = min(xs), max(xs), min(ys), max(ys)
    width, height = right - left, top - bottom
    top_gap = outer_top - top
    bottom_gap = bottom - outer_bottom
    centered = abs(top_gap - bottom_gap) < 0.5
    
    # For left door, measure from right edge of inner frame (handle is on right side)
    # For right door (or single door), measure from left edge of inner frame
    if is_left_door:
        left_gap = inner_right - right  # distance from inner_right edge to handle's right edge
    else:
        left_gap = left - inner_left  # distance from inner_left edge to handle's left edge

    return {
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


def _validate_fire_door_cutouts(cutouts, outer, inner, outer_h, option, is_double_door=False):
    """Validate fire door specific cutouts (keybox and glass).
    
    For double doors, use FIRE_GAP_TOP_DOUBLE (150) instead of FIRE_GAP_TOP (170).
    """
    outer_left, outer_right, outer_bottom, outer_top = get_frame_bounds(outer)
    inner_left, inner_right, inner_bottom, inner_top = get_frame_bounds(inner)
    
    results = {}
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
        outer_center_y = outer_h / 2

        # Use different top gap for double doors
        expected_top_gap = FIRE_GAP_TOP_DOUBLE if is_double_door else FIRE_GAP_TOP

        if option == "option1" or option == "option4":
            # Option1: Single door standard fire glass
            # Option4: Double door standard fire glass (one panel per door)
            glass_ok = (
                abs(left_gap - FIRE_GAP_LR) < 1
                and abs(right_gap - FIRE_GAP_LR) < 1
                and abs(top_gap - expected_top_gap) < 1
                and abs(bottom_gap - FIRE_GAP_BOTTOM) < 1
            )
        elif option == "option2":
            glass_ok = (
                abs(left_gap - FIRE_GAP_LR) < 1
                and abs(right_gap - FIRE_GAP_LR) < 1
                and abs(top_gap - expected_top_gap) < 1
                and abs(bottom_gap - outer_center_y) < 1
            )
        elif option == "option3":
            glass_ok = (
                abs(left_gap - FIRE_GAP_LR) < 1
                and abs(right_gap - FIRE_GAP_LR) < 1
                and abs(bottom_gap - FIRE_GAP_BOTTOM) < 1
                and abs(top_gap - outer_center_y) < 1
            )
        elif option == "option5":
            # Option5: Four glass panels (two per door, split top and bottom)
            # Each panel has LR margins of 190, and one fixed margin (240) on either top or bottom
            # The other margin is variable (center split area)
            glass_ok = (
                abs(left_gap - FIRE_GAP_LR) < 1
                and abs(right_gap - FIRE_GAP_LR) < 1
                and (abs(top_gap - FIRE_GAP_BOTTOM) < 1 or abs(bottom_gap - FIRE_GAP_BOTTOM) < 1)
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
    
    return results


def validate_single_door(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handles both normal and fire single door validation."""
    door_type = data.get("door_type", "")
    door_cat = data.get("door_category", "")
    option = str(data.get("option", "")).lower()

    if door_cat != "Single":
        return {"is_single_door": False}

    results: Dict[str, Any] = {}

    # --- Parse metadata and frames ---
    # NOTE: callers (for example `validate_schema`) are expected to
    # normalize rotated inputs by calling `adjust_for_rotation` once
    # before invoking this validator. This function assumes the
    # coordinate system is already non-rotated (Y is vertical).
    meta = data["metadata"]
    frames = data["geometry"]["frames"]
    outer = next(f for f in frames if f["name"] == "outer")
    inner = next(f for f in frames if f["name"] == "inner")

    outer_w, outer_h = get_dimensions(outer)
    inner_w, inner_h = get_dimensions(inner)

    outer_left, outer_right, outer_bottom, outer_top = get_frame_bounds(outer)
    inner_left, inner_right, inner_bottom, inner_top = get_frame_bounds(inner)

    # --- Frame dimensions validation ---
    dims = meta.get("dimensions", {})
    width_meas = dims.get("width_measurement", 0)
    height_meas = dims.get("height_measurement", 0)
    
    results["frame_dimensions"] = _validate_frame_dimensions(outer, inner, meta, width_meas, height_meas)

    # --- Frame gaps validation ---
    results["frame_gaps"] = _validate_frame_gaps(outer, inner)

    # --- Keyholes (position-based to handle rotation swaps) ---
    holes_list = data["geometry"].get("holes", [])
    hole_results = _validate_holes(holes_list, outer, inner, meta)
    results.update(hole_results)

    # --- Center handle cutout ---
    cutouts = {c["name"]: c["points"] for c in data["geometry"]["cutouts"]}
    if "center_handle" in cutouts:
        results["center_handle"] = _validate_handle(cutouts["center_handle"], outer, inner)

    # --- Fire door special validations ---
    if door_type == "Fire":
        fire_results = _validate_fire_door_cutouts(cutouts, outer, inner, outer_h, option)
        results.update(fire_results)

    results["is_single_door"] = True
    return results


# ===============================================================
# 🚪 DOUBLE DOOR VALIDATION
# ===============================================================
def validate_double_door(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate double door with detailed checks for both left and right doors."""
    if data.get("door_category") != "Double":
        return {"is_double_door": False}

    door_type = data.get("door_type", "")
    option = str(data.get("option", "")).lower()
    
    results: Dict[str, Any] = {"door_category": "Double"}
    
    meta = data["metadata"]
    geometry = data["geometry"]
    frames = geometry.get("frames", [])
    cutouts_list = geometry.get("cutouts", [])
    holes = geometry.get("holes", [])
    cutouts = {c["name"]: c["points"] for c in cutouts_list}
    cutout_names = set(cutouts.keys())

    # 1️⃣ Frame count check
    results["frame_count_ok"] = len(frames) == 4
    if not results["frame_count_ok"]:
        results["is_valid"] = False
        results["is_double_door"] = True
        return results

    # Get all frames
    left_outer = next((f for f in frames if f["name"] == "left_outer"), None)
    left_inner = next((f for f in frames if f["name"] == "left_inner"), None)
    right_outer = next((f for f in frames if f["name"] == "outer"), None)
    right_inner = next((f for f in frames if f["name"] == "inner"), None)

    # 2️⃣ Gap between left and right door
    if left_outer and right_outer:
        left_right_gap = right_outer["points"][0][0] - left_outer["points"][1][0]
        results["double_door_gap"] = {
            "actual": round(left_right_gap, 2),
            "expected": DOUBLE_DOOR_GAP,
            "is_valid": abs(left_right_gap - DOUBLE_DOOR_GAP) < 0.5,
        }
    else:
        results["double_door_gap"] = {"is_valid": False}

    # 3️⃣ Calculate door widths for double door
    dims = meta.get("dimensions", {})
    total_width_meas = dims.get("width_measurement", 0)
    height_meas = dims.get("height_measurement", 0)
    left_allow = dims.get("left_side_allowance_width", 0)
    right_allow = dims.get("right_side_allowance_width", 0)
    
    # Formula: (1240 + 25 + 25) / 2 = 645, then 645 - (68+3)/2 = 645 - 35.5 = 609.5
    half_width_with_allowances = (total_width_meas + left_allow + right_allow) / 2
    half_door_minus = (DOOR_MINUS_W + DOUBLE_DOOR_GAP) / 2
    inner_width_per_door = half_width_with_allowances - half_door_minus

    # 4️⃣ Validate LEFT DOOR frames (uses BENDING_W_DOUBLE = 43.0)
    if left_outer and left_inner:
        results["left_door"] = {}
        results["left_door"]["frame_dimensions"] = _validate_frame_dimensions(
            left_outer, left_inner, meta, inner_width_per_door, height_meas,
            bending_width_override=BENDING_W_DOUBLE, is_double_door=True
        )
        results["left_door"]["frame_gaps"] = _validate_frame_gaps(left_outer, left_inner, bending_width_override=BENDING_W_DOUBLE)
        
        # Left handle validation - left_handle is always for left door
        if "left_handle" in cutouts:
            results["left_door"]["left_handle"] = _validate_handle(
                cutouts["left_handle"], left_outer, left_inner, "left_handle", is_left_door=True
            )

    # 5️⃣ Validate RIGHT DOOR frames (uses BENDING_WIDTH = 31.0)
    if right_outer and right_inner:
        results["right_door"] = {}
        results["right_door"]["frame_dimensions"] = _validate_frame_dimensions(
            right_outer, right_inner, meta, inner_width_per_door, height_meas,
            bending_width_override=BENDING_WIDTH, is_double_door=True
        )
        results["right_door"]["frame_gaps"] = _validate_frame_gaps(right_outer, right_inner)
        
        # Holes validation (on right door only)
        if holes:
            hole_results = _validate_holes(holes, right_outer, right_inner, meta)
            results["right_door"].update(hole_results)
        
        # Center handle validation - center_handle is always for right door
        if "center_handle" in cutouts:
            results["right_door"]["right_handle"] = _validate_handle(
                cutouts["center_handle"], right_outer, right_inner, "right_handle", is_left_door=False
            )

    # 6️⃣ Both handles should exist
    results["handles_ok"] = "left_handle" in cutout_names and "center_handle" in cutout_names

    # 7️⃣ Fire double door glass validation
    if door_type == "Fire":
        glass_cuts = [c for c in cutouts_list if "glass" in c["name"]]
        if option == "option4":
            results["glass_cut_valid"] = len(glass_cuts) == 2
        elif option == "option5":
            results["glass_cut_valid"] = len(glass_cuts) == 4
        else:
            results["glass_cut_valid"] = False
        
        # Validate glass cuts for both doors if they exist
        # Check for glass names containing "_left" or "_right" to properly assign to doors
        left_glass_names = [name for name in cutout_names if "glass" in name and "_left" in name]
        right_glass_names = [name for name in cutout_names if "glass" in name and "_right" in name]
        
        # Validate left door glass if exists
        if left_glass_names and left_outer and left_inner:
            left_outer_h = get_dimensions(left_outer)[1]
            for glass_name in left_glass_names:
                if glass_name in cutouts:
                    # Create a temporary cutouts dict for fire validation
                    temp_cutouts = {"glass_cut": cutouts[glass_name]}
                    if "keybox" in cutouts:
                        temp_cutouts["keybox"] = cutouts["keybox"]
                    
                    fire_results = _validate_fire_door_cutouts(
                        temp_cutouts, left_outer, left_inner, left_outer_h, option, is_double_door=True
                    )
                    if "left_door" not in results:
                        results["left_door"] = {}
                    results["left_door"][glass_name] = fire_results.get("glass_cut", {})
        
        # Validate right door glass if exists
        if right_glass_names and right_outer and right_inner:
            right_outer_h = get_dimensions(right_outer)[1]
            for glass_name in right_glass_names:
                if glass_name in cutouts:
                    # Create a temporary cutouts dict for fire validation
                    temp_cutouts = {"glass_cut": cutouts[glass_name]}
                    if "keybox" in cutouts:
                        temp_cutouts["keybox"] = cutouts["keybox"]
                    
                    fire_results = _validate_fire_door_cutouts(
                        temp_cutouts, right_outer, right_inner, right_outer_h, option, is_double_door=True
                    )
                    if "right_door" not in results:
                        results["right_door"] = {}
                    results["right_door"][glass_name] = fire_results.get("glass_cut", {})

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
    """Load and validate a door geometry JSON file."""
    data = json.loads(Path(json_path).read_text())
    return validate_double_door(data) if data.get("door_category") == "Double" else validate_single_door(data)


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
            
            # Evaluate pass/fail by collecting 'is_valid'/'valid' flags
            flags = _collect_valid_flags(result)
            if flags:
                passed = all(flags)
            else:
                # Fallback: check top-level door type indicators
                passed = result.get("is_single_door") is True or result.get("is_double_door") is True

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
