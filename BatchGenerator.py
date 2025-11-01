"""BatchGenerator

Helper class to create per-bin JSON manifests and generate DXF files from them.

Usage patterns:

1) Create JSON manifests for all bins (useful for review / CI):

    bg = BatchGenerator(sheet_width=1250, sheet_height=2500, output_dir="output")
    bg.create_bin_jsons(bins, door_params_list)

Each produced JSON is named `bin_{i+1}.json` and contains:
    { "sheet_width": ..., "sheet_height": ..., "doors": [ {"file_name":..., "request": {...}, "placement": {"x":...,"y":...,"rotated":...} } ] }

2) Generate DXFs from the JSON manifests (reconstructs pydantic requests):

    bg.generate_dxf_for_bin_json(json_path, isannotationRequired=False)

3) Convenience: create all jsons then generate all DXFs.

Also includes a helper to generate a single door DXF from a DoorDXFRequest.
"""
from __future__ import annotations

import json
import os
from typing import List, Dict, Any, Optional

from fastapi_app.schemas_input import DoorDXFRequest
from fastapi_app.schemas_output import BinDoor, BinManifest, SchemasOutput
from DoorDrawingGenerator import DoorDrawingGenerator
from fastapi_app.schemas_output import BinDoorTransformed, BinTransformedManifest
from geometry.door_geometry import compute_door_geometry


