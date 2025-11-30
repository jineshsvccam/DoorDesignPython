"""Validator for ExcelTestCases folder.

Runs validation on all *_output.json files in the ExcelTestCases folder
and generates a summary report.

Usage:
    python validate_excel_tests.py
"""

import json
import sys
from pathlib import Path

# Add parent directory to path so we can import validator
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.validator import validate_geometry_auto, _collect_valid_flags


def main() -> int:
    """Main execution function."""
    base_dir = Path(__file__).resolve().parent.parent / "ExcelTestCases"
    
    if not base_dir.exists():
        print(f"Error: ExcelTestCases folder not found: {base_dir}", file=sys.stderr)
        return 1
    
    # Find all *_output.json files
    output_files = sorted(base_dir.glob("*_output.json"))
    
    if not output_files:
        print(f"No *_output.json files found in {base_dir}", file=sys.stderr)
        return 1
    
    print(f"Found {len(output_files)} test output files to validate\n")
    print("=" * 70)
    
    summary = {"files": {}, "missing": [], "errors": []}
    
    for file_path in output_files:
        file_name = file_path.name
        
        try:
            print(f"\nValidating {file_name}...")
            result = validate_geometry_auto(str(file_path))
            
            # Evaluate pass/fail by collecting 'is_valid'/'valid' flags
            flags = _collect_valid_flags(result)
            if flags:
                passed = all(flags)
            else:
                # Fallback: check top-level door type indicators
                passed = result.get("is_single_door") is True or result.get("is_double_door") is True
            
            status = "✓ PASS" if passed else "✗ FAIL"
            print(f"  {status}")
            
            # Store result in summary
            summary["files"][file_name] = {
                "path": str(file_path),
                "result": result,
                "passed": passed,
                "status": "pass" if passed else "fail",
            }
            
            # Print brief validation details if failed
            if not passed:
                print(f"  Failed checks:")
                for key, value in result.items():
                    if isinstance(value, dict) and value.get("is_valid") is False:
                        print(f"    - {key}: {value}")
        
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            summary["errors"].append({
                "file": file_name,
                "error": str(e),
            })
    
    # Calculate summary statistics
    pass_count = sum(1 for f in summary["files"].values() if f.get("passed"))
    fail_count = sum(1 for f in summary["files"].values() if not f.get("passed"))
    error_count = len(summary["errors"])
    
    summary["summary"] = {
        "total_files": len(output_files),
        "validated_count": len(summary["files"]),
        "pass_count": pass_count,
        "fail_count": fail_count,
        "error_count": error_count,
    }
    
    # Print summary
    print("\n" + "=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)
    print(f"Total files:      {summary['summary']['total_files']}")
    print(f"Validated:        {summary['summary']['validated_count']}")
    print(f"✓ Passed:         {pass_count}")
    print(f"✗ Failed:         {fail_count}")
    print(f"✗ Errors:         {error_count}")
    
    if fail_count > 0:
        print("\nFailed validations:")
        for file_name, info in summary["files"].items():
            if not info.get("passed"):
                print(f"  ✗ {file_name}")
    
    if error_count > 0:
        print("\nErrors encountered:")
        for err in summary["errors"]:
            print(f"  ✗ {err['file']}: {err['error']}")
    
    # Save summary to JSON file
    try:
        out_path = base_dir / "validation_summary.json"
        out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"\n✓ Saved detailed summary to: {out_path}")
    except Exception as e:
        print(f"\n✗ Failed to write summary: {e}", file=sys.stderr)
    
    # Return exit code based on validation results
    if fail_count > 0 or error_count > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
