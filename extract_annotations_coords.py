"""Extract annotation coordinates from a DXF file.

Heuristics:
- Report all TEXT and MTEXT entities with their insertion coordinates and content.
- For each DIMENSION entity, attempt to print any available dxf attributes that look like points.
- For each DIMENSION, find the nearest MTEXT/TEXT (by Euclidean distance) and report that association.

Run: python extract_annotations_coords.py [path]
"""
import sys
import math
from ezdxf.filemanagement import readfile

PATH = sys.argv[1] if len(sys.argv) > 1 else "door_F14P2.dxf"


def dist(a, b):
    return math.hypot(a[0]-b[0], a[1]-b[1])


def to_xy(obj, attr_names):
    for name in attr_names:
        v = getattr(obj.dxf, name, None)
        if v is None:
            continue
        try:
            x = float(v[0])
            y = float(v[1])
            return (x, y)
        except Exception:
            continue
    return None


def main(path):
    try:
        doc = readfile(path)
    except Exception as e:
        print("Failed to open DXF:", e)
        return
    msp = doc.modelspace()

    texts = []  # (handle, type, text, insert)
    for ent in msp.query('MTEXT TEXT'):
        # Access text content safely (some DXFEntity variants may not expose attribute in stubs)
        txt = None
        try:
            if ent.dxftype() == 'MTEXT':
                txt = getattr(ent, 'text', None)
            else:
                txt = getattr(ent.dxf, 'text', None)
        except Exception:
            txt = None

        # Access insert coordinate safely
        insert = None
        try:
            raw_insert = getattr(ent.dxf, 'insert', None)
            if raw_insert is not None:
                try:
                    insert = tuple(raw_insert)
                except Exception:
                    # fallback: try converting sequence-like
                    try:
                        insert = (float(raw_insert[0]), float(raw_insert[1]), float(raw_insert[2]) if len(raw_insert) > 2 else 0.0)
                    except Exception:
                        insert = None
        except Exception:
            insert = None

        handle = getattr(ent.dxf, 'handle', None)
        texts.append((handle, ent.dxftype(), txt, insert))

    dims = []  # (handle, dxf-attribs, inferred_point)
    for dim in msp.query('DIMENSION'):
        handle = getattr(dim.dxf, 'handle', None)
        # Try common point-like attributes
        pt = to_xy(dim, ('insert', 'defpoint', 'defpoint1', 'defpoint2', 'generation_point', 'location'))
        # fallback: try to parse raw tag data (guard for missing 'tags')
        if pt is None:
            try:
                tags = getattr(dim, 'tags', None)
                if tags:
                    for tag in tags:
                        try:
                            code = tag[0]
                            value = tag[1]
                        except Exception:
                            # Not a 2-tuple-like DXF tag; skip
                            continue
                        # group code 10 is X,Y,Z point
                        if code == 10:
                            try:
                                x = float(value[0])
                                y = float(value[1])
                                pt = (x, y)
                                break
                            except Exception:
                                continue
            except Exception:
                pass
    dims.append((handle, repr(dim.dxf), pt))

    print(f"Found {len(texts)} text/mtxt entities and {len(dims)} DIMENSION entities")
    print('\nTexts:')
    for h, ttype, txt, ins in texts:
        print(f"  handle={h} type={ttype} insert={ins} text={repr(txt)[:80]}")

    print('\nDimensions and nearest text:')
    for handle, dxfinfo, pt in dims:
        print(f"DIM handle={handle} dxf-pt={pt}")
        # find nearest text
        best = None
        bestd = float('inf')
        for h, ttype, txt, ins in texts:
            if ins is None:
                continue
            # compare using xy only
            d = dist(pt, ins) if (pt is not None and ins is not None) else float('inf')
            if d < bestd:
                bestd = d
                best = (h, ttype, txt, ins, d)
        if best is not None and best[4] < 100:  # threshold in drawing units
            print(f"  nearest text handle={best[0]} type={best[1]} insert={best[3]} dist={best[4]:.2f} text={repr(best[2])[:80]}")
        else:
            print("  no nearby text found (or beyond threshold)")

if __name__ == '__main__':
    main(PATH)
