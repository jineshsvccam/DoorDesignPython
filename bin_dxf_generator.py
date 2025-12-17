import os
import shutil
import zipfile
from pathlib import Path
from ezdxf.filemanagement import new
from DoorDrawingGenerator import DoorDrawingGenerator
from geometry.door_geometry import compute_door_geometry
from fastapi_app.schemas_output import BinDoor, BinManifest, BinDoorTransformed, BinTransformedManifest
from fastapi_app.schemas_input import DoorDXFRequest
from BatchGenerator import BatchGenerator
from tools.validate_transformed_batch import validate_single_transformed_file


def _normalize_request_dict(req):
    """Return a dict representation of a request object (pydantic model or dict).

    Tries pydantic v2 `model_dump`, falls back to `dict()` (v1), then to the raw dict.
    Returns an empty dict if normalization fails or req is None.
    """
    if req is None:
        return {}
    # pydantic v2
    if hasattr(req, "model_dump"):
        try:
            return req.model_dump()
        except Exception:
            pass
    # pydantic v1
    if hasattr(req, "dict"):
        try:
            return req.dict()
        except Exception:
            pass
    # if it's already a dict
    if isinstance(req, dict):
        return req
    # fallback
    try:
        return dict(req)
    except Exception:
        return {}


def _safe_model_dump(obj):
    """Return a JSON-serializable dict for a pydantic model or dict, or None."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump()
        except Exception:
            pass
    if hasattr(obj, "dict"):
        try:
            return obj.dict()
        except Exception:
            pass
    try:
        return dict(obj)
    except Exception:
        return None


def _write_manifest_atomic(path: Path, manifest_obj):
    """Write a pydantic manifest to path atomically with a small fallback."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        try:
            # Use aliases when dumping so fields like Annotation.from_ are
            # serialized as the JSON key "from" which matches the pydantic
            # model aliases and allows parsing the manifest back later.
            payload = manifest_obj.model_dump_json(indent=2, by_alias=True)
        except Exception:
            try:
                payload = manifest_obj.json(indent=2, by_alias=True)
            except Exception:
                payload = str(manifest_obj)

        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(payload)
        os.replace(tmp, path)
    except Exception:
        # fallback non-atomic write
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(payload)


