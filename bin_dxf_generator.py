import os
import shutil
from ezdxf.filemanagement import new
from DoorDrawingGenerator import DoorDrawingGenerator
from geometry.door_geometry import compute_door_geometry


def generate_bin_dxf(sheet_width, sheet_height, doors, placements, file_name, isannotationRequired=True):
    """
    Generates a DXF file for a bin (sheet) with multiple doors placed at specified offsets.

    Args:
        sheet_width: Width of the bin/sheet.
        sheet_height: Height of the bin/sheet.
        doors: List of dicts, each containing door parameters for DoorDrawingGenerator.generate_door_dxf.
        placements: List of placement dicts (or None) for each door. Expected keys: 'x','y', optional 'rotated'.
        file_name: Output DXF file name for the bin.
        isannotationRequired: Whether to annotate dimensions.
    """
    if sheet_width <= 0 or sheet_height <= 0:
        raise ValueError("Sheet dimensions must be positive numbers.")
    if not file_name.lower().endswith('.dxf'):
        raise ValueError("Output file name must end with .dxf")

    # Create DXF document
    doc = new(dxfversion="R2010")
    doc.layers.new(name="BIN", dxfattribs={"color": 2})  # Yellow
    doc.layers.new(name="CUT", dxfattribs={"color": 4})  # Cyan
    doc.layers.new(name="DIMENSIONS", dxfattribs={"color": 1})  # Red
    msp = doc.modelspace()

    # Draw bin boundary
    msp.add_lwpolyline(
        [(0, 0), (sheet_width, 0), (sheet_width, sheet_height), (0, sheet_height), (0, 0)],
        dxfattribs={"layer": "BIN"}
    )

    # Draw each door in the bin
    # Only allow the DoorDXFRequest model and DXF-generation related kwargs
    # when calling DoorDrawingGenerator.generate_door_dxf. Previous versions
    # passed measurement primitives which the current signature does not
    # accept (causing TypeError). Keep only safe keys here.
    allowed_keys = [
        'request', 'file_name', 'isannotationRequired', 'offset', 'doc', 'msp', 'save_file', 'label_name', 'rotated'
    ]

    for door_params, placement in zip(doors, placements):
        rotated = False
        if isinstance(placement, dict):
            x = placement.get('x', 0) or 0
            y = placement.get('y', 0) or 0
            rotated = bool(placement.get('rotated', False))
            offset = (x, y)
        else:
            offset = (0, 0)

        params = {k: v for k, v in dict(door_params).items() if k in allowed_keys}
        params.update({
            'file_name': None,
            'isannotationRequired': isannotationRequired,
            'offset': offset,
            'doc': doc,
            'msp': msp,
            'save_file': False
        })
        # supply a label_name so the generator can draw file name text even when
        # file saving is disabled (file_name=None)
        params['label_name'] = door_params.get('file_name')

        # Pass rotated flag to DoorDrawingGenerator which will handle coordinate transforms.
        params['rotated'] = rotated
        # Debug: compare requested placement (from packer) with actual
        # geometry bounding box that will be produced by the generator.
        dbg_vals = {
            'file_name': door_params.get('file_name'),
            'outer_w': door_params.get('outer_width'),
            'outer_h': door_params.get('outer_height'),
            'rotated': rotated,
            'placement_offset': offset,
        }
        print(f"[DEBUG bin_dxf] placement request: {dbg_vals}")

        # If we have a DoorDXFRequest, compute the geometry (without saving)
        # to inspect the transformed frame coordinates and bounding box.
        if 'request' in params and params['request'] is not None:
            req = params['request']
            try:
                # First compute geometry at origin to get local bbox
                schema_origin = compute_door_geometry(req, rotated=rotated, offset=(0.0, 0.0))
                all_pts = [p for f in schema_origin.geometry.frames for p in f.points]
                if all_pts:
                    xs = [pt[0] for pt in all_pts]
                    ys = [pt[1] for pt in all_pts]
                    local_min_x, local_min_y = min(xs), min(ys)
                    local_max_x, local_max_y = max(xs), max(ys)
                else:
                    local_min_x = local_min_y = local_max_x = local_max_y = 0.0

                # Compute corrected offset so the geometry's local bbox min aligns with placement offset
                corrected_offset = (offset[0] - local_min_x, offset[1] - local_min_y)

                print(f"[DEBUG bin_dxf] local bbox for {door_params.get('file_name')}: min=({local_min_x},{local_min_y}) max=({local_max_x},{local_max_y})")
                print(f"[DEBUG bin_dxf] corrected_offset={corrected_offset} (placement {offset} - local_min)")
            except Exception as e:
                print(f"[DEBUG bin_dxf] failed to compute geometry for debug: {e}")
                corrected_offset = offset

            # Now call the existing generator to draw into the shared msp/doc
            call_kwargs = {
                'request': req,
                'file_name': params.get('file_name'),
                'label_name': params.get('label_name'),
                'isannotationRequired': params.get('isannotationRequired', isannotationRequired),
                'offset': corrected_offset,
                'doc': params.get('doc'),
                'msp': params.get('msp'),
                'save_file': params.get('save_file', False),
                'rotated': params.get('rotated', False),
            }
            DoorDrawingGenerator.generate_door_dxf(**call_kwargs)
        else:
            raise RuntimeError("Missing 'request' DoorDXFRequest in door_params; cannot generate DXF.")

    doc.saveas(file_name)
    print(f" Bin DXF file '{file_name}' created successfully.")


def generate_all_bins_dxf(sheet_width, sheet_height, bins, door_params_list, isannotationRequired=True):
    """
    Loops through bins and generates a DXF file for each bin.

    Args:
        sheet_width: Width of the bin/sheet.
        sheet_height: Height of the bin/sheet.
        bins: List of bins, each with placements.
        door_params_list: List of all door parameter dicts.
        isannotationRequired: Whether to annotate dimensions.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, 'output')
    os.makedirs(output_dir, exist_ok=True)

    for i, bin_data in enumerate(bins):
        placements = bin_data.get("placements", [])
        doors_in_bin = []
        offsets_in_bin = []

        for placement in placements:
            file_name = placement.get("file_name") if isinstance(placement, dict) else None
            door_params = next((d for d in door_params_list if d.get("file_name") == file_name), None)
            if door_params:
                doors_in_bin.append(door_params)
                offsets_in_bin.append(placement if isinstance(placement, dict) else None)

        output_file = os.path.join(output_dir, f"bin_{i+1}.dxf")
        generate_bin_dxf(sheet_width, sheet_height, doors_in_bin, offsets_in_bin, output_file, isannotationRequired)

        print(f"Bin {i+1} DXF '{output_file}' generation complete.")

    print(" All bins generated successfully.")

    # --- Create ZIP file of all generated DXFs ---
    zip_path = os.path.join(script_dir, "output_bins.zip")
    # shutil.make_archive expects the base name without extension
    base_name = os.path.splitext(zip_path)[0]
    try:
        shutil.make_archive(base_name, "zip", output_dir)
        print(f"ZIP file created at: {zip_path}")
        return zip_path
    except Exception as e:
        print(f"Failed to create ZIP archive: {e}")
        # Still return None to indicate failure to create archive
        return None
