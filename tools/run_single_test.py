"""Test runner for door geometry computation.

Usage:
    python run_single_test.py                    # Run all test cases
    python run_single_test.py 0                  # Run first test (DoubleStandard.json)
    python run_single_test.py SingleNormal       # Run by name (case-insensitive, .json optional)
    python run_single_test.py all                # Explicitly run all tests
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Optional

# Ensure project root is on sys.path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi_app.schemas_input import DoorDXFRequest
from geometry.door_geometry import compute_door_geometry


TEST_CASES = [
    "DoubleStandard.json",
    "DoubleFourGlass.json",
    "DoubleNormal.json",
    "SingleFireBottom.json",
    "SingleFireTop.json",
    "SingleFireStandard.json",
    "SingleNormal.json",
]


def parse_model(data: dict) -> DoorDXFRequest:
    """Parse JSON data into DoorDXFRequest (Pydantic v1/v2 compatible)."""
    if hasattr(DoorDXFRequest, "model_validate"):
        return DoorDXFRequest.model_validate(data)
    return DoorDXFRequest.parse_obj(data)


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


def run_test_case(test_file: Path, verbose: bool = True) -> bool:
    """Run a single test case and save output.
    
    Returns:
        True if successful, False otherwise.
    """
    if not test_file.exists():
        print(f"✗ Error: test file not found: {test_file}", file=sys.stderr)
        return False

    try:
        data = json.loads(test_file.read_text(encoding="utf-8"))
        req = parse_model(data)
        output = compute_door_geometry(req)
        output_text = serialize_output(output)
        
        # Save output file
        output_path = test_file.with_name(test_file.stem + "_output.json")
        output_path.write_text(output_text, encoding="utf-8")
        
        if verbose:
            print(f"✓ {test_file.name}")
            print(f"  Output: {output_path.name}")
        
        return True
        
    except Exception as e:
        print(f"✗ {test_file.name}: {e}", file=sys.stderr)
        return False


def find_test_by_name(name: str, test_cases: list[str]) -> Optional[str]:
    """Find test case by partial name match (case-insensitive)."""
    name_lower = name.lower().replace(".json", "")
    
    for test_case in test_cases:
        if name_lower == test_case.lower().replace(".json", ""):
            return test_case
        if name_lower in test_case.lower():
            return test_case
    
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run door geometry test cases",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                      Run all test cases
  %(prog)s 0                    Run first test case (index 0)
  %(prog)s 5                    Run test case at index 5
  %(prog)s SingleNormal         Run by name
  %(prog)s all                  Explicitly run all tests
  
Available test cases:
""" + "\n".join(f"  [{i}] {name}" for i, name in enumerate(TEST_CASES))
    )
    
    parser.add_argument(
        "test",
        nargs="?",
        default="all",
        help="Test case index, name, or 'all' (default: all)"
    )
    
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    test_dir = repo_root / "Door TestCases"
    
    # Determine which tests to run
    tests_to_run = []
    
    if args.test == "all":
        tests_to_run = TEST_CASES
    elif args.test.isdigit():
        index = int(args.test)
        if 0 <= index < len(TEST_CASES):
            tests_to_run = [TEST_CASES[index]]
        else:
            print(f"Error: index {index} out of range (0..{len(TEST_CASES)-1})", file=sys.stderr)
            return 2
    else:
        # Try to find by name
        found = find_test_by_name(args.test, TEST_CASES)
        if found:
            tests_to_run = [found]
        else:
            print(f"Error: test case '{args.test}' not found", file=sys.stderr)
            print("\nAvailable test cases:", file=sys.stderr)
            for i, name in enumerate(TEST_CASES):
                print(f"  [{i}] {name}", file=sys.stderr)
            return 2
    
    # Run tests
    print(f"Running {len(tests_to_run)} test case(s)...\n")
    
    results = []
    for test_name in tests_to_run:
        test_file = test_dir / test_name
        success = run_test_case(test_file, verbose=True)
        results.append((test_name, success))
    
    # Summary
    print("\n" + "=" * 50)
    passed = sum(1 for _, success in results if success)
    total = len(results)
    print(f"Results: {passed}/{total} passed")
    
    if passed < total:
        print("\nFailed tests:")
        for name, success in results:
            if not success:
                print(f"  ✗ {name}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
