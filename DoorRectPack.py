
"""
Uses rectpack to place doors (rectangles) efficiently on a sheet.
Reads door dimensions from Restructured_Door_Measurements.xlsx and packs them using rectpack.
"""
import pandas as pd
from rectpack import newPacker

def pack_rectangles(rectangles, sheet_width, sheet_height):
    from rectpack import newPacker
    gap = 10  # mm, change as needed
    print(f"Packing {len(rectangles)} rectangles with {gap}mm gap...")
    packer = newPacker()
    for width, height, name in rectangles:
        packer.add_rect(width + gap, height + gap, rid=name)
    bin_count = max(1, len(rectangles))
    packer.add_bin(sheet_width, sheet_height, bin_count)
    packer.pack() # type: ignore
    # Organize placements by bin
    bins = {}
    for rect in packer.rect_list():
        # rectpack returns: bin_id, x, y, w, h, rid, *rotated (rotated is optional)
        if len(rect) == 7:
            bin_id, x, y, w, h, rid, rotated = rect
        else:
            bin_id, x, y, w, h, rid = rect
            rotated = False
        placement = {
            "file_name": rid,
            "bin_id": bin_id,
            "x": x,
            "y": y,
            "width": w - gap,
            "height": h - gap,
            "rotated": rotated
        }
        if bin_id not in bins:
            bins[bin_id] = []
        bins[bin_id].append(placement)
    print(f"Returned {sum(len(v) for v in bins.values())} placements across {len(bins)} bins.")
    # Return bins as a list of dicts
    bin_list = []
    for bin_id, placements in bins.items():
        bin_list.append({
            "bin_id": bin_id,
            "placements": placements
        })
    return bin_list


