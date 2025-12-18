"""
Generate bins (DXF) from an Excel file using BatchDoorDXFGenerator,
then copy generated DXF and JSON outputs from `outputBulk` to
Door TestCases/ BinPacking baselines folders.

Usage:
    python tools/generate_bins_fromexcel.py --excel <path-to-excel>

If `--excel` is not provided the script will use
`BatchDoorDXFGenerator.EXCEL_FILE` as default.
"""
from __future__ import annotations
import argparse
import os
import shutil
from pathlib import Path
import glob
import sys

# Ensure repo root is on sys.path when running from tools/BaseLines
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import BatchDoorDXFGenerator as bdg


def copy_outputs(output_bulk_dir: Path, dxf_target: Path, json_target: Path) -> dict:
    dxf_target.mkdir(parents=True, exist_ok=True)
    json_target.mkdir(parents=True, exist_ok=True)

    copied = {"dxf": [], "json": []}

    # Search recursively for DXF and JSON files under outputBulk
    for filepath in output_bulk_dir.rglob("*"):
        if filepath.is_file():
            if filepath.suffix.lower() == ".dxf":
                dest = dxf_target.joinpath(filepath.name)
                shutil.copy2(filepath, dest)
                copied["dxf"].append(str(dest))
            elif filepath.suffix.lower() == ".json":
                dest = json_target.joinpath(filepath.name)
                shutil.copy2(filepath, dest)
                copied["json"].append(str(dest))
    return copied


def main():
    parser = argparse.ArgumentParser(description="Generate bin DXFs from Excel and copy outputs to BinPacking baselines")
    parser.add_argument("--excel", help="Path to Excel file", default=None)
    parser.add_argument("--sheet-width", type=int, default=1250)
    parser.add_argument("--sheet-height", type=int, default=2500)
    parser.add_argument("--no-pdf", action="store_true", help="Skip PDF generation")
    parser.add_argument("--dest-dxf", help="Path to destination DXF folder (overrides default baseline)", default=None)
    parser.add_argument("--dest-json", help="Path to destination JSON folder (overrides default baseline)", default=None)
    args = parser.parse_args()

    # Default Excel file for BinPacking inputs
    DEFAULT_EXCEL = REPO_ROOT.joinpath("Door TestCases", "BinPacking", "Inputs", "Excel", "sample_door_template.xlsm")

    excel_file = args.excel or getattr(bdg, "EXCEL_FILE", None) or str(DEFAULT_EXCEL)
    if not excel_file:
        print("No Excel file provided and no default Excel was found. Exiting.")
        return 1

    excel_path = Path(excel_file)
    if not excel_path.exists():
        print(f"Excel file not found: {excel_path}")
        return 1

    print(f"Generating bins from Excel: {excel_path}")

    # Call generator; this writes files into outputBulk under the repo
    try:
        zip_path = bdg.generate_zip_from_excel(
            str(excel_path),
            fixed_params=getattr(bdg, "FIXED_PARAMS", {}),
            sheet_width=args.sheet_width,
            sheet_height=args.sheet_height,
            isannotationRequired=False,
            ispdfrequired=False,
        )
    except Exception as e:
        print(f"Generation failed: {e}")
        raise

    # Determine outputBulk location (same logic as bin_dxf_generator)
    script_dir = Path(bdg.__file__).resolve().parent
    output_bulk_dir = script_dir.joinpath("outputBulk")

    if not output_bulk_dir.exists():
        print(f"No outputBulk directory found at expected location: {output_bulk_dir}")
        if zip_path and Path(zip_path).exists():
            print(f"ZIP produced at: {zip_path}")
        return 1

    # Destination paths: if provided, use them; otherwise default to Baselines
    dxf_target = Path(args.dest_dxf) if args.dest_dxf else REPO_ROOT.joinpath("Door TestCases", "BinPacking", "Baselines", "Dxf")
    json_target = Path(args.dest_json) if args.dest_json else REPO_ROOT.joinpath("Door TestCases", "BinPacking", "Baselines", "Bin_JsonOutputs")

    copied = copy_outputs(output_bulk_dir, dxf_target, json_target)

    print("Copy summary:")
    print(f"  DXF files copied: {len(copied['dxf'])}")
    for p in copied["dxf"]:
        print(f"    {p}")
    print(f"  JSON files copied: {len(copied['json'])}")
    for p in copied["json"]:
        print(f"    {p}")

    if zip_path:
        print(f"ZIP archive created at: {zip_path}")

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
