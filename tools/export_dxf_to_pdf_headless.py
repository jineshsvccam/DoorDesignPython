import sys
import os
from typing import Union, Optional, Callable, cast
import ezdxf
from ezdxf.document import Drawing
from ezdxf.addons.drawing.properties import RenderContext
from ezdxf.addons.drawing.frontend import Frontend
from ezdxf.addons.drawing import layout, config
from ezdxf.addons.drawing.pymupdf import PyMuPdfBackend

# --- Constants ---

# Define a standard page size (A4 portrait) in millimeters
A4_PORTRAIT_MM = (210.0, 297.0)

# Provide a typed alias for ezdxf.readfile using getattr as a safe fallback
_ezdxf_readfile_attr = getattr(ezdxf, "readfile", None)
ezdxf_readfile: Optional[Callable[[str | os.PathLike], Drawing]] = (
    cast(Callable[[str | os.PathLike], Drawing], _ezdxf_readfile_attr)
    if callable(_ezdxf_readfile_attr)
    else None
)

# --- Main Function ---

def export_dxf_to_pdf_headless(
    dxf_source: Union[str, os.PathLike, Drawing],
    pdf_path: str | os.PathLike,
    margin_mm: float = 5.0,
    skip_problematic: bool = True,
):
    """
    Simple DXF -> PDF exporter using PyMuPDF backend.

    This implementation accepts either an ezdxf Drawing object or a path to a DXF file.

    Args:
        dxf_source: Path to the DXF file or an existing ezdxf Drawing object.
        pdf_path: The path where the output PDF should be saved.
        margin_mm: Margins in millimeters for the PDF page.
        skip_problematic: If True, filters out known problematic entities (POINT, TEXT, MTEXT)
                          during rendering to prevent potential crashes in older ezdxf versions.
    """
    doc: Drawing

    # 1. Load the DXF document
    if isinstance(dxf_source, Drawing):
        doc = dxf_source
    else:
        if not ezdxf_readfile:
             raise RuntimeError("ezdxf.readfile function is not available in the installed ezdxf version.")
        
        doc = ezdxf_readfile(str(dxf_source))

    msp = doc.modelspace()

    # 2. Sanitize POINT entities using the widely compatible .query() method
    try:
        for pt in msp.query("POINT"):
            if pt.dxf.get("pdmode") is None:
                pt.dxf.pdmode = 0
            if pt.dxf.get("pdsize") is None:
                pt.dxf.pdsize = 1.0
    except Exception as e:
        print(f"Warning: Failed to sanitize POINT entities. Continuing anyway. Error: {e}", file=sys.stderr)

    # 3. Setup renderer pipeline
    context = RenderContext(doc)
    backend = PyMuPdfBackend()
    
    # Configure frontend with a white background policy
    cfg = config.Configuration(background_policy=config.BackgroundPolicy.WHITE)
    frontend = Frontend(context, backend, config=cfg)

    # Ensure backend uses white background explicitly if possible
    try:
        backend.set_background("#FFFFFF")
    except Exception:
        pass

    # 4. Draw modelspace, optionally skipping problematic entities
    if skip_problematic:
        def _no_problematic(entity):
            """Filter function to skip problematic entity types."""
            try:
                return entity.dxftype() not in ("POINT", "TEXT", "MTEXT")
            except Exception:
                return False

        try:
            frontend.draw_layout(msp, filter_func=_no_problematic)
        except TypeError:
            print("Info: ezdxf version does not support filter_func; drawing without filtering.", file=sys.stderr)
            frontend.draw_layout(msp)
    else:
        frontend.draw_layout(msp)

    # 5. Finalize the PDF export with requested parameters
    mm_w, mm_h = A4_PORTRAIT_MM
    page = layout.Page(mm_w, mm_h, layout.Units.mm, margins=layout.Margins.all(margin_mm))

    pdf_bytes = backend.get_pdf_bytes(page)
    
    with open(pdf_path, "wb") as fp:
        fp.write(pdf_bytes)

    print(f"Exported DXF to PDF: {pdf_path}")

# --- Example Usage (Main Method Updated) ---
if __name__ == "__main__":
    # Define the input and output file names relative to the script location
    input_dxf_file = "door_F14P2.dxf"
    output_pdf_file = "door_F14P2.pdf"
    
    # Check if the specific DXF file exists before trying to process it
    if os.path.exists(input_dxf_file):
        print(f"Attempting to process {input_dxf_file}...")
        try:
            # Call the main function with the specified file names
            export_dxf_to_pdf_headless(
                dxf_source=input_dxf_file,
                pdf_path=output_pdf_file,
                margin_mm=10.0 # Example margin setting
            )
        except Exception as e:
            print(f"\nAn error occurred during DXF processing: {e}")
            sys.exit(1)
    else:
        print(f"Error: The file '{input_dxf_file}' was not found in the current directory.")
        print("Please ensure the file is present or provide correct paths via command line arguments.")
        print("Usage (if you prefer command line args): python script_name.py input.dxf output.pdf")
        sys.exit(1)
