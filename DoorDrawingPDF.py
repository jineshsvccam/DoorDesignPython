from typing import Any, cast
from ezdxf.document import Drawing

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
            import matplotlib.pyplot as plt

            msp = cast(Any, doc.modelspace())
            ctx = RenderContext(doc)

            # --- A4 Page ---
            A4_WIDTH_INCH = 8.27
            A4_HEIGHT_INCH = 11.69

            fig, ax = plt.subplots(figsize=(A4_WIDTH_INCH, A4_HEIGHT_INCH), facecolor="white")
            ax.set_facecolor("white")
            ax.axis("off")
            ax.set_aspect("equal")

            # --- Render ---
            out = MatplotlibBackend(ax)
            Frontend(ctx, out).draw_layout(msp, finalize=True)

            # --- Fit entire drawing properly ---
            try:
                # get extents from entities directly
                extents = msp.bbox()
                if getattr(extents, "has_data", False):
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

            # --- Enforce black lines ---
            for line in ax.get_lines():
                line.set_color("black")
                line.set_linewidth(0.8)

            # --- Save ---
            fig.savefig(
                pdf_file_name,
                dpi=600,
                bbox_inches="tight",
                pad_inches=0.05,
                facecolor="white"
            )
            plt.close(fig)

            print(f"✅ PDF exported successfully: {pdf_file_name}")

        except Exception as e:
            print(f"❌ PDF export failed: {e}")
