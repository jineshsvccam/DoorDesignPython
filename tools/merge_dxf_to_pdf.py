"""
Tool to convert multiple DXF files to PDFs and merge them into a single PDF.
Uses PyMuPDF backend for both conversion and merging.
"""
import os
import sys
import shutil
import tempfile
from pathlib import Path
from typing import List, Optional, Union

import fitz  # PyMuPDF

# Add parent directory to path for imports when running directly
if __name__ == "__main__":
    script_dir = Path(__file__).parent.parent
    if str(script_dir) not in sys.path:
        sys.path.insert(0, str(script_dir))

from tools.export_dxf_to_pdf_headless import export_dxf_to_pdf_headless


# ============================================================================
# CONSTANTS
# ============================================================================

# Default sheet size in mm
SHEET_WIDTH = 1250
SHEET_HEIGHT = 2500
DEFAULT_SHEET_SIZE_MM = (SHEET_WIDTH, SHEET_HEIGHT)

# A3 Portrait size in mm (alternative)
A3_PORTRAIT_MM = (297.0, 420.0)


# ============================================================================
# CORE FUNCTIONS
# ============================================================================

def convert_dxf_to_pdf(
    dxf_path: Union[str, os.PathLike],
    pdf_path: Union[str, os.PathLike],
    page_size_mm: tuple = DEFAULT_SHEET_SIZE_MM,
    margin_mm: float = 10.0
) -> bool:
    """
    Convert a single DXF file to PDF using specified page size and margin.
    
    Args:
        dxf_path: Path to input DXF file
        pdf_path: Path to output PDF file
        page_size_mm: Tuple of (width, height) in millimeters. Default is 1250x2500mm
        margin_mm: Margin size in millimeters
        
    Returns:
        True if conversion successful, False otherwise
    """
    try:
        export_dxf_to_pdf_headless(dxf_path, pdf_path, margin_mm=margin_mm)
        return True
    except Exception as e:
        print(f"[ERROR] Failed to convert {dxf_path} to PDF: {e}")
        return False


def merge_pdfs_to_single_file(
    pdf_paths: List[Union[str, os.PathLike]],
    output_pdf_path: Union[str, os.PathLike]
) -> bool:
    """
    Merge multiple PDF files into a single PDF document.
    
    Args:
        pdf_paths: List of paths to PDF files to merge
        output_pdf_path: Path to the output merged PDF file
        
    Returns:
        True if merge successful, False otherwise
    """
    if not pdf_paths:
        print("[WARN] No PDF files to merge.")
        return False
    
    merged_pdf = None
    try:
        merged_pdf = fitz.open()
        page_count = 0
        
        for pdf_path in pdf_paths:
            if not os.path.exists(pdf_path):
                print(f"[WARN] PDF file not found, skipping: {pdf_path}")
                continue
                
            try:
                with fitz.open(pdf_path) as pdf_doc:
                    merged_pdf.insert_pdf(pdf_doc)
                    page_count += pdf_doc.page_count
                    print(f"[INFO] Added: {os.path.basename(pdf_path)} ({pdf_doc.page_count} page(s))")
            except Exception as e:
                print(f"[WARN] Failed to add {pdf_path}: {e}")
        
        if page_count == 0:
            print("[ERROR] No pages to save in merged PDF.")
            return False
            
        merged_pdf.save(output_pdf_path)
        print(f"[SUCCESS] Merged PDF created with {page_count} page(s): {output_pdf_path}")
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to merge PDFs: {e}")
        return False
    finally:
        if merged_pdf is not None:
            merged_pdf.close()


