import sys
import json
from pathlib import Path

# Ensure repo root is on sys.path so imports like `tests.helpers` resolve
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import pytest

from tests.helpers.run_geometry import compute_output

BASE_DIR = Path(__file__).resolve().parents[1]
INPUT_DIR = BASE_DIR / "Door TestCases" / "DoorGeometry" /"Inputs"
BASELINE_DIR = BASE_DIR / "Door TestCases" / "DoorGeometry" / "Baselines" / "JsonOutput"
OUTPUT_SUFFIX = "_output.json"


def _round_floats(obj, ndigits=3):
    if isinstance(obj, float):
        return round(obj, ndigits)
    if isinstance(obj, dict):
        return {k: _round_floats(v, ndigits) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_round_floats(v, ndigits) for v in obj]
    return obj


# Build test list excluding baseline outputs and non-door fixtures
TEST_FILES = sorted(
    [p for p in INPUT_DIR.glob("*.json") if p.name != "validation_summary.json"]
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("input_file", TEST_FILES)
def test_geometry_against_baseline(input_file: Path):
    expected_file = BASELINE_DIR / (input_file.stem + OUTPUT_SUFFIX)

    assert expected_file.exists(), (
        f"Missing baseline output for {input_file.name}"
    )

    input_data = load_json(input_file)
    expected_output = load_json(expected_file)

    actual_output = compute_output(input_data)

    assert _round_floats(actual_output) == _round_floats(expected_output)
