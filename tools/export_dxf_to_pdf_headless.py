import sys
import os
from typing import Union, Optional, Callable, cast
import ezdxf
from ezdxf.addons.drawing import layout, config
from ezdxf.document import Drawing
from ezdxf.addons.drawing.properties import RenderContext
from ezdxf.addons.drawing.frontend import Frontend
from ezdxf.addons.drawing.pymupdf import PyMuPdfBackend
import fitz # Import fitz directly for clarity

# 🔹 Explicit Font Embedding (Works on EC2)
FONT_PATHS = [
    "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

# Global variable to store the found font path for later use in export function
FOUND_FONT_PATH: Optional[str] = None

def register_fallback_font():
    """Ensure PyMuPDF has a valid TrueType fallback font and captures the path."""
    global FOUND_FONT_PATH
    try:
        fitz.TOOLS.set_small_glyph_heights(True)

        for path in FONT_PATHS:
            if os.path.exists(path):
                fitz.Font(fontfile=path)
                FOUND_FONT_PATH = path
                print(f"✔ Registered fallback and found font path: {path}")
                return
        print("⚠ No fallback font file found. Text may render as boxes.")
    except ImportError:
        print("⚠ PyMuPDF (fitz) not available – font registration skipped.")

# Register font at startup (EC2 compatible)
register_fallback_font()

# 📄 A4 Portrait size in mm
A4_PORTRAIT_MM = (210.0, 297.0)
A4_WIDTH_MM, A4_HEIGHT_MM = A4_PORTRAIT_MM # Unpack the tuple for clarity

# Safe readfile detection
ezdxf_readfile: Optional[Callable] = (
    cast(Callable, getattr(ezdxf, "readfile", None))
    if callable(getattr(ezdxf, "readfile", None)) else None
)

def export_dxf_to_pdf_headless(
    dxf_source: Union[str, os.PathLike, Drawing],
    pdf_path: Union[str, os.PathLike],
    margin_mm: float = 8.0,
):
    """DXF ➜ PDF Export using PyMuPDF with TrueType fonts."""
    if isinstance(dxf_source, Drawing):
        doc = dxf_source
    else:
        if not ezdxf_readfile:
            raise RuntimeError("ezdxf.readfile unavailable.")
        doc = ezdxf_readfile(str(dxf_source))

    msp = doc.modelspace()

    # 🔹 Fix POINT entities (prevent small dot size issues)
    for pt in msp.query("POINT"):
        pt.dxf.pdmode = pt.dxf.get("pdmode", 0)
        pt.dxf.pdsize = pt.dxf.get("pdsize", 1.0)

    # 👇 FIX 1 (Font Management): Force access to the internal font map via sys.modules
    if FOUND_FONT_PATH:
        print(f"Configuring internal font map for 'DejaVuSans' via sys.modules access...")
        try:
            # Access the internal font mapping dictionary directly
            # This is a low-level hack to bypass Pylance strictness
            sys.modules["ezdxf.addons.drawing.setup_fonts"].FONT_MAP["DejaVuSans"] = FOUND_FONT_PATH
        except KeyError:
            print("⚠ Failed to access internal ezdxf font map via sys.modules. Check ezdxf installation.")
    else:
        print("⚠ Could not find a suitable font path to configure!")

    # 🔹 Render Setup
    context = RenderContext(doc) 
    backend = PyMuPdfBackend()
    cfg = config.Configuration(
        background_policy=config.BackgroundPolicy.WHITE,
        lineweight_scaling=1.0
    )
    frontend = Frontend(context, backend, config=cfg)
    backend.set_background("#FFFFFF")

    # 👇 FIX 2: Normalize all text styles to use the registered logical font name
    for style in doc.styles:
        if style.dxf.font != "DejaVuSans":
            style.dxf.font = "DejaVuSans"
   
    frontend.draw_layout(msp)

    # 🔹 PDF Page Setup
    page = layout.Page(
        A4_WIDTH_MM, 
        A4_HEIGHT_MM,
        layout.Units.mm,
        margins=layout.Margins.all(margin_mm)
    )

    pdf_bytes = backend.get_pdf_bytes(page)

    with open(pdf_path, "wb") as fp:
        fp.write(pdf_bytes)

    print(f"🎯 Exported DXF to PDF successfully ➜ {pdf_path}")

# 🚀 Example Usage
if __name__ == "__main__":
    input_dxf_file = "door_F14P2.dxf"
    output_pdf_file = "door_F14P2.pdf"

    if os.path.exists(input_dxf_file):
        print(f"Processing: {input_dxf_file}...")
        export_dxf_to_pdf_headless(input_dxf_file, output_pdf_file, margin_mm=10.0)
    else:
        print(f"⚠ DXF file '{input_dxf_file}' not found.")
        sys.exit(1)
