from typing import List, Any
from fastapi_app.schemas_output import Label


def create_labels(request) -> List[Label]:
    """Create only label objects from the request metadata.

    Returns a list[Label]. Annotation/dimension generation is handled in
    `geometry.generate_annotations`.
    """
    labels: List[Label] = []

    text = getattr(request.metadata, "label", "") or getattr(request.metadata, "file_name", "")
    if text:
        labels.append(Label(type="center_label", text=text, position="center"))

    file_name = getattr(request.metadata, "file_name", "")
    if file_name and file_name != text:
        labels.append(Label(type="corner_label", text=file_name, position="top_left"))

    return labels


# Backwards compatibility: keep add_labels name but return labels only.
def add_labels(request) -> List[Label]:
    return create_labels(request)
