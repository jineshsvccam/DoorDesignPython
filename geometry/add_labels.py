from typing import List, Any
from fastapi_app.schemas_output import Label


def create_labels(request,metadata) -> List[Label]:
    """Create only label objects from the request metadata.

    Returns a list[Label]. Annotation/dimension generation is handled in
    `geometry.generate_annotations`.
    """
    labels: List[Label] = []

    # metadata values used for computing placement coordinates
    offs = getattr(metadata, "offset", (0.0, 0.0)) or (0.0, 0.0)
    width = float(getattr(metadata, "width", 0.0) or 0.0)
    height = float(getattr(metadata, "height", 0.0) or 0.0)

    # prefer defaults.dim_text_height when available
    defaults = getattr(request, "defaults", None)
    dim_text_height = getattr(defaults, "dim_text_height", 8.0) if defaults is not None else 8.0

    # center label: originally centered; place at right border and rotate if you prefer
    text = getattr(metadata, "label", "") or getattr(metadata, "file_name", "")
    if text:
        # keep the centered coordinates available if you need them later
        center_pos = (offs[0] + width / 2.0, offs[1] + height / 2.0)
        # place near the right border and vertically centered
    # leave a 50 mm gap from the right border to avoid overlap with frame
        right_pos = (offs[0] + max(width - 50.0, 10.0), offs[1] + height / 2.0)
        labels.append(
            Label(
                type="center_label",
                text=text,
                # use explicit coordinates so draw_label will place this directly
                position=right_pos,
                # align right/center vertically so text sits against the border
                align="MIDDLE_RIGHT",
                height=dim_text_height,
                # rotate 90 degrees to run text vertical (clockwise)
                rotation=90.0,
                layer="DIMENSIONS",
                show_dimensions=True,
            )
        )

    # corner label (file name) at top-left by default (explicit coordinates)
    file_name = getattr(request.metadata, "file_name", "")
    if file_name and file_name != text:
        top_left = (offs[0] + 10.0, offs[1] + max(height - 10.0, 10.0))
        # labels.append(
        #     Label(
        #         type="corner_label",
        #         text=file_name,
        #         position=top_left,
        #         align="TOP_LEFT",
        #         height=dim_text_height,
        #         layer="DIMENSIONS",
        #     )
        # )

    return labels


# Backwards compatibility: keep add_labels name but return labels only.
def add_labels(request) -> List[Label]:
    return create_labels(request,request.metadata)