class BatchGenerator:
    def __init__(self, sheet_width: int = 1250, sheet_height: int = 2500, output_dir: str = "output"):
        self.sheet_width = sheet_width
        self.sheet_height = sheet_height
        self.output_dir = os.path.abspath(output_dir)
        os.makedirs(self.output_dir, exist_ok=True)

    def create_bin_jsons(self, bins: List[Dict[str, Any]], door_params_list: List[Dict[str, Any]]) -> List[str]:
        """Write per-bin JSON manifest files and return list of file paths.

        bins: as returned by packer (list of {'placements': [...]})
        door_params_list: list of dicts where each dict contains at least 'file_name' and 'request' (pydantic model or dict)
        """
        json_paths = []
        for i, bin_data in enumerate(bins):
            placements = bin_data.get("placements", [])
            doors_out = []
            for p in placements:
                fn = p.get("file_name") if isinstance(p, dict) else None
                dp = next((d for d in door_params_list if d.get("file_name") == fn), None)
                if not dp:
                    continue
                req = dp.get("request")
                # Normalize request to a dict
                if req is not None and hasattr(req, "dict"):
                    req_dict = req.dict()
                else:
                    req_dict = req or {}

                bd = BinDoor(file_name=fn, request=req_dict, placement=(p.get("x", 0), p.get("y", 0)), rotated=bool(p.get("rotated", False)))
                doors_out.append(bd)

            out_path = os.path.join(self.output_dir, f"bin_{i+1}.json")
            manifest = BinManifest(sheet_width=self.sheet_width, sheet_height=self.sheet_height, doors=doors_out)
            with open(out_path, "w", encoding="utf-8") as fh:
                try:
                    fh.write(manifest.model_dump_json(indent=2))
                except Exception:
                    fh.write(manifest.json(indent=2))
            json_paths.append(out_path)

        return json_paths

    def generate_dxf_for_bin_json(self, json_path: str, isannotationRequired: bool = False) -> Optional[str]:
        """Read a bin JSON, reconstruct DoorDXFRequest objects and generate a DXF for the bin.

        Returns the generated DXF file path or None on failure.
        """
        # Read manifest JSON once
        try:
            with open(json_path, "r", encoding="utf-8") as fh:
                raw_text = fh.read()
                raw_obj = json.loads(raw_text)
        except Exception as e:
            print(f"Failed to read/parse JSON '{json_path}': {e}")
            return None

        # Detect transformed manifest (contains per-door 'transformed' nodes)
        transformed_mode = isinstance(raw_obj, dict) and any(
            isinstance(d, dict) and "transformed" in d for d in raw_obj.get("doors", [])
        )

        # Parse into the correct pydantic manifest model
        try:
            if transformed_mode:
                manifest = BinTransformedManifest.parse_raw(raw_text)
            else:
                manifest = BinManifest.parse_raw(raw_text)
        except Exception as e:
            print(f"Failed to parse manifest '{json_path}': {e}")
            return None

        sheet_w = manifest.sheet_width
        sheet_h = manifest.sheet_height
        doors = manifest.doors

        doors_for_generator: List[Dict[str, Any]] = []
        placements: List[Dict[str, Any]] = []

        for d in doors:
            fn = getattr(d, "file_name", None)
            req_obj = None
            transformed_obj = None

            if transformed_mode:
                orig_req = getattr(d, "original_request", None) or getattr(d, "request", None) or {}
                try:
                    req_obj = DoorDXFRequest.parse_obj(orig_req or {})
                except Exception:
                    req_obj = orig_req

                tval = getattr(d, "transformed", None)
                if tval is not None:
                    try:
                        transformed_obj = SchemasOutput.parse_obj(tval) if isinstance(tval, (dict, str)) else tval
                    except Exception:
                        transformed_obj = tval
            else:
                try:
                    req_obj = DoorDXFRequest.parse_obj(getattr(d, "request", {}) or {})
                except Exception:
                    req_obj = getattr(d, "request", {})

            doors_for_generator.append({"file_name": fn, "request": req_obj, "transformed": transformed_obj})
            # placement can be a tuple/list; guard access
            placement_val = getattr(d, "placement", (0.0, 0.0)) or (0.0, 0.0)
            try:
                px = float(placement_val[0])
                py = float(placement_val[1])
            except Exception:
                px, py = 0.0, 0.0
            placements.append({"file_name": fn, "x": px, "y": py, "rotated": bool(getattr(d, "rotated", False))})

        # Output DXF path
        base = os.path.splitext(os.path.basename(json_path))[0]
        out_dxf = os.path.join(self.output_dir, f"{base}.dxf")

        try:
            # Import here to avoid circular import: bin_dxf_generator imports BatchGenerator
            from bin_dxf_generator import generate_bin_dxf
            generate_bin_dxf(sheet_w, sheet_h, doors_for_generator, placements, out_dxf, isannotationRequired=isannotationRequired)
            return out_dxf
        except Exception as e:
            print(f"Failed to generate DXF for '{json_path}': {e}")
            return None

    def generate_all_from_bins(self, bins: List[Dict[str, Any]], door_params_list: List[Dict[str, Any]], isannotationRequired: bool = False) -> List[str]:
        """Create JSONs and generate DXFs for all bins. Returns list of generated DXF paths."""
        jsons = self.create_bin_jsons(bins, door_params_list)
        out = []
        for j in jsons:
            dxf = self.generate_dxf_for_bin_json(j, isannotationRequired=isannotationRequired)
            if dxf:
                out.append(dxf)
        return out

    def generate_transformed_manifest(self, json_path: str, out_path: Optional[str] = None) -> Optional[str]:
        """Read a BinManifest JSON, compute transformed SchemasOutput for each door,
        and write a BinTransformedManifest to out_path (or same directory with suffix).

        Returns the written path or None on failure.
        """
        try:
            with open(json_path, "r", encoding="utf-8") as fh:
                manifest = BinManifest.parse_raw(fh.read())
        except Exception as e:
            print(f"Failed to load JSON '{json_path}': {e}")
            return None

        doors_out: List[BinDoorTransformed] = []
        for d in manifest.doors:
            fn = d.file_name
            placement = (float(d.placement[0]), float(d.placement[1])) if d.placement else (0.0, 0.0)
            rotated = bool(d.rotated)

            # Try to reconstruct DoorDXFRequest
            req_obj = None
            try:
                req_obj = DoorDXFRequest.parse_obj(d.request or {})
            except Exception:
                req_obj = None

            transformed = None
            original_response = None
            transformed = None
            if req_obj is not None:
                # Compute the original (pre-transform) geometry: no rotation, no placement offset
                try:
                    original_response = compute_door_geometry(req_obj, rotated=False, offset=(0.0, 0.0))
                except Exception as e:
                    print(f"Failed to compute original geometry for '{fn}': {e}")
                    original_response = None

                # Compute the transformed geometry (applies rotation/placement as used by packer)
                try:
                    transformed = compute_door_geometry(req_obj, rotated=rotated, offset=placement)
                except Exception as e:
                    print(f"Failed to compute transformed geometry for '{fn}': {e}")
                    transformed = None

            # Build a safe original_request dict: prefer the parsed pydantic model dump
            # (pydantic v2 `model_dump`) if available, else fallback to `dict()` (v1),
            # else use the raw request dict from the manifest.
            orig_req = None
            if req_obj is not None:
                if hasattr(req_obj, "model_dump"):
                    try:
                        orig_req = req_obj.model_dump()
                    except Exception:
                        orig_req = None
                elif hasattr(req_obj, "dict"):
                    try:
                        orig_req = req_obj.dict()
                    except Exception:
                        orig_req = None
            if orig_req is None:
                orig_req = d.request or None

            bd = BinDoorTransformed(
                file_name=fn,
                original_request=orig_req,
                placement=placement,
                rotated=rotated,
                transformed=transformed,
                original_response=original_response,
            )
            doors_out.append(bd)

        out_manifest = BinTransformedManifest(sheet_width=manifest.sheet_width, sheet_height=manifest.sheet_height, doors=doors_out)

        if out_path is None:
            base = os.path.splitext(os.path.basename(json_path))[0]
            out_path = os.path.join(self.output_dir, f"{base}_transformed.json")

        try:
            with open(out_path, "w", encoding="utf-8") as fh:
                # Prefer pydantic v2 model_dump_json with aliases so fields like
                # `Annotation.from_` are written as the JSON key `from` (alias).
                # This ensures the manifest is parseable by the pydantic models
                # when read back.
                try:
                    fh.write(out_manifest.model_dump_json(indent=2, by_alias=True))
                except Exception:
                    # Fallback for pydantic v1 or other edge cases that expose
                    # .json(by_alias=...) signature.
                    try:
                        fh.write(out_manifest.json(indent=2, by_alias=True))
                    except Exception:
                        # Final fallback: dump the plain dict and write JSON.
                        try:
                            fh.write(json.dumps(out_manifest.model_dump(), indent=2))
                        except Exception as e:
                            raise RuntimeError(f"Failed to serialize manifest: {e}")
            return out_path
        except Exception as e:
            print(f"Failed to write transformed manifest '{out_path}': {e}")
            return None

    def generate_single(self, request: DoorDXFRequest, file_name: str, isannotationRequired: bool = True) -> Optional[str]:
        """Generate a single-door DXF directly from a DoorDXFRequest."""
        try:
            DoorDrawingGenerator.generate_door_dxf(request, file_name=file_name, isannotationRequired=isannotationRequired)
            return os.path.abspath(file_name)
        except Exception as e:
            print(f"Failed to generate single DXF '{file_name}': {e}")
            return None


if __name__ == "__main__":
    print("BatchGenerator module loaded. Use BatchGenerator(...) in your scripts.")
