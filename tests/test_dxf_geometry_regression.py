import sys
import json
from pathlib import Path

# Ensure repo root is on sys.path so imports like `tools.extract_dxf_geometry` resolve
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import pytest

from tools.BaseLines.extract_dxf_geometry import extract_geometry, normalize_geometry


DXF_DIR = REPO_ROOT / "Door TestCases"/ "DoorGeometry" / "Baselines" / "Dxf"
BASELINE_DIR = REPO_ROOT / "Door TestCases" / "DoorGeometry" / "Baselines" / "DxfGeometry"


def _round_floats(obj, ndigits=3):
    if isinstance(obj, float):
        return round(obj, ndigits)
    if isinstance(obj, dict):
        return {k: _round_floats(v, ndigits) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_round_floats(v, ndigits) for v in obj]
    return obj


DXF_FILES = sorted([p for p in DXF_DIR.glob("*.dxf")])


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("dxf_file", DXF_FILES)
def test_dxf_geometry_against_baseline(dxf_file: Path):
    expected_file = BASELINE_DIR / (dxf_file.stem + "_geometry.json")
    assert expected_file.exists(), f"Missing baseline geometry for {dxf_file.name}"

    geom = extract_geometry(str(dxf_file))
    norm = normalize_geometry(geom, ndigits=3)

    expected = load_json(expected_file)

    assert _round_floats(norm) == _round_floats(expected)
