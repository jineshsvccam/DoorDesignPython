import sys
import os
from typing import Union, Optional, Callable, cast
import ezdxf
from ezdxf.document import Drawing
from ezdxf.addons.drawing.properties import RenderContext
from ezdxf.addons.drawing.frontend import Frontend
from ezdxf.addons.drawing import layout, config
from ezdxf.addons.drawing.pymupdf import PyMuPdfBackend

# The FONT_PATHS list and the global FOUND_FONT_PATH are no longer used for mapping,
# as we rely on the OS config, but the register function remains for clarity.
FONT_PATHS = [
    "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf",
    # ... other paths are irrelevant now
]

# We no longer need this global variable, rely entirely on the OS.
# FOUND_FONT_PATH: Optional[str] = None 

def register_fallback_font():
    """Rely entirely on system font configuration (fontconfig)."""
    print("Relying on system font configuration (fontconfig) for font resolution.")
    # No fitz imports or font path finding needed here anymore.
    pass

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
    """DXF ➜ PDF Export using PyMuPDF with TrueType fonts via system fallbacks."""
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
   
    # 🔹 Render Setup
    context = RenderContext(doc)
    backend = PyMuPdfBackend()
    cfg = config.Configuration(
        background_policy=config.BackgroundPolicy.WHITE,
        lineweight_scaling=1.0
    )
    frontend = Frontend(context, backend, config=cfg)
    backend.set_background("#FFFFFF")

    # 👇 FONT FIX: Do not manipulate doc.styles or internal font maps here.
    # We let the DXF use its default styles (like "Standard" or "Arial").
    # The OS fontconfig intercepts these names and points to the DejaVuSans .ttf file.
   
    frontend.draw_layout(msp)

    # 🔹 PDF Page Setup (Pylance type errors fixed by unpacking A4_PORTRAIT_MM earlier)
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
