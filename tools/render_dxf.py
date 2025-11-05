import sys
import os
import matplotlib.pyplot as plt

def render_dxf(dxf_path: str, out_png: str):
    try:
        import ezdxf
        # RenderContext is defined in the properties submodule; importing
        # from the top-level drawing package may trigger Pylance diagnostics.
        from ezdxf.addons.drawing.properties import RenderContext
        from ezdxf.addons.drawing.frontend import Frontend
        from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
        # Some linters/Pylance prefer explicit imports for commonly-used helpers
        from ezdxf.filemanagement import readfile
    except Exception as e:
        print(f"Missing dependency to render DXF: {e}")
        raise

    # use the explicit readfile import to satisfy static analysis tools
    doc = readfile(dxf_path)
    msp = doc.modelspace()

    fig = plt.figure(figsize=(6, 10), dpi=150)
    ax = fig.add_subplot(1, 1, 1)
    ax.set_facecolor("white")

    ctx = RenderContext(doc)
    out = MatplotlibBackend(ax)
    try:
        Frontend(ctx, out).draw_layout(msp, finalize=True)
    except Exception as e:
        # Fallback: some DXF text entities may have missing insertion points
        # which cause the renderer to fail. Retry while skipping TEXT/MTEXT
        # entities to produce a robust visual preview.
        def _no_text(entity):
            try:
                return entity.dxftype() not in ("TEXT", "MTEXT")
            except Exception:
                return True

        Frontend(ctx, out).draw_layout(msp, filter_func=_no_text, finalize=True)

    # Try to autoscale and save
    ax.relim()
    ax.autoscale_view()
    ax.set_aspect('equal')
    # Invert Y to match typical CAD coordinate orientation if needed
    ax.invert_yaxis()

    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    fig.savefig(out_png, bbox_inches='tight')
    plt.close(fig)
    print(f"Rendered PNG saved to: {out_png}")


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python tools/render_dxf.py <dxf_path> <out_png>")
        sys.exit(2)
    dxf_path = sys.argv[1]
    out_png = sys.argv[2]
    render_dxf(dxf_path, out_png)
