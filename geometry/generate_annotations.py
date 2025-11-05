from typing import List, Tuple, Any, Dict, Optional
from fastapi_app.schemas_output import Annotation


def _bbox(points: List[Tuple[float, float]]):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)

def _get_name(obj: Any):
    return getattr(obj, "name", None) or (obj.get("name") if isinstance(obj, dict) else None)


def _get_points(obj: Any):
    if hasattr(obj, "points"):
        return obj.points
    if isinstance(obj, dict):
        return obj.get("points")
    return obj


def _frame_dimensions_annotations(frame: Any, offset_base: float = 10.0, placement: str = "bottom_left"):
    """Create width/height annotations for a frame.

    placement: "bottom_left" or "top_right" determines which edges receive
    the width and height dims. This allows alternating frames to place
    dimensions on different sides (clockwise alternation).
    """
    pts = frame.points
    min_x, min_y, max_x, max_y = _bbox(pts)
    width = round(max_x - min_x, 3)
    height = round(max_y - min_y, 3)

    # Default to bottom-left: width on bottom edge, height on left edge.
    if placement == "bottom_left":
        w_from = (min_x, min_y)
        w_to = (max_x, min_y)
        w_text = f"W {width}"

        h_from = (min_x, min_y)
        h_to = (min_x, max_y)
        h_text = f"H {height}"

        w_offset = -offset_base
        h_offset = -offset_base
        w_angle = 0.0
        h_angle = 90.0
    else:
        # top_right: width on top edge, height on right edge
        w_from = (min_x, max_y)
        w_to = (max_x, max_y)
        w_text = f"W {width}"

        h_from = (max_x, min_y)
        h_to = (max_x, max_y)
        h_text = f"H {height}"

        w_offset = offset_base
        h_offset = offset_base
        w_angle = 0.0
        h_angle = 90.0

    width_ann = Annotation.parse_obj({
        "type": "dimension",
        "from": w_from,
        "to": w_to,
        "text": w_text,
        "offset": w_offset,
        "angle": w_angle,
        "category": "frame",
        "owner": _get_name(frame) or "frame",
    })

    height_ann = Annotation.parse_obj({
        "type": "dimension",
        "from": h_from,
        "to": h_to,
        "text": h_text,
        "offset": h_offset,
        "angle": h_angle,
        "category": "frame",
        "owner": _get_name(frame) or "frame",
    })

    return [width_ann, height_ann]


def _cutout_dimensions_annotations(cutout: Any, left_frame: Any = None, offset_base: float = 6.0):
    pts = _get_points(cutout) or []
    min_x, min_y, max_x, max_y = _bbox(pts)
    width = round(max_x - min_x, 3)
    height = round(max_y - min_y, 3)

    w_from = (min_x, min_y)
    w_to = (max_x, min_y)
    w_text = f"W {width}"

    h_from = (min_x, min_y)
    h_to = (min_x, max_y)
    h_text = f"H {height}"

    width_ann = Annotation.parse_obj({
        "type": "dimension",
        "from": w_from,
        "to": w_to,
        "text": w_text,
        "offset": -offset_base,
        "angle": 0.0,
        "category": "cutout",
        "owner": _get_name(cutout) or "cutout",
    })

    height_ann = Annotation.parse_obj({
        "type": "dimension",
        "from": h_from,
        "to": h_to,
        "text": h_text,
        "offset": -offset_base,
        "angle": 90.0,
        "category": "cutout",
        "owner": _get_name(cutout) or "cutout",
    })

    anns = [width_ann, height_ann]

    # Optional left-gap: measure from the provided left_frame right edge
    if left_frame is not None:
        lf_pts = _get_points(left_frame) or []
        if lf_pts:
            lf_right = max(p[0] for p in lf_pts)
            gap = round(max(0.0, min_x - lf_right), 3)
            if gap > 0:
                anns.append(Annotation.parse_obj({
                    "type": "dimension",
                    "from": (lf_right, (min_y + max_y) / 2.0),
                    "to": (min_x, (min_y + max_y) / 2.0),
                    "text": f"G {gap}",
                    "offset": -offset_base,
                    "angle": 0.0,
                    "category": "cutout",
                    "owner": _get_name(cutout) or "cutout",
                }))

    return anns


