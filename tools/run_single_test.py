"""Simple runner: reads a single JSON testcase by name and runs compute_door_geometry.

Set FILE_TO_RUN to the filename in `Door TestCases` you want to run.
"""

import sys
import json
from pathlib import Path
import traceback

# Ensure project root is on sys.path so local imports work
sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi_app.schemas_input import DoorDXFRequest
from geometry.door_geometry import compute_door_geometry

# Edit this to choose which testcase to run
FILE_TO_RUN = "DoubleStandard.json"


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    test_file = repo_root / "Door TestCases" / FILE_TO_RUN

    if not test_file.exists():
        print(f"Error: test file not found: {test_file}", file=sys.stderr)
        return 2

    try:
        data = json.loads(test_file.read_text(encoding="utf-8"))

        if hasattr(DoorDXFRequest, "model_validate"):
            req = DoorDXFRequest.model_validate(data)
        else:
            req = DoorDXFRequest.parse_obj(data)

        out = compute_door_geometry(req)

        # Produce JSON text in a way compatible with both pydantic v1 and v2
        output_text = None
        if hasattr(out, "model_dump_json"):
            # pydantic v2 returns a JSON string
            try:
                output_text = out.model_dump_json(indent=2)
            except TypeError:
                output_text = out.model_dump_json()
        elif hasattr(out, "json"):
            # pydantic v1
            try:
                output_text = out.json(indent=2)
            except TypeError:
                output_text = out.json()
        else:
            # Fallback: use model_dump then json.dumps
            try:
                output_text = json.dumps(out.model_dump(), indent=2)
            except Exception:
                output_text = str(out)

        # Print to stdout (preserve previous behaviour) and write to file
        if output_text is not None:
            print(output_text)
            # Save to same directory with suffix _output.json
            output_path = test_file.with_name(test_file.stem + "_output.json")
            output_path.write_text(output_text, encoding="utf-8")
            print(f"Wrote output JSON to: {output_path}")

        return 0

    except Exception:
        print("Error while running test:", file=sys.stderr)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
