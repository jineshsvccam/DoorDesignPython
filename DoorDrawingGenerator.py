from __future__ import annotations

"""DoorDrawingGenerator.py

Generate DXF files for door designs with annotated dimensions and cutouts.
Uses ezdxf for DXF creation.
"""

from ezdxf.filemanagement import new
from typing import Tuple, Optional, Union
from ezdxf.document import Drawing
from ezdxf.layouts.layout import Modelspace
from geometry.door_geometry import compute_door_geometry
from fastapi_app.schemas_input import DoorDXFRequest

class DoorDrawingGenerator:
    """
    Static class for generating door DXF files with dimensions and cutouts.
    """
    # Visual/geometry defaults moved to DefaultInfo in schemas_input

    @staticmethod
    def generate_door_dxf(
        request: DoorDXFRequest,  # expecting DoorDXFRequest pydantic model
        file_name: Optional[str] = None,
        label_name: Optional[str] = None,
        isannotationRequired: bool = True,
        offset: Tuple[float, float] = (0.0, 0.0),
        doc: Optional[Drawing] = None,
        msp: Optional[Modelspace] = None,
        save_file: bool = True,
        rotated: bool = False
    ) -> None:
        """Generate a DXF file for the door with annotations.

        The request is a `DoorDXFRequest` model. If `doc`/`msp` are not provided,
        a new ezdxf document will be created. If `save_file` is True and
        `file_name` is provided the DXF will be saved.
        """
        if doc is None and (file_name is None or not file_name.lower().endswith('.dxf')):
            raise ValueError("Output file name must end with .dxf")

        if doc is None or msp is None:
            doc = new(dxfversion="R2010")
            doc.layers.new(name="CUT", dxfattribs={"color": 4})
            doc.layers.new(name="DIMENSIONS", dxfattribs={"color": 1})
            msp = doc.modelspace()

        # Compute geometry and load visual defaults
        schema = compute_door_geometry(request, rotated=rotated, offset=offset)
        defaults = request.defaults
        dim_text_height = getattr(defaults, "dim_text_height", 8.0)
        dim_arrow_size = getattr(defaults, "dim_arrow_size", 6.0)
        horiz_dim_offset = getattr(defaults, "horizontal_dim_visual_offset", 20.0)
        vert_dim_offset = getattr(defaults, "vertical_dim_visual_offset", 40.0)

        # Determine placement offset from metadata (frames are returned
        # normalized to local origin by compute_door_geometry). Apply the
        # metadata offset when drawing so the DXF entities appear at the
        # packer placement coordinates.
        offs = getattr(schema.metadata, "offset", (0.0, 0.0)) or (0.0, 0.0)
        def _t(p):
            return (float(p[0]) + offs[0], float(p[1]) + offs[1])

        # Draw frames
        for frame in schema.geometry.frames:
            pts = [_t(p) for p in frame.points]
            msp.add_lwpolyline(pts, dxfattribs={"layer": frame.layer})

        # Draw cutouts (apply metadata offset)
        for cut in schema.geometry.cutouts:
            pts = [_t(p) for p in cut.points]
            msp.add_lwpolyline(pts, dxfattribs={"layer": cut.layer})

        # Draw holes (apply metadata offset)
        for hole in schema.geometry.holes:
            center = _t(hole.center)
            msp.add_circle(center, hole.radius, dxfattribs={"layer": hole.layer})

        # Draw annotations from schema.geometry.annotations (dimensions, notes, leaders)
        is_schema_annotation_enabled = getattr(schema.metadata, "is_annotation_required", True) and isannotationRequired
        for ann in getattr(schema.geometry, "annotations", []) or []:
            try:
                atype = getattr(ann, "type", "dimension")
                if atype == "dimension":
                    # Draw dimension directly from coordinates in the schema JSON.
                    raw_from = getattr(ann, "from_", None)
                    if raw_from is None:
                        raw_from = getattr(ann, "from", None)
                    if raw_from is None:
                        raw_from = (0.0, 0.0)
                    p1 = _t(raw_from)

                    raw_to = getattr(ann, "to", None)
                    if raw_to is None:
                        raw_to = (0.0, 0.0)
                    p2 = _t(raw_to)
                    text = getattr(ann, "text", "")
                    dim_offset = getattr(ann, "offset", None)
                    angle = int(getattr(ann, "angle", 0) or 0)
                    text_offset = getattr(ann, "text_offset", None)

                    # Determine offsets (fallback to visual defaults)
                    if dim_offset is None:
                        dim_offset = horiz_dim_offset if angle == 0 else vert_dim_offset
                    if text_offset is None:
                        text_offset = dim_text_height * 2

                    # Compute a parallel (dimension) line shifted by offset from the measured edge
                    if angle == 0:
                        # horizontal measured edge: shift in Y
                        dim_p1 = (p1[0], p1[1] + dim_offset)
                        dim_p2 = (p2[0], p2[1] + dim_offset)
                        text_pos = ((p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0 + dim_offset + text_offset)
                    else:
                        # vertical measured edge: shift in X
                        dim_p1 = (p1[0] + dim_offset, p1[1])
                        dim_p2 = (p2[0] + dim_offset, p2[1])
                        text_pos = ((p1[0] + p2[0]) / 2.0 + dim_offset + text_offset, (p1[1] + p2[1]) / 2.0)

                    # Draw the dimension line
                    try:
                        msp.add_line(dim_p1, dim_p2, dxfattribs={"layer": "DIMENSIONS"})
                        # Optional short extension lines from measured feature to dimension line
                        ext_len = 2.0
                        if angle == 0:
                            msp.add_line((p1[0], p1[1]), (p1[0], p1[1] + dim_offset - ext_len), dxfattribs={"layer": "DIMENSIONS"})
                            msp.add_line((p2[0], p2[1]), (p2[0], p2[1] + dim_offset - ext_len), dxfattribs={"layer": "DIMENSIONS"})
                        else:
                            msp.add_line((p1[0], p1[1]), (p1[0] + dim_offset - ext_len, p1[1]), dxfattribs={"layer": "DIMENSIONS"})
                            msp.add_line((p2[0], p2[1]), (p2[0] + dim_offset - ext_len, p2[1]), dxfattribs={"layer": "DIMENSIONS"})

                        # Add text at computed location
                        txt = msp.add_text(text, dxfattribs={"layer": "DIMENSIONS", "height": dim_text_height, "style": "Standard"})
                        txt.dxf.insert = text_pos
                        # Horizontal dims centered, vertical dims left aligned
                        txt.dxf.halign = 2 if angle == 0 else 0
                        txt.dxf.valign = 2
                    except Exception:
                        # Fallback: place plain text at midpoint of measured feature
                        mid = ((p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0)
                        txt = msp.add_text(text, dxfattribs={"layer": "DIMENSIONS", "height": dim_text_height, "style": "Standard"})
                        txt.dxf.insert = (mid[0], mid[1] + text_offset if angle == 0 else mid[1])
                        txt.dxf.halign = 2 if angle == 0 else 0
                        txt.dxf.valign = 2
                elif atype == "note":
                    # place note text at the `to` coordinate if present
                    raw_to = getattr(ann, "to", None)
                    if raw_to is None:
                        raw_to = getattr(ann, "from", None)
                    if raw_to is None:
                        raw_to = (0.0, 0.0)
                    pos = _t(raw_to)
                    txt = msp.add_text(getattr(ann, "text", ""), dxfattribs={"layer": "DIMENSIONS", "height": dim_text_height, "style": "Standard"})
                    txt.dxf.insert = pos
                    txt.dxf.halign = 0
                    txt.dxf.valign = 2
                elif atype == "leader":
                    raw_from = getattr(ann, "from_", None)
                    if raw_from is None:
                        raw_from = getattr(ann, "from", None)
                    if raw_from is None:
                        raw_from = (0.0, 0.0)
                    p_from = _t(raw_from)

                    raw_to = getattr(ann, "to", None)
                    if raw_to is None:
                        raw_to = (0.0, 0.0)
                    p_to = _t(raw_to)
                    # simple leader: a line from from->to and the text at `to`
                    msp.add_line(p_from, p_to, dxfattribs={"layer": "DIMENSIONS"})
                    txt = msp.add_text(getattr(ann, "text", ""), dxfattribs={"layer": "DIMENSIONS", "height": dim_text_height, "style": "Standard"})
                    txt.dxf.insert = p_to
                    txt.dxf.halign = 0
                    txt.dxf.valign = 2
            except Exception:
                # keep drawing even if a single annotation fails
                continue

        # Draw labels from schema.geometry.labels
        # Disabled: comment out placement loop and handle one label later if needed
        # for label in getattr(schema.geometry, "labels", []) or []:
        #     try:
        #         ltype = getattr(label, "type", "center_label")
        #         ltext = getattr(label, "text", "")
        #         if ltype == "center_label":
        #             # place centered text inside the door; build simple transform to account for metadata offset
        #             offs = getattr(schema.metadata, "offset", (0.0, 0.0))
        #             transform = lambda p: (p[0] + offs[0], p[1] + offs[1])
        #             DoorDrawingGenerator.add_center_label(
        #                 msp,
        #                 transform,
        #                 getattr(schema.metadata, "width", 0.0),
        #                 getattr(schema.metadata, "height", 0.0),
        #                 ltext,
        #                 rotated,
        #                 dim_text_height=dim_text_height,
        #             )
        #         else:
        #             # Generic placement for corner or note labels at top-left
        #             offs = getattr(schema.metadata, "offset", (0.0, 0.0))
        #             top_left = (offs[0] + 10.0, offs[1] + max(getattr(schema.metadata, "height", 0.0) - 10.0, 10.0))
        #             txt = msp.add_text(ltext, dxfattribs={"layer": "DIMENSIONS", "height": dim_text_height, "style": "Standard"})
        #             txt.dxf.insert = top_left
        #             txt.dxf.halign = 0
        #             txt.dxf.valign = 2
        #     except Exception:
        #         continue

        # Save file only if requested
        if save_file and file_name is not None:
            doc.saveas(file_name)
            print(f"DXF file '{file_name}' created successfully.")

    @staticmethod
    def add_dimension_line(
        msp,
        p1: Tuple[float, float],
        p2: Tuple[float, float],
        text: str,
        offset: Optional[float] = None,
        angle: int = 0,
        text_offset: Optional[float] = None,
        arrow_size: Optional[float] = None,
        isannotationRequired: bool = True,
        dim_text_height: float = 8.0,
        dim_arrow_size: float = 6.0,
        horiz_dim_offset: float = 20.0,
        vert_dim_offset: float = 40.0,
    ) -> None:
        """Draw a dimension line with optional annotation.

        If `isannotationRequired` is False, the method returns immediately.
        """
        if not isannotationRequired:
            return
        if offset is None:
            offset = horiz_dim_offset if angle == 0 else vert_dim_offset
        if text_offset is None:
            text_offset = dim_text_height * 2
        if arrow_size is None:
            arrow_size = dim_arrow_size
    # Calculate a base point for the dimension line offset in the perpendicular
    # direction from the feature (p1->p2). For axis-aligned edges this is
    # simplified to a +/- offset in X or Y.

    # midpoint
        mid_x = (p1[0] + p2[0]) / 2.0
        mid_y = (p1[1] + p2[1]) / 2.0
        # direction normal depending on angle
        if angle == 0:
            # horizontal edge: normal points in +Y (up). offset positive moves dim up.
            base = (mid_x, mid_y + offset)
        else:
            # vertical edge: normal points in +X (right). offset positive moves dim right.
            base = (mid_x + offset, mid_y)

        try:
            dim = msp.add_linear_dim(base=base, p1=p1, p2=p2, angle=angle, dxfattribs={"layer": "DIMENSIONS"})
            dim.render()
        except Exception:
            txt = msp.add_text(text, dxfattribs={"layer": "DIMENSIONS", "height": dim_text_height, "style": "Standard"})
            if angle == 0:
                txt.dxf.insert = (mid_x, mid_y + offset + text_offset)
                txt.dxf.halign = 2
                txt.dxf.valign = 2
            else:
                txt.dxf.insert = (mid_x + offset + text_offset, mid_y)
                txt.dxf.halign = 0
                txt.dxf.valign = 2
            return

    # Place the text near the dimension line. If direct override isn't
    # supported by the dim object, add a separate text entity.
        try:
            # calculate text insert point
            if angle == 0:
                text_insert = (mid_x, mid_y + offset + (text_offset if text_offset is not None else dim_text_height * 2))
                halign = 2
            else:
                text_insert = (mid_x + offset + (text_offset if text_offset is not None else dim_text_height * 2), mid_y)
                halign = 0

            txt = msp.add_text(text, dxfattribs={"layer": "DIMENSIONS", "height": dim_text_height, "style": "Standard"})
            txt.dxf.insert = text_insert
            txt.dxf.halign = halign
            txt.dxf.valign = 2
        except Exception:
            pass

    @staticmethod
    def add_center_label(msp, transform_point_func, outer_width: float, outer_height: float, source_label: Optional[str], rotated: bool, dim_text_height: float = 8.0) -> None:
        """
        Add two centered single-line text entities inside the door: top line = label, bottom line = WxH.
        transform_point_func: function that converts local points to final coordinates (accepts a tuple).
        """
        try:
            label_text = f"{source_label}\n{int(round(outer_width))} x {int(round(outer_height))}"
        except Exception:
            label_text = f"{source_label}\n{int(outer_width)} x {int(outer_height)}"

        # Calculate center in local coordinates
        local_center_x = outer_width / 2.0
        local_center_y = outer_height / 2.0

        # For rotated doors, rotate text 90 degrees
        text_rotation = 90 if rotated else 0

        # Create two single-line text entities (top: filename, bottom: WxH)
        line_spacing = dim_text_height * 1.3
        top_local = (local_center_x, local_center_y + (line_spacing / 2.0))
        bot_local = (local_center_x, local_center_y - (line_spacing / 2.0))
        top_pos = transform_point_func(top_local)
        bot_pos = transform_point_func(bot_local)

        line1 = source_label if source_label is not None else ""
        line2 = f"{int(round(outer_width))} x {int(round(outer_height))}"

        t1 = msp.add_text(line1, dxfattribs={"layer": "DIMENSIONS", "height": dim_text_height, "style": "Standard"})
        t1.dxf.insert = top_pos
        t1.dxf.halign = 2
        t1.dxf.valign = 2
        try:
            t1.dxf.rotation = text_rotation
        except Exception:
            pass

        t2 = msp.add_text(line2, dxfattribs={"layer": "DIMENSIONS", "height": dim_text_height, "style": "Standard"})
        t2.dxf.insert = bot_pos
        t2.dxf.halign = 2
        t2.dxf.valign = 2
        try:
            t2.dxf.rotation = text_rotation
        except Exception:
            pass


# Example usage
if __name__ == "__main__":
    try:
        from fastapi_app.schemas_input import DoorDXFRequest, DoorInfo, DimensionInfo, DefaultInfo
        from fastapi_app.schemas_output import Metadata as OutMeta

        req = DoorDXFRequest(
            mode="single",
            door=DoorInfo(category="Single", type="Normal", option=None, hole_offset="40", default_allowance="standard"),
            dimensions=DimensionInfo(
                width_measurement=600,
                height_measurement=1105,
                left_side_allowance_width=25,
                right_side_allowance_width=25,
                top_side_allowance_height=25,
                bottom_side_allowance_height=0,
            ),
            metadata=OutMeta(label="door_F14P2", file_name="door_F14P2.dxf", width=0, height=0, rotated=False, is_annotation_required=True),
            defaults=DefaultInfo()
        )

        DoorDrawingGenerator.generate_door_dxf(req, file_name="door_F14P2.dxf")
    except Exception as e:
        print(f"Error: {e}")
