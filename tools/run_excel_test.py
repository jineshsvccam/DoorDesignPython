"""Test runner for door geometry computation from Excel file.

Reads the sample_door_template.xlsm from frontend folder,
processes each door configuration, and generates JSON test cases
in the "ExcelTestCases" folder.

Usage:
    python run_excel_test.py
"""

import sys
import json
from pathlib import Path

# Ensure project root is on sys.path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from BatchDoorDXFGenerator import process_excel
from geometry.door_geometry import compute_door_geometry


EXCEL_FILE = "frontend/sample_door_template.xlsm"
FIXED_PARAMS = {
    "door_minus_measurement_width": 68,
    "door_minus_measurement_height": 70,
    "bending_width": 31,
    "bending_height": 24,
}


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


def process_door_param(door_param: dict, index: int, output_dir: Path) -> tuple[bool, str]:
    """Process a single door parameter and generate request/response JSON files.
    
    Args:
        door_param: Dictionary containing door parameters (from process_excel)
        index: Index of the door in the list (for naming)
        output_dir: Directory to save the output files
    
    Returns:
        Tuple of (success, message)
    """
    try:
        # Extract the DoorDXFRequest object from the door_param dict
        request_obj = door_param.get("request")
        if not request_obj:
            return False, f"✗ Door {index}: No request object found"
        
        # Get door name from the request metadata
        door_name = door_param.get("door_name", f"door_{index:03d}")
        door_name = door_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
        
        # Convert request object to dict for JSON serialization
        if hasattr(request_obj, "model_dump"):
            request_dict = request_obj.model_dump()
        elif hasattr(request_obj, "dict"):
            request_dict = request_obj.dict()
        else:
            request_dict = dict(request_obj)
        
        # Save request JSON in the same format as DoubleFourGlass.json
        request_path = output_dir / f"{door_name}.json"
        request_json = json.dumps(request_dict, indent=2, default=str)
        request_path.write_text(request_json, encoding="utf-8")
        
        # Compute geometry using the request object directly
        output = compute_door_geometry(request_obj)
        
        # Save output JSON
        output_path = output_dir / f"{door_name}_output.json"
        output_text = serialize_output(output)
        output_path.write_text(output_text, encoding="utf-8")
        
        return True, f"✓ {door_name}"
        
    except Exception as e:
        import traceback
        return False, f"✗ Door {index} ({door_param.get('door_name', 'unknown')}): {str(e)}\n{traceback.format_exc()}"


def main() -> int:
    """Main execution function."""
    repo_root = Path(__file__).resolve().parents[1]
    excel_path = repo_root / EXCEL_FILE
    
    # Check if Excel file exists
    if not excel_path.exists():
        print(f"Error: Excel file not found: {excel_path}", file=sys.stderr)
        return 1
    
    # Create output directory
    output_dir = repo_root / "ExcelTestCases"
    output_dir.mkdir(exist_ok=True)
    
    print(f"Processing Excel file: {excel_path}")
    print(f"Output directory: {output_dir}\n")
    
    try:
        # Process Excel file
        rectangles, door_params_list = process_excel(str(excel_path), FIXED_PARAMS)
        
        print(f"Found {len(door_params_list)} door configurations\n")
        
        # Process each door parameter
        results = []
        for index, door_param in enumerate(door_params_list):
            success, message = process_door_param(door_param, index, output_dir)
            results.append((success, message))
            print(message)
        
        # Summary
        print("\n" + "=" * 60)
        passed = sum(1 for success, _ in results if success)
        total = len(results)
        print(f"Results: {passed}/{total} door configurations processed successfully")
        
        if passed < total:
            print("\nFailed configurations:")
            for success, message in results:
                if not success:
                    print(f"  {message}")
            return 1
        
        print(f"\nTest cases saved to: {output_dir}")
        return 0
        
    except Exception as e:
        print(f"Error processing Excel file: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