def _glass_cut_annotations(cutout: Any, inner_frame: Any, outer_frame: Any, offset_base: float = 6.0) -> List[Annotation]:
    """Create five annotations for a glass cut:
    - left and right distances from the inner frame edges
    - top and bottom distances from the outer frame edges
    - an internal note (box) displaying the cutout W x H centered inside the cutout
    """
    anns: List[Annotation] = []
    pts = _get_points(cutout) or []
    if not pts:
        return anns
    min_x, min_y, max_x, max_y = _bbox(pts)
    cx = (min_x + max_x) / 2.0
    cy = (min_y + max_y) / 2.0

    # Width/height for internal label
    width = round(max_x - min_x, 3)
    height = round(max_y - min_y, 3)

    # Resolve inner frame extents (prefer provided inner_frame, else find by name)
    inner_left = None
    inner_right = None
    if inner_frame is not None:
        ipts = _get_points(inner_frame) or []
        if ipts:
            inner_left = min(p[0] for p in ipts)
            inner_right = max(p[0] for p in ipts)
    if (inner_left is None or inner_right is None):
        # try to find frame named 'inner' in the caller's frames list by inspecting variable scope (best-effort)
        # Note: caller usually passes inner_frame; fallback omitted here for simplicity.
        pass

    # Resolve outer frame extents
    outer_top = None
    outer_bot = None
    if outer_frame is not None:
        of_pts = _get_points(outer_frame) or []
        if of_pts:
            outer_top = max(p[1] for p in of_pts)
            outer_bot = min(p[1] for p in of_pts)

    # Left gap from inner_left -> cutout left
    if inner_left is not None:
        gap_left = round(max(0.0, min_x - inner_left), 3)
        if gap_left > 0:
            anns.append(Annotation.parse_obj({
                "type": "dimension",
                "from": (inner_left, cy),
                "to": (min_x, cy),
                "text": f"G {gap_left}",
                "offset": -offset_base,
                "angle": 0.0,
                "category": "glass_cut",
                "owner": _get_name(cutout) or "glass_cut",
            }))

    # Right gap from cutout right -> inner_right
    if inner_right is not None:
        gap_right = round(max(0.0, inner_right - max_x), 3)
        if gap_right > 0:
            anns.append(Annotation.parse_obj({
                "type": "dimension",
                "from": (max_x, cy),
                "to": (inner_right, cy),
                "text": f"G {gap_right}",
                "offset": -offset_base,
                "angle": 0.0,
                "category": "glass_cut",
                "owner": _get_name(cutout) or "glass_cut",
            }))

    # Top gap from outer_top -> cutout top
    if outer_top is not None:
        gap_top = round(max(0.0, outer_top - max_y), 3)
        if gap_top > 0:
            anns.append(Annotation.parse_obj({
                "type": "dimension",
                "from": (cx, max_y),
                "to": (cx, outer_top),
                "text": f"G {gap_top}",
                "offset": offset_base,
                "angle": 90.0,
                "category": "glass_cut",
                "owner": _get_name(cutout) or "glass_cut",
            }))

    # Bottom gap from cutout bottom -> outer_bot
    if outer_bot is not None:
        gap_bot = round(max(0.0, min_y - outer_bot), 3)
        if gap_bot > 0:
            anns.append(Annotation.parse_obj({
                "type": "dimension",
                "from": (cx, outer_bot),
                "to": (cx, min_y),
                "text": f"G {gap_bot}",
                "offset": offset_base,
                "angle": 90.0,
                "category": "glass_cut",
                "owner": _get_name(cutout) or "glass_cut",
            }))

    # Internal label: draw a small horizontal dimension across the inside so
    # renderers that ignore 'note' will still show the W x H text.
    # By default suppress the internal W x H label (not required in JSON).
    # Consumers can opt-in to the internal label by setting
    # `suppress_internal_label=False` on the cutout (either as an attribute
    # on an object or as a dict key).
    suppress = True
    try:
        val = getattr(cutout, "suppress_internal_label", None)
        if val is not None:
            suppress = bool(val)
    except Exception:
        pass
    if isinstance(cutout, dict) and ("suppress_internal_label" in cutout):
        suppress = bool(cutout.get("suppress_internal_label"))

    if not suppress:
        inner_from_x = min_x + (max_x - min_x) * 0.25
        inner_to_x = max_x - (max_x - min_x) * 0.25
        if inner_to_x > inner_from_x:
            anns.append(Annotation.parse_obj({
                "type": "dimension",
                "from": (inner_from_x, cy),
                "to": (inner_to_x, cy),
                "text": f"W {width} x H {height}",
                "offset": 0.0,
                "angle": 0.0,
                "category": "glass_cut",
                "owner": _get_name(cutout) or "glass_cut",
            }))

    return anns


