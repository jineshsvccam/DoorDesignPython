import json
import sys
from pathlib import Path
import copy

# Add tools directory to path for validator import
sys.path.insert(0, str(Path(__file__).resolve().parent))

from validator import (
    validate_schema,
    _collect_valid_flags,
    adjust_for_rotation,
    validate_single_door,
    validate_double_door,
)

# ===============================================================
# � VALIDATE SINGLE _transformed.json FILE
# ===============================================================
def validate_single_transformed_file(file_path: str) -> dict:
    """Validate a single transformed JSON file and return validation results.
    
    Returns a dict with structure:
    {
        "file_name": str,
        "door_count": int,
        "pass_count": int,
        "fail_count": int,
        "doors": [list of door validation results]
    }
    """
    file_path_obj = Path(file_path)
    if not file_path_obj.exists():
        return {
            "file_name": file_path_obj.name,
            "error": f"File not found: {file_path}",
            "door_count": 0,
            "pass_count": 0,
            "fail_count": 0,
            "doors": []
        }
    
    print(f"🔍 Validating: {file_path_obj.name}")
    try:
        data = json.loads(file_path_obj.read_text())
    except Exception as e:
        return {
            "file_name": file_path_obj.name,
            "error": f"Failed to read file: {e}",
            "door_count": 0,
            "pass_count": 0,
            "fail_count": 0,
            "doors": []
        }
    
    file_results = []
    for idx, door in enumerate(data.get("doors", []), start=1):
        print(f"  ▶ Door {idx}")
        
        door_result = {"door_index": idx, "file": file_path_obj.name, "results": {}}
        
        # Validate both original_response and transformed
        for label in ("original_response", "transformed"):
            section = door.get(label)
            if not section:
                door_result["results"][label] = {"error": "missing"}
                continue
            
            try:
                section_copy = copy.deepcopy(section)
                if label == "transformed" and section_copy.get("metadata", {}).get("rotated"):
                    geom = section_copy["geometry"]
                    outer_height_orig = section_copy["metadata"]["width"]
                    
                    all_pts = []
                    for frame in geom.get("frames", []):
                        all_pts.extend(frame["points"])
                    for cutout in geom.get("cutouts", []):
                        all_pts.extend(cutout["points"])
                    for hole in geom.get("holes", []):
                        all_pts.append(hole["center"])
                    
                    min_x = min(p[0] for p in all_pts) if all_pts else 0
                    min_y = min(p[1] for p in all_pts) if all_pts else 0
                    translate_x = min_x
                    translate_y = min_y
                    
                    def inverse_rotate(pt):
                        x_rot = pt[0] - translate_x
                        y_rot = pt[1] - translate_y
                        return (y_rot, outer_height_orig - x_rot)
                    
                    for frame in geom.get("frames", []):
                        frame["points"] = [inverse_rotate(p) for p in frame["points"]]
                    for cutout in geom.get("cutouts", []):
                        cutout["points"] = [inverse_rotate(p) for p in cutout["points"]]
                    for hole in geom.get("holes", []):
                        hole["center"] = inverse_rotate(hole["center"])
                    
                    # Swap width and height back after inverse rotation
                    orig_width = section_copy["metadata"]["width"]
                    orig_height = section_copy["metadata"]["height"]
                    section_copy["metadata"]["width"] = orig_height
                    section_copy["metadata"]["height"] = orig_width
                    section_copy["metadata"]["rotated"] = False
                
                result = validate_schema(section_copy)
                if isinstance(result, dict):
                    door_result["results"][label] = result
                    flags = _collect_valid_flags(result)
                    door_result["results"][label]["passed"] = all(flags) if flags else False
                else:
                    door_result["results"][label] = {"passed": bool(result)}
            except Exception as e:
                door_result["results"][label] = {"error": str(e), "passed": False}
        
        file_results.append(door_result)
    
    # Count passes/fails
    pass_count = sum(1 for d in file_results if all(
        r.get("passed") for r in d["results"].values() if isinstance(r, dict)
    ))
    fail_count = len(file_results) - pass_count
    
    result = {
        "file_name": file_path_obj.name,
        "door_count": len(file_results),
        "pass_count": pass_count,
        "fail_count": fail_count,
        "doors": file_results,
    }
    
    print(f"  ✅ Validation complete: {pass_count} passed, {fail_count} failed")
    return result


