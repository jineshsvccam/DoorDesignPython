from typing import Tuple, List


def apply_transform(point_sets: List[List[tuple]], rotated: bool, offset: Tuple[float, float], outer_height: float):
    """Apply translation and rotation to all point sets."""
    all_x = [p[0] for pts in point_sets for p in pts]
    all_y = [p[1] for pts in point_sets for p in pts]
    min_x, min_y = min(all_x), min(all_y)
    translate_x = max(0.0, -min_x)
    translate_y = max(0.0, -min_y)

    def transform(pt):
        x, y = pt
        if not rotated:
            return (offset[0] + translate_x + x, offset[1] + translate_y + y)
        return (offset[0] + translate_x + (outer_height - y), offset[1] + translate_y + x)

    transformed_sets = [[transform(p) for p in pts] for pts in point_sets]
    return transformed_sets, (translate_x, translate_y)
