import sys
import json
from pathlib import Path

# Ensure repo root is on sys.path so imports resolve
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import pytest

from tools.BaseLines.extract_dxf_geometry import extract_geometry, normalize_geometry


DXF_DIR = REPO_ROOT / "Door TestCases" / "BinPacking" / "Outputs" / "dxf"
BASELINE_DIR = REPO_ROOT / "Door TestCases" / "BinPacking" / "Baselines" / "DxfGeometry"


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
def test_binpacking_dxf_geometry_against_baseline(dxf_file: Path):
    """Extract geometry from each bin DXF and compare to baseline geometry JSON.

    If the baseline file is missing, the test will fail with instructions to
    generate baselines using `tools/extract_dxf_geometry.py`.
    """
    expected_file = BASELINE_DIR / (dxf_file.stem + "_geometry.json")
    # Fail fast if baseline is missing. Do NOT auto-create baseline files here.
    if not expected_file.exists():
        pytest.fail(
            (
                f"Missing baseline geometry for {dxf_file.name}.\n"
                f"Generate baselines with: python tools/extract_dxf_geometry.py \"{DXF_DIR}\"\n"
                f"This will write files to: {BASELINE_DIR}\n"
                "After verifying generated baselines, re-run the tests."
            )
        )

    # Extract geometry from the generated DXF file
    geom = extract_geometry(str(dxf_file))
    norm = normalize_geometry(geom, ndigits=3)

    expected = load_json(expected_file)

    assert _round_floats(norm) == _round_floats(expected)
