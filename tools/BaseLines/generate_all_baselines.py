"""Generate all baselines by running the six baseline steps in order.

Usage (dry-run):
    python tools/BaseLines/generate_all_baselines.py

To actually run generation:
    python tools/BaseLines/generate_all_baselines.py --run --overwrite --ndigits 3

The script locates the repository root and invokes the following scripts in order:
  1) tools/BaseLines/generate_single_json.py
  2) tools/BaseLines/generate_single_dxf.py
  3) tools/BaseLines/generate_inputjsons_fromexcel.py
  4) tools/BaseLines/generate_bins_fromexcel.py
  5) tools/BaseLines/extract_dxf_geometry.py
  6) tools/BaseLines/extract_bixdxf_geometry.py

This file only shells out to the existing scripts to preserve their CLI behaviour.
"""
from pathlib import Path
import sys
import subprocess
import argparse
import logging
import shutil


def find_repo_root(markers=("requirements.txt", "BatchDoorDXFGenerator.py", "fastapi_app")) -> Path:
    p = Path(__file__).resolve().parent
    for _ in range(10):
        if any((p / m).exists() for m in markers):
            return p
        if p.parent == p:
            break
        p = p.parent
    return Path(__file__).resolve().parents[2]


REPO_ROOT = find_repo_root()
sys.path.insert(0, str(REPO_ROOT))


logger = logging.getLogger("generate_all_baselines")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


DEFAULT_STEPS = [
    "tools/BaseLines/generate_single_json.py",
    "tools/BaseLines/generate_single_dxf.py",
    "tools/BaseLines/extract_dxf_geometry.py",
    "tools/BaseLines/generate_inputjsons_fromexcel.py",
    "tools/BaseLines/generate_bins_fromexcel.py",    
    "tools/BaseLines/extract_bixdxf_geometry.py",
]


def run_step(script_path: Path, args: list, run: bool, env=None) -> int:
    cmd = [sys.executable, str(script_path)] + args
    logger.info("Step: %s", script_path)
    logger.info("Command: %s", " ".join(cmd))
    if not run:
        return 0
    res = subprocess.run(cmd, env=env)
    return res.returncode


def main():
    parser = argparse.ArgumentParser(description="Run all baseline generation steps in order")
    parser.add_argument("--run", action="store_true", help="Actually execute the steps (default is dry-run)")
    parser.add_argument("--overwrite", action="store_true", help="Pass --overwrite to steps that accept it")
    parser.add_argument("--no-overwrite", dest="overwrite", action="store_false", help="Do not pass --overwrite")
    parser.add_argument("--ndigits", type=int, default=3, help="Decimal places for extraction steps")
    parser.add_argument("--clean", action="store_true", help="Clear target baseline/output subfolders before running")
    parser.add_argument("--clean-only", action="store_true", help="Only clear target folders, do not run generation steps")
    parser.add_argument("--steps", nargs="*", help="Optional list of step script basenames to run (in order)")
    parser.set_defaults(overwrite=False)
    args = parser.parse_args()

    steps = DEFAULT_STEPS if not args.steps else [str(Path(s)) for s in args.steps]

    logger.info("Repo root: %s", REPO_ROOT)
    logger.info("Dry-run mode (no --run) will only print commands")

    # Directories to clear when requested. These are repo-relative paths.
    to_clear = [
        REPO_ROOT / "Door TestCases" / "DoorGeometry" / "Baselines",
        REPO_ROOT / "Door TestCases" / "BinPacking" / "Baselines",
        REPO_ROOT / "Door TestCases" / "BinPacking" / "Outputs",
    ]

    def _clear_dir_contents(d: Path):
        if not d.exists() or not d.is_dir():
            logger.debug("Skip clearing missing path: %s", d)
            return
        # Safety: ensure target dir is inside repo root
        try:
            if not d.resolve().is_relative_to(REPO_ROOT.resolve()):
                logger.warning("Refusing to clear %s: not under repo root", d)
                return
        except Exception:
            logger.warning("Could not verify path safety for %s; skipping", d)
            return

        for child in list(d.iterdir()):
            try:
                if child.is_dir():
                    shutil.rmtree(child)
                    logger.info("Removed directory: %s", child)
                else:
                    child.unlink()
                    logger.info("Removed file: %s", child)
            except Exception as e:
                logger.error("Failed to remove %s: %s", child, e)

    # If the user asked to only clean, do that and exit early.
    if args.clean_only:
        logger.info("Cleaning target folders (clean-only)...")
        for p in to_clear:
            _clear_dir_contents(p)
        logger.info("Cleaning complete")
        return

    # If clean requested together with --run, perform cleaning before running.
    if args.clean and args.run:
        logger.info("Cleaning target folders before running generation...")
        for p in to_clear:
            _clear_dir_contents(p)
    elif args.clean and not args.run:
        logger.info("--clean provided but --run not set; use --clean-only to just clean, or pass --run to clean before running")

    for step in steps:
        script = REPO_ROOT / step
        if not script.exists():
            logger.error("Script not found: %s", script)
            return

        step_args = []
        # heuristics: pass --ndigits to extract scripts; only pass --overwrite to the
        # bixdxf extractor which supports it.
        name = script.stem.lower()
        if "extract" in name:
            # both extract_dxf_geometry and extract_bixdxf_geometry accept --ndigits
            step_args += ["--ndigits", str(args.ndigits)]
        if "bixdxf" in name and args.overwrite:
            step_args.append("--overwrite")

        rc = run_step(script, step_args, run=args.run)
        if rc != 0:
            logger.error("Step failed: %s (rc=%d)", script, rc)
            return

    logger.info("All requested steps completed (or planned in dry-run).")


if __name__ == "__main__":
    main()
