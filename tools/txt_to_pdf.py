import fitz
from pathlib import Path

def txt_to_pdf(txt_path, pdf_path, page_size_mm=(297, 420), font_size=12, margin_mm=20):
    """
    Convert a plain text file to a single-page PDF using PyMuPDF.
    Args:
        txt_path: Path to the input text file
        pdf_path: Path to the output PDF file
        page_size_mm: Tuple (width, height) in mm
        font_size: Font size in points
        margin_mm: Margin in mm
    """
    txt_path = Path(txt_path)
    pdf_path = Path(pdf_path)
    if not txt_path.exists():
        raise FileNotFoundError(f"Text file not found: {txt_path}")
    
    # Convert mm to points (1 mm = 2.83465 pt)
    mm_to_pt = 2.83465
    width_pt = page_size_mm[0] * mm_to_pt
    height_pt = page_size_mm[1] * mm_to_pt
    margin_pt = margin_mm * mm_to_pt
    
    # Read text
    with open(txt_path, 'r', encoding='utf-8') as f:
        text = f.read()
    
    # Create PDF
    doc = fitz.open()
    page = doc.new_page(width=width_pt, height=height_pt)
    rect = fitz.Rect(margin_pt, margin_pt, width_pt - margin_pt, height_pt - margin_pt)
    
    # Draw text (auto-wrap)
    page.insert_textbox(rect, text, fontsize=font_size, fontname="helv", align=0)
    doc.save(str(pdf_path))
    doc.close()
