"""Generate geometry JSON from DoorGeometry inputs into Baselines.

This script is a small helper to run the `compute_door_geometry` code over
input JSON fixtures and write normalized outputs to a Baselines folder.

Features added:
- CLI override for input/output directories
- Pydantic v1/v2 compatible parsing/serialization
- Clear logging and deterministic behavior
"""

import sys
import json
import argparse
import logging
from pathlib import Path
from typing import Optional


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from fastapi_app.schemas_input import DoorDXFRequest
from geometry.door_geometry import compute_door_geometry


logger = logging.getLogger("generate_single_json")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def parse_model(data: dict) -> DoorDXFRequest:
    if hasattr(DoorDXFRequest, "model_validate"):
        return DoorDXFRequest.model_validate(data)
    return DoorDXFRequest.parse_obj(data)


def serialize_output(output) -> str:
    # Pydantic v2
    if hasattr(output, "model_dump_json"):
        try:
            return output.model_dump_json(indent=2)
        except TypeError:
            return output.model_dump_json()
    # Pydantic v1
    if hasattr(output, "json"):
        try:
            return output.json(indent=2)
        except TypeError:
            return output.json()
    # Fallback to dict -> json
    try:
        return json.dumps(output.model_dump(), indent=2)
    except Exception:
        return json.dumps(output, indent=2)


def generate_geometry_from_file(test_file: Path, outputs_dir: Path) -> bool:
    if not test_file.exists():
        logger.error("Input file not found: %s", test_file)
        return False

    try:
        data = json.loads(test_file.read_text(encoding="utf-8"))
        req = parse_model(data)
        output = compute_door_geometry(req)
        text = serialize_output(output)

        out_path = outputs_dir / (test_file.stem + "_output.json")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        logger.info("Wrote %s", out_path)
        return True
    except Exception as exc:
        logger.exception("Failed to process %s: %s", test_file, exc)
        return False


def find_test_by_name(name: str, candidates: list[Path]) -> Optional[Path]:
    name_lower = name.lower().replace(".json", "")
    for p in candidates:
        stem = p.stem.lower()
        if name_lower == stem or name_lower in stem:
            return p
    return None


def main() -> int:
    default_inputs = REPO_ROOT / "Door TestCases" / "DoorGeometry" / "Inputs"
    default_outputs = REPO_ROOT / "Door TestCases" / "DoorGeometry" / "Baselines" / "JsonOutput"

    parser = argparse.ArgumentParser(description="Generate geometry JSON from inputs into Baselines/JsonOutput")
    parser.add_argument("test", nargs="?", default="all", help="Test case index, name, or 'all' (default: all)")
    parser.add_argument("--input-dir", "-i", default=str(default_inputs), help="Input folder containing .json files")
    parser.add_argument("--output-dir", "-o", default=str(default_outputs), help="Output folder for generated JSON files")

    args = parser.parse_args()
    inputs_dir = Path(args.input_dir)
    outputs_dir = Path(args.output_dir)
    outputs_dir.mkdir(parents=True, exist_ok=True)

    candidates = sorted(inputs_dir.glob("*.json"))
    if not candidates:
        logger.error("No input files in %s", inputs_dir)
        return 0

    if args.test == "all":
        tests_to_run = candidates
    elif args.test.isdigit():
        idx = int(args.test)
        tests_to_run = [candidates[idx]] if 0 <= idx < len(candidates) else []
    else:
        found = find_test_by_name(args.test, candidates)
        tests_to_run = [found] if found else []

    for test_file in tests_to_run:
        generate_geometry_from_file(test_file, outputs_dir)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
