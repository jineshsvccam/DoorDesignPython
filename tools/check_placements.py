import math
import os, sys
# ensure repo root is on sys.path so imports like DoorRectPack/door_utils resolve
sys.path.insert(0, os.path.abspath(os.getcwd()))
from DoorRectPack import pack_rectangles
from door_utils import get_door_rectangles
from geometry.door_geometry import compute_door_geometry

EXCEL = 'Restructured_Door_Measurements.xlsm'
SHEET_W = 1250
SHEET_H = 2500


def bbox_from_frames(frames):
    all_pts = []
    for f in frames:
        if f and getattr(f, 'points', None) is not None:
            all_pts += [tuple(p) for p in f.points]
        elif isinstance(f, list):
            all_pts += [tuple(p) for p in f]
    if not all_pts:
        return None
    xs = [p[0] for p in all_pts]
    ys = [p[1] for p in all_pts]
    return (min(xs), min(ys), max(xs), max(ys))


def main():
    rectangles, door_params = get_door_rectangles(__import__('pandas').read_excel(EXCEL), {})
    bins = pack_rectangles(rectangles, SHEET_W, SHEET_H)
    issues = []
    for b in bins:
        for p in b['placements']:
            fname = p['file_name']
            placement_x = p['x']
            placement_y = p['y']
            rotated = bool(p.get('rotated', False))
            # find door_params for this file
            dp = next((d for d in door_params if d.get('file_name') == fname), None)
            if dp is None:
                issues.append((fname, 'missing door_params'))
                continue
            req = dp.get('request')
            if req is None:
                issues.append((fname, 'missing request'))
                continue
            try:
                # compute geometry with NO external placement so frames are returned
                # normalized to local origin; metadata.offset will contain the
                # placement that should be applied when drawing.
                schema = compute_door_geometry(req, rotated=rotated, offset=(placement_x, placement_y))
                frames = schema.geometry.frames
                bbox = bbox_from_frames(frames)
                if not bbox:
                    issues.append((fname, 'no frames'))
                    continue
                min_x, min_y, max_x, max_y = bbox
                # The geometry frames are normalized (min_x/min_y are typically 0.0).
                # The effective world position of the bbox min is schema.metadata.offset + (min_x, min_y).
                eff_min_x = schema.metadata.offset[0] + min_x
                eff_min_y = schema.metadata.offset[1] + min_y
                dx = abs(eff_min_x - placement_x)
                dy = abs(eff_min_y - placement_y)
                if dx > 1e-6 or dy > 1e-6:
                    issues.append((fname, placement_x, placement_y, min_x, min_y, eff_min_x, eff_min_y, dx, dy, rotated))
            except Exception as e:
                issues.append((fname, 'compute_error', str(e)))
    if not issues:
        print('All placements align: no mismatches')
    else:
        print('Mismatches found:')
        for it in issues[:50]:
            print(it)


if __name__ == '__main__':
    main()
