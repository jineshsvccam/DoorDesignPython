import sys
import os
from typing import Union, Optional, Callable, cast
import ezdxf
from ezdxf.document import Drawing
from ezdxf.addons.drawing.properties import RenderContext
from ezdxf.addons.drawing.frontend import Frontend
from ezdxf.addons.drawing import layout, config
from ezdxf.addons.drawing.pymupdf import PyMuPdfBackend

# Configure fontconfig for Linux systems to find system fonts
if os.name == 'posix':  # Linux/Unix
    if 'FONTCONFIG_PATH' not in os.environ:
        os.environ['FONTCONFIG_PATH'] = '/etc/fonts'
    if 'FONTCONFIG_FILE' not in os.environ:
        os.environ['FONTCONFIG_FILE'] = '/etc/fonts/fonts.conf'

# 📄 A4 Portrait size in mm
A4_PORTRAIT_MM = (210.0, 297.0)
A4_WIDTH_MM, A4_HEIGHT_MM = A4_PORTRAIT_MM

# 🛡 Safe ezdxf readfile detection
ezdxf_readfile: Optional[Callable] = (
    cast(Callable, getattr(ezdxf, "readfile", None))
    if callable(getattr(ezdxf, "readfile", None)) else None
)


def export_dxf_to_pdf_headless(
    dxf_source: Union[str, os.PathLike, Drawing],
    pdf_path: Union[str, os.PathLike],
    margin_mm: float = 8.0,
):
    """
    DXF ➜ PDF Export using PyMuPDF backend.
    Uses system-installed fonts like Arial or Calibri.
    """

    # 🔹 Load DXF
    if isinstance(dxf_source, Drawing):
        doc = dxf_source
    else:
        if not ezdxf_readfile:
            raise RuntimeError("ezdxf.readfile unavailable.")
        doc = ezdxf_readfile(str(dxf_source))

    msp = doc.modelspace()

    # 🔹 Fix POINT entities visibility
    for pt in msp.query("POINT"):
        pt.dxf.pdmode = pt.dxf.get("pdmode", 0)
        pt.dxf.pdsize = pt.dxf.get("pdsize", 1.0)

    # 🔹 Render Setup
    context = RenderContext(doc)
    backend = PyMuPdfBackend()

    cfg = config.Configuration(
        background_policy=config.BackgroundPolicy.WHITE,
        lineweight_scaling=1.0,
        min_lineweight=0.15,
    )

    frontend = Frontend(context, backend, config=cfg)
    backend.set_background("#FFFFFF")  # White background

    frontend.draw_layout(msp)

    # 📄 Page Setup (A4 with margin)
    page = layout.Page(
        width=A4_WIDTH_MM,
        height=A4_HEIGHT_MM,
        units=layout.Units.mm,
        margins=layout.Margins.all(margin_mm),
    )

    # ✨ Generate PDF bytes
    pdf_bytes = backend.get_pdf_bytes(page)

    # 💾 Save File
    with open(pdf_path, "wb") as fp:
        fp.write(pdf_bytes)

    print(f"🎯 Exported DXF ➜ PDF successfully: {pdf_path}")


# 🚀 Example (Run directly)
if __name__ == "__main__":
    input_dxf_file = "door_F14P2.dxf"
    output_pdf_file = "door_F14P2.pdf"

    if os.path.exists(input_dxf_file):
        print(f"Processing: {input_dxf_file}...")
        export_dxf_to_pdf_headless(input_dxf_file, output_pdf_file, margin_mm=10.0)
    else:
        print(f"⚠ DXF file '{input_dxf_file}' not found.")
        sys.exit(1)
