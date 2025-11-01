from typing import List, Tuple, Any
from fastapi_app.schemas_output import Annotation


def _bbox(points: List[Tuple[float, float]]):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


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
    })

    height_ann = Annotation.parse_obj({
        "type": "dimension",
        "from": h_from,
        "to": h_to,
        "text": h_text,
        "offset": h_offset,
        "angle": h_angle,
    })

    return [width_ann, height_ann]


def _cutout_dimensions_annotations(cutout: Any, offset_base: float = 6.0):
    pts = cutout.points
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
    })

    height_ann = Annotation.parse_obj({
        "type": "dimension",
        "from": h_from,
        "to": h_to,
        "text": h_text,
        "offset": -offset_base,
        "angle": 90.0,
    })

    return [width_ann, height_ann]


def _hole_dimensions_annotations(hole: Any, offset_base: float = 4.0):
    cx, cy = hole.center
    dia = round(hole.radius * 2.0, 3)

    p_from = (cx, cy)
    p_to = (cx + hole.radius * 1.5, cy)
    text = f"Ø{dia}"

    ann = Annotation.parse_obj({
        "type": "dimension",
        "from": p_from,
        "to": p_to,
        "text": text,
        "offset": offset_base,
        "angle": 0.0,
    })
    return [ann]


def _frame_gap_annotation(frame1: Any, frame2: Any, offset_base: float = 6.0):
    """Create an annotation that measures the gap between two frame bboxes.

    Returns a list with zero or one Annotation (empty if frames overlap).
    """
    min_x1, min_y1, max_x1, max_y1 = _bbox(frame1.points)
    min_x2, min_y2, max_x2, max_y2 = _bbox(frame2.points)

    # Compute horizontal and vertical separation (non-negative). If both are zero,
    # rectangles intersect/overlap and there is no gap annotation needed.
    dx = max(min_x2 - max_x1, min_x1 - max_x2, 0.0)
    dy = max(min_y2 - max_y1, min_y1 - max_y2, 0.0)

    if dx == 0.0 and dy == 0.0:
        # Rectangles overlap or touch — no gap to annotate
        return []

    # Choose the primary gap direction (shorter separation axis preferred)
    ann = None
    if dx <= dy:
        # horizontal gap preferred
        # pick x positions of nearest edges
        if min_x1 < min_x2:
            from_x = max_x1
            to_x = min_x2
            # y: prefer actual vertical overlap if exists, else midpoint between centers
            overlap_y_min = max(min_y1, min_y2)
            overlap_y_max = min(max_y1, max_y2)
            if overlap_y_max > overlap_y_min:
                y = (overlap_y_min + overlap_y_max) / 2.0
            else:
                y = ((min_y1 + max_y1) / 2.0 + (min_y2 + max_y2) / 2.0) / 2.0
            from_pt = (from_x, y)
            to_pt = (to_x, y)
        else:
            from_x = max_x2
            to_x = min_x1
            overlap_y_min = max(min_y1, min_y2)
            overlap_y_max = min(max_y1, max_y2)
            if overlap_y_max > overlap_y_min:
                y = (overlap_y_min + overlap_y_max) / 2.0
            else:
                y = ((min_y1 + max_y1) / 2.0 + (min_y2 + max_y2) / 2.0) / 2.0
            from_pt = (from_x, y)
            to_pt = (to_x, y)

        gap = round(max(0.0, to_pt[0] - from_pt[0]), 3)
        if gap <= 0:
            return []
        ann = Annotation.parse_obj({
            "type": "dimension",
            "from": from_pt,
            "to": to_pt,
            "text": f"G {gap}",
            "offset": offset_base,
            "angle": 0.0,
        })
    else:
        # vertical gap preferred
        if min_y1 < min_y2:
            from_y = max_y1
            to_y = min_y2
            overlap_x_min = max(min_x1, min_x2)
            overlap_x_max = min(max_x1, max_x2)
            if overlap_x_max > overlap_x_min:
                x = (overlap_x_min + overlap_x_max) / 2.0
            else:
                x = ((min_x1 + max_x1) / 2.0 + (min_x2 + max_x2) / 2.0) / 2.0
            from_pt = (x, from_y)
            to_pt = (x, to_y)
        else:
            from_y = max_y2
            to_y = min_y1
            overlap_x_min = max(min_x1, min_x2)
            overlap_x_max = min(max_x1, max_x2)
            if overlap_x_max > overlap_x_min:
                x = (overlap_x_min + overlap_x_max) / 2.0
            else:
                x = ((min_x1 + max_x1) / 2.0 + (min_x2 + max_x2) / 2.0) / 2.0
            from_pt = (x, from_y)
            to_pt = (x, to_y)

        gap = round(max(0.0, to_pt[1] - from_pt[1]), 3)
        if gap <= 0:
            return []
        ann = Annotation.parse_obj({
            "type": "dimension",
            "from": from_pt,
            "to": to_pt,
            "text": f"G {gap}",
            "offset": offset_base,
            "angle": 90.0,
        })

    return [ann] if ann is not None else []


def generate_annotations(frames: List[Any], cutouts: List[Any], holes: List[Any]) -> List[Annotation]:
    """Generate a flattened list of Annotation objects from provided geometry lists.

    This function intentionally uses simple bbox-based dimensions. For more
    sophisticated dimensioning (rotated frames, ledgers, etc.) extend the
    helper functions accordingly.
    """
    annotations: List[Annotation] = []

    for i, f in enumerate(frames or []):
        offs = 8.0 + i * 4.0
        # Alternate placement clockwise: even frames -> bottom_left, odd -> top_right
        placement = "bottom_left" if (i % 2) == 0 else "top_right"
        annotations.extend(_frame_dimensions_annotations(f, offset_base=offs, placement=placement))

    for i, c in enumerate(cutouts or []):
        offs = 6.0 + i * 3.0
        annotations.extend(_cutout_dimensions_annotations(c, offset_base=offs))

    for i, h in enumerate(holes or []):
        offs = 4.0 + i * 2.0
        annotations.extend(_hole_dimensions_annotations(h, offset_base=offs))

    # Annotate gaps between frame pairs: (0,1) and (2,3) if available
    if frames and len(frames) >= 2:
        annotations.extend(_frame_gap_annotation(frames[0], frames[1], offset_base=6.0))
    if frames and len(frames) >= 4:
        annotations.extend(_frame_gap_annotation(frames[2], frames[3], offset_base=6.0))

    return annotations
