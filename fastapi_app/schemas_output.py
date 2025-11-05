from pydantic import BaseModel, Field
from typing import List, Optional, Tuple, Literal, Dict


# ---------- Supporting Models ----------

class Metadata(BaseModel):
    label: str
    file_name: str
    width: float
    height: float
    rotated: bool = False
    is_annotation_required: bool = True
    offset: Tuple[float, float] = (0.0, 0.0)
    hole_offset: str = ""


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
    # optional classification to help group and identify annotations
    category: Optional[str] = None
    owner: Optional[str] = None


class Label(BaseModel):
    type: Literal["center_label", "corner_label", "note"]
    text: str
    position: str  # "center", "top_left", etc.


# ---------- Geometry Collection ----------

class Geometry(BaseModel):
    frames: List[Frame] = []
    cutouts: List[Cutout] = []
    holes: List[Hole] = []
    # annotations are grouped by logical category (e.g. "frames", "glass_cut",
    # "keybox", "holes", "frame_gaps"). Each value is a list of Annotation
    # objects belonging to that category. This makes it easy for consumers to
    # present annotations grouped under headings.
    annotations: Dict[str, List[Annotation]] = {}
    labels: List[Label] = []


# ---------- Main Output Schema ----------

class SchemasOutput(BaseModel):
    door_category: Literal["Single", "Double"]
    door_type: Literal["Normal", "Fire"]
    # Allow Option4 and Option5 as requested by UI tokens (standard_double -> Option4, fourglass -> Option5)
    option: Optional[Literal["Option1", "Option2", "Option3", "Option4", "Option5"]] = None
    metadata: Metadata
    geometry: Geometry


# ---------- Batch / Bin manifest models ----------
class BinDoor(BaseModel):
    file_name: Optional[str]
    # request stored as a generic dict to avoid tight coupling; callers may
    # pass a DoorDXFRequest.dict() or raw dict.
    request: Optional[dict] = None
    placement: Tuple[float, float] = (0.0, 0.0)
    rotated: bool = False


class BinManifest(BaseModel):
    sheet_width: float
    sheet_height: float
    doors: List[BinDoor] = []


# ---------- Detailed bin output (original + transformed) ----------
class BinDoorTransformed(BaseModel):
    """Per-door entry for a transformed-bin JSON.

    - file_name: original filename (if available)
    - original_request: the original DoorDXFRequest serialized as a dict (if present)
    - placement: packer placement (x, y)
    - rotated: whether the door was rotated for packing
    - transformed: the computed SchemasOutput (frames, cutouts, holes, metadata)
    """
    file_name: Optional[str]
    original_request: Optional[dict] = None
    placement: Tuple[float, float] = (0.0, 0.0)
    rotated: bool = False
    # The transformed SchemasOutput (geometry normalized and placed for packing)
    transformed: Optional[SchemasOutput] = None
    # The original SchemasOutput before any packer placement/rotation is applied.
    # This shows the door geometry in its initial local coordinate system and
    # can be used to verify how offsets/rotations change coordinates.
    original_response: Optional[SchemasOutput] = None


class BinTransformedManifest(BaseModel):
    """Manifest for a single bin containing original inputs and computed/transformed outputs
    for every door. This can be written to JSON and later used to generate DXFs directly from
    the transformed geometry without re-running the geometry pipeline.
    """
    sheet_width: float
    sheet_height: float
    doors: List[BinDoorTransformed] = []