def _hole_dimensions_annotations(hole: Any, offset_base: float = 4.0):
    cx, cy = hole.center
    dia = round(hole.radius * 2.0, 3)

    # Draw the diameter line across the circle (left edge to right edge)
    p_from = (cx - hole.radius, cy)
    p_to = (cx + hole.radius, cy)
    text = f"Ø{dia}"

    ann = Annotation.parse_obj({
        "type": "dimension",
        "from": p_from,
        "to": p_to,
        "text": text,
        "offset": offset_base,
        "angle": 0.0,
        "category": "hole",
        "owner": _get_name(hole) or "hole",
    })
    return [ann]


def _frame_gap_annotation(frame1: Any, frame2: Any, offset_base: float = 6.0):
    """Create an annotation that measures the gap between two frame bboxes.

    Returns a list with zero or one Annotation (empty if frames overlap).
    """
    min_x1, min_y1, max_x1, max_y1 = _bbox(frame1.points)
    min_x2, min_y2, max_x2, max_y2 = _bbox(frame2.points)

    anns: List[Annotation] = []

    # centers (used when there is no overlap to place the annotation)
    c1x = (min_x1 + max_x1) / 2.0
    c1y = (min_y1 + max_y1) / 2.0
    c2x = (min_x2 + max_x2) / 2.0
    c2y = (min_y2 + max_y2) / 2.0

    owner = f"{getattr(frame1, 'name', 'frame1')}_{getattr(frame2, 'name', 'frame2')}"

    # Determine overlap midpoints where possible
    overlap_y_min = max(min_y1, min_y2)
    overlap_y_max = min(max_y1, max_y2)
    if overlap_y_max > overlap_y_min:
        mid_y = (overlap_y_min + overlap_y_max) / 2.0
    else:
        mid_y = (c1y + c2y) / 2.0

    overlap_x_min = max(min_x1, min_x2)
    overlap_x_max = min(max_x1, max_x2)
    if overlap_x_max > overlap_x_min:
        mid_x = (overlap_x_min + overlap_x_max) / 2.0
    else:
        mid_x = (c1x + c2x) / 2.0

    # Left edge gap: distance between the two left edges
    left_gap = round(abs(min_x2 - min_x1), 3)
    if left_gap > 0:
        lx_from = (min(min_x1, min_x2), mid_y)
        lx_to = (max(min_x1, min_x2), mid_y)
        anns.append(Annotation.parse_obj({
            "type": "dimension",
            "from": lx_from,
            "to": lx_to,
            "text": f"G {left_gap}",
            "offset": offset_base,
            "angle": 0.0,
            "category": "frame_gap",
            "owner": owner,
        }))

    # Right edge gap: distance between the two right edges
    right_gap = round(abs(max_x1 - max_x2), 3)
    if right_gap > 0:
        rx_from = (min(max_x1, max_x2), mid_y)
        rx_to = (max(max_x1, max_x2), mid_y)
        anns.append(Annotation.parse_obj({
            "type": "dimension",
            "from": rx_from,
            "to": rx_to,
            "text": f"G {right_gap}",
            "offset": offset_base,
            "angle": 0.0,
            "category": "frame_gap",
            "owner": owner,
        }))

    # Top edge gap: distance between the two top edges (max y)
    top_gap = round(abs(max_y1 - max_y2), 3)
    if top_gap > 0:
        ty_from = (mid_x, min(max_y1, max_y2))
        ty_to = (mid_x, max(max_y1, max_y2))
        anns.append(Annotation.parse_obj({
            "type": "dimension",
            "from": ty_from,
            "to": ty_to,
            "text": f"G {top_gap}",
            "offset": offset_base,
            "angle": 90.0,
            "category": "frame_gap",
            "owner": owner,
        }))

    # Bottom edge gap: distance between the two bottom edges (min y)
    bottom_gap = round(abs(min_y2 - min_y1), 3)
    if bottom_gap > 0:
        by_from = (mid_x, min(min_y1, min_y2))
        by_to = (mid_x, max(min_y1, min_y2))
        anns.append(Annotation.parse_obj({
            "type": "dimension",
            "from": by_from,
            "to": by_to,
            "text": f"G {bottom_gap}",
            "offset": offset_base,
            "angle": 90.0,
            "category": "frame_gap",
            "owner": owner,
        }))

    return anns


