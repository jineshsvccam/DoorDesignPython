import sys
import json
import argparse
from pathlib import Path
import traceback
import difflib

# Ensure project root is on sys.path so imports work the same as other tools/tests
sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi_app.schemas_input import DoorDXFRequest
from geometry.door_geometry import compute_door_geometry


def discover_testcases(test_dir: Path):
    # Exclude any files that are expected-output artifacts (contain 'output' in the filename)
    files = sorted([p for p in test_dir.glob("*.json") if "output" not in p.stem.lower()])
    return files


def load_request_from_file(path: Path) -> DoorDXFRequest:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    # Use pydantic model parsing to validate/convert.
    # Be compatible with both pydantic v1 and v2 entrypoints.
    if hasattr(DoorDXFRequest, "model_validate"):
        return DoorDXFRequest.model_validate(data)
    else:
        return DoorDXFRequest.parse_obj(data)


def run_cases(paths, selected_indices=None):
    total = 0
    successes = 0
    failures = 0
    for idx, p in enumerate(paths, start=1):
        if selected_indices and idx not in selected_indices:
            continue
        total += 1
        print("\n== Test case {}: {} ==".format(idx, p.name))
        try:
            req = load_request_from_file(p)
            out = compute_door_geometry(req)
            # Produce JSON text compatible with both pydantic v1 and v2
            output_text = None
            if hasattr(out, "model_dump_json"):
                try:
                    output_text = out.model_dump_json(indent=2)
                except TypeError:
                    output_text = out.model_dump_json()
            elif hasattr(out, "json"):
                try:
                    output_text = out.json(indent=2)
                except TypeError:
                    output_text = out.json()
            else:
                try:
                    output_text = json.dumps(out.model_dump(), indent=2)
                except Exception:
                    output_text = str(out)

            # Compare with expected output file if it exists. Do not write files.
            output_path = p.with_name(p.stem + "_output.json")
            if output_text is None:
                print("No output produced from compute_door_geometry.")
                failures += 1
            elif output_path.exists():
                expected_text = output_path.read_text(encoding="utf-8")
                try:
                    expected_obj = json.loads(expected_text)
                    actual_obj = json.loads(output_text)
                    equal = expected_obj == actual_obj
                except Exception:
                    equal = expected_text.strip() == output_text.strip()

                if equal:
                    print(f"PASS: Output matches expected file: {output_path}")
                    successes += 1
                else:
                    print(f"FAIL: Output differs from expected file: {output_path}")
                    diff_lines = list(difflib.unified_diff(
                        expected_text.splitlines(),
                        output_text.splitlines(),
                        fromfile=str(output_path),
                        tofile="current_run",
                        lineterm=""
                    ))
                    for line in diff_lines[:200]:
                        print(line)
                    failures += 1
            else:
                print(f"Missing expected output file: {output_path}")
                # Print actual output for inspection but do not write it
                #print(output_text)
                failures += 1
        except Exception as e:
            failures += 1
            print("ERROR running test case {}: {}".format(idx, e))
            traceback.print_exc()

    print("\nSummary: total={}, successes={}, failures={}".format(total, successes, failures))


def parse_indices(arg_list, max_idx):
    # Accept strings like: 1 2 3 or ranges like 1-3
    if not arg_list:
        return None
    indices = set()
    for token in arg_list:
        token = token.strip()
        if not token:
            continue
        if token.lower() in ("all", "a"):
            return None
        if "-" in token:
            try:
                a, b = token.split("-", 1)
                a_i = int(a)
                b_i = int(b)
                for i in range(max(1, a_i), min(max_idx, b_i) + 1):
                    indices.add(i)
            except ValueError:
                continue
        else:
            try:
                i = int(token)
                if 1 <= i <= max_idx:
                    indices.add(i)
            except ValueError:
                continue
    return indices


def main():
    parser = argparse.ArgumentParser(description="Run door geometry test cases from JSON files.")
    parser.add_argument("cases", nargs="*", help="Test case numbers (1-based), ranges (1-3), or 'all'. If omitted runs all.")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    test_dir = repo_root / "Door TestCases"
    if not test_dir.exists():
        print("Test cases directory not found:", test_dir)
        return

    files = discover_testcases(test_dir)
    if not files:
        print("No JSON test files found in:", test_dir)
        return

    max_idx = len(files)
    selected = parse_indices(args.cases, max_idx)

    print("Found {} test cases:".format(max_idx))
    for i, p in enumerate(files, start=1):
        print("  {}. {}".format(i, p.name))

    if selected is None:
        print("\nRunning all test cases...")
    else:
        print("\nRunning selected test cases: {}".format(sorted(selected)))

    run_cases(files, selected)


if __name__ == "__main__":
    main()
