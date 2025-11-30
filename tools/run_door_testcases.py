"""Regression test runner for door geometry computation.

Validates that compute_door_geometry produces expected outputs by comparing
against pre-generated *_output.json reference files.

Usage:
    python run_door_testcases.py           # Run all tests
    python run_door_testcases.py 1 2 5     # Run specific tests by number
    python run_door_testcases.py 1-3       # Run range of tests
    python run_door_testcases.py all       # Explicitly run all tests
"""

import sys
import json
import argparse
import difflib
from pathlib import Path
from typing import Optional

# Ensure project root is on sys.path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi_app.schemas_input import DoorDXFRequest
from geometry.door_geometry import compute_door_geometry


def discover_test_cases(test_dir: Path) -> list[Path]:
    """Discover test case JSON files, excluding *_output.json and summary files."""
    files = [
        p for p in test_dir.glob("*.json") 
        if "output" not in p.stem.lower() 
        and "summary" not in p.stem.lower()
        and "validation" not in p.stem.lower()
    ]
    return sorted(files)


def parse_model(data: dict) -> DoorDXFRequest:
    """Parse JSON data into DoorDXFRequest (Pydantic v1/v2 compatible)."""
    if hasattr(DoorDXFRequest, "model_validate"):
        return DoorDXFRequest.model_validate(data)
    return DoorDXFRequest.parse_obj(data)


def load_test_case(path: Path) -> DoorDXFRequest:
    """Load and parse a test case from JSON file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return parse_model(data)


def serialize_output(output) -> str:
    """Serialize Pydantic model to JSON string (v1/v2 compatible)."""
    if hasattr(output, "model_dump_json"):
        try:
            return output.model_dump_json(indent=2)
        except TypeError:
            return output.model_dump_json()
    elif hasattr(output, "json"):
        try:
            return output.json(indent=2)
        except TypeError:
            return output.json()
    
    # Fallback
    try:
        return json.dumps(output.model_dump(), indent=2)
    except Exception:
        return str(output)


def compare_outputs(expected_path: Path, actual_text: str) -> tuple[bool, list[str]]:
    """Compare actual output with expected output file.
    
    Returns:
        Tuple of (is_equal, diff_lines)
    """
    if not expected_path.exists():
        return False, [f"Missing expected output file: {expected_path}"]
    
    expected_text = expected_path.read_text(encoding="utf-8")
    
    # Try JSON comparison first (more robust)
    try:
        expected_obj = json.loads(expected_text)
        actual_obj = json.loads(actual_text)
        if expected_obj == actual_obj:
            return True, []
    except Exception:
        # Fall back to text comparison
        if expected_text.strip() == actual_text.strip():
            return True, []
    
    # Generate diff
    diff_lines = list(difflib.unified_diff(
        expected_text.splitlines(),
        actual_text.splitlines(),
        fromfile=str(expected_path),
        tofile="actual_output",
        lineterm=""
    ))
    
    return False, diff_lines[:200]  # Limit diff output


def run_single_test(test_path: Path, test_index: int) -> bool:
    """Run a single test case and validate output.
    
    Returns:
        True if test passed, False otherwise.
    """
    print(f"\n== Test case {test_index}: {test_path.name} ==")
    
    try:
        # Load and run test
        request = load_test_case(test_path)
        output = compute_door_geometry(request)
        actual_text = serialize_output(output)
        
        if not actual_text:
            print("✗ FAIL: No output produced from compute_door_geometry")
            return False
        
        # Compare with expected output
        expected_path = test_path.with_name(test_path.stem + "_output.json")
        is_equal, diff_lines = compare_outputs(expected_path, actual_text)
        
        if is_equal:
            print(f"✓ PASS: Output matches {expected_path.name}")
            return True
        else:
            print(f"✗ FAIL: Output differs from {expected_path.name}")
            for line in diff_lines:
                print(line)
            return False
            
    except Exception as e:
        print(f"✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_test_suite(test_paths: list[Path], selected_indices: Optional[set[int]] = None) -> dict:
    """Run selected test cases and return results.
    
    Returns:
        Dictionary with 'total', 'passed', 'failed' counts.
    """
    results = {"total": 0, "passed": 0, "failed": 0}
    
    for index, test_path in enumerate(test_paths, start=1):
        if selected_indices and index not in selected_indices:
            continue
        
        results["total"] += 1
        success = run_single_test(test_path, index)
        
        if success:
            results["passed"] += 1
        else:
            results["failed"] += 1
    
    return results


def parse_test_selection(args: list[str], max_index: int) -> Optional[set[int]]:
    """Parse test selection arguments into a set of test indices.
    
    Supports:
        - Individual numbers: 1 2 5
        - Ranges: 1-3 (expands to 1, 2, 3)
        - 'all' keyword: runs all tests
    
    Returns:
        Set of 1-based indices, or None for all tests.
    """
    if not args:
        return None
    
    indices = set()
    
    for token in args:
        token = token.strip()
        if not token:
            continue
        
        if token.lower() in ("all", "a"):
            return None
        
        # Handle range (e.g., "1-3")
        if "-" in token:
            try:
                start, end = token.split("-", 1)
                start_idx = int(start)
                end_idx = int(end)
                for i in range(max(1, start_idx), min(max_index, end_idx) + 1):
                    indices.add(i)
            except ValueError:
                print(f"Warning: Invalid range '{token}', skipping")
                continue
        else:
            # Handle single index
            try:
                index = int(token)
                if 1 <= index <= max_index:
                    indices.add(index)
                else:
                    print(f"Warning: Index {index} out of range (1-{max_index}), skipping")
            except ValueError:
                print(f"Warning: Invalid index '{token}', skipping")
                continue
    
    return indices if indices else None


def print_summary(results: dict):
    """Print test execution summary."""
    print("\n" + "=" * 60)
    print(f"Test Summary: {results['passed']}/{results['total']} passed")
    
    if results['failed'] > 0:
        print(f"\n{results['failed']} test(s) failed")
    else:
        print("\n✓ All tests passed!")
    print("=" * 60)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Regression test runner for door geometry computation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                Run all tests
  %(prog)s 1 2 5          Run tests 1, 2, and 5
  %(prog)s 1-3            Run tests 1 through 3
  %(prog)s all            Explicitly run all tests
        """
    )
    
    parser.add_argument(
        "cases",
        nargs="*",
        help="Test case numbers (1-based), ranges (1-3), or 'all' (default: all)"
    )
    
    args = parser.parse_args()
    
    # Locate test directory
    repo_root = Path(__file__).resolve().parents[1]
    test_dir = repo_root / "Door TestCases"
    
    if not test_dir.exists():
        print(f"Error: Test directory not found: {test_dir}", file=sys.stderr)
        return 2
    
    # Discover test cases
    test_files = discover_test_cases(test_dir)
    if not test_files:
        print(f"Error: No test files found in: {test_dir}", file=sys.stderr)
        return 2
    
    # Parse test selection
    max_index = len(test_files)
    selected_indices = parse_test_selection(args.cases, max_index)
    
    # Display available tests
    print(f"Found {max_index} test case(s):")
    for index, test_file in enumerate(test_files, start=1):
        marker = "→" if selected_indices is None or index in selected_indices else " "
        print(f"  {marker} [{index}] {test_file.name}")
    
    # Run tests
    if selected_indices is None:
        print(f"\nRunning all {max_index} test cases...")
    else:
        print(f"\nRunning {len(selected_indices)} selected test case(s): {sorted(selected_indices)}")
    
    results = run_test_suite(test_files, selected_indices)
    
    # Print summary and return exit code
    print_summary(results)
    return 0 if results["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
