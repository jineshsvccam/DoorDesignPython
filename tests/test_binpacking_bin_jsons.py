import sys
import json
from pathlib import Path

# Ensure repo root is on sys.path so imports resolve
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import pytest

from fastapi_app.schemas_output import BinTransformedManifest


_outputs_dir = REPO_ROOT / "Door TestCases" /  "BinPacking" / "Outputs" / "json"
_baseline_dir = REPO_ROOT / "Door TestCases" / "BinPacking" / "Baselines" / "Bin_JsonOutputs"

# Prefer generated Outputs if present, otherwise fall back to Baselines
if _outputs_dir.exists() and any(_outputs_dir.glob("*.json")):
    JSON_DIR = _outputs_dir
else:
    JSON_DIR = _baseline_dir

JSON_FILES = sorted([p for p in JSON_DIR.glob("*.json")])

assert JSON_FILES, f"No bin manifest JSON files found in {JSON_DIR}. Run tools/generate_bins_fromexcel.py to produce them."


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _round_floats(obj, ndigits=3):
    if isinstance(obj, float):
        return round(obj, ndigits)
    if isinstance(obj, dict):
        return {k: _round_floats(v, ndigits) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_round_floats(v, ndigits) for v in obj]
    return obj


@pytest.mark.parametrize("json_file", JSON_FILES)
def test_binpacking_bin_json_parses_and_basic_checks(json_file: Path):
    """Validate each bin JSON parses into `BinTransformedManifest` and has doors.

    This checks schema compatibility and performs a light structural assertion
    so downstream DXF generation can rely on these manifests.
    """
    raw = load_json(json_file)

    # pydantic v2/v1 compatibility: prefer model_validate if available
    try:
        if hasattr(BinTransformedManifest, "model_validate"):
            manifest = BinTransformedManifest.model_validate(raw)
        else:
            manifest = BinTransformedManifest.parse_obj(raw)
    except Exception as e:
        pytest.fail(f"Failed to parse generated manifest {json_file.name} as BinTransformedManifest: {e}. Run tools/generate_inputjsons_fromexcel.py to produce outputs.")

    # basic sanity checks
    assert getattr(manifest, "sheet_width", 0) > 0
    assert getattr(manifest, "sheet_height", 0) > 0
    doors = getattr(manifest, "doors", None)
    assert doors is not None, "Manifest missing 'doors'"
    assert len(doors) > 0, "Manifest contains no doors"

    # Compare the full JSON output to the baseline for exact structure (with
    # float rounding to avoid minor numeric noise). Prefer the Baselines
    # directory as the expected source.
    expected_file = _baseline_dir / json_file.name
    assert expected_file.exists(), f"Missing baseline JSON for {json_file.name}: {expected_file}"

    actual_json = load_json(json_file)
    expected_json = load_json(expected_file)

    assert _round_floats(actual_json) == _round_floats(expected_json)
