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
    for i, bin_data in enumerate(bins):
        bin_id = bin_data["bin_id"]
        placements = bin_data["placements"]
        doors_in_bin = []
        offsets_in_bin = []
        for placement in placements:
            file_name = placement["file_name"]
            offset = (placement["x"], placement["y"])
            door_params = next((d for d in door_params_list if d["file_name"] == file_name), None)
            if door_params:
                doors_in_bin.append(door_params)
                offsets_in_bin.append(offset)
        output_file = f"bin_{i+1}.dxf"
        generate_bin_dxf(
            sheet_width,
            sheet_height,
            doors_in_bin,
            offsets_in_bin,
            output_file,
            isannotationRequired=isannotationRequired
        )
        print(f"Bin DXF '{output_file}' generation complete.")
    print("Execution Complete.")
from ezdxf.filemanagement import new
from DoorDrawingGenerator import DoorDrawingGenerator

def generate_bin_dxf(sheet_width, sheet_height, doors, placements, file_name, isannotationRequired=True):
    """
    Generates a DXF file for a bin (sheet) with multiple doors placed at specified offsets.
    Args:
        sheet_width: Width of the bin/sheet.
        sheet_height: Height of the bin/sheet.
        doors: List of dicts, each containing door parameters for DoorDrawingGenerator.generate_door_dxf.
        placements: List of (x, y) offsets for each door in the bin.
        file_name: Output DXF file name for the bin.
        isannotationRequired: Whether to annotate dimensions.
    """
    if sheet_width <= 0 or sheet_height <= 0:
        raise ValueError("Sheet dimensions must be positive numbers.")
    if not file_name.lower().endswith('.dxf'):
        raise ValueError("Output file name must end with .dxf")

    doc = new(dxfversion="R2010")
    doc.layers.new(name="BIN", dxfattribs={"color": 2})  # Yellow
    doc.layers.new(name="CUT", dxfattribs={"color": 4})  # Cyan
    doc.layers.new(name="DIMENSIONS", dxfattribs={"color": 1})  # Red
    msp = doc.modelspace()

    # Draw bin boundary
    msp.add_lwpolyline([
        (0, 0),
        (sheet_width, 0),
        (sheet_width, sheet_height),
        (0, sheet_height),
        (0, 0)
    ], dxfattribs={"layer": "BIN"})

    # Draw each door at its placement
    allowed_keys = [
        'width_measurement', 'height_measurement',
        'left_side_allowance_width', 'right_side_allowance_width',
        'left_side_allowance_height', 'right_side_allowance_height',
        'door_minus_measurement_width', 'door_minus_measurement_height',
        'bending_width', 'bending_height',
        'file_name', 'isannotationRequired', 'offset', 'doc', 'msp', 'save_file'
    ]
    for door_params, offset in zip(doors, placements):
        params = {k: v for k, v in dict(door_params).items() if k in allowed_keys}
        params['file_name'] = None  # Don't save individual door DXFs
        params['isannotationRequired'] = isannotationRequired
        params['offset'] = offset
        params['doc'] = doc
        params['msp'] = msp
        params['save_file'] = False
        DoorDrawingGenerator.generate_door_dxf(**params)

    doc.saveas(file_name)
    print("Bin DXF file '{}' created successfully.".format(file_name))