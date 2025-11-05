"""Small helper to inspect door_F14P2.dxf and summarize modelspace entities.
Produces counts by DXF type and prints a short sample of entities.
"""
from ezdxf.filemanagement import readfile
from collections import Counter

PATH = "door_F14P2.dxf"

def summarize(path):
    try:
        doc = readfile(path)
    except Exception as e:
        print(f"Failed to read DXF: {e}")
        return
    msp = doc.modelspace()
    types = Counter()
    samples = []
    for i, ent in enumerate(msp):
        t = ent.dxftype()
        types[t] += 1
        if len(samples) < 40:
            try:
                layer = getattr(ent.dxf, 'layer', None)
            except Exception:
                layer = None
            try:
                handle = getattr(ent.dxf, 'handle', None)
            except Exception:
                handle = None
            samples.append((i+1, t, layer, handle))
    print(f"Modelspace entity count: {sum(types.values())}")
    print("Counts by DXF type:")
    for t, c in types.most_common():
        print(f"  {t:12} : {c}")
    print("\nSample entities (index, type, layer, handle):")
    for s in samples:
        print(" ", s)

    # Quick checks for dimension-related content
    dim_like = {k: types.get(k, 0) for k in ("DIMENSION", "LINE", "TEXT", "MTEXT", "INSERT", "POINT")}
    print('\nQuick dimension-like summary:')
    for k,v in dim_like.items():
        print(f"  {k:8} -> {v}")

if __name__ == '__main__':
    summarize(PATH)
