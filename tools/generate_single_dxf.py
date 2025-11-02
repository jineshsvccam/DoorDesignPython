"""Simple runner: reads a single JSON testcase by name and runs DoorDrawingGenerator.generate_door_dxf.

Set INDEX to pick a file from the FILES list or pass a path by editing FILE_TO_RUN logic.
"""

import sys
import json
from pathlib import Path
import traceback

# Ensure project root is on sys.path so local imports work
sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi_app.schemas_input import DoorDXFRequest
from DoorDrawingGenerator import DoorDrawingGenerator

# Keep filenames in a simple array; run by index if you pass an integer CLI arg.
FILES = [
    "DoubleStandard.json",
    "DoubleFourGlass.json",
    "DoubleNormal.json",
    "SingleFireBottom.json",
    "SingleFireTop.json",
    "SingleFireStandard.json",
    "SingleNormal.json",
]
# Choose by editing the integer INDEX below (change this before running).
INDEX = 4  # <-- change this integer to select a different file from FILES
try:
    FILE_TO_RUN = FILES[INDEX]
except Exception:
    print(f"Index {INDEX} out of range (0..{len(FILES)-1})", file=sys.stderr)
    raise SystemExit(2)


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

        # Determine output DXF filename: prefer metadata.file_name if provided
        out_file_name = None
        try:
            meta = getattr(req, "metadata", None)
            if meta is not None:
                # metadata may be a pydantic model or dict-like
                out_file_name = getattr(meta, "file_name", None) or (meta.get("file_name") if isinstance(meta, dict) else None)
        except Exception:
            out_file_name = None

        if not out_file_name:
            out_file_name = test_file.with_suffix(".dxf").name

        output_path = test_file.with_name(out_file_name)

        # Call generator: this will save the DXF when save_file=True
        DoorDrawingGenerator.generate_door_dxf(request=req, file_name=str(output_path), isannotationRequired=True, save_file=True)

        print(f"Wrote DXF to: {output_path}")
        return 0

    except Exception:
        print("Error while generating DXF:", file=sys.stderr)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
