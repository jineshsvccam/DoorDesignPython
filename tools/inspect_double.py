import json
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi_app.schemas_input import DoorDXFRequest
from geometry.door_geometry import compute_door_geometry

p = Path(__file__).resolve().parents[1] / 'Door TestCases' / 'DoubleStandard.json'
print('Loading', p)
with p.open('r', encoding='utf-8') as fh:
    data = json.load(fh)
# pydantic compatibility
if hasattr(DoorDXFRequest, 'model_validate'):
    req = DoorDXFRequest.model_validate(data)
else:
    req = DoorDXFRequest.parse_obj(data)

out = compute_door_geometry(req)
# out is a pydantic model; get geometry
geom = out.geometry
# Find inner frame
inner = next((f for f in geom.frames if f.name == 'inner'), None)
left_inner = next((f for f in geom.frames if f.name == 'left_inner'), None)
print('inner frame width/height:', inner.width if inner else None, inner.height if inner else None)
# find cutouts with names containing 'top' or 'bottom'
for c in geom.cutouts:
    if 'glass' in c.name:
        # compute bbox
        ys = [pt[1] for pt in c.points]
        print(f"{c.name}: minY={min(ys)}, maxY={max(ys)}")

# compute expected top margin used for right leaf if available
if inner and geom.cutouts:
    # right leaf top panel name typically 'glass_top_right'
    top_right = next((c for c in geom.cutouts if c.name == 'glass_top_right'), None)
    if top_right:
        maxY = max(pt[1] for pt in top_right.points)
        inner_top = max(pt[1] for pt in inner.points)
        margin = inner_top - maxY
        print('Computed top margin (inner_top - glass_top):', margin)
        # also report margin measured against outer frame top for clarity
        outer = next((f for f in geom.frames if f.name == 'outer'), None)
        if outer:
            outer_top = max(p[1] for p in outer.points)
            print('Computed top margin (outer_top - glass_top):', outer_top - maxY)

print('\nDone')
