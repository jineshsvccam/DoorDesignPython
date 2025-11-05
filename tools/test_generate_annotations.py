import json
import importlib.util
import importlib.machinery
from typing import cast
from pathlib import Path

# load module directly from file to avoid package import issues
mod_path = Path(__file__).resolve().parents[1] / 'geometry' / 'generate_annotations.py'
spec = importlib.util.spec_from_file_location('generate_annotations', str(mod_path))
if spec is None:
    raise ImportError(f"Could not create module spec for {mod_path}")
# mypy/pylance-friendly cast
spec = cast(importlib.machinery.ModuleSpec, spec)
ga = importlib.util.module_from_spec(spec)
# Provide a minimal stub for fastapi_app.schemas_output.Annotation used by the module
import sys
import types
schemas_mod = types.SimpleNamespace()

class AnnotationStub:
    def __init__(self, **kwargs):
        # map 'from' -> 'from_' to match usage in the code and in output
        if 'from' in kwargs:
            kwargs['from_'] = kwargs.pop('from')
        for k, v in kwargs.items():
            setattr(self, k, v)

    @classmethod
    def parse_obj(cls, d):
        # accept dict-like input, mapping keys safely
        data = dict(d)
        if 'from' in data:
            data['from_'] = data.pop('from')
        return cls(**data)

    def dict(self):
        return {k: getattr(self, k) for k in self.__dict__}

schemas_mod.Annotation = AnnotationStub
sys.modules['fastapi_app'] = types.ModuleType('fastapi_app')
sys.modules['fastapi_app.schemas_output'] = types.ModuleType('fastapi_app.schemas_output')
setattr(sys.modules['fastapi_app.schemas_output'], 'Annotation', AnnotationStub)

if spec.loader is None:
    raise ImportError(f"No loader available for module spec from {mod_path}")
# mypy/pylance-friendly cast for loader
loader = cast(importlib.machinery.SourceFileLoader, spec.loader)
loader.exec_module(ga)
generate_annotations = ga.generate_annotations

# Data adapted from user's JSON
frames = [
    {"name": "outer", "points": [[635.5,12],[1256,12],[1256,1692],[635.5,1692],[635.5,12]]},
    {"name": "inner", "points": [[654.5,0],[1244,0],[1244,1704],[654.5,1704],[654.5,0]]},
    {"name": "left_outer", "points": [[0,12],[632.5,12],[632.5,1692],[0,1692],[0,12]]},
    {"name": "left_inner", "points": [[12,0],[601.5,0],[601.5,1704],[12,1704],[12,0]]},
]
cutouts = [
    {"name": "left_handle", "points": [[556.5,796],[578.5,796],[578.5,908],[556.5,908],[556.5,796]]},
    {"name": "center_handle", "points": [[684.5,796],[706.5,796],[706.5,908],[684.5,908],[684.5,796]]},
    {"name": "glass_bottom_right", "points": [[864.5,1542],[1034,1542],[1037.9018064403226,1541.6157056080647],[1041.6536686473019,1540.4775906502257],[1045.111404660392,1538.6293922460509],[1048.142135623731,1536.142135623731],[1050.6293922460509,1533.111404660392],[1052.4775906502257,1529.6536686473019],[1053.6157056080647,1525.9018064403226],[1054,1522],[1054,272],[1053.6157056080647,268.09819355967744],[1052.4775906502257,264.3463313526982],[1050.6293922460509,260.88859533960795],[1048.142135623731,257.85786437626905],[1045.111404660392,255.3706077539491],[1041.6536686473019,253.52240934977425],[1037.9018064403226,252.38429439193538],[1034,252],[864.5,252],[860.5981935596774,252.38429439193538],[856.8463313526981,253.52240934977425],[853.388595339608,255.3706077539491],[850.357864376269,257.85786437626905],[847.8706077539491,260.88859533960795],[846.0224093497743,264.3463313526982],[844.8842943919353,268.09819355967744],[844.5,272],[844.5,1522],[844.8842943919353,1525.9018064403226],[846.0224093497743,1529.6536686473019],[847.8706077539491,1533.111404660392],[850.357864376269,1536.142135623731],[853.388595339608,1538.6293922460509],[856.8463313526981,1540.4775906502257],[860.5981935596774,1541.6157056080647],[864.5,1542]]},
    {"name": "glass_top_right", "points": [[222,1542],[391.5,1542],[395.40180644032256,1541.6157056080647],[399.1536686473018,1540.4775906502257],[402.61140466039205,1538.6293922460509],[405.64213562373095,1536.142135623731],[408.1293922460509,1533.111404660392],[409.97759065022575,1529.6536686473019],[411.1157056080646,1525.9018064403226],[411.5,1522],[411.5,272],[411.1157056080646,268.09819355967744],[409.97759065022575,264.3463313526982],[408.1293922460509,260.88859533960795],[405.64213562373095,257.85786437626905],[402.61140466039205,255.3706077539491],[399.1536686473018,253.52240934977425],[395.40180644032256,252.38429439193538],[391.5,252],[222,252],[218.09819355967744,252.38429439193538],[214.3463313526982,253.52240934977425],[210.88859533960795,255.3706077539491],[207.85786437626905,257.85786437626905],[205.37060775394912,260.88859533960795],[203.52240934977425,264.3463313526982],[202.38429439193538,268.09819355967744],[202,272],[202,1522],[202.38429439193538,1525.9018064403226],[203.52240934977425,1529.6536686473019],[205.37060775394912,1533.111404660392],[207.85786437626905,1536.142135623731],[210.88859533960795,1538.6293922460509],[214.3463313526982,1540.4775902257],[218.09819355967744,1541.6157056080647],[222,1542]]},
    {"name": "keybox", "points": [[914.25,62],[984.25,62],[984.25,102],[914.25,102],[914.25,62]]},
]
holes = [
    {"name": "hole_top", "center": [694.5,1542], "radius": 11},
    {"name": "hole_bottom", "center": [694.5,162], "radius": 11},
]

# generate_annotations expects frame objects with a .points attribute in some helpers;
# provide simple wrappers so both dict-like and attribute access work.
class FrameObj:
    def __init__(self, d):
        self.points = d.get('points')
        self.name = d.get('name')

frames_objs = [FrameObj(f) for f in frames]

# simple hole wrapper with attributes
class HoleObj:
    def __init__(self, d):
        self.center = tuple(d.get('center'))
        self.radius = d.get('radius')
        self.name = d.get('name')

holes_objs = [HoleObj(h) for h in holes]

anns = generate_annotations(frames_objs, cutouts, holes_objs)

# Convert pydantic Annotation objects to dicts for printing
out = {}
for k, v in anns.items():
    out[k] = [a.dict() for a in v]

print(json.dumps(out, indent=2))
