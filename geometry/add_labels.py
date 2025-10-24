from fastapi_app.schemas_output import Label


def add_labels(request):
    """Add central label with door name or file."""
    text = getattr(request.metadata, "label", "") or getattr(request.metadata, "file_name", "")
    return [Label(type="center_label", text=text, position="center")]