def _center_handle_annotations(center_cut: Any, frames: Optional[List[Any]], outer_frame: Any) -> List[Annotation]:
    anns: List[Annotation] = []
    pts = _get_points(center_cut) or []
    if not pts:
        return anns
    c_min_x, c_min_y, c_max_x, c_max_y = _bbox(pts)
    c_cx = (c_min_x + c_max_x) / 2.0
    c_cy = (c_min_y + c_max_y) / 2.0

    # Horizontal gap to left inner frame
    # Determine left reference x-coordinate. Prefer explicitly provided
    # frames named 'left_inner' (use their right edge) or 'inner' (use their left edge),
    # else pick the nearest frame whose right edge sits to the left of the center handle.
    left_ref_x = None
    frames_list = frames or []
    # Try explicit named left/inner frames first
    if frames_list:
        # Prefer an explicitly-named 'inner' frame first (right-side inner for double doors),
        # then fallback to 'left_inner' if 'inner' not present.
        fr_named = next((fr for fr in frames_list if ((_get_name(fr) or "").strip().lower() == "inner")), None)
        if fr_named is None:
            fr_named = next((fr for fr in frames_list if ((_get_name(fr) or "").strip().lower() == "left_inner")), None)
        if fr_named is not None:
            fpts = _get_points(fr_named) or []
            if fpts:
                nm = ((_get_name(fr_named) or "").strip().lower())
                fr_min_x = min(p[0] for p in fpts)
                fr_max_x = max(p[0] for p in fpts)
                # Prefer an edge that lies to the left of the center handle (<= c_cx).
                # Choose the edge closest to c_cx (max of candidates) so we measure from
                # the nearest edge on the left side. This handles double-door cases where
                # an 'inner' frame may be positioned to the left or right of the center.
                candidates = []
                if fr_max_x <= c_cx:
                    candidates.append(fr_max_x)
                if fr_min_x <= c_cx:
                    candidates.append(fr_min_x)
                if candidates:
                    left_ref_x = max(candidates)
                else:
                    # no edge sits to the left of center; fall back to the nearer edge
                    # (choose the one with smaller distance to c_cx)
                    if abs(fr_max_x - c_cx) < abs(fr_min_x - c_cx):
                        left_ref_x = fr_max_x
                    else:
                        left_ref_x = fr_min_x

    # Fallback: choose nearest frame to the left based on right edge
    if left_ref_x is None and frames_list:
        left_candidates = []
        for fr in frames_list:
            fps = _get_points(fr) or []
            if not fps:
                continue
            fr_min_x = min(p[0] for p in fps)
            fr_max_x = max(p[0] for p in fps)
            if fr_max_x <= c_cx:
                left_candidates.append((fr_max_x, fr))
        if left_candidates:
            left_ref_x = max(left_candidates, key=lambda t: t[0])[0]

    if left_ref_x is not None:
        gap_h = round(max(0.0, c_min_x - left_ref_x), 3)
        if gap_h > 0:
            anns.append(Annotation.parse_obj({
                "type": "dimension",
                "from": (left_ref_x, c_cy),
                "to": (c_min_x, c_cy),
                "text": f"G {gap_h}",
                "offset": 6.0,
                "angle": 0.0,
                "category": "center_handle",
                "owner": _get_name(center_cut) or "center_handle",
            }))

    # Vertical gaps to outer frame top/bottom
    if outer_frame is not None:
        of_pts = _get_points(outer_frame) or []
        if of_pts:
            of_top = max(p[1] for p in of_pts)
            of_bot = min(p[1] for p in of_pts)

            gap_top = round(max(0.0, of_top - c_max_y), 3)
            if gap_top > 0:
                anns.append(Annotation.parse_obj({
                    "type": "dimension",
                    "from": (c_cx, c_max_y),
                    "to": (c_cx, of_top),
                    "text": f"G {gap_top}",
                    "offset": 6.0,
                    "angle": 90.0,
                    "category": "center_handle",
                    "owner": _get_name(center_cut) or "center_handle",
                }))

            gap_bot = round(max(0.0, c_min_y - of_bot), 3)
            if gap_bot > 0:
                anns.append(Annotation.parse_obj({
                    "type": "dimension",
                    "from": (c_cx, of_bot),
                    "to": (c_cx, c_min_y),
                    "text": f"G {gap_bot}",
                    "offset": 6.0,
                    "angle": 90.0,
                    "category": "center_handle",
                    "owner": _get_name(center_cut) or "center_handle",
                }))

    return anns


