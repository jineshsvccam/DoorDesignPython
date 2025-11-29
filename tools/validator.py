import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Add parent directory to path so we can import fastapi_app
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi_app.schemas_input import DefaultInfo

# Single source of truth for all constants
_DEFAULTS = DefaultInfo()

# ===============================================================
# 🧩 COMMON HELPER FUNCTIONS
# ===============================================================
def get_frame_bounds(frame: Dict[str, Any]) -> Tuple[float, float, float, float]:
    """Extract (left, right, bottom, top) bounds from frame points."""
    xs = [p[0] for p in frame["points"]]
    ys = [p[1] for p in frame["points"]]
    return min(xs), max(xs), min(ys), max(ys)


def get_dimensions(frame: Dict[str, Any]) -> Tuple[float, float]:
    """Calculate (width, height) from frame bounds."""
    left, right, bottom, top = get_frame_bounds(frame)
    return round(right - left, 2), round(top - bottom, 2)


def _collect_valid_flags(obj: Any) -> List[bool]:
    """Recursively collect boolean flags named 'is_valid' or 'valid' from a nested result object."""
    if isinstance(obj, dict):
        flags = [v for k, v in obj.items() if k in ("is_valid", "valid") and isinstance(v, bool)]
        flags.extend(flag for v in obj.values() for flag in _collect_valid_flags(v))
        return flags
    elif isinstance(obj, list):
        return [flag for item in obj for flag in _collect_valid_flags(item)]
    return []


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
    bending_w = bending_width_override if bending_width_override is not None else _DEFAULTS.bending_width
    
    # Calculate expected dimensions based on door type
    if is_double_door:
        expected_inner_w = door_width_meas
        expected_outer_w = expected_inner_w + bending_w
    else:
        expected_outer_w = door_width_meas + left_allow + right_allow - _DEFAULTS.door_minus_measurement_width + _DEFAULTS.bending_width
        expected_inner_w = expected_outer_w - _DEFAULTS.bending_width

    expected_outer_h = door_height_meas + top_allow + bottom_allow - _DEFAULTS.door_minus_measurement_height + _DEFAULTS.bending_height
    expected_inner_h = expected_outer_h - _DEFAULTS.bending_height

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
    bending_w = bending_width_override if bending_width_override is not None else _DEFAULTS.bending_width
    
    expected_top_gap = expected_bottom_gap = _DEFAULTS.bending_height - _DEFAULTS.bend_adjust
    
    # For left door: use BEND_ADJUST on left, bending_w - BEND_ADJUST on right
    # For right/single door: reverse the gaps
    is_left_door = bending_width_override == _DEFAULTS.bending_width_double_door
    expected_left_gap = _DEFAULTS.bend_adjust if is_left_door else bending_w - _DEFAULTS.bend_adjust
    expected_right_gap = bending_w - _DEFAULTS.bend_adjust if is_left_door else _DEFAULTS.bend_adjust

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
            abs(left_gap - _DEFAULTS.box_gap) < 0.5
            and abs(width - _DEFAULTS.box_width) < 0.5
            and abs(height - _DEFAULTS.box_height) < 0.5
            and centered
        ),
    }


