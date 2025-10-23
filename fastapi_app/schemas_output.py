from pydantic import BaseModel, Field
from typing import List, Optional, Tuple, Literal


# ---------- Supporting Models ----------

class Metadata(BaseModel):
    label: str
    file_name: str
    width: float
    height: float
    rotated: bool = False
    is_annotation_required: bool = True
    offset: Tuple[float, float] = (0.0, 0.0)


class Frame(BaseModel):
    name: str
    layer: str
    points: List[Tuple[float, float]]
    width: float
    height: float


class Cutout(BaseModel):
    name: str
    layer: str
    points: List[Tuple[float, float]]


class Hole(BaseModel):
    name: str
    layer: str
    center: Tuple[float, float]
    radius: float


class Annotation(BaseModel):
    type: Literal["dimension", "note", "leader"]
    from_: Tuple[float, float] = Field(..., alias="from")
    to: Tuple[float, float]
    text: str
    offset: float = 0.0
    angle: float = 0.0
    text_offset: Optional[float] = None


class Label(BaseModel):
    type: Literal["center_label", "corner_label", "note"]
    text: str
    position: str  # "center", "top_left", etc.


# ---------- Geometry Collection ----------

class Geometry(BaseModel):
    frames: List[Frame] = []
    cutouts: List[Cutout] = []
    holes: List[Hole] = []
    annotations: List[Annotation] = []
    labels: List[Label] = []


# ---------- Main Output Schema ----------

class SchemasOutput(BaseModel):
    door_category: Literal["Single", "Double"]
    door_type: Literal["Normal", "Fire"]
    option: Optional[Literal["Option1", "Option2", "Option3"]] = None
    metadata: Metadata
    geometry: Geometry
