
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
    # Keep a map of original (padded) sizes so we can infer rotation when
    # rectpack doesn't return an explicit rotated flag in the rect tuple.
    orig_sizes = {}
    for width, height, name in rectangles:
        padded_w = width + gap
        padded_h = height + gap
        orig_sizes[name] = (padded_w, padded_h)
        packer.add_rect(padded_w, padded_h, rid=name)
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
            # rectpack sometimes does not include an explicit rotated flag
            # in the returned tuple. Infer rotation by comparing the returned
            # (w,h) with the original padded sizes we submitted. If the
            # dimensions are swapped, the rect was rotated.
            rotated = False
            orig = orig_sizes.get(rid)
            if orig is not None:
                orig_w, orig_h = orig
                if (w, h) == (orig_h, orig_w):
                    rotated = True
        # The packer placed rectangles using an expanded size (width+gap, height+gap).
        # To keep the visual gap evenly around each rectangle, offset the actual
        # placement by half the gap in both x and y. The stored width/height
        # should exclude the gap portion.
        half_gap = gap / 2.0
        placement = {
            "file_name": rid,
            "bin_id": bin_id,
            "x": x + half_gap,
            "y": y + half_gap,
            "width": max(0, w - gap),
            "height": max(0, h - gap),
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