def _validate_single_glass_cutout(cutout_points: List[Tuple[float, float]], outer: Dict[str, Any], inner: Dict[str, Any], 
                                  outer_h: float, option: str, is_double_door: bool = False) -> Dict[str, Any]:
    """Validate a single glass cutout with fire door margins."""
    outer_left, outer_right, outer_bottom, outer_top = get_frame_bounds(outer)
    inner_left, inner_right, inner_bottom, inner_top = get_frame_bounds(inner)
    
    xs = [p[0] for p in cutout_points]
    ys = [p[1] for p in cutout_points]
    left, right, bottom, top = min(xs), max(xs), min(ys), max(ys)

    left_gap = left - inner_left
    right_gap = inner_right - right
    top_gap = outer_top - top
    bottom_gap = bottom - outer_bottom
    outer_center_y = outer_h / 2

    expected_top_gap = _DEFAULTS.fire_glass_top_margin_double if is_double_door else _DEFAULTS.fire_glass_top_margin
    lr_valid = abs(left_gap - _DEFAULTS.fire_glass_lr_margin) < 1 and abs(right_gap - _DEFAULTS.fire_glass_lr_margin) < 1

    # Standard fire glass validation for different options
    if option in ("option1", "option4"):
        glass_ok = lr_valid and abs(top_gap - expected_top_gap) < 1 and abs(bottom_gap - _DEFAULTS.fire_glass_bottom_margin) < 1
    elif option == "option2":
        glass_ok = lr_valid and abs(top_gap - expected_top_gap) < 1 and abs(bottom_gap - outer_center_y) < 1
    elif option == "option3":
        glass_ok = lr_valid and abs(bottom_gap - _DEFAULTS.fire_glass_bottom_margin) < 1 and abs(top_gap - outer_center_y) < 1
    elif option == "option5":
        glass_ok = lr_valid and (abs(top_gap - _DEFAULTS.fire_glass_bottom_margin) < 1 or abs(bottom_gap - _DEFAULTS.fire_glass_bottom_margin) < 1)
    else:
        glass_ok = False

    return {
        "left_gap": left_gap,
        "right_gap": right_gap,
        "top_gap": top_gap,
        "bottom_gap": bottom_gap,
        "is_valid": glass_ok,
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
                abs(right - left - _DEFAULTS.keybox_width) < 0.5
                and abs(top - bottom - _DEFAULTS.keybox_height) < 0.5
                and abs(bottom_gap - _DEFAULTS.keybox_bottom_offset) < 0.5
                and centered_lr
            ),
        }

    # 🔹 Glass cut validation
    if "glass_cut" in cutouts:
        results["glass_cut"] = _validate_single_glass_cutout(cutouts["glass_cut"], outer, inner, outer_h, option, is_double_door)
    
    return results


