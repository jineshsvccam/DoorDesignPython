from pydantic import BaseModel, Field
from typing import Optional
from fastapi_app.schemas_output import Metadata as OutputMetadata


class DefaultInfo(BaseModel):
    left_side_allowance_width: float = 25.0
    right_side_allowance_width: float = 25.0
    left_side_allowance_height: float = 25.0
    right_side_allowance_height: float = 25.0
    door_minus_measurement_width: float = 68.0
    door_minus_measurement_height: float = 70.0
    bending_width: float = 31.0
    bending_height: float = 24.0
    # Visual and geometry defaults
    bend_adjust: float = 12.0
    box_gap: float = 30.0
    box_width: float = 22.0
    box_height: float = 112.0
    # Glass visual defaults
    glass_corner_radius: float = 20.0
    glass_segments: int = 8
    circle_radius: float = 5.0
    left_circle_offset: float = 40.0
    top_circle_offset: float = 150.0
    dim_text_height: float = 8.0
    dim_arrow_size: float = 6.0
    horizontal_dim_visual_offset: float = 20.0
    vertical_dim_visual_offset: float = 40.0
    # Keybox defaults (width x height in points, bottom offset from inner bottom)
    keybox_width: float = 70.0
    keybox_height: float = 40.0
    keybox_bottom_offset: float = 50.0
    # Fire door glass margins (defaults)
    fire_glass_lr_margin: float = 190.0
    fire_glass_top_margin: float = 170.0
    fire_glass_bottom_margin: float = 240.0


class DoorInfo(BaseModel):
    category: str
    type: str
    option: Optional[str] = None
    hole_offset: str
    default_allowance: str


class DimensionInfo(BaseModel):
    width_measurement: float
    height_measurement: float
    left_side_allowance_width: float
    right_side_allowance_width: float
    top_side_allowance_height: float
    bottom_side_allowance_height: float


class DoorDXFRequest(BaseModel):
    mode: str
    door: DoorInfo
    dimensions: DimensionInfo
    metadata: OutputMetadata
    defaults: DefaultInfo = Field(default_factory=DefaultInfo)
