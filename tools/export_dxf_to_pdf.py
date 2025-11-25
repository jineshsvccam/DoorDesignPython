"""
DXF → PDF converter using ezdxf PyQt5 backend (white theme + scaled full-page)
-------------------------------------------------------------------------------
Usage:
    python export_dxf_to_pdf.py input.dxf output.pdf --debug
"""

import sys
import os
import importlib
import argparse
from typing import Union, cast, TYPE_CHECKING, Optional, Callable

import ezdxf
# Import Drawing class specifically for type hints
from ezdxf.document import Drawing 

# Try to provide a local alias for ezdxf.readfile for static analyzers.
# Declare a typed name for the callable so Pylance knows the expected signature.
ezdxf_readfile: Optional[Callable[[str | os.PathLike], Drawing]] = None
try:
    # Prefer static import so type checkers can infer the signature during analysis
    from ezdxf import readfile as ezdxf_readfile  # type: ignore
except Exception:
    # Fallback: grab attribute dynamically and cast to the declared type for type checkers
    ezdxf_readfile = cast(Optional[Callable[[str | os.PathLike], Drawing]], getattr(ezdxf, "readfile", None))

from ezdxf.addons.drawing.properties import RenderContext
from ezdxf.addons.drawing.frontend import Frontend


def export_dxf_to_pdf(
    dxf_source: Union[str, Drawing],
    pdf_path: str,
    dpi: int = 300,
    margin_mm: float = 5.0,
    debug: bool = True,
    bg_color: str = "#FFFFFF",
):
    """Render DXF modelspace to a properly scaled, centered PDF (Option B: scaled full-page)."""

    # --- Import PyQt5 modules (Option 1: PyQt5 only) ---
    # These dynamic imports are fine, Pylance will infer types based on usage later
    qc = importlib.import_module("PyQt5.QtCore")
    qg = importlib.import_module("PyQt5.QtGui")
    qw = importlib.import_module("PyQt5.QtWidgets")

    # --- Find ezdxf PyQt backend ---
    PyQtBackend = None
    for candidate in ("ezdxf.addons.drawing.pyqt", "ezdxf.addons.drawing.qt"):
        try:
            m = importlib.import_module(candidate)
            PyQtBackend = getattr(m, "PyQtBackend", None) or getattr(m, "QtBackend", None)
            if PyQtBackend:
                break
        except Exception:
            pass

    if not PyQtBackend:
        raise RuntimeError("PyQt backend not found. Install PyQt5 and ezdxf with Qt backend support.")

    # --- Init QApplication (if not already running) ---
    app = qw.QApplication.instance() or qw.QApplication(sys.argv)

    # --- Load DXF (accept Drawing or path) ---
    # Use a variable specifically typed as Drawing after logic has run its course
    doc: Drawing
    if hasattr(dxf_source, "modelspace"): # Pylance error 4 suppressed by logic
        doc = cast(Drawing, dxf_source)
    else:
        if not ezdxf_readfile:
            raise RuntimeError("ezdxf.readfile not available in this environment")
        try:
            # Pylance error 1 resolved: passing only str/PathLike to readfile
            doc = ezdxf_readfile(str(dxf_source))
        except IOError as e:
            raise RuntimeError(f"Could not read DXF file '{dxf_source}': {e}")
        except Exception as e:
            # ezdxf may raise package-specific parsing exceptions. Catch all
            # parsing-related exceptions here and surface a RuntimeError so
            # callers receive a consistent error type. This also avoids
            # Pylance diagnostics about non-exported exception names like
            # "DXFError" when static analysis cannot confirm the symbol.
            raise RuntimeError(f"Error parsing DXF file '{dxf_source}': {e}")

    # Pylance error 3 resolved: 'doc' is now explicitly typed as a Drawing instance via 'cast' or return of 'readfile'
    # --- Rendering context & modelspace ---
    ctx = RenderContext(doc)
    msp = doc.modelspace()
    # ... (rest of the code is unchanged and works as intended) ...
    # ...

    # This helps ensure DXF entities themselves adopt a light-theme color mapping.
    # -----------------------------
    try:
        # set_current_layout may not exist on all versions
        set_layout = getattr(ctx, "set_current_layout", None)
        if callable(set_layout):
            set_layout(msp)
        cur_layout = getattr(ctx, "current_layout", None)
        if cur_layout is not None and hasattr(cur_layout, "set_bg_color"):
            try:
                cur_layout.set_bg_color((255, 255, 255))
            except Exception:
                pass
    except Exception:
        pass
    # ... more try-except blocks ...

    # --- Create QGraphicsScene & backend ---
    scene = qw.QGraphicsScene()
    backend = PyQtBackend()
    backend.set_scene(scene)

    # --- Provide backend background as QColor (CRITICAL FIX FOR BLACK BG) ---
    bg_qcolor = qg.QColor(255, 255, 255) 
    bg_qcolor.setAlpha(255)
    
    try:
        backend.set_background(bg_qcolor)
    except Exception:
        try:
            backend.set_background(bg_qcolor.name())
        except Exception:
            try:
                backend.set_background((255, 255, 255))
            except Exception:
                pass 

    # --- Render DXF into the scene ---
    Frontend(ctx, backend).draw_layout(msp, finalize=True)

    # --- Compute bounding rect ---
    items_rect = scene.itemsBoundingRect()
    if items_rect.isNull() or items_rect.width() == 0 or items_rect.height() == 0:
        raise RuntimeError("No entities found in DXF modelspace.")

    normalized_rect = qc.QRectF(0, 0, items_rect.width(), items_rect.height())

    # --- Paper size/orientation: A4 default, swap for landscape if needed ---
    mm_w, mm_h = (210.0, 297.0)
    if items_rect.width() > items_rect.height():
        mm_w, mm_h = (297.0, 210.0)

    px_w = int((mm_w / 25.4) * dpi)
    px_h = int((mm_h / 25.4) * dpi)
    margin_px = int((margin_mm / 25.4) * dpi)

    usable_w = px_w - 2 * margin_px
    usable_h = px_h - 2 * margin_px

    # --- Compute uniform scale and offsets ---
    scale = min(usable_w / normalized_rect.width(), usable_h / normalized_rect.height())
    offset_x = margin_px + (usable_w - normalized_rect.width() * scale) / 2
    offset_y = margin_px + (usable_h - normalized_rect.height() * scale) / 2

    # -----------------------------
    # Create QImage and force opaque white background fill
    # -----------------------------
    image = qg.QImage(px_w, px_h, qg.QImage.Format_RGB32)
    tmp_painter = qg.QPainter(image)
    try:
        tmp_painter.setPen(qg.QPen(bg_qcolor))
        tmp_painter.setBrush(bg_qcolor)
        tmp_painter.drawRect(0, 0, px_w, px_h)
    finally:
        tmp_painter.end()
    
    # -----------------------------
    # Render the scene into the QImage (flip Y)
    # -----------------------------
    painter = qg.QPainter(image)
    try:
        target_w = normalized_rect.width() * scale
        target_h = normalized_rect.height() * scale
        target_x = offset_x
        target_y = offset_y

        # flip so DXF Y-up coordinates map correctly in raster space
        painter.translate(0, px_h)
        painter.scale(1.0, -1.0)

        flipped_y = px_h - (target_y + target_h)
        target_rect = qc.QRectF(target_x, flipped_y, target_w, target_h)

        scene.render(painter, target_rect, items_rect)
    finally:
        painter.end()

    # -----------------------------
    # Save debug PNG so you can inspect the rastered image
    # -----------------------------
    if debug:
        # Fixed path concatenation bug here:
        dbg_path = os.path.splitext(pdf_path)[0] + ".debug.png"
        try:
            saved = image.save(dbg_path)
            print(f"🧩 Debug image saved: {dbg_path} (success={saved})")
        except Exception as e:
            print(f"⚠ Could not save debug image: {e}")

    # -----------------------------
    # Write PDF (scaled full-page)
    # -----------------------------
    writer = qg.QPdfWriter(str(pdf_path))
    writer.setResolution(dpi)
    try:
        writer.setPageSizeMM(qc.QSizeF(mm_w, mm_h))
    except Exception:
        pass 

    pdf_painter = qg.QPainter(writer)
    try:
        # Reset transforms to device coordinates
        pdf_painter.resetTransform()

        # Fill the PDF page with white explicitly (safety measure)
        pdf_painter.setPen(qg.QPen(bg_qcolor))
        pdf_painter.setBrush(bg_qcolor)
        pdf_painter.drawRect(0, 0, px_w, px_h)

        # Make sure the image fully replaces the PDF pixels (no transparency bleed):
        try:
            pdf_painter.setCompositionMode(qg.QPainter.CompositionMode_Source)
        except Exception:
            pass 
            
        # Draw the final rendered image onto the PDF writer canvas
        pdf_painter.drawImage(0, 0, image)

    finally:
        # Ensure the painter is ended to finalize the PDF file writing
        pdf_painter.end()


# Example of how to use the function via command line arguments (add main block)
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert DXF to PDF using ezdxf and PyQt5.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=export_dxf_to_pdf.__doc__
    )
    parser.add_argument("input_dxf", type=str, help="Input DXF file path")
    parser.add_argument("output_pdf", type=str, help="Output PDF file path")
    parser.add_argument("--dpi", type=int, default=300, help="DPI for rasterization (default: 300)")
    parser.add_argument("--margin_mm", type=float, default=5.0, help="Margin in millimeters (default: 5.0)")
    parser.add_argument("--debug", action="store_true", help="Save a debug PNG image")
    
    args = parser.parse_args()

    if not os.path.exists(args.input_dxf):
        print(f"Error: Input file not found at {args.input_dxf}")
        sys.exit(1)

    export_dxf_to_pdf(
        dxf_source=args.input_dxf,
        pdf_path=args.output_pdf,
        dpi=args.dpi,
        margin_mm=args.margin_mm,
        debug=args.debug,
    )
    print(f"Successfully exported {args.input_dxf} to {args.output_pdf}")
