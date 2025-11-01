from rectpack import newPacker
from door_utils import get_door_rectangles
from bin_dxf_generator import generate_all_bins_dxf
"""
Read Restructured_Door_Measurements.xlsx and generate DXF files for each row with 'Run Required' == 'Y'.
Uses pandas to read Excel and DoorDrawingGenerator.generate_door_dxf for DXF creation.
"""
import pandas as pd
from DoorDrawingGenerator import DoorDrawingGenerator

EXCEL_FILE = "Restructured_Door_Measurements.xlsm"
FIXED_PARAMS = {
    "door_minus_measurement_width": 68,
    "door_minus_measurement_height": 70,
    "bending_width": 31,
    "bending_height": 24,
}


def process_excel(excel_file: str, fixed_params: dict):
    """Read an Excel file and return rectangles and door parameter list.

    This isolates Excel I/O so callers can pass a file path.
    """
    df = pd.read_excel(excel_file)
    return get_door_rectangles(df, fixed_params)


def process_bins(rectangles, door_params_list, sheet_width: int = 1250, sheet_height: int = 2500, isannotationRequired: bool = False):
    """Pack rectangles into sheets, (optionally) visualize placements, and generate DXF files.

    Returns the list of bins produced by the packing algorithm.
    """
    from DoorRectPack import pack_rectangles
    from visualize_utils import visualize_placements

    bins = pack_rectangles(rectangles, sheet_width=sheet_width, sheet_height=sheet_height)

    # Flatten all placements for visualization
    all_placements = [p for bin_data in bins for p in bin_data["placements"]]
    # Uncomment to visualize placements during development
    visualize_placements(all_placements, sheet_width=sheet_width, sheet_height=sheet_height)

    # Generate DXF for all bins and capture zip path returned by generator
    zip_path = generate_all_bins_dxf(
        sheet_width,
        sheet_height,
        bins,
        door_params_list,
        isannotationRequired=isannotationRequired,
    )

    return bins, zip_path


def generate_zip_from_excel(excel_file: str, fixed_params: dict = FIXED_PARAMS, sheet_width: int = 1250, sheet_height: int = 2500, isannotationRequired: bool = False):
    """High-level helper that processes an Excel file, packs rectangles, generates DXFs, and returns the ZIP path.

    This is suitable for calling from a service: pass the Excel file path and receive the path to the ZIP archive containing generated DXFs.
    """
    rectangles, door_params_list = process_excel(excel_file, fixed_params)
    _, zip_path = process_bins(rectangles, door_params_list, sheet_width=sheet_width, sheet_height=sheet_height, isannotationRequired=isannotationRequired)
    return zip_path

def main():
    # Load and process the Excel file (moved to a separate function)
    rectangles, door_params_list = process_excel(EXCEL_FILE, FIXED_PARAMS)
    # print("Rectangles:", rectangles)
    #print("Door Params List:", door_params_list)

    SHEET_WIDTH = 1250
    SHEET_HEIGHT = 2500

    # Pack rectangles and generate DXF files (extracted to a separate function)
    bins, zip_path = process_bins(rectangles, door_params_list, sheet_width=SHEET_WIDTH, sheet_height=SHEET_HEIGHT, isannotationRequired=False)
    if zip_path:
        print(f"Generated ZIP archive: {zip_path}")

if __name__ == "__main__":
    main()
