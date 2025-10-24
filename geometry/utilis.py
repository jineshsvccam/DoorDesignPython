"""Utility functions moved out of door_geometry.py.

This module contains pure helper functions: frame dimension computation and
rounded-rectangle / rounded-box polygon builders used by the geometry code.

The implementations were moved verbatim from the top-level `utilis.py`.
"""
from typing import List, Tuple
import math


def compute_frame_dimensions(points: List[Tuple[float, float]]) -> Tuple[float, float]:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    width = max(xs) - min(xs)
    height = max(ys) - min(ys)
    return width, height


def create_rounded_box(left_x, bottom_y, width, height, radius, segments=12):
    """Return list of points approximating a rectangle with semicircular ends (rounded box/capsule).

    The shape is a capsule oriented horizontally: semicircle at left and right, connected by straight edges.
    """
    cx_left = left_x + radius
    cx_right = left_x + width - radius
    top = bottom_y + height
    # If radius is larger than half of height, clamp it
    radius = min(radius, height / 2.0)

    pts = []
    # top edge from left to right (excluding corners)
    pts.append((cx_left, top))
    pts.append((cx_right, top))

    # right semicircle (top->bottom)
    for i in range(segments + 1):
        theta = (i / segments) * math.pi  # 0..pi
        x = cx_right + radius * math.cos(theta)
        y = bottom_y + height / 2.0 + radius * math.sin(theta)
        pts.append((x, y))

    # bottom edge from right to left
    pts.append((cx_left, bottom_y))

    # left semicircle (bottom->top)
    for i in range(segments + 1):
        theta = math.pi + (i / segments) * math.pi  # pi..2pi
        x = cx_left + radius * math.cos(theta)
        y = bottom_y + height / 2.0 + radius * math.sin(theta)
        pts.append((x, y))

    # close
    pts.append(pts[0])
    return pts


def create_rounded_rect(left_x, bottom_y, width, height, radius, segments=8):
    """Create a rounded-rectangle polygon (clockwise) with quarter-circle corners.

    Constructed in clockwise order: top edge left->right, top-right arc, right edge,
    bottom-right arc, bottom edge, bottom-left arc, left edge, top-left arc.
    """
    right = left_x + width
    top = bottom_y + height
    r = min(radius, width / 2.0, height / 2.0)

    # corner centers
    tl_c = (left_x + r, top - r)
    tr_c = (right - r, top - r)
    br_c = (right - r, bottom_y + r)
    bl_c = (left_x + r, bottom_y + r)

    pts = []

    # top edge tangents (exact coordinates)
    pts.append((left_x + r, top))
    pts.append((right - r, top))

    # helper to sample arc between start_angle -> end_angle (exclude endpoints)
    def sample_arc(center, start_ang, end_ang, segs):
        cx, cy = center
        arc_pts = []
        if segs > 1:
            for i in range(1, segs):
                t = i / segs
                theta = start_ang + (end_ang - start_ang) * t
                arc_pts.append((cx + r * math.cos(theta), cy + r * math.sin(theta)))
        return arc_pts

    # top-right arc: 90deg -> 0deg
    pts += sample_arc(tr_c, math.pi / 2.0, 0.0, segments)
    # right edge tangents
    pts.append((right, top - r))
    pts.append((right, bottom_y + r))

    # bottom-right arc: 0 -> -90deg
    pts += sample_arc(br_c, 0.0, -math.pi / 2.0, segments)
    # bottom edge tangents
    pts.append((right - r, bottom_y))
    pts.append((left_x + r, bottom_y))

    # bottom-left arc: -90 -> -180deg
    pts += sample_arc(bl_c, -math.pi / 2.0, -math.pi, segments)
    # left edge tangents
    pts.append((left_x, bottom_y + r))
    pts.append((left_x, top - r))

    # top-left arc: pi -> pi/2 (i.e. 180deg -> 90deg)
    pts += sample_arc(tl_c, math.pi, math.pi / 2.0, segments)

    # Snap points very close to exact tangent coordinates to avoid floating-point micro-gaps
    tangents = [
        (left_x + r, top),         # top-left tangent
        (right - r, top),          # top-right tangent
        (right, top - r),          # right-top
        (right, bottom_y + r),     # right-bottom
        (right - r, bottom_y),     # bottom-right
        (left_x + r, bottom_y),    # bottom-left
        (left_x, bottom_y + r),    # left-bottom
        (left_x, top - r),         # left-top
    ]
    eps = 1e-6
    snapped = []
    for x, y in pts:
        snapped_point = (x, y)
        for tx, ty in tangents:
            if (abs(x - tx) <= eps) and (abs(y - ty) <= eps):
                snapped_point = (tx, ty)
                break
        snapped.append(snapped_point)

    # close and dedupe
    pts = dedupe_consecutive_points(snapped)
    return pts


def dedupe_consecutive_points(points, eps=1e-6):
    if not points:
        return points
    out = [points[0]]
    for p in points[1:]:
        if abs(p[0] - out[-1][0]) > eps or abs(p[1] - out[-1][1]) > eps:
            out.append(p)
    # If closed, ensure explicit close
    if out[0] != out[-1]:
        out.append(out[0])
    return out