def convert_and_merge_dxf_directory(
    dxf_directory: Union[str, os.PathLike],
    output_pdf_path: Union[str, os.PathLike],
    page_size_mm: tuple = DEFAULT_SHEET_SIZE_MM,
    margin_mm: float = 10.0,
    summary_txt_path: Optional[str] = None,
    summary_page_size_mm: tuple = DEFAULT_SHEET_SIZE_MM,
    summary_font_size: int = 12,
    summary_margin_mm: int = 20
) -> Optional[str]:
    """
    Convert all DXF files in a directory to PDFs and merge into a single PDF.
    Individual PDFs are generated in a temporary folder and automatically cleaned up.
    
    Args:
        dxf_directory: Directory containing DXF files
        output_pdf_path: Path to the output merged PDF file
        page_size_mm: Tuple of (width, height) in millimeters. Default is 1250x2500mm
        margin_mm: Margin size in millimeters
        
    Returns:
        Path to merged PDF if successful, None otherwise
    """
    dxf_dir = Path(dxf_directory)
    if not dxf_dir.exists() or not dxf_dir.is_dir():
        print(f"[ERROR] Directory not found: {dxf_directory}")
        return None
    
    # Find all DXF files
    dxf_files = sorted(dxf_dir.glob("*.dxf"))
    temp_dir = Path(tempfile.mkdtemp(prefix="pdf_temp_"))
    print(f"[INFO] Using temporary directory: {temp_dir}")

    try:
        pdf_paths = []
        if dxf_files:
            print(f"[INFO] Found {len(dxf_files)} DXF file(s) to convert")
            # Convert each DXF to PDF in temp directory
            for dxf_file in dxf_files:
                pdf_file = temp_dir / dxf_file.with_suffix('.pdf').name
                print(f"[INFO] Converting {dxf_file.name} to PDF...")
                if convert_dxf_to_pdf(dxf_file, pdf_file, page_size_mm, margin_mm):
                    pdf_paths.append(pdf_file)
                else:
                    print(f"[WARN] Skipping {dxf_file.name} due to conversion failure")
        else:
            print(f"[WARN] No DXF files found in directory: {dxf_directory}")

        # If a summary text file is provided, convert it to PDF and append as last page
        summary_pdf_path = None
        if summary_txt_path and Path(summary_txt_path).exists():
            try:
                from tools.txt_to_pdf import txt_to_pdf
                summary_pdf_path = temp_dir / "bin_utilization_summary.pdf"
                # Use a larger font for better visibility
                txt_to_pdf(summary_txt_path, summary_pdf_path, page_size_mm=summary_page_size_mm, font_size=max(14, summary_font_size), margin_mm=summary_margin_mm)
                pdf_paths.append(summary_pdf_path)
                print(f"[INFO] Added summary PDF as last page: {summary_pdf_path}")
            except Exception as e:
                print(f"[WARN] Could not convert summary txt to PDF: {e}")

        if not pdf_paths:
            print("[WARN] No DXF PDFs or summary PDF to merge. Nothing to do.")
            return None

        # Merge all PDFs
        print(f"[INFO] Merging {len(pdf_paths)} PDF(s) into single file...")
        output_path = Path(output_pdf_path)

        if merge_pdfs_to_single_file(pdf_paths, output_path):
            return str(output_path)
        return None
    finally:
        # Always cleanup temporary directory
        if temp_dir.exists():
            print(f"[INFO] Cleaning up temporary directory: {temp_dir}")
            try:
                shutil.rmtree(temp_dir)
                print("[INFO] Temporary files cleaned up successfully")
            except Exception as e:
                print(f"[WARN] Failed to delete temporary directory: {e}")


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution function for standalone usage."""
    script_dir = Path(__file__).parent.parent
    dxf_directory = script_dir / "outputBulk"
    output_merged_pdf = dxf_directory / "merged_output.pdf"
    
    if not dxf_directory.exists():
        print(f"❌ Directory not found: {dxf_directory}")
        return 1
    
    result = convert_and_merge_dxf_directory(
        dxf_directory=dxf_directory,
        output_pdf_path=output_merged_pdf,
        page_size_mm=DEFAULT_SHEET_SIZE_MM,
        margin_mm=10.0
    )
    
    if result:
        print(f"\n✅ Successfully created merged PDF: {result}")
        return 0
    else:
        print("\n❌ Failed to create merged PDF")
        return 1


if __name__ == "__main__":
    sys.exit(main())
