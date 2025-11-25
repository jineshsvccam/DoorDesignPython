from typing import Any, cast
from ezdxf.document import Drawing
import matplotlib.pyplot as plt

class DoorDrawingPDF:
    """Utility class to export DXF drawings to PDF using ezdxf's Matplotlib backend."""

    @staticmethod
    def export_to_pdf(doc: Drawing, pdf_file_name: str) -> None:
        """
        Export DXF to A4-sized PDF with correct scaling and full visibility.
        """
        try:
            from ezdxf.addons.drawing.properties import RenderContext
            from ezdxf.addons.drawing.frontend import Frontend
            from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

            msp = cast(Any, doc.modelspace())
            
            # --- Use the default RenderContext (no config parameter) ---
            ctx = RenderContext(doc) 

            # --- A4 Page ---
            A4_WIDTH_INCH = 8.27
            A4_HEIGHT_INCH = 11.69

            fig, ax = plt.subplots(figsize=(A4_WIDTH_INCH, A4_HEIGHT_INCH), facecolor="white")
            ax.axis("off")
            ax.set_aspect("equal")

            # --- Render ---
            out = MatplotlibBackend(ax)
            Frontend(ctx, out).draw_layout(msp, finalize=True)

            # --- Fit entire drawing properly ---
            try:
                extents = msp.bbox()
                if getattr(extents, "has_data", False) and extents.has_data:
                    xmin, ymin = extents.extmin
                    xmax, ymax = extents.extmax
                    width = xmax - xmin
                    height = ymax - ymin
                    margin_x = width * 0.1
                    margin_y = height * 0.1
                    ax.set_xlim(xmin - margin_x, xmax + margin_x)
                    ax.set_ylim(ymin - margin_y, ymax + margin_y)
                else:
                    ax.relim()
                    ax.autoscale_view()
            except Exception:
                ax.relim()
                ax.autoscale_view()
            
            # --- Manual Color Remapping (Crucial for older versions) ---
            # Iterate over all line objects created by the backend and force them black 
            # so they contrast against the white background.
            for line in ax.get_lines():
                 # Use a visible color like black or a dark gray for all lines
                line.set_color("black") 
                line.set_linewidth(0.8) # Optional: standardize linewidth

            # --- Save ---
            fig.savefig(
                pdf_file_name,
                dpi=600,
                bbox_inches="tight",
                pad_inches=0.05,
                facecolor="white", # Explicitly save figure with white background
                transparent=False,
            )
            plt.close(fig)

            print(f"✅ PDF exported successfully: {pdf_file_name}")

        except ImportError:
             print("❌ Required libraries not installed. Please install matplotlib: `pip install matplotlib`")
        except Exception as e:
            print(f"❌ PDF export failed: {e}")
