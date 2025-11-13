"""
DXF → PDF converter using ezdxf PyQt backend (fully centered + scaled)
---------------------------------------------------------------------
Usage:
    python export_dxf_to_pdf.py input.dxf output.pdf
"""

import sys
import os
import importlib
import argparse
import ezdxf
from ezdxf.addons.drawing.properties import RenderContext
from ezdxf.addons.drawing.frontend import Frontend


# --- Try to import PyQt backend ---
# NOTE: Backend detection is delayed until export_dxf_to_pdf() is called so
# that importing this module from other scripts does not execute CLI logic
# or exit the process. If a caller calls export_dxf_to_pdf() and the
# PyQt backend is not available, a RuntimeError will be raised which the
# caller can catch and handle (or the CLI will catch and exit).


def export_dxf_to_pdf(
    dxf_source,
    pdf_path: str,
    dpi: int = 300,
    margin_mm: float = 5.0,
    debug: bool = False,
    bg_color: str = "white",
):
    """Render the DXF modelspace to a properly scaled, centered PDF."""

    # --- Import Qt modules dynamically ---
    qc = importlib.import_module("PyQt5.QtCore")
    qg = importlib.import_module("PyQt5.QtGui")
    qw = importlib.import_module("PyQt5.QtWidgets")

    # --- Try to import ezdxf PyQt backend lazily ---
    PyQtBackend = None
    for candidate in ("ezdxf.addons.drawing.pyqt", "ezdxf.addons.drawing.qt"):
        try:
            m = importlib.import_module(candidate)
            PyQtBackend = getattr(m, "PyQtBackend", None) or getattr(m, "QtBackend", None)
            if PyQtBackend:
                break
        except Exception:
            PyQtBackend = None

    if PyQtBackend is None:
        # Caller should handle this error; raise instead of sys.exit so
        # importing this module remains side-effect free.
        raise RuntimeError("PyQt backend not found. Please install PyQt5 or PySide6.")

    # --- Init QApplication ---
    app = qw.QApplication.instance() or qw.QApplication(sys.argv)

    # --- Load DXF (accept either a path or an ezdxf Drawing) ---
    if hasattr(dxf_source, "modelspace"):
        # already a Drawing
        doc = dxf_source
    else:
        # assume a file path
        doc = ezdxf.readfile(dxf_source)  # type: ignore[attr-defined]
    ctx = RenderContext(doc)
    msp = doc.modelspace()

    # --- Setup scene ---
    scene = qw.QGraphicsScene()
    # PyQtBackend is determined earlier; assert so static analyzers know it's present
    assert PyQtBackend is not None, "PyQt backend must be available"
    backend = PyQtBackend()
    backend.set_scene(scene)
    Frontend(ctx, backend).draw_layout(msp, finalize=True)

    # --- Compute full bounding rect ---
    items_rect = scene.itemsBoundingRect()
    if items_rect.isNull() or items_rect.width() == 0 or items_rect.height() == 0:
        raise RuntimeError("No entities found in DXF modelspace.")

    # --- Normalize to origin (fixes bottom-left cropping issue) ---
    normalized_rect = qc.QRectF(0, 0, items_rect.width(), items_rect.height())

    # --- Choose page orientation automatically ---
    mm_w, mm_h = (210.0, 297.0)
    if items_rect.width() > items_rect.height():
        mm_w, mm_h = (297.0, 210.0)

    px_w = int((mm_w / 25.4) * dpi)
    px_h = int((mm_h / 25.4) * dpi)
    margin_px = int((margin_mm / 25.4) * dpi)

    usable_w = px_w - 2 * margin_px
    usable_h = px_h - 2 * margin_px

    # --- Compute uniform scale and offset ---
    scale = min(usable_w / normalized_rect.width(), usable_h / normalized_rect.height())
    offset_x = margin_px + (usable_w - normalized_rect.width() * scale) / 2
    offset_y = margin_px + (usable_h - normalized_rect.height() * scale) / 2

    # --- Render to QImage (background color) ---
    image = qg.QImage(px_w, px_h, qg.QImage.Format_ARGB32)
    # Accept color names or hex strings like "#ffffff"
    image.fill(qg.QColor(bg_color))

    painter = qg.QPainter(image)
    try:
        # Render the scene into a target rectangle on the image while
        # preserving uniform scale and centering. Compute the target
        # size based on the uniform scale already calculated above.
        target_w = normalized_rect.width() * scale
        target_h = normalized_rect.height() * scale
        target_x = offset_x + (usable_w - target_w) / 2
        target_y = offset_y + (usable_h - target_h) / 2

        # The QImage coordinate system has origin at top-left (y down).
        # DXF coordinates are typically y-up and the scene was created
        # using those coordinates. To render upright we flip the painter
        # vertically, then adjust the target Y so the mapped region
        # lands in the correct place.
        painter.translate(0, px_h)
        painter.scale(1.0, -1.0)

        # After flipping, the target y must be measured from the bottom
        # of the image: flipped_y = image_height - (target_y + target_h)
        flipped_target_y = px_h - (target_y + target_h)
        target_rect = qc.QRectF(target_x, flipped_target_y, target_w, target_h)

        # Render only the items bounding rect (source) into the target rect
        scene.render(painter, target_rect, items_rect)
    finally:
        painter.end()

    # --- Optional debug output ---
    if debug:
        dbg_path = pdf_path + ".debug.png"
        image.save(dbg_path)
        print(f"🧩 Debug image saved: {dbg_path}")
        print(f"Scene rect: {items_rect}, scale={scale}")

    # --- Write PDF ---
    writer = qg.QPdfWriter(str(pdf_path))
    writer.setResolution(dpi)
    writer.setPageSizeMM(qc.QSizeF(mm_w, mm_h))

    pdf_painter = qg.QPainter(writer)
    pdf_painter.drawImage(0, 0, image)
    pdf_painter.end()

    print(f"✅ PDF created: {pdf_path}")


# ---------------- MAIN ---------------- #
def main(argv=None):
    parser = argparse.ArgumentParser(description="Convert DXF to PDF (auto-fit to page)")
    parser.add_argument("input", help="Input DXF file path")
    parser.add_argument("output", help="Output PDF file path")
    parser.add_argument("--dpi", type=int, default=300, help="Resolution in DPI")
    parser.add_argument("--margin", type=float, default=5.0, help="Page margin (mm)")
    parser.add_argument("--debug", action="store_true", help="Save debug image (.png)")
    parser.add_argument("--bg", type=str, default="white", help="Background color name or hex (e.g. '#ffffff')")
    args = parser.parse_args(argv)

    if not os.path.exists(args.input):
        print(f"❌ DXF file not found: {args.input}")
        sys.exit(2)

    try:
        export_dxf_to_pdf(
            args.input,
            args.output,
            dpi=args.dpi,
            margin_mm=args.margin,
            debug=args.debug,
            bg_color=args.bg,
        )
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(3)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
