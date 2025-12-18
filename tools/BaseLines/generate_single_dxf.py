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

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from fastapi_app.schemas_input import DoorDXFRequest
from DoorDrawingGenerator import DoorDrawingGenerator
import logging

logger = logging.getLogger("generate_single_dxf")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")



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


def generate_dxf(test_file: Path, outputs_dir: Path, with_annotations: bool = True) -> bool:
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
        
        # Determine output filename and ensure output dir exists
        output_filename = get_output_filename(request, test_file)
        output_path = outputs_dir / output_filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Generate DXF
        DoorDrawingGenerator.generate_door_dxf(
            request=request,
            file_name=str(output_path),
            isannotationRequired=with_annotations,
            save_file=True
        )
        logger.info("Wrote %s", output_path)
        return True
        
    except Exception as e:
        print(f"✗ {test_file.name}: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return False


def find_test_by_name(name: str, candidates: list[Path]) -> Optional[Path]:
    """Find test case by partial name match (case-insensitive)."""
    name_lower = name.lower().replace(".json", "")

    for p in candidates:
        stem = p.stem.lower()
        if name_lower == stem:
            return p
        if name_lower in stem:
            return p

    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate DXF files from JSON inputs in Door TestCases/Inputs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                      Generate for all JSON files in Door TestCases/Inputs
  %(prog)s 0                    Generate for first JSON file (index 0)
  %(prog)s SingleNormal         Generate by name (partial match)
  %(prog)s all                  Explicitly generate all
  %(prog)s 2 --no-annotations   Generate without annotations
"""
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
    parser.add_argument(
        "--input-dir",
        dest="input_dir",
        help="Input folder containing .json files (overrides default)",
        default=None,
    )
    parser.add_argument(
        "--output-dir",
        dest="output_dir",
        help="Output folder for generated DXF files (overrides default)",
        default=None,
    )
    
    args = parser.parse_args()
    # Try several common input locations and pick the first that exists.
    candidates = [
        REPO_ROOT / "Door TestCases" / "DoorGeometry" / "Inputs",
        REPO_ROOT / "Door TestCases" / "Inputs",
        REPO_ROOT / "Door TestCases" / "BinPacking" / "Inputs",
    ]

    chosen_input = None
    for c in candidates:
        if c.exists() and any(c.glob("*.json")):
            chosen_input = c
            break

    if args.input_dir:
        inputs_dir = Path(args.input_dir)
    elif chosen_input is not None:
        inputs_dir = chosen_input
    else:
        # fallback to first candidate even if empty
        inputs_dir = candidates[0]

    # Choose output folder near the inputs when possible
    if args.output_dir:
        outputs_dir = Path(args.output_dir)
    else:
        if inputs_dir.match("*DoorGeometry*/Inputs"):
            outputs_dir = inputs_dir.parent / "Baselines" / "Dxf"
        else:
            outputs_dir = REPO_ROOT / "Door TestCases" / "Baselines" / "Dxf"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    # Gather all JSON test files in Inputs
    candidates = sorted([p for p in inputs_dir.glob("*.json")])
    if not candidates:
        print(f"No test files found in {inputs_dir}", file=sys.stderr)
        return 2

    # Determine which tests to run
    tests_to_run: list[Path] = []

    if args.test == "all":
        tests_to_run = candidates
    elif args.test.isdigit():
        index = int(args.test)
        if 0 <= index < len(candidates):
            tests_to_run = [candidates[index]]
        else:
            print(f"Error: index {index} out of range (0..{len(candidates)-1})", file=sys.stderr)
            return 2
    else:
        # Try to find by name among candidate files
        found = find_test_by_name(args.test, candidates)
        if found:
            tests_to_run = [found]
        else:
            print(f"Error: test case '{args.test}' not found", file=sys.stderr)
            print("\nAvailable test cases:", file=sys.stderr)
            for i, p in enumerate(candidates):
                print(f"  [{i}] {p.name}", file=sys.stderr)
            return 2
    
    # Generate DXF files
    with_annotations = not args.no_annotations
    annotation_status = "with annotations" if with_annotations else "without annotations"
    print(f"Generating DXF for {len(tests_to_run)} test case(s) {annotation_status}...\n")
    
    results = []
    for test_file in tests_to_run:
        try:
            success = generate_dxf(test_file, outputs_dir, with_annotations=with_annotations)
        except Exception:
            logger.exception("Failed to generate for %s", test_file)
            success = False
        results.append((test_file.name, success))
    
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
    raise SystemExit(main())
