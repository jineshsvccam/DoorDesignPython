from typing import Optional
from ezdxf.document import Drawing


class DoorDrawingPDF:
    """Utility class to export DXF drawings to PDF using ezdxf's Matplotlib backend."""

    @staticmethod
    def export_to_pdf(doc: Drawing, pdf_file_name: str) -> None:
        """
        Export the current DXF Drawing (doc) to a PDF using ezdxf's Matplotlib backend.
        If matplotlib or the backends are not available, this will print an error.
        """
        try:
            # RenderContext is exported from ezdxf.addons.drawing.properties
            # (Pylance recommends importing it from there to avoid private import warnings).
            from ezdxf.addons.drawing.properties import RenderContext
            from ezdxf.addons.drawing.frontend import Frontend
            from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
            import matplotlib.pyplot as plt

            # Use modelspace as the drawing source
            msp = doc.modelspace()
            ctx = RenderContext(doc)

            # Create a matplotlib figure with tight layout
            fig = plt.figure(figsize=(8, 8))
            # use a tuple for the rect to satisfy type checkers (tuple[float, ...])
            ax = fig.add_axes((0.0, 0.0, 1.0, 1.0))
            out = MatplotlibBackend(ax)

            # Render the DXF into the Matplotlib canvas
            Frontend(ctx, out).draw_layout(msp, finalize=True)

            # Save as PDF
            fig.savefig(pdf_file_name, bbox_inches="tight", pad_inches=0)
            plt.close(fig)

            print(f"✅ PDF file '{pdf_file_name}' created successfully.")
        except Exception as e:
            print(f"❌ PDF export failed: {e}")
