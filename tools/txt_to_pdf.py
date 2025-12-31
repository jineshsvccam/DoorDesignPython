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
    import logging
    txt_path = Path(txt_path)
    pdf_path = Path(pdf_path)
    logger = logging.getLogger("txt_to_pdf")
    logger.info(f"txt_to_pdf: txt_path={txt_path}, pdf_path={pdf_path}, page_size_mm={page_size_mm}, font_size={font_size}, margin_mm={margin_mm}")
    if not txt_path.exists():
        logger.error(f"Text file not found: {txt_path}")
        raise FileNotFoundError(f"Text file not found: {txt_path}")
    # Convert mm to points (1 mm = 2.83465 pt)
    mm_to_pt = 2.83465
    width_pt = page_size_mm[0] * mm_to_pt
    height_pt = page_size_mm[1] * mm_to_pt
    margin_pt = margin_mm * mm_to_pt
    # Read text
    with open(txt_path, 'r', encoding='utf-8') as f:
        text = f.read()
    logger.info(f"txt_to_pdf: Read {len(text)} characters from text file.")
    # Create PDF (multi-page if needed)
    doc = fitz.open()
    remaining_text = text
    page_num = 1
    while True:
        if isinstance(remaining_text, str) and not remaining_text.strip():
            break
        page = doc.new_page(width=width_pt, height=height_pt)
        rect = fitz.Rect(margin_pt, margin_pt, width_pt - margin_pt, height_pt - margin_pt)
        try:
            unused = page.insert_textbox(rect, remaining_text, fontsize=font_size, fontname="courier", align=0)
            logger.info(f"txt_to_pdf: Page {page_num} inserted with 'courier' font. Unused type: {type(unused)}")
        except Exception as e:
            logger.warning(f"txt_to_pdf: Failed to use 'courier' font, falling back to 'helv'. Error: {e}")
            unused = page.insert_textbox(rect, remaining_text, fontsize=font_size, fontname="helv", align=0)
        if isinstance(unused, float):
            # All text fit on this page
            break
        if not isinstance(unused, str) or unused == remaining_text:
            # Nothing fit or unexpected type, avoid infinite loop
            break
        remaining_text = unused
        page_num += 1
    doc.save(str(pdf_path))
    doc.close()
    logger.info(f"txt_to_pdf: PDF saved to {pdf_path}")
