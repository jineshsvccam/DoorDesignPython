from typing import Tuple, List


def apply_transform(point_sets: List[List[tuple]], rotated: bool, offset: Tuple[float, float], outer_height: float):
    """Apply translation and rotation to all point sets."""
    all_x = [p[0] for pts in point_sets for p in pts]
    all_y = [p[1] for pts in point_sets for p in pts]
    min_x, min_y = min(all_x), min(all_y)
    translate_x = max(0.0, -min_x)
    translate_y = max(0.0, -min_y)
    # NOTE: do not apply the external `offset` here. We only apply a local
    # translation/rotation to make all point-sets non-negative. The external
    # placement offset (packer position) should be applied by the caller or
    # represented via the returned metadata.offset. Applying the external
    # offset here and then normalizing later would cancel it out.
    def transform(pt):
        x, y = pt
        if not rotated:
            return (translate_x + x, translate_y + y)
        # rotated: rotate around origin then apply the same translate
        return (translate_x + (outer_height - y), translate_y + x)

    transformed_sets = [[transform(p) for p in pts] for pts in point_sets]
    return transformed_sets, (translate_x, translate_y)