def validate_single_door(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate both normal and fire single door geometry."""
    if data.get("door_category") != "Single":
        return {"is_single_door": False}

    door_type = data.get("door_type", "")
    option = str(data.get("option", "")).lower()
    meta = data["metadata"]
    frames = data["geometry"]["frames"]
    
    outer = next(f for f in frames if f["name"] == "outer")
    inner = next(f for f in frames if f["name"] == "inner")
    outer_w, outer_h = get_dimensions(outer)

    # Validate frame dimensions and gaps
    dims = meta.get("dimensions", {})
    width_meas = dims.get("width_measurement", 0)
    height_meas = dims.get("height_measurement", 0)
    
    results: Dict[str, Any] = {
        "frame_dimensions": _validate_frame_dimensions(outer, inner, meta, width_meas, height_meas),
        "frame_gaps": _validate_frame_gaps(outer, inner),
        "is_single_door": True,
    }

    # Validate keyholes, handles, and fire door cutouts
    holes_list = data["geometry"].get("holes", [])
    if holes_list:
        results.update(_validate_holes(holes_list, outer, inner, meta))
    
    cutouts = {c["name"]: c["points"] for c in data["geometry"]["cutouts"]}
    if "center_handle" in cutouts:
        results["center_handle"] = _validate_handle(cutouts["center_handle"], outer, inner)
    
    if door_type == "Fire":
        results.update(_validate_fire_door_cutouts(cutouts, outer, inner, outer_h, option))
    
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
    meta = data["metadata"]
    geometry = data["geometry"]
    
    frames = geometry.get("frames", [])
    cutouts_list = geometry.get("cutouts", [])
    holes = geometry.get("holes", [])
    cutouts = {c["name"]: c["points"] for c in cutouts_list}
    cutout_names = set(cutouts.keys())

    results: Dict[str, Any] = {"is_double_door": True}

    # Validate frame count
    if len(frames) != 4:
        results["frame_count_ok"] = False
        results["is_valid"] = False
        return results
    
    results["frame_count_ok"] = True

    # Get frames
    left_outer = next((f for f in frames if f["name"] == "left_outer"), None)
    left_inner = next((f for f in frames if f["name"] == "left_inner"), None)
    right_outer = next((f for f in frames if f["name"] == "outer"), None)
    right_inner = next((f for f in frames if f["name"] == "inner"), None)

    # Validate gap between doors
    if left_outer and right_outer:
        left_right_gap = right_outer["points"][0][0] - left_outer["points"][1][0]
        results["double_door_gap"] = {
            "actual": round(left_right_gap, 2),
            "expected": _DEFAULTS.double_door_gap,
            "is_valid": abs(left_right_gap - _DEFAULTS.double_door_gap) < 0.5,
        }
    else:
        results["double_door_gap"] = {"is_valid": False}

    # Calculate inner width per door
    dims = meta.get("dimensions", {})
    total_width_meas = dims.get("width_measurement", 0)
    height_meas = dims.get("height_measurement", 0)
    left_allow = dims.get("left_side_allowance_width", 0)
    right_allow = dims.get("right_side_allowance_width", 0)
    
    half_width_with_allowances = (total_width_meas + left_allow + right_allow) / 2
    half_door_minus = (_DEFAULTS.door_minus_measurement_width + _DEFAULTS.double_door_gap) / 2
    inner_width_per_door = half_width_with_allowances - half_door_minus

    # Validate left door (uses bending_width_double_door)
    if left_outer and left_inner:
        results["left_door"] = {}
        results["left_door"]["frame_dimensions"] = _validate_frame_dimensions(
            left_outer, left_inner, meta, inner_width_per_door, height_meas,
            bending_width_override=_DEFAULTS.bending_width_double_door, is_double_door=True
        )
        results["left_door"]["frame_gaps"] = _validate_frame_gaps(left_outer, left_inner, bending_width_override=_DEFAULTS.bending_width_double_door)
        
        # Validate left handle
        if "left_handle" in cutouts:
            results["left_door"]["left_handle"] = _validate_handle(
                cutouts["left_handle"], left_outer, left_inner, "left_handle", is_left_door=True
            )

    # Validate right door (uses bending_width)
    if right_outer and right_inner:
        results["right_door"] = {}
        results["right_door"]["frame_dimensions"] = _validate_frame_dimensions(
            right_outer, right_inner, meta, inner_width_per_door, height_meas,
            bending_width_override=_DEFAULTS.bending_width, is_double_door=True
        )
        results["right_door"]["frame_gaps"] = _validate_frame_gaps(right_outer, right_inner)
        
        # Validate holes
        if holes:
            results["right_door"].update(_validate_holes(holes, right_outer, right_inner, meta))
        
        # Validate center handle
        if "center_handle" in cutouts:
            results["right_door"]["right_handle"] = _validate_handle(
                cutouts["center_handle"], right_outer, right_inner, "right_handle", is_left_door=False
            )

    # Validate handles presence
    results["handles_ok"] = "left_handle" in cutout_names and "center_handle" in cutout_names

    # 7️⃣ Fire double door glass validation
    if door_type == "Fire":
        glass_cuts = [c for c in cutouts_list if "glass" in c["name"]]
        expected_glass_count = 2 if option == "option4" else 4 if option == "option5" else 0
        results["glass_cut_valid"] = len(glass_cuts) == expected_glass_count
        
        # Validate glass cuts for both doors using helper function
        for door_side, door_outer, door_inner in [("left", left_outer, left_inner), ("right", right_outer, right_inner)]:
            if not door_outer or not door_inner:
                continue
                
            glass_names = [name for name in cutout_names if "glass" in name and f"_{door_side}" in name]
            if not glass_names:
                continue
            
            door_outer_h = get_dimensions(door_outer)[1]
            door_key = f"{door_side}_door"
            
            if door_key not in results:
                results[door_key] = {}
            
            for glass_name in glass_names:
                if glass_name in cutouts:
                    results[door_key][glass_name] = _validate_single_glass_cutout(
                        cutouts[glass_name], door_outer, door_inner, door_outer_h, option, is_double_door=True
                    )

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
    """Validate a schema (dict or Pydantic model) and return pass/fail.
    
    Automatically adjusts for rotation if needed. Returns True if all
    validation checks pass, False otherwise. Prints detailed results on failure.
    """
    # Convert Pydantic models to plain dict if necessary
    try:
        data = schema.dict() if hasattr(schema, "dict") else dict(schema)
    except Exception:
        data = schema

    # Adjust for rotation if needed
    try:
        data = adjust_for_rotation(data)
    except Exception:
        print(json.dumps({"validation": {"error": "rotation_adjustment_failed"}}, indent=2))
        return False

    # Run appropriate validator
    result = validate_double_door(data) if data.get("door_category") == "Double" else validate_single_door(data)

    # Determine pass/fail from validation flags
    flags = _collect_valid_flags(result)
    passed = all(flags) if flags else result.get("is_single_door") or result.get("is_double_door") or False

    # Print detailed results on failure
    if not passed:
        print(json.dumps({"validation": result}, indent=2))

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
            print(f"Validating {file_path}")
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
            print(f"Missing file: {file_path}")
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
        print(f"Failed to write summary: {e}")
