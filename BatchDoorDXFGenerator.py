from rectpack import newPacker
from door_utils import get_door_rectangles
from bin_dxf_generator import generate_bin_dxf
"""
Read Restructured_Door_Measurements.xlsx and generate DXF files for each row with 'Run Required' == 'Y'.
Uses pandas to read Excel and DoorDrawingGenerator.generate_door_dxf for DXF creation.
"""
import pandas as pd
from DoorDrawingGenerator import DoorDrawingGenerator

EXCEL_FILE = "Restructured_Door_Measurements.xlsx"
FIXED_PARAMS = {
    "door_minus_measurement_width": 68,
    "door_minus_measurement_height": 70,
    "bending_width": 31,
    "bending_height": 24,
}

def main():
    df = pd.read_excel(EXCEL_FILE)
    rectangles, door_params_list = get_door_rectangles(df, FIXED_PARAMS)
    print("Rectangles:", rectangles)
    print("Door Params List:", door_params_list)

    SHEET_WIDTH = 1250
    SHEET_HEIGHT = 2500
    from DoorRectPack import pack_rectangles
    from visualize_utils import visualize_placements
    bins = pack_rectangles(rectangles, sheet_width=SHEET_WIDTH, sheet_height=SHEET_HEIGHT)
    print("Bins:", bins)

    # Flatten all placements for visualization
    all_placements = [p for bin_data in bins for p in bin_data["placements"]]
    visualize_placements(all_placements, sheet_width=SHEET_WIDTH, sheet_height=SHEET_HEIGHT)

    from bin_dxf_generator import generate_all_bins_dxf
    generate_all_bins_dxf(
        SHEET_WIDTH,
        SHEET_HEIGHT,
        bins,
        door_params_list,
        isannotationRequired=True
    )

if __name__ == "__main__":
    main()