def _keybox_annotations(key_cut: Any, frames: List[Any], outer_frame: Any) -> List[Annotation]:
    anns: List[Annotation] = []
    k_pts = _get_points(key_cut) or []
    if not k_pts:
        return anns
    k_min_x, k_min_y, k_max_x, k_max_y = _bbox(k_pts)
    k_cx = (k_min_x + k_max_x) / 2.0
    k_cy = (k_min_y + k_max_y) / 2.0

    # find nearest frame to the left and right of key center
    left_candidates = []
    right_candidates = []
    for fr in (frames or []):
        fps = _get_points(fr) or []
        if not fps:
            continue
        fr_min_x = min(p[0] for p in fps)
        fr_max_x = max(p[0] for p in fps)
        if fr_max_x <= k_cx:
            left_candidates.append((fr_max_x, fr))
        # also consider an 'inner' frame's left edge as a potential left reference
        # (useful when inner spans across the key center but its left edge is the
        # nearest meaningful reference)
        if ((_get_name(fr) or "").strip().lower() == "inner"):
            # add inner's left edge as candidate if it's left of the key center
            if fr_min_x <= k_cx:
                left_candidates.append((fr_min_x, fr))
        if fr_min_x >= k_cx:
            right_candidates.append((fr_min_x, fr))

    left_ref_x = None
    if left_candidates:
        left_ref_x = max(left_candidates, key=lambda t: t[0])[0]
    right_ref_x = None
    if right_candidates:
        right_ref_x = min(right_candidates, key=lambda t: t[0])[0]

    # Fallback: look for explicitly named left/right/inner frames if nearest
    # candidate search didn't find suitable edges. This helps when frames are
    # provided but the simple center-based split misses them.
    if left_ref_x is None and frames:
        for nm in ("left_inner", "left_outer", "inner"):
            fr = next((fr for fr in frames if ((_get_name(fr) or "").strip().lower() == nm)), None)
            if fr is not None:
                fps = _get_points(fr) or []
                if fps:
                    # If the named frame is 'inner', prefer the left edge (min x)
                    # as the left reference; for explicit left_* frames use the
                    # right edge (max x).
                    if nm == "inner":
                        left_ref_x = min(p[0] for p in fps)
                    else:
                        left_ref_x = max(p[0] for p in fps)
                    break
    if right_ref_x is None and frames:
        for nm in ("right_inner", "right_outer", "inner"):
            fr = next((fr for fr in frames if ((_get_name(fr) or "").strip().lower() == nm)), None)
            if fr is not None:
                fps = _get_points(fr) or []
                if fps:
                    # If the named frame is 'inner', prefer the right edge (max x)
                    # as the right reference; for explicit right_* frames use the
                    # left edge (min x).
                    if nm == "inner":
                        right_ref_x = max(p[0] for p in fps)
                    else:
                        right_ref_x = min(p[0] for p in fps)
                    break

    # horizontal gaps
    if left_ref_x is not None:
        gap_left = round(max(0.0, k_min_x - left_ref_x), 3)
        if gap_left > 0:
            anns.append(Annotation.parse_obj({
                "type": "dimension",
                "from": (left_ref_x, k_cy),
                "to": (k_min_x, k_cy),
                "text": f"G {gap_left}",
                "offset": 6.0,
                "angle": 0.0,
                "category": "keybox",
                "owner": _get_name(key_cut) or "keybox",
            }))
    if right_ref_x is not None:
        gap_right = round(max(0.0, right_ref_x - k_max_x), 3)
        if gap_right > 0:
            anns.append(Annotation.parse_obj({
                "type": "dimension",
                "from": (k_max_x, k_cy),
                "to": (right_ref_x, k_cy),
                "text": f"G {gap_right}",
                "offset": 6.0,
                "angle": 0.0,
                "category": "keybox",
                "owner": _get_name(key_cut) or "keybox",
            }))

    # bottom gap to outer frame bottom
    ofr = outer_frame if outer_frame is not None else None
    if ofr is None:
        ofr = next((fr for fr in (frames or []) if (_get_name(fr) or "").strip().lower() == "outer"), None)
    if ofr is not None:
        of_pts = _get_points(ofr) or []
        if of_pts:
            of_bot = min(p[1] for p in of_pts)
            gap_bot = round(max(0.0, k_min_y - of_bot), 3)
            if gap_bot > 0:
                anns.append(Annotation.parse_obj({
                    "type": "dimension",
                    "from": (k_cx, of_bot),
                    "to": (k_cx, k_min_y),
                    "text": f"G {gap_bot}",
                    "offset": 6.0,
                    "angle": 90.0,
                    "category": "keybox",
                    "owner": _get_name(key_cut) or "keybox",
                }))

    return anns


