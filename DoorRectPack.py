
"""
Uses rectpack to place doors (rectangles) efficiently on a sheet.
Reads door dimensions from Restructured_Door_Measurements.xlsx and packs them using rectpack.
"""
import pandas as pd
from rectpack import newPacker
import logging

logger = logging.getLogger(__name__)

def pack_rectangles(rectangles, sheet_width, sheet_height):
    from rectpack import newPacker
    gap = 10  # mm, change as needed
    
    logger.info(f"=== PACKING START ===")
    logger.info(f"Sheet dimensions: {sheet_width}x{sheet_height}mm")
    logger.info(f"Total rectangles to pack: {len(rectangles)}")
    logger.info(f"Gap between rectangles: {gap}mm")
    print(f"Packing {len(rectangles)} rectangles with {gap}mm gap...")
    
    # Log first 5 and last 5 rectangle dimensions for debugging
    if len(rectangles) <= 10:
        for i, (w, h, name) in enumerate(rectangles):
            logger.debug(f"  Rectangle {i+1}: {name} = {w}x{h}mm")
    else:
        for i, (w, h, name) in enumerate(rectangles[:5]):
            logger.debug(f"  Rectangle {i+1}: {name} = {w}x{h}mm")
        logger.debug(f"  ... ({len(rectangles)-10} more rectangles)")
        for i, (w, h, name) in enumerate(rectangles[-5:], start=len(rectangles)-4):
            logger.debug(f"  Rectangle {i}: {name} = {w}x{h}mm")
    
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
    logger.info(f"Adding {bin_count} bins (WARNING: This allows up to {bin_count} separate bins!)")
    logger.warning(f"Current implementation adds bin_count={bin_count} which may cause inefficient packing")
    
    packer.add_bin(sheet_width, sheet_height, bin_count)
    logger.info(f"Starting rectpack.pack() operation...")
    packer.pack() # type: ignore
    logger.info(f"Packing complete. Processing results...")
    # Organize placements by bin
    bins = {}
    rect_list = packer.rect_list()
    logger.info(f"Rectpack returned {len(rect_list)} placement results")
    
    for rect in rect_list:
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
    
    total_placements = sum(len(v) for v in bins.values())
    bins_used = len(bins)
    logger.info(f"=== PACKING RESULTS ===")
    logger.info(f"Bins used: {bins_used} out of {bin_count} available bins")
    logger.info(f"Total placements: {total_placements}")
    
    # Log distribution of rectangles per bin
    for bin_id in sorted(bins.keys()):
        count = len(bins[bin_id])
        logger.info(f"  Bin {bin_id}: {count} rectangles")
    
    if bins_used > 30:
        logger.warning(f"HIGH BIN COUNT DETECTED: {bins_used} bins used! This may indicate packing inefficiency.")
    
    print(f"Returned {total_placements} placements across {bins_used} bins.")
    # Return bins as a list of dicts
    bin_list = []
    for bin_id, placements in bins.items():
        bin_list.append({
            "bin_id": bin_id,
            "placements": placements
        })
    return bin_list


