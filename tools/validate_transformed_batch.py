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
                    result = validate_schema(section)
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
                        detailed = adjust_for_rotation(detailed)
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