def _hole_offset_annotations(hole: Any, frames: List[Any], inner_frame: Any, outer_frame: Any) -> List[Annotation]:
    anns: List[Annotation] = []
    h_name = (_get_name(hole) or "").strip().lower()
    if h_name not in ("hole_top", "hole_bottom"):
        return anns
    try:
        hx, hy = hole.center
    except Exception:
        return anns

    # Determine inner (for left offset) and outer (for top/bottom) frame extents
    inner_left = None
    if inner_frame is not None:
        ipts = _get_points(inner_frame) or []
        if ipts:
            inner_left = min(p[0] for p in ipts)
    # fallback: try to find a frame named 'inner'
    if inner_left is None and frames:
        fr_in = next((fr for fr in frames if ((_get_name(fr) or "").strip().lower() == "inner")), None)
        if fr_in is not None:
            ipts = _get_points(fr_in) or []
            if ipts:
                inner_left = min(p[0] for p in ipts)

    of = outer_frame if outer_frame is not None else None
    if of is None and frames:
        of = next((fr for fr in frames if ((_get_name(fr) or "").strip().lower() == "outer")), None)

    outer_left = None
    outer_top = None
    outer_bot = None
    if of is not None:
        of_pts = _get_points(of) or []
        if of_pts:
            outer_left = min(p[0] for p in of_pts)
            outer_top = max(p[1] for p in of_pts)
            outer_bot = min(p[1] for p in of_pts)
    else:
        if frames:
            all_x = [p[0] for fr in frames for p in (_get_points(fr) or [])]
            all_y = [p[1] for fr in frames for p in (_get_points(fr) or [])]
            if all_x:
                outer_left = min(all_x)
            if all_y:
                outer_top = max(all_y)
                outer_bot = min(all_y)

    # Horizontal offset from inner left edge to hole center (preferred)
    if inner_left is not None:
        dx = round(max(0.0, hx - inner_left), 3)
        if dx > 0:
            anns.append(Annotation.parse_obj({
                "type": "dimension",
                "from": (inner_left, hy),
                "to": (hx, hy),
                "text": f"X {dx}",
                "offset": 6.0,
                "angle": 0.0,
                "category": "hole",
                "owner": _get_name(hole) or "hole",
            }))
    elif outer_left is not None:
        dx = round(max(0.0, hx - outer_left), 3)
        if dx > 0:
            anns.append(Annotation.parse_obj({
                "type": "dimension",
                "from": (outer_left, hy),
                "to": (hx, hy),
                "text": f"X {dx}",
                "offset": 6.0,
                "angle": 0.0,
                "category": "hole",
                "owner": _get_name(hole) or "hole",
            }))

    # Vertical offsets
    if h_name == "hole_top" and outer_top is not None:
        dy = round(max(0.0, outer_top - hy), 3)
        if dy > 0:
            anns.append(Annotation.parse_obj({
                "type": "dimension",
                "from": (hx, hy),
                "to": (hx, outer_top),
                "text": f"Y {dy}",
                "offset": 6.0,
                "angle": 90.0,
                "category": "hole",
                "owner": _get_name(hole) or "hole",
            }))
    if h_name == "hole_bottom" and outer_bot is not None:
        dyb = round(max(0.0, hy - outer_bot), 3)
        if dyb > 0:
            anns.append(Annotation.parse_obj({
                "type": "dimension",
                "from": (hx, outer_bot),
                "to": (hx, hy),
                "text": f"Y {dyb}",
                "offset": 6.0,
                "angle": 90.0,
                "category": "hole",
                "owner": _get_name(hole) or "hole",
            }))

    return anns