# ===============================================================
# �🚀 VALIDATE ALL _transformed.json FILES
# ===============================================================
def validate_transformed_folder(folder_path: str):
    folder = Path(folder_path)
    summary = {"files": {}, "summary": {}}

    transformed_files = sorted(folder.glob("*_transformed.json"))
    if not transformed_files:
        print("⚠️ No *_transformed.json files found.")
        return

    for file_path in transformed_files:
        print(f"\n🔍 Validating: {file_path.name}")
        try:
            data = json.loads(file_path.read_text())
        except Exception as e:
            print(f"❌ Failed to read {file_path}: {e}")
            continue

        file_results = []
        for idx, door in enumerate(data.get("doors", []), start=1):
            print(f"  ▶ Door {idx}")

            door_result = {"door_index": idx, "file": file_path.name, "results": {}}

            # Validate both original_response and transformed
            for label in ("original_response", "transformed"):
                section = door.get(label)
                if not section:
                    door_result["results"][label] = {"error": "missing"}
                    continue

                try:
                    # For transformed rotated geometry, apply proper inverse rotation
                    # to convert back to original non-rotated coordinate space.
                    section_copy = copy.deepcopy(section)
                    if label == "transformed" and section_copy.get("metadata", {}).get("rotated"):
                        geom = section_copy["geometry"]
                        # Get original outer_height (equals transformed width after rotation)
                        outer_height_orig = section_copy["metadata"]["width"]
                        
                        # Calculate translate values from current geometry
                        # (they were applied to make coordinates non-negative)
                        all_pts = []
                        for frame in geom.get("frames", []):
                            all_pts.extend(frame["points"])
                        for cutout in geom.get("cutouts", []):
                            all_pts.extend(cutout["points"])
                        for hole in geom.get("holes", []):
                            all_pts.append(hole["center"])
                        
                        min_x = min(p[0] for p in all_pts) if all_pts else 0
                        min_y = min(p[1] for p in all_pts) if all_pts else 0
                        translate_x = min_x  # Should be close to 0 or frame thickness
                        translate_y = min_y
                        
                        # Apply inverse rotation: (x', y') -> (y' - ty, outer_height - (x' - tx))
                        def inverse_rotate(pt):
                            x_rot = pt[0] - translate_x
                            y_rot = pt[1] - translate_y
                            return (y_rot, outer_height_orig - x_rot)
                        
                        for frame in geom.get("frames", []):
                            frame["points"] = [inverse_rotate(p) for p in frame["points"]]
                        for cutout in geom.get("cutouts", []):
                            cutout["points"] = [inverse_rotate(p) for p in cutout["points"]]
                        for hole in geom.get("holes", []):
                            hole["center"] = inverse_rotate(hole["center"])
                        
                        # Swap width and height back after inverse rotation
                        orig_width = section_copy["metadata"]["width"]
                        orig_height = section_copy["metadata"]["height"]
                        section_copy["metadata"]["width"] = orig_height
                        section_copy["metadata"]["height"] = orig_width
                        # Mark as not rotated so validator treats it as non-rotated geometry
                        section_copy["metadata"]["rotated"] = False
                    
                    result = validate_schema(section_copy)
                    # `validate_schema` may return either a detailed dict
                    # (with validation fields) or a simple boolean. Handle
                    # both cases safely.
                    if isinstance(result, dict):
                        door_result["results"][label] = result
                        # collect pass/fail
                        flags = _collect_valid_flags(result)
                        door_result["results"][label]["passed"] = all(flags) if flags else False
                    else:
                        # boolean result: store minimal dict with passed flag
                        door_result["results"][label] = {"passed": bool(result)}
                except Exception as e:
                    door_result["results"][label] = {"error": str(e), "passed": False}

            file_results.append(door_result)

            # If the door failed (either original or transformed), attach
            # the detailed validator `result` (prefer `transformed` if it
            # failed). This provides the full breakdown (frame_gaps,
            # cutouts, holes, etc.) in the summary JSON.
            def _attach_detailed_result_if_failed(dr):
                # dr is door_result
                # prefer transformed failure
                for lbl in ("transformed", "original_response"):
                    entry = dr["results"].get(lbl)
                    if not entry:
                        continue
                    passed = bool(entry.get("passed")) if isinstance(entry, dict) else bool(entry)
                    if passed:
                        continue

                    # If the entry already contains the detailed dict
                    # (validator returned a dict), use it directly.
                    if isinstance(entry, dict) and ("frame_gaps" in entry or "is_single_door" in entry or "is_double_door" in entry):
                        dr["result"] = entry
                        return

                    # Otherwise, compute a detailed result by calling the
                    # appropriate validator. Make a deepcopy so we don't
                    # mutate the original.
                    try:
                        detailed = copy.deepcopy(door.get(lbl) or door)
                        # For transformed rotated geometry, apply proper inverse rotation
                        if lbl == "transformed" and detailed.get("metadata", {}).get("rotated"):
                            geom = detailed["geometry"]
                            outer_height_orig = detailed["metadata"]["width"]
                            
                            # Calculate translate values
                            all_pts = []
                            for frame in geom.get("frames", []):
                                all_pts.extend(frame["points"])
                            for cutout in geom.get("cutouts", []):
                                all_pts.extend(cutout["points"])
                            for hole in geom.get("holes", []):
                                all_pts.append(hole["center"])
                            
                            min_x = min(p[0] for p in all_pts) if all_pts else 0
                            min_y = min(p[1] for p in all_pts) if all_pts else 0
                            translate_x = min_x
                            translate_y = min_y
                            
                            def inverse_rotate(pt):
                                x_rot = pt[0] - translate_x
                                y_rot = pt[1] - translate_y
                                return (y_rot, outer_height_orig - x_rot)
                            
                            for frame in geom.get("frames", []):
                                frame["points"] = [inverse_rotate(p) for p in frame["points"]]
                            for cutout in geom.get("cutouts", []):
                                cutout["points"] = [inverse_rotate(p) for p in cutout["points"]]
                            for hole in geom.get("holes", []):
                                hole["center"] = inverse_rotate(hole["center"])
                            
                            # Swap width and height back after inverse rotation
                            orig_width = detailed["metadata"]["width"]
                            orig_height = detailed["metadata"]["height"]
                            detailed["metadata"]["width"] = orig_height
                            detailed["metadata"]["height"] = orig_width
                            detailed["metadata"]["rotated"] = False
                        if detailed.get("door_category") == "Double":
                            dr["result"] = validate_double_door(detailed)
                        else:
                            dr["result"] = validate_single_door(detailed)
                        return
                    except Exception:
                        # If we can't compute a detailed result, skip
                        # attaching it.
                        return

            _attach_detailed_result_if_failed(door_result)

        # Summary for this file
        pass_count = sum(1 for d in file_results if all(
            r.get("passed") for r in d["results"].values() if isinstance(r, dict)
        ))
        fail_count = len(file_results) - pass_count

        summary["files"][file_path.name] = {
            "door_count": len(file_results),
            "pass_count": pass_count,
            "fail_count": fail_count,
            "doors": file_results,
        }

    # Compute global summary
    total_files = len(summary["files"])
    total_doors = sum(f["door_count"] for f in summary["files"].values())
    total_pass = sum(f["pass_count"] for f in summary["files"].values())
    total_fail = sum(f["fail_count"] for f in summary["files"].values())

    summary["summary"] = {
        "file_count": total_files,
        "door_count": total_doors,
        "pass_count": total_pass,
        "fail_count": total_fail,
    }

    # Save summary JSON
    out_path = folder / "batch_validation_summary.json"
    out_path.write_text(json.dumps(summary, indent=2))
    print(f"\n✅ Summary saved to: {out_path}")


