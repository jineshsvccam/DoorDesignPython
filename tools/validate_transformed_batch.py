import json
from pathlib import Path
import copy
from validator import (
    validate_schema,
    _collect_valid_flags,
    adjust_for_rotation,
    validate_single_door,
    validate_double_door,
)

# ===============================================================
# 🚀 VALIDATE ALL _transformed.json FILES
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
    # Adjust folder as needed (default: same directory)
    # The `output` folder lives at the repository root, one level above
    # the `tools` directory where this script is located.
    base_dir = Path(__file__).resolve().parent.parent / "output"
    validate_transformed_folder(str(base_dir))
