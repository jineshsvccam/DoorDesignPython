"""Inspect DimStyleOverride internals to find possible renderer/virtual-entity accessors.

Run with: python inspect_dim.py
"""

import ezdxf
from ezdxf.filemanagement import new
import inspect


def main():
    print("ezdxf version:", getattr(ezdxf, "__version__", "unknown"))
    doc = new(dxfversion="R2010")
    msp = doc.modelspace()
    p1 = (0, 0)
    p2 = (200, 0)

    dim = msp.add_linear_dim(base=(0, 0), p1=p1, p2=p2, angle=0)
    print("dim type:", type(dim))

    # Basic introspection
    print("class mro:", dim.__class__.__mro__)
    attrs = dir(dim)
    # show attributes with probable names
    interesting = [a for a in attrs if any(k in a for k in ("virt", "rend", "draw", "entity", "render", "items", "_renderer", "_drawing", "_entities", "_virtual"))]
    print("interesting attrs:", interesting)

    # Try to print attributes and their values/types
    for a in interesting:
        try:
            v = getattr(dim, a)
            print(f"{a}: type={type(v)} repr={repr(v)[:200]}")
        except Exception as e:
            print(f"{a}: ERROR reading attribute: {e}")

    # show first 200 entries of dir to help manual inspection
    print("\nFULL dir (first 200 chars):")
    print(repr(attrs)[:2000])

    # Try to find callables that might produce entities
    callables = [a for a in attrs if callable(getattr(dim, a, None))]
    candidates = [c for c in callables if any(k in c for k in ("virtual", "entities", "render", "draw", "to_entities", "get_entities", "items"))]
    print("callable candidates:", candidates)

    for c in candidates:
        try:
            print(f"Calling {c}() ...")
            res = getattr(dim, c)()
            print(f"  returned type: {type(res)}")
            try:
                print(f"  len(res): {len(res)}")
            except Exception:
                pass
            # if iterable, print types of first few items
            try:
                for i, e in enumerate(res):
                    if i >= 5:
                        break
                    print(f"    [{i}] -> type={type(e)} repr={repr(e)[:200]}")
            except Exception as e:
                print(f"  iterating res failed: {e}")
        except Exception as e:
            print(f"  call {c}() raised: {e}")

    # Try to inspect source if available
    try:
        src = inspect.getsource(dim.__class__)
        print("\nCLASS SOURCE:\n", src[:4000])
    except Exception as e:
        print("getsource failed:", e)

    # Save doc
    doc.saveas("inspect_dim_out.dxf")
    print("Saved inspect_dim_out.dxf")


if __name__ == '__main__':
    main()