# ===============================================================
# ▶️ RUN AS SCRIPT
# ===============================================================
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate transformed JSON files")
    parser.add_argument("--file", "-f", type=str, help="Validate a single file (path or filename)")
    parser.add_argument("--folder", type=str, help="Validate all files in a folder")
    args = parser.parse_args()
    
    if args.file:
        # Validate single file
        file_path = Path(args.file)
        if not file_path.exists():
            # Try looking in outputBulk directory
            base_dir = Path(__file__).resolve().parent.parent / "outputBulk"
            file_path = base_dir / args.file
        
        if not file_path.exists():
            print(f"❌ File not found: {args.file}")
            sys.exit(1)
        
        result = validate_single_transformed_file(str(file_path))
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"File: {result['file_name']}")
        print(f"Doors: {result['door_count']}")
        print(f"Passed: {result['pass_count']}")
        print(f"Failed: {result['fail_count']}")
        print(f"{'='*60}")
        
        # Save validation report
        output_path = file_path.with_name(file_path.stem + "_validation.json")
        with open(output_path, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"\n✅ Validation report saved to: {output_path}")
        
    else:
        # Validate all files in folder (default behavior)
        base_dir = Path(args.folder) if args.folder else Path(__file__).resolve().parent.parent / "outputBulk"
        validate_transformed_folder(str(base_dir))
