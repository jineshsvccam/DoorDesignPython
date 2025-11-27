"""DXF file generator from JSON test cases.

Generates actual DXF files (and optionally PDF) from door parameter test cases.

Usage:
    python generate_single_dxf.py                    # Generate for all test cases
    python generate_single_dxf.py 0                  # Generate for first test (index 0)
    python generate_single_dxf.py SingleNormal       # Generate by name (case-insensitive)
    python generate_single_dxf.py all                # Explicitly generate all
    python generate_single_dxf.py 2 --no-annotations # Generate without annotations
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Optional

# Ensure project root is on sys.path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi_app.schemas_input import DoorDXFRequest
from DoorDrawingGenerator import DoorDrawingGenerator


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


def get_output_filename(request: DoorDXFRequest, test_file: Path) -> str:
    """Extract output filename from request metadata or use test case name."""
    try:
        meta = getattr(request, "metadata", None)
        if meta is not None:
            # Handle both Pydantic model and dict-like metadata
            file_name = getattr(meta, "file_name", None)
            if not file_name and isinstance(meta, dict):
                file_name = meta.get("file_name")
            
            if file_name:
                # Ensure it has .dxf extension
                if not file_name.endswith('.dxf'):
                    file_name = file_name + '.dxf'
                return file_name
    except Exception:
        pass
    
    # Use test case filename with .dxf extension (e.g., SingleNormal.json -> SingleNormal.dxf)
    return test_file.stem + ".dxf"


def generate_dxf(test_file: Path, with_annotations: bool = True, verbose: bool = True) -> bool:
    """Generate DXF file from a test case.
    
    Returns:
        True if successful, False otherwise.
    """
    if not test_file.exists():
        print(f"✗ Error: test file not found: {test_file}", file=sys.stderr)
        return False

    try:
        # Load and parse test case
        data = json.loads(test_file.read_text(encoding="utf-8"))
        request = parse_model(data)
        
        # Determine output filename
        output_filename = get_output_filename(request, test_file)
        output_path = test_file.with_name(output_filename)
        
        # Generate DXF
        DoorDrawingGenerator.generate_door_dxf(
            request=request,
            file_name=str(output_path),
            isannotationRequired=with_annotations,
            save_file=True
        )
        
        if verbose:
            print(f"✓ {test_file.name} → {output_filename}")
        
        return True
        
    except Exception as e:
        print(f"✗ {test_file.name}: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
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
        description="Generate DXF files from door test cases",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                      Generate for all test cases
  %(prog)s 0                    Generate for first test case (index 0)
  %(prog)s 5                    Generate for test case at index 5
  %(prog)s SingleNormal         Generate by name
  %(prog)s all                  Explicitly generate all
  %(prog)s 2 --no-annotations   Generate without annotations
  
Available test cases:
""" + "\n".join(f"  [{i}] {name}" for i, name in enumerate(TEST_CASES))
    )
    
    parser.add_argument(
        "test",
        nargs="?",
        default="all",
        help="Test case index, name, or 'all' (default: all)"
    )
    
    parser.add_argument(
        "--no-annotations",
        action="store_true",
        help="Generate DXF without annotations"
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
    
    # Generate DXF files
    with_annotations = not args.no_annotations
    annotation_status = "with annotations" if with_annotations else "without annotations"
    print(f"Generating DXF for {len(tests_to_run)} test case(s) {annotation_status}...\n")
    
    results = []
    for test_name in tests_to_run:
        test_file = test_dir / test_name
        success = generate_dxf(test_file, with_annotations=with_annotations, verbose=True)
        results.append((test_name, success))
    
    # Summary
    print("\n" + "=" * 50)
    succeeded = sum(1 for _, success in results if success)
    total = len(results)
    print(f"Results: {succeeded}/{total} generated successfully")
    
    if succeeded < total:
        print("\nFailed:")
        for name, success in results:
            if not success:
                print(f"  ✗ {name}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
