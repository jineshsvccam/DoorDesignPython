import ezdxf
import json
import sys
from pathlib import Path
import argparse
from typing import List, Any
from collections.abc import Iterable
import logging

logger = logging.getLogger("extract_dxf_geometry")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def extract_geometry(dxf_path: str) -> List[dict]:
    # ezdxf may not expose precise stubs for readfile; silence type checker here
    doc = ezdxf.readfile(dxf_path)  # type: ignore[attr-defined]
    msp = doc.modelspace()

    geometry = []

    for e in msp:
        t = e.dxftype()
        if t == "LINE":
            geometry.append({
                "type": "LINE",
                "start": [float(e.dxf.start[0]), float(e.dxf.start[1])],
                "end": [float(e.dxf.end[0]), float(e.dxf.end[1])],
            })

        elif t == "LWPOLYLINE":
            # Use getattr to avoid type-checker attribute complaints
            gp = getattr(e, "get_points", None)
            pts: List[Any] = []
            if callable(gp):
                raw = gp()
                if isinstance(raw, Iterable):
                    pts = list(raw)
                elif isinstance(raw, (list, tuple)):
                    pts = list(raw)
                else:
                    # unknown return type from get_points
                    try:
                        pts = list(raw)  # type: ignore
                    except Exception:
                        pts = []
            closed_flag = bool(getattr(e, "closed", False))
            geometry.append({
                "type": "LWPOLYLINE",
                "points": [[float(p[0]), float(p[1])] for p in pts],
                "closed": closed_flag,
            })

        elif t == "CIRCLE":
            geometry.append({
                "type": "CIRCLE",
                "center": [float(e.dxf.center[0]), float(e.dxf.center[1])],
                "radius": float(e.dxf.radius),
            })

        elif t == "ARC":
            geometry.append({
                "type": "ARC",
                "center": [float(e.dxf.center[0]), float(e.dxf.center[1])],
                "radius": float(e.dxf.radius),
                "start_angle": float(e.dxf.start_angle),
                "end_angle": float(e.dxf.end_angle),
            })

    return geometry


def _collect_points(geometry: List[dict]) -> List[List[float]]:
    pts = []
    for g in geometry:
        if g["type"] == "LINE":
            pts.append(g["start"]) 
            pts.append(g["end"]) 
        elif g["type"] == "LWPOLYLINE":
            pts.extend(g.get("points", []))
        elif g["type"] in ("CIRCLE", "ARC"):
            pts.append(g.get("center", [0.0, 0.0]))
    return pts


def normalize_geometry(geometry: List[dict], ndigits: int = 3) -> List[dict]:
    pts = _collect_points(geometry)
    if not pts:
        return geometry

    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    min_x, min_y = min(xs), min(ys)

    def _shift_point(p):
        return [round(p[0] - min_x, ndigits), round(p[1] - min_y, ndigits)]

    out = []
    for g in geometry:
        g2 = dict(g)
        if g2["type"] == "LINE":
            g2["start"] = _shift_point(g2["start"])
            g2["end"] = _shift_point(g2["end"])
        elif g2["type"] == "LWPOLYLINE":
            g2["points"] = [_shift_point(p) for p in g2.get("points", [])]
        elif g2["type"] in ("CIRCLE", "ARC"):
            g2["center"] = _shift_point(g2.get("center", [0.0, 0.0]))
            if "radius" in g2:
                g2["radius"] = round(float(g2["radius"]), ndigits)
        out.append(g2)

    return out


def write_actual_geometry(output_dir: Path, geometry: List[dict]):
    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / "actual.geometry.json"
    out_file.write_text(json.dumps(geometry, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Extract and normalize geometry from DXF files")
    parser.add_argument("path", nargs="?", default=None, help="DXF file or folder to process (overrides defaults)")
    parser.add_argument("--input-dir", "-i", default=None, help="Input folder containing .dxf files (overrides defaults)")
    parser.add_argument("--output-dir", "-o", default=None, help="Output folder for geometry JSON files (overrides defaults)")
    parser.add_argument("--ndigits", type=int, default=3, help="Decimal places to round coordinates")
    args = parser.parse_args()

    # Determine repository root (two levels up from tools/BaseLines)
    repo_root = Path(__file__).resolve().parents[2]

    # Prefer DXFs under DoorGeometry; fall back to generic Baselines/Dxf
    candidate_inputs = [
        repo_root / "Door TestCases" / "DoorGeometry" / "Baselines" / "Dxf",
        repo_root / "Door TestCases" / "Baselines" / "Dxf",
        repo_root / "Door TestCases" / "BinPacking" / "Baselines" / "Dxf",
    ]

    default_inputs = next((p for p in candidate_inputs if p.exists()), candidate_inputs[0])
    default_outputs = default_inputs.parent / "DxfGeometry"

    # Allow CLI overrides of input/output dirs before deciding which files to
    # process so that --output-dir is honored even when a positional path is
    # provided.
    if args.input_dir:
        default_inputs = Path(args.input_dir)
    if args.output_dir:
        default_outputs = Path(args.output_dir)

    # Determine files to process
    files: list[Path] = []
    if args.path:
        p = Path(args.path)
        if p.is_dir():
            files = sorted(p.glob("*.dxf"))
        elif p.is_file():
            files = [p]
        else:
            print(f"No such file or directory: {p}", file=sys.stderr)
            return 2
    else:
        if not default_inputs.exists():
            print(f"Input directory not found: {default_inputs}", file=sys.stderr)
            return 0
        files = sorted(default_inputs.glob("*.dxf"))

    if not files:
        print("No DXF files found to process.")
        return 0

    outputs_dir = default_outputs
    outputs_dir.mkdir(parents=True, exist_ok=True)

    for f in files:
        try:
            geom = extract_geometry(str(f))
            norm = normalize_geometry(geom, ndigits=args.ndigits)
            out_file = outputs_dir / (f.stem + "_geometry.json")
            out_file.write_text(json.dumps(norm, indent=2), encoding="utf-8")
            try:
                rel = out_file.relative_to(repo_root)
            except Exception:
                rel = out_file
            logger.info("Wrote %s", rel)
        except Exception as e:
            print(f"Failed to process {f}: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
