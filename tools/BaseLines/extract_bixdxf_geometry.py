"""Wrapper to extract and normalize DXF geometry from any folder.

Usage:
    python tools/extract_bixdxf_gemotry.py --input "path/to/dxf_folder" --output "path/to/out_folder" --ndigits 3 --overwrite

This imports the extraction and normalization helpers from
`tools.extract_dxf_geometry` and applies them to all `*.dxf` files found
under `--input` (non-recursive). Output files are written as
`<stem>_geometry.json` in `--output`.
"""
from pathlib import Path
import sys
import argparse
import json
import logging
import tempfile

# Ensure repo root is on sys.path when running this script from tools/BaseLines
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Robustly locate the repository root by climbing directories until we find
# a known marker (requirements.txt, BatchDoorDXFGenerator.py, or fastapi_app).
def find_repo_root(markers=("requirements.txt", "BatchDoorDXFGenerator.py", "fastapi_app")):
    p = Path(__file__).resolve().parent
    # limit to avoid infinite loops in weird mounts
    for _ in range(10):
        if any((p / m).exists() for m in markers):
            return p
        if p.parent == p:
            break
        p = p.parent
    # fallback: assume two levels up (tools/BaseLines -> repo root)
    return Path(__file__).resolve().parents[2]

REPO_ROOT = find_repo_root()
sys.path.insert(0, str(REPO_ROOT))

from tools.BaseLines.extract_dxf_geometry import extract_geometry, normalize_geometry


logger = logging.getLogger("extract_bixdxf_gemotry")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def atomic_write(path: Path, data: str):
    path_parent = path.parent
    path_parent.mkdir(parents=True, exist_ok=True)
    # write to temp then move
    with tempfile.NamedTemporaryFile("w", delete=False, dir=str(path_parent), encoding="utf-8") as fh:
        fh.write(data)
        tmp = Path(fh.name)
    tmp.replace(path)


def process_folder(input_dir: Path, output_dir: Path, ndigits: int = 3, overwrite: bool = False) -> int:
    """Process all DXF files in `input_dir`, writing normalized geometry to `output_dir`.

    Returns number of files written.
    """
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    if not input_dir.exists() or not input_dir.is_dir():
        logger.error("Input directory not found: %s", input_dir)
        return 0

    # find DXF files recursively and match case-insensitively
    files = [p for p in sorted(input_dir.rglob("*")) if p.is_file() and p.suffix.lower() == ".dxf"]
    if not files:
        logger.info("No DXF files found in %s", input_dir)
        return 0

    logger.info("Found %d DXF files (showing up to 10): %s", len(files), ", ".join(str(x.name) for x in files[:10]))

    written = 0
    skipped = 0
    for f in files:
        try:
            stem = f.stem
            out_file = output_dir / f"{stem}_geometry.json"
            if out_file.exists() and not overwrite:
                skipped += 1
                logger.info("Skipping existing baseline (use --overwrite to force): %s", out_file)
                continue

            geom = extract_geometry(str(f))
            norm = normalize_geometry(geom, ndigits=ndigits)
            atomic_write(out_file, json.dumps(norm, indent=2))
            logger.info("Wrote %s", out_file)
            written += 1
        except Exception as e:
            logger.error("Failed to process %s: %s", f, e)
    logger.info("Wrote %d files, skipped %d existing files", written, skipped)
    return written


def main():
    parser = argparse.ArgumentParser(description="Extract and normalize DXF geometry from a folder")
    parser.add_argument("--input", "-i", required=False, help="Input folder containing .dxf files (optional)")
    parser.add_argument("--output", "-o", required=False, help="Output folder for geometry JSON files (optional)")
    parser.add_argument("--ndigits", type=int, default=3, help="Decimal places to round coordinates")
    # default to overwriting when running without args; allow opting out with --no-overwrite
    parser.add_argument("--overwrite", dest="overwrite", action="store_true", help="Overwrite existing geometry files (default when no args are provided)")
    parser.add_argument("--no-overwrite", dest="overwrite", action="store_false", help="Do not overwrite existing geometry files")
    parser.set_defaults(overwrite=True)
    args = parser.parse_args()

    # Default to BinPacking Baselines DXF and corresponding DxfGeometry unless overridden
    if args.input:
        input_dir = Path(args.input)
    else:
        input_dir = REPO_ROOT / "Door TestCases" / "BinPacking" / "Baselines" / "Dxf"

    if args.output:
        output_dir = Path(args.output)
    else:
        output_dir = REPO_ROOT / "Door TestCases" / "BinPacking" / "Baselines" / "DxfGeometry"

    # Log chosen paths for user clarity
    logger.info("Using input dir: %s", input_dir)
    logger.info("Using output dir: %s", output_dir)
    # If user passed no command-line args, inform that overwrite default is enabled
    if len(sys.argv) == 1:
        logger.info("No arguments provided — using defaults and overwriting existing geometry files.")

    cnt = process_folder(input_dir, output_dir, ndigits=args.ndigits, overwrite=args.overwrite)
    logger.info("Processed %d files", cnt)


if __name__ == "__main__":
    main()
