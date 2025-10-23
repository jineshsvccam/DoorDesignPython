"""DoorDrawingGenerator.py

Generate DXF files for door designs with annotated dimensions and cutouts.
Uses ezdxf for DXF creation.
"""

from ezdxf.filemanagement import new
from typing import Tuple, Optional, Union
from ezdxf.document import Drawing
from ezdxf.layouts.layout import Modelspace
from door_geometry import compute_door_geometry
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

        # Draw frames
        for frame in schema.geometry.frames:
            pts = [tuple(p) for p in frame.points]
            msp.add_lwpolyline(pts, dxfattribs={"layer": frame.layer})

        # Draw cutouts
        for cut in schema.geometry.cutouts:
            pts = [tuple(p) for p in cut.points]
            msp.add_lwpolyline(pts, dxfattribs={"layer": cut.layer})

        # Draw holes
        for hole in schema.geometry.holes:
            msp.add_circle(tuple(hole.center), hole.radius, dxfattribs={"layer": hole.layer})

        # Draw dimensions and center label (combined, tolerant)
        try:
            outer = schema.geometry.frames[0].points

            def as_2tuple(pt):
                return (float(pt[0]), float(pt[1]))

            DoorDrawingGenerator.add_dimension_line(
                msp,
                as_2tuple(outer[0]),
                as_2tuple(outer[1]),
                f"{int(round(schema.metadata.width))}",
                offset=horiz_dim_offset,
                angle=0,
                isannotationRequired=isannotationRequired,
                dim_text_height=dim_text_height,
                dim_arrow_size=dim_arrow_size,
            )

            DoorDrawingGenerator.add_dimension_line(
                msp,
                as_2tuple(outer[0]),
                as_2tuple(outer[3]),
                f"{int(round(schema.metadata.height))}",
                offset=vert_dim_offset,
                angle=90,
                isannotationRequired=isannotationRequired,
                dim_text_height=dim_text_height,
                dim_arrow_size=dim_arrow_size,
            )

            # center label using metadata (center point)
            off_x, off_y = schema.metadata.offset
            cx = off_x + (schema.metadata.width / 2.0)
            cy = off_y + (schema.metadata.height / 2.0)
            line_spacing = dim_text_height * 1.3
            top_pos = (cx, cy + (line_spacing / 2.0))
            bot_pos = (cx, cy - (line_spacing / 2.0))
            line1 = schema.metadata.label or ""
            line2 = f"{int(round(schema.metadata.width))} x {int(round(schema.metadata.height))}"

            t1 = msp.add_text(line1, dxfattribs={"layer": "DIMENSIONS", "height": dim_text_height, "style": "Standard"})
            t1.dxf.insert = top_pos
            t1.dxf.halign = 2
            t1.dxf.valign = 2
            try:
                t1.dxf.rotation = 90 if schema.metadata.rotated else 0
            except Exception:
                pass

            t2 = msp.add_text(line2, dxfattribs={"layer": "DIMENSIONS", "height": dim_text_height, "style": "Standard"})
            t2.dxf.insert = bot_pos
            t2.dxf.halign = 2
            t2.dxf.valign = 2
            try:
                t2.dxf.rotation = 90 if schema.metadata.rotated else 0
            except Exception:
                pass

        except Exception:
            pass

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