def generate_annotations(frames: List[Any], cutouts: List[Any], holes: List[Any]) -> Dict[str, List[Annotation]]:
    """Generate annotations for frames, cutouts, and holes.

    - Each frame gets its own dimension.
    - Even frames -> bottom-left, Odd frames -> top-right.
    - Offsets automatically adjusted so dimension lines sit outside all frames.
    """

    # grouped annotations by logical category
    annotations: Dict[str, List[Annotation]] = {
        "frames": [],
        "cutouts": [],
        "glass_cut": [],
        "center_handle": [],
        "keybox": [],
        "holes": [],
        "frame_gaps": [],
        "other": [],
    }

    # Cached frame lookups so other parts (center handle, keybox, holes)
    # can reuse the same frames without repeating search logic.

    left_frame = None
    outer_frame = None
    inner_frame = None
    left_outer_frame = None
    if frames:
        # prefer explicit left_inner and outer frames by name
        for fr in frames:
            nm = (_get_name(fr) or "").strip().lower()
            if nm == "left_inner":
                left_frame = fr
            elif nm == "left_outer":
                left_outer_frame = fr
            elif nm == "inner":
                inner_frame = fr
            elif nm == "outer":
                outer_frame = fr
        # fallback: if left_inner absent, prefer 'inner'
        if left_frame is None:
            left_frame = next((fr for fr in frames if ((_get_name(fr) or "").strip().lower() == "inner")), None)

    # --- 🧩 Handle frames ---
    if frames:
        # Fixed clearance (distance from extreme outer bbox to annotation lines).
        clearance = 5.0

        for i, f in enumerate(frames):
            placement = "bottom_left" if (i % 2) == 0 else "top_right"
            # Place width/height annotations for this frame using a fixed
            # clearance so outer annotation gaps are consistent.
            annotations["frames"].extend(_frame_dimensions_annotations(
                f,
                offset_base=clearance,
                placement=placement,
            ))

    # --- 🧩 Existing logic for cutouts ---
    for i, c in enumerate(cutouts or []):
        offs = 6.0 + i * 3.0
        name = (_get_name(c) or "").strip().lower()
        # determine nearest left frame for this specific cutout (prefer local nearest)
        pts_c = _get_points(c) or []
        c_min_x = None
        if pts_c:
            c_min_x = min(p[0] for p in pts_c)

        left_ref_for_cutout = None
        if frames and c_min_x is not None:
            # prefer a frame that horizontally contains the cutout (tightest fit)
            # — this avoids measuring large irrelevant gaps to distant frames
            # (for example, a right-side glass cutout shouldn't measure to the far-left frame).
            c_max_x = max(p[0] for p in pts_c)
            containing = []
            left_candidates = []
            for fr in frames:
                fps = _get_points(fr) or []
                if not fps:
                    continue
                fr_min_x = min(p[0] for p in fps)
                fr_max_x = max(p[0] for p in fps)
                # collect frames that fully contain the cutout horizontally
                if fr_min_x <= c_min_x and fr_max_x >= c_max_x:
                    containing.append((fr_max_x - fr_min_x, fr))
                # fallback candidates: frames whose right edge lies to the left of cutout
                if fr_max_x <= c_min_x:
                    left_candidates.append((fr_max_x, fr))
            if containing:
                # pick the tightest containing frame (smallest width)
                left_ref_for_cutout = min(containing, key=lambda t: t[0])[1]
            elif left_candidates:
                # otherwise pick the nearest frame to the left
                left_ref_for_cutout = max(left_candidates, key=lambda t: t[0])[1]

        # glass_cut and named variants (glass_*) get specialized annotations plus
        # standard W/H dims. For glass gaps we need to choose the correct inner
        # frame (there may be two 'inner' frames for double doors). Prefer an
        # inner frame that actually contains the cutout horizontally (tightest
        # fit); fall back to the global inner_frame or left_frame.
        if name == "glass_cut" or name.startswith("glass_"):
            chosen_inner = None
            try:
                c_pts = _get_points(c) or []
                if c_pts:
                    c_min_x = min(p[0] for p in c_pts)
                    c_max_x = max(p[0] for p in c_pts)
                    # prefer the provided inner_frame if it contains the cutout
                    if inner_frame is not None:
                        ipts = _get_points(inner_frame) or []
                        if ipts:
                            if min(p[0] for p in ipts) <= c_min_x and max(p[0] for p in ipts) >= c_max_x:
                                chosen_inner = inner_frame
                    # else try the left_frame (commonly left_inner) if it contains
                    if chosen_inner is None and left_frame is not None:
                        lf_pts = _get_points(left_frame) or []
                        if lf_pts and min(p[0] for p in lf_pts) <= c_min_x and max(p[0] for p in lf_pts) >= c_max_x:
                            chosen_inner = left_frame
            except Exception:
                chosen_inner = None

            if chosen_inner is None:
                # fallback to whichever inner we have available
                chosen_inner = inner_frame or left_frame

            annotations["glass_cut"].extend(_glass_cut_annotations(c, chosen_inner, outer_frame, offset_base=offs))
            # include only W/H dims under 'cutouts' (no left-gap)
            annotations["cutouts"].extend(_cutout_dimensions_annotations(c, None, offset_base=offs))
        elif name in ("center_handle", "keybox"):
            # center_handle and keybox have their own specialized annotations; avoid duplicating the
            # left-gap in the generic cutouts group by not passing a left reference here.
            annotations["cutouts"].extend(_cutout_dimensions_annotations(c, None, offset_base=offs))
        else:
            # pass local left ref (or global left_frame fallback) so other cutouts get correct left-gap
            annotations["cutouts"].extend(_cutout_dimensions_annotations(c, left_ref_for_cutout or left_frame, offset_base=offs))

    # --- 🧩 Extra measurements for center handle ---
    center_cut = next((c for c in (cutouts or []) if (_get_name(c) or "").strip().lower() == "center_handle"), None)
    if center_cut:
        # pass the full frames list so the center-handle helper can
        # determine the nearest left reference when an explicit left
        # frame isn't configured.
        annotations["center_handle"].extend(_center_handle_annotations(center_cut, frames, outer_frame))

    # --- 🧩 Existing logic for holes ---
    for i, h in enumerate(holes or []):
        offs = 4.0 + i * 2.0
        annotations["holes"].extend(_hole_dimensions_annotations(h, offset_base=offs))
        # use inner_frame for horizontal offset and outer_frame for vertical offsets
        annotations["holes"].extend(_hole_offset_annotations(h, frames, inner_frame, outer_frame))

    # --- 🧩 Keybox extra measurements ---
    # Find a 'keybox' cutout and annotate horizontal gaps to nearest frames
    # (left/right) and vertical gap from outer bottom to keybox bottom.
    key_cut = next((c for c in (cutouts or []) if (_get_name(c) or "").strip().lower() == "keybox"), None)
    if key_cut:
        annotations["keybox"].extend(_keybox_annotations(key_cut, frames, outer_frame))

    # --- 🧩 Frame gap annotations (your original logic) ---
    if frames and len(frames) >= 2:
        annotations["frame_gaps"].extend(_frame_gap_annotation(frames[0], frames[1], offset_base=6.0))
    if frames and len(frames) >= 4:
        annotations["frame_gaps"].extend(_frame_gap_annotation(frames[2], frames[3], offset_base=6.0))

    return annotations
