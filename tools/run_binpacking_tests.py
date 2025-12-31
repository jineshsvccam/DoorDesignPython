#!/usr/bin/env python3
"""Run bin generation then execute binpacking-related tests in order.

Usage: python tools/run_binpacking_tests.py
"""
import subprocess
import sys
from pathlib import Path


def main():
    repo_root = Path(__file__).resolve().parents[1]

    dest_dxf = repo_root / "Door TestCases" / "BinPacking" / "Outputs" / "dxf"
    dest_json = repo_root / "Door TestCases" / "BinPacking" / "Outputs" / "json"
    dest_dxf.mkdir(parents=True, exist_ok=True)
    dest_json.mkdir(parents=True, exist_ok=True)

    generator = repo_root / "tools" / "BaseLines" / "generate_bins_fromexcel.py"
    if not generator.exists():
        print(f"Generator script not found: {generator}")
        sys.exit(2)

    try:
        print("Running bin generator to produce DXF/JSON outputs...")
        subprocess.check_call([
            sys.executable, str(generator),
            "--dest-dxf", str(dest_dxf),
            "--dest-json", str(dest_json),
        ])
    except subprocess.CalledProcessError as e:
        print(f"Bin generator failed (exit {e.returncode})")
        sys.exit(e.returncode)

    test_files = [
        "tests/test_door_geometry_regression.py",
        "tests/test_dxf_geometry_regression.py",
        "tests/test_binpacking_json_regression.py",
        "tests/test_binpacking_bin_jsons.py",
        "tests/test_binpacking_dxf_geometry.py",
    ]

    print("Running tests in order:")
    for t in test_files:
        print(" ", t)

    cmd = [sys.executable, "-m", "pytest", "-q"] + test_files
    print("Executing:", " ".join(cmd))
    p = subprocess.run(cmd)
    print(f"pytest exit code: {p.returncode}")
    sys.exit(p.returncode)


if __name__ == "__main__":
    main()
