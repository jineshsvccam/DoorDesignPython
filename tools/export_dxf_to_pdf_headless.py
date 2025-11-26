import sys
import os
from typing import Union, Optional, Callable, cast
import ezdxf
from ezdxf.document import Drawing
from ezdxf.addons.drawing.properties import RenderContext
from ezdxf.addons.drawing.frontend import Frontend
from ezdxf.addons.drawing import layout, config
from ezdxf.addons.drawing.pymupdf import PyMuPdfBackend

# 🔹 --- Fix Font Discovery on EC2 (Linux) ---
if os.name == 'posix':  # Linux/Unix
    # Ensure system fonts are visible
    os.environ.setdefault("FONTCONFIG_PATH", "/etc/fonts")
    os.environ.setdefault("FONTCONFIG_FILE", "/etc/fonts/fonts.conf")

    # Register common fallback fonts manually (PyMuPDF)
    try:
        import fitz  # PyMuPDF
        fitz.TOOLS.set_small_glyph_heights(True)  # Helps render text better
        # Try to register fonts (EC2 usually has these)
        FONT_NAMES = ["DejaVuSans", "LiberationSans-Regular", "Arial", "Helvetica"]
        for fn in FONT_NAMES:
            try:
                fitz.Font(fn)  # register if available
                print(f"Registered font: {fn}")
            except Exception:
                pass
    except ImportError:
        print("PyMuPDF font registration skipped (fitz not available)")

# 📄 Constants: A4 Portrait size in mm
A4_PORTRAIT_MM = (210.0, 297.0)

# Safe ezdxf.readfile alias
_ezdxf_readfile_attr = getattr(ezdxf, "readfile", None)
ezdxf_readfile: Optional[Callable[[Union[str, os.PathLike]], Drawing]] = (
    cast(Callable[[Union[str, os.PathLike]], Drawing], _ezdxf_readfile_attr)
    if callable(_ezdxf_readfile_attr)
    else None
)

def export_dxf_to_pdf_headless(
    dxf_source: Union[str, os.PathLike, Drawing],
    pdf_path: Union[str, os.PathLike],
    margin_mm: float = 8.0,
    skip_problematic: bool = False,  # Now render all text also
):
    """
    DXF ➜ PDF Export using PyMuPDF
    Supports TrueType font rendering properly in EC2.
    """
    doc: Drawing

    # 🔹 Load DXF file
    if isinstance(dxf_source, Drawing):
        doc = dxf_source
    else:
        if not ezdxf_readfile:
            raise RuntimeError("ezdxf.readfile is unavailable in ezdxf version.")
        doc = ezdxf_readfile(str(dxf_source))

    msp = doc.modelspace()

    # 🔹 Fix POINT entities (avoids random crashes)
    try:
        for pt in msp.query("POINT"):
            if pt.dxf.get("pdmode") is None:
                pt.dxf.pdmode = 0
            if pt.dxf.get("pdsize") is None:
                pt.dxf.pdsize = 1.0
    except Exception as e:
        print(f"Warning: POINT sanitization failed. {e}", file=sys.stderr)

    # 🔹 Setup rendering pipeline
    context = RenderContext(doc)
    backend = PyMuPdfBackend()

    cfg = config.Configuration(
        background_policy=config.BackgroundPolicy.WHITE,
        lineweight_scaling=1.0)
       
    frontend = Frontend(context, backend, config=cfg)

    try:
        backend.set_background("#FFFFFF")
    except Exception:
        pass

    # 🔹 Draw all entities (include text, MTEXT, DIMENSION)
    frontend.draw_layout(msp)

    # 🔹 PDF Page Setup
    mm_w, mm_h = A4_PORTRAIT_MM
    page = layout.Page(
        mm_w, mm_h,
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
        try:
            export_dxf_to_pdf_headless(
                dxf_source=input_dxf_file,
                pdf_path=output_pdf_file,
                margin_mm=10.0
            )
        except Exception as e:
            print(f"\n❌ DXF processing error: {e}")
            sys.exit(1)
    else:
        print(f"⚠ DXF file '{input_dxf_file}' not found.")
        sys.exit(1)
