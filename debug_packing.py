#!/usr/bin/env python3
"""
Diagnostic script to debug packing differences between local and EC2.
Run this script with your Excel file to see detailed packing information.

Usage:
    python debug_packing.py [path_to_excel_file]
    
If no file is provided, uses the default sample template.
"""
import sys
import logging
from BatchDoorDXFGenerator import process_excel, FIXED_PARAMS, EXCEL_FILE
from DoorRectPack import pack_rectangles

# Configure detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('packing_debug.log', mode='w')
    ]
)

logger = logging.getLogger(__name__)

def main():
    excel_file = sys.argv[1] if len(sys.argv) > 1 else EXCEL_FILE
    
    logger.info("=" * 80)
    logger.info("PACKING DEBUG SCRIPT")
    logger.info("=" * 80)
    logger.info(f"Excel file: {excel_file}")
    logger.info(f"Fixed params: {FIXED_PARAMS}")
    
    # Check rectpack version
    try:
        import rectpack
        try:
            from importlib.metadata import version
            rectpack_version = version('rectpack')
            logger.info(f"rectpack version: {rectpack_version}")
        except Exception:
            # Fallback for older Python versions
            try:
                import pkg_resources  # type: ignore
                rectpack_version = pkg_resources.get_distribution('rectpack').version
                logger.info(f"rectpack version: {rectpack_version}")
            except Exception:
                logger.info("rectpack version: unknown (package metadata not available)")
    except Exception as e:
        logger.error(f"Error checking rectpack: {e}")
    
    # Check Python version
    logger.info(f"Python version: {sys.version}")
    
    # Process Excel to get rectangles
    logger.info("\n" + "=" * 80)
    logger.info("PROCESSING EXCEL FILE")
    logger.info("=" * 80)
    
    try:
        rectangles, door_params_list = process_excel(excel_file, FIXED_PARAMS)
        logger.info(f"Successfully extracted {len(rectangles)} rectangles from Excel")
        
        # Log statistics about rectangle sizes
        if rectangles:
            widths = [r[0] for r in rectangles]
            heights = [r[1] for r in rectangles]
            logger.info(f"Rectangle width range: {min(widths):.1f} - {max(widths):.1f}mm")
            logger.info(f"Rectangle height range: {min(heights):.1f} - {max(heights):.1f}mm")
            logger.info(f"Average dimensions: {sum(widths)/len(widths):.1f} x {sum(heights)/len(heights):.1f}mm")
        
    except Exception as e:
        logger.error(f"Failed to process Excel: {e}", exc_info=True)
        return 1
    
    # Test packing with standard sheet sizes
    logger.info("\n" + "=" * 80)
    logger.info("TESTING PACKING")
    logger.info("=" * 80)
    
    SHEET_WIDTH = 1250
    SHEET_HEIGHT = 2500
    
    try:
        bins = pack_rectangles(rectangles, sheet_width=SHEET_WIDTH, sheet_height=SHEET_HEIGHT)
        
        logger.info("\n" + "=" * 80)
        logger.info("FINAL SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total rectangles: {len(rectangles)}")
        logger.info(f"Total bins created: {len(bins)}")
        logger.info(f"Sheet size: {SHEET_WIDTH}x{SHEET_HEIGHT}mm")
        
        # Calculate efficiency
        total_rect_area = sum(r[0] * r[1] for r in rectangles)
        sheet_area = SHEET_WIDTH * SHEET_HEIGHT
        total_sheet_area = sheet_area * len(bins)
        efficiency = (total_rect_area / total_sheet_area * 100) if total_sheet_area > 0 else 0
        
        logger.info(f"Total rectangle area: {total_rect_area:,.0f} mm²")
        logger.info(f"Total sheet area used: {total_sheet_area:,.0f} mm²")
        logger.info(f"Packing efficiency: {efficiency:.2f}%")
        
        # Detail per bin
        for i, bin_data in enumerate(bins):
            placements = bin_data.get("placements", [])
            bin_area = sum(p["width"] * p["height"] for p in placements)
            bin_efficiency = (bin_area / sheet_area * 100) if sheet_area > 0 else 0
            logger.info(f"  Bin {i}: {len(placements)} rectangles, {bin_efficiency:.2f}% utilized")
        
        if len(bins) > 30:
            logger.warning("\n" + "!" * 80)
            logger.warning("WARNING: HIGH BIN COUNT DETECTED!")
            logger.warning(f"Expected ~20-25 bins for typical workload, got {len(bins)} bins")
            logger.warning("This suggests rectpack may be using inefficient packing algorithm")
            logger.warning("!" * 80)
        
        logger.info("\nDebug log saved to: packing_debug.log")
        return 0
        
    except Exception as e:
        logger.error(f"Packing failed: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(main())
