import os
import shutil
from ezdxf.filemanagement import new
from DoorDrawingGenerator import DoorDrawingGenerator


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
    allowed_keys = [
        'width_measurement', 'height_measurement',
        'left_side_allowance_width', 'right_side_allowance_width',
        'left_side_allowance_height', 'right_side_allowance_height',
        'door_minus_measurement_width', 'door_minus_measurement_height',
        'bending_width', 'bending_height',
        'file_name', 'isannotationRequired', 'offset', 'doc', 'msp', 'save_file', 'label_name'
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
        # Debug print of key parameters before drawing
        dbg_keys = [
            'width_measurement', 'height_measurement',
            'left_side_allowance_width', 'right_side_allowance_width',
            'left_side_allowance_height', 'right_side_allowance_height',
            'door_minus_measurement_width', 'door_minus_measurement_height',
            'bending_width', 'bending_height'
        ]
        dbg_vals = {k: params.get(k) for k in dbg_keys}
        print(f"[DEBUG bin_dxf] file={door_params.get('file_name')} rotated={rotated} offset={offset} params={dbg_vals}")
        DoorDrawingGenerator.generate_door_dxf(**params)

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