def create_and_write_bin_manifest(index, bin_data, door_params_list, sheet_width, sheet_height, output_dir):
    """Create a BinTransformedManifest for a single bin and write it to JSON.

    Returns (transformed_json_path, transformed_manifest).
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    placements = bin_data.get("placements", [])
    doors_transformed = []

    for placement in placements:
        file_name = placement.get("file_name") if isinstance(placement, dict) else None
        door_params = next((d for d in door_params_list if d.get("file_name") == file_name), None)
        if not door_params:
            continue

        req = door_params.get("request")
        req_dict = _normalize_request_dict(req)
        placement_tuple = (placement.get("x", 0), placement.get("y", 0))
        rotated = bool(placement.get("rotated", False))

        # Attempt to parse request into DoorDXFRequest (if dict) or use model
        req_obj = None
        if isinstance(req, dict):
            try:
                req_obj = DoorDXFRequest.parse_obj(req)
            except Exception:
                req_obj = None
        else:
            req_obj = req

        original_response = None
        transformed = None
        if req_obj is not None:
            try:
                # compute both geometries in a single try/except block
                original_response = compute_door_geometry(req_obj, rotated=False, offset=(0.0, 0.0))
                transformed = compute_door_geometry(req_obj, rotated=rotated, offset=placement_tuple)
            except Exception as e:
                print(f"[WARN] Failed to compute geometry for '{file_name}': {e}")

        # Safe original_request dict (single helper)
        orig_req = _safe_model_dump(req_obj) or req_dict or None

        bd_t = BinDoorTransformed(
            file_name=file_name,
            original_request=orig_req,
            placement=placement_tuple,
            rotated=rotated,
            transformed=transformed,
            original_response=original_response,
        )
        doors_transformed.append(bd_t)

    # Build and write only the transformed manifest (contains full details)
    transformed_manifest = BinTransformedManifest(sheet_width=sheet_width, sheet_height=sheet_height, doors=doors_transformed)
    transformed_json_path = out_dir.joinpath(f"bin_{index+1}_transformed.json")
    _write_manifest_atomic(transformed_json_path, transformed_manifest)

    return str(transformed_json_path), transformed_manifest


def generate_bin_dxf(sheet_w, sheet_h, doors_for_generator, placements, out_dxf, isannotationRequired=True):
    """Generate a DXF for a bin using precomputed transformed SchemasOutput values.

    This function does not recompute geometry. It uses the `transformed` entry
    present on each door dict in `doors_for_generator` and asks
    DoorDrawingGenerator to draw that schema directly into the shared DXF
    document. The transformed schema is expected to already contain the
    correct metadata.offset (packer placement coordinates).
    """
    if sheet_w <= 0 or sheet_h <= 0:
        raise ValueError("Sheet dimensions must be positive numbers.")
    if not out_dxf.lower().endswith('.dxf'):
        raise ValueError("Output file name must end with .dxf")

    # Create DXF document
    doc = new(dxfversion="R2010")
    doc.layers.new(name="BIN", dxfattribs={"color": 2})  # Yellow
    doc.layers.new(name="CUT", dxfattribs={"color": 4})  # Cyan
    doc.layers.new(name="DIMENSIONS", dxfattribs={"color": 1})  # Red
    msp = doc.modelspace()

    # Draw bin boundary
    msp.add_lwpolyline(
        [(0, 0), (sheet_w, 0), (sheet_w, sheet_h), (0, sheet_h), (0, 0)],
        dxfattribs={"layer": "BIN"}
    )

    # Draw each door using the precomputed transformed schema.
    for door, placement in zip(doors_for_generator, placements):
        transformed = None
        file_label = None
        if isinstance(door, dict):
            transformed = door.get('transformed')
            file_label = door.get('file_name')
        else:
            # if a non-dict entry is passed, assume it is already a transformed schema
            transformed = door

        if transformed is None:
            print(f"[WARN] No transformed schema for door '{file_label}' - skipping")
            continue

        # rotated flag may be present in placement; pass it through if available
        rotated_flag = False
        if isinstance(placement, dict):
            rotated_flag = bool(placement.get('rotated', False))

        # Draw using DoorDrawingGenerator with the precomputed schema
        DoorDrawingGenerator.generate_door_dxf(
            request=door.get('request') if isinstance(door, dict) else None,
            schema=transformed,
            file_name=None,
            label_name=file_label,
            isannotationRequired=isannotationRequired,
            doc=doc,
            msp=msp,
            save_file=False,
            rotated=rotated_flag,
        )

    doc.saveas(out_dxf)
    print(f" Bin DXF file '{out_dxf}' created successfully.")


def generate_all_bins_dxf(sheet_width, sheet_height, bins, door_params_list, isannotationRequired=True, ispdfrequired=True):
   
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, 'outputBulk')
    # Ensure output directory exists and is empty before generating new files
    if os.path.exists(output_dir):
        # remove all contents inside output_dir (files and subdirectories)
        for entry in Path(output_dir).iterdir():
            try:
                if entry.is_dir():
                    shutil.rmtree(entry)
                else:
                    entry.unlink()
            except Exception as e:
                print(f"[WARN] Failed to remove '{entry}': {e}")
    else:
        os.makedirs(output_dir, exist_ok=True)

    bg = BatchGenerator(sheet_width=sheet_width, sheet_height=sheet_height, output_dir=output_dir)
    generated_dxf_paths = []

    for i, bin_data in enumerate(bins):
        json_path, transformed_manifest = create_and_write_bin_manifest(i, bin_data, door_params_list, sheet_width, sheet_height, output_dir)

        # Validate the transformed manifest before DXF generation
        print(f"\n[VALIDATION] Validating bin {i+1} manifest before DXF generation...")
        validation_result = validate_single_transformed_file(json_path)
        
        if validation_result.get("fail_count", 0) > 0:
            print(f"[WARN] Bin {i+1} has {validation_result['fail_count']} validation failures out of {validation_result['door_count']} doors")
            # Optional: save validation report for this bin
            validation_path = Path(json_path).with_name(f"bin_{i+1}_validation.json")
            import json
            with open(validation_path, 'w') as f:
                json.dump(validation_result, f, indent=2)
            print(f"[INFO] Validation report saved: {validation_path}")
        else:
            print(f"[SUCCESS] Bin {i+1} validation passed for all {validation_result['door_count']} doors")

        dxf_path = bg.generate_dxf_for_bin_json(json_path, isannotationRequired=isannotationRequired)
        if dxf_path:
            generated_dxf_paths.append(dxf_path)
            print(f"Bin {i+1} DXF generated: {dxf_path}")
        else:
            print(f"Bin {i+1} DXF generation failed for manifest: {json_path}")

    # Generate merged PDF from all DXF files (if required)
    if ispdfrequired:
        merged_pdf_path = os.path.join(output_dir, "output_bins_merged.pdf")
        print("[INFO] Starting PDF generation and merging...")
        try:
            from tools.merge_dxf_to_pdf import convert_and_merge_dxf_directory
            
            pdf_result = convert_and_merge_dxf_directory(
                dxf_directory=output_dir,
                output_pdf_path=merged_pdf_path,
                page_size_mm=(sheet_width, sheet_height),
                margin_mm=10.0                
            )
            
            if pdf_result:
                print(f"[SUCCESS] Merged PDF created: {pdf_result}")
            else:
                print("[WARN] Failed to create merged PDF")
        except Exception as e:
            print(f"[ERROR] PDF generation failed: {e}")
            merged_pdf_path = None
    else:
        print("[INFO] PDF generation skipped (ispdfrequired=False)")

    # Create ZIP archive containing .dxf and .pdf files from the output directory
    zip_path = os.path.join(script_dir, "output_bins.zip")
    try:
        with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(output_dir):
                for f in files:
                    if f.lower().endswith(('.dxf', '.pdf')):
                        full = os.path.join(root, f)
                        # store files with a relative path inside the archive
                        arcname = os.path.relpath(full, output_dir)
                        zf.write(full, arcname)
        print(f"ZIP created: {zip_path}")
        return zip_path
    except Exception as e:
        print(f"Failed to create ZIP archive: {e}")
        return None
