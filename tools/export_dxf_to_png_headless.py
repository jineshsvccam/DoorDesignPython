import sys
import os
from typing import Union, Optional, Callable, cast
import ezdxf
from ezdxf.document import Drawing
from ezdxf.addons.drawing.properties import RenderContext
from ezdxf.addons.drawing.frontend import Frontend
from ezdxf.addons.drawing import layout, config
from ezdxf.addons.drawing.pymupdf import PyMuPdfBackend

# 🛡 Safe ezdxf readfile detection
ezdxf_readfile: Optional[Callable] = (
    cast(Callable, getattr(ezdxf, "readfile", None))
    if callable(getattr(ezdxf, "readfile", None)) else None
)

def export_dxf_to_png_headless(
    dxf_source: Union[str, os.PathLike, Drawing],
    png_path: Union[str, os.PathLike],
    margin_mm: float = 8.0,
    dpi: int = 96,
):
    """
    DXF ➜ PNG Export using PyMuPdfBackend.
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
        width=210.0,
        height=297.0,
        units=layout.Units.mm,
        margins=layout.Margins.all(margin_mm),
    )

    # ✨ Generate PNG bytes
    png_bytes = backend.get_pixmap_bytes(page, fmt="png", dpi=dpi)

    # 💾 Save File
    with open(png_path, "wb") as fp:
        fp.write(png_bytes)

    print(f"🎯 Exported DXF ➜ PNG successfully: {png_path}")

# 🚀 Example (Run directly)
if __name__ == "__main__":
    input_dxf_file = os.path.join("Door TestCases", "DoorGeometry", "Baselines", "Dxf", "SingleNormal.dxf")
    output_png_file = os.path.splitext(input_dxf_file)[0] + ".png"

    if os.path.exists(input_dxf_file):
        print(f"Processing: {input_dxf_file}...")
        export_dxf_to_png_headless(input_dxf_file, output_png_file, margin_mm=10.0, dpi=96)
    else:
        print(f"⚠ DXF file '{input_dxf_file}' not found.")
        sys.exit(1)
