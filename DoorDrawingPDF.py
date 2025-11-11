from typing import Optional, Any, cast
from ezdxf.document import Drawing

class DoorDrawingPDF:
    """Utility class to export DXF drawings to PDF using ezdxf's Matplotlib backend."""

    @staticmethod
    def export_to_pdf(doc: Drawing, pdf_file_name: str) -> None:
        """
        Export the DXF Drawing (doc) to a high-quality A4 PDF
        with a white background and visible black lines for printing.
        """
        try:
            from ezdxf.addons.drawing.properties import RenderContext
            from ezdxf.addons.drawing.frontend import Frontend
            from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
            import matplotlib.pyplot as plt

            # Get modelspace (cast to Any for Pylance/type checkers)
            msp = cast(Any, doc.modelspace())
            ctx = RenderContext(doc)

            # --- A4 Page Setup ---
            A4_WIDTH_INCH = 8.27
            A4_HEIGHT_INCH = 11.69

            # Create a Matplotlib figure with white background
            fig, ax = plt.subplots(figsize=(A4_WIDTH_INCH, A4_HEIGHT_INCH), facecolor="white")
            ax.set_facecolor("white")  # White drawing area
            ax.set_aspect("equal")
            ax.axis("off")  # Hide axes for clean PDF

            # Render DXF content
            out = MatplotlibBackend(ax)
            Frontend(ctx, out).draw_layout(msp, finalize=True)

            # --- Auto-fit to drawing bounding box ---
            if hasattr(msp, "bbox"):
                try:
                    extents = msp.bbox()
                    if getattr(extents, "has_data", False):
                        xmin, ymin, xmax, ymax = tuple(extents.extmin) + tuple(extents.extmax)
                        x_margin = (xmax - xmin) * 0.05
                        y_margin = (ymax - ymin) * 0.05
                        ax.set_xlim(xmin - x_margin, xmax + x_margin)
                        ax.set_ylim(ymin - y_margin, ymax + y_margin)
                    else:
                        ax.relim()
                        ax.autoscale_view()
                except Exception:
                    ax.relim()
                    ax.autoscale_view()
            else:
                ax.relim()
                ax.autoscale_view()

            # --- Improve visibility ---
            for line in ax.get_lines():
                line.set_color("black")
                line.set_linewidth(0.8)

            # --- Save as high-DPI PDF ---
            fig.savefig(
                pdf_file_name,
                bbox_inches="tight",
                pad_inches=0.2,
                dpi=600,  # High DPI for print clarity
                facecolor=fig.get_facecolor(),
            )
            plt.close(fig)

            print(f"✅ High-quality A4 PDF generated successfully: {pdf_file_name}")

        except Exception as e:
            print(f"❌ PDF export failed: {e}")
