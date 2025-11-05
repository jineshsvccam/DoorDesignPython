"""Simple test to inspect ezdxf linear dimension behavior in this environment.

Saves a small DXF and prints diagnostics: dim type, whether virtual_entities exists,
counts of virtual entities, modelspace counts before/after render.

Run with:
    python test_dim.py

"""

import ezdxf
from ezdxf.filemanagement import new
from typing import cast, Iterable, Any


def main():
    print("ezdxf version:", getattr(ezdxf, "__version__", "unknown"))

    doc = new(dxfversion="R2010")
    msp = doc.modelspace()

    p1 = (0, 0)
    p2 = (200, 0)

    print("Creating linear dimension (horizontal) ...")
    try:
        dim = msp.add_linear_dim(base=(0, 0), p1=p1, p2=p2, angle=0, dimstyle="EZDXF")
    except Exception as e:
        print("add_linear_dim raised:", repr(e))
        return

    print("dim type:", type(dim))
    # Use getattr to access the attribute to satisfy static analyzers (Pylance)
    vf = getattr(dim, "virtual_entities", None)
    print("has virtual_entities (callable):", callable(vf))

    if callable(vf):
        try:
            v = list(cast(Iterable[Any], vf()))
            print("virtual_entities count:", len(v))
            for i, e in enumerate(v[:10]):
                try:
                    print(f"  [{i}] ->", e.dxftype())
                except Exception:
                    print(f"  [{i}] -> <no-dxftype()>")
        except Exception as e:
            print("virtual_entities() raised:", repr(e))

    before = len(list(msp))
    print("modelspace count before render:", before)

    try:
        # set a visible offset and render
        try:
            dim.set_location((0, 10), relative=True)
        except Exception as e:
            print("set_location raised:", repr(e))
        try:
            dim.render()
            print("dim.render() succeeded")
        except Exception as e:
            print("dim.render() raised:", repr(e))
    except Exception as e:
        print("rendering block raised:", repr(e))

    after = len(list(msp))
    print("modelspace count after render:", after)

    # try to save the document for visual inspection
    out_name = "test_dim_out.dxf"
    try:
        doc.saveas(out_name)
        print("Saved:", out_name)
    except Exception as e:
        print("saveas raised:", repr(e))


if __name__ == "__main__":
    main()
