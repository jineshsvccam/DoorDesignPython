"""
DoorDrawingGenerator.py

Generates a DXF file for a door design with annotated dimensions and cutouts.
Uses ezdxf for DXF creation. All geometry and dimension annotations are drawn manually.
"""

from ezdxf.filemanagement import new
from typing import Tuple, Optional, Union
from ezdxf.document import Drawing
from ezdxf.layouts.layout import Modelspace

class DoorDrawingGenerator:
    """
    Static class for generating door DXF files with dimensions and cutouts.
    """
    DefaultBendAdjust = 12.0
    DefaultBoxGap = 30.0
    DefaultBoxWidth = 22.0
    DefaultBoxHeight = 112.0
    DefaultCircleRadius = 5.0
    DefaultLeftCircleOffset = 40.0
    DefaultTopCircleOffset = 150.0
    DimTextHeight = 8.0
    DimArrowSize = 6.0
    HorizontalDimVisualOffset = 20.0
    VerticalDimVisualOffset = 40.0

    @staticmethod
    def generate_door_dxf(
        width_measurement: float,
        height_measurement: float,
        left_side_allowance_width: float,
        right_side_allowance_width: float,
        left_side_allowance_height: float,
        right_side_allowance_height: float,
        door_minus_measurement_width: float,
        door_minus_measurement_height: float,
        bending_width: float,
        bending_height: float,
        file_name: Optional[str] = None,
        label_name: Optional[str] = None,
        isannotationRequired: bool = True,
        offset: Tuple[float, float] = (0.0, 0.0),
        doc: Optional[Drawing] = None,
        msp: Optional[Modelspace] = None,
        save_file: bool = True,
        rotated: bool = False
    ) -> None:
        """
        Generates a DXF file for the door design with all geometry and dimension annotations.
        Args:
            width_measurement: Main door width.
            height_measurement: Main door height.
            left_side_allowance_width: Allowance on left side.
            right_side_allowance_width: Allowance on right side.
            left_side_allowance_height: Allowance on top.
            right_side_allowance_height: Allowance on bottom.
            door_minus_measurement_width: Subtract from total width for inner rectangle.
            door_minus_measurement_height: Subtract from total height for inner rectangle.
            bending_width: Bending width for outer rectangle.
            bending_height: Bending height for inner rectangle.
            file_name: Output DXF file name.
            isannotationRequired: Flag to control dimension annotation.
        """
        # Validate input
        if width_measurement <= 0 or height_measurement <= 0:
            raise ValueError("Width and height must be positive numbers.")
        if doc is None and (file_name is None or not file_name.lower().endswith('.dxf')):
            raise ValueError("Output file name must end with .dxf")

        # Create doc/msp if not provided
        if doc is None or msp is None:
            doc = new(dxfversion="R2010")
            doc.layers.new(name="CUT", dxfattribs={"color": 4})  # Cyan
            doc.layers.new(name="DIMENSIONS", dxfattribs={"color": 1})  # Red
            msp = doc.modelspace()

        # Offset unpack
        offset_x, offset_y = offset

        # Calculate geometry
        frame_total_width = width_measurement + left_side_allowance_width + right_side_allowance_width
        frame_total_height = height_measurement + left_side_allowance_height + right_side_allowance_height
        inner_width = frame_total_width - door_minus_measurement_width
        inner_height = frame_total_height - door_minus_measurement_height
        outer_width = inner_width + bending_width
        # outer_height should include bending_height so the center calculation
        # matches the outer rectangle used by the packer and drawing.
        outer_height = inner_height + bending_height
        bend_adjust = DoorDrawingGenerator.DefaultBendAdjust
        inner_offset_x = bending_width - bend_adjust
        inner_offset_y = bend_adjust - bending_height

        # Before transforming points, compute a small translation so no coords are negative.
        # Gather key local points (outer, inner, box, circles) and find their mins.
        # We'll also account for possible negative dimension offsets (e.g. -20) by
        # adding a small safety margin so dimension lines don't go negative.

        # Local (model) points
        outer_pts = [
            (0, 0),
            (outer_width, 0),
            (outer_width, outer_height),
            (0, outer_height),
            (0, 0),
        ]

        inner_pts = [
            (inner_offset_x, inner_offset_y),
            (inner_offset_x + inner_width, inner_offset_y),
            (inner_offset_x + inner_width, inner_offset_y + inner_height + bending_height),
            (inner_offset_x, inner_offset_y + inner_height + bending_height),
            (inner_offset_x, inner_offset_y),
        ]

        # center box points (local)
        box_gap = DoorDrawingGenerator.DefaultBoxGap
        box_width = DoorDrawingGenerator.DefaultBoxWidth
        box_height = DoorDrawingGenerator.DefaultBoxHeight
        box_left_x = inner_offset_x + box_gap
        box_bottom_y = inner_offset_y + ((inner_height + bending_height - box_height) / 2.0)
        box_pts = [
            (box_left_x, box_bottom_y),
            (box_left_x + box_width, box_bottom_y),
            (box_left_x + box_width, box_bottom_y + box_height),
            (box_left_x, box_bottom_y + box_height),
        ]

        # circle centers (local)
        left_circle_offset = DoorDrawingGenerator.DefaultLeftCircleOffset
        circle_center_x = inner_offset_x + left_circle_offset
        circle_center_y_top = inner_height - DoorDrawingGenerator.DefaultTopCircleOffset + inner_offset_y + bend_adjust
        circle_center_y_bottom = DoorDrawingGenerator.DefaultTopCircleOffset + inner_offset_y + bend_adjust
        circle_pts = [(circle_center_x, circle_center_y_top), (circle_center_x, circle_center_y_bottom)]

        # Collect all points to determine mins
        all_x = [p[0] for p in outer_pts + inner_pts + box_pts + circle_pts]
        all_y = [p[1] for p in outer_pts + inner_pts + box_pts + circle_pts]
        min_x = min(all_x)
        min_y = min(all_y)

        # Account for any negative dimension offsets used in this generator (e.g. outer dims use -20)
        # We'll compute the most negative explicit offset used in calls below. The known values
        # in this module are -20, 20 and 40; the worst negative is -20 -> need margin 20 to keep dim >=0.
        worst_negative_dim_offset = -20
        margin_y = abs(worst_negative_dim_offset) if worst_negative_dim_offset < 0 else 0

        # Compute required translation so min coords (and dim offsets) are non-negative
        translate_x = max(0.0, -min_x)
        translate_y = max(0.0, -min_y + margin_y)

        # Apply translation to the provided offset so transform_point will include it
        offset_x += translate_x
        offset_y += translate_y

        # Helper to transform local points into final coordinates.
        # If rotated is False: identity + offset. If rotated is True: rotate 90deg CCW
        # about the local origin and translate so the rotated shape sits in the
        # positive quadrant starting at (offset_x, offset_y).
        def transform_point(pt):
            x, y = pt
            if not rotated:
                return (offset_x + x, offset_y + y)
            # 90deg CCW rotation: (x,y) -> (-y, x). After rotation x-range is [-outer_height,0]
            # so translate by +outer_height to bring into positive quadrant: (outer_height - y, x)
            return (offset_x + (outer_height - y), offset_y + x)

        # Debug: computed geometry values
        print(f"[DEBUG door] file={file_name} rotated={rotated} offset=({offset_x},{offset_y}) outer_width={outer_width} outer_height={outer_height} inner_offset=({inner_offset_x},{inner_offset_y})")
        # Draw outer rectangle (door frame) using transformed points
        outer_pts = [
            (0, 0),
            (outer_width, 0),
            (outer_width, outer_height),
            (0, outer_height),
            (0, 0)
        ]
        outer_trans = [transform_point(p) for p in outer_pts]
        print(f"[DEBUG door] outer_transformed={outer_trans}")
        msp.add_lwpolyline(outer_trans, dxfattribs={"layer": "CUT"})

        # Add centered label inside the door: filename and size (W x H)    
        # Move label drawing to helper for clarity
        source_label = label_name if label_name is not None else file_name
        DoorDrawingGenerator.add_center_label(msp, transform_point, outer_width, outer_height, source_label, rotated)

        # Annotate outer rectangle dimensions
        DoorDrawingGenerator.add_dimension_line(msp, transform_point((0, 0)), transform_point((outer_width, 0)), f"{outer_width}", offset=-20, angle=0, isannotationRequired=isannotationRequired)
        DoorDrawingGenerator.add_dimension_line(msp, transform_point((0, 0)), transform_point((0, outer_height)), f"{outer_height}", offset=-20, angle=90, isannotationRequired=isannotationRequired)

        # Draw inner rectangle (door cutout)
        inner_pts = [
            (inner_offset_x, inner_offset_y),
            (inner_offset_x + inner_width, inner_offset_y),
            (inner_offset_x + inner_width, inner_offset_y + inner_height + bending_height),
            (inner_offset_x, inner_offset_y + inner_height + bending_height),
            (inner_offset_x, inner_offset_y)
        ]
        inner_trans = [transform_point(p) for p in inner_pts]
        print(f"[DEBUG door] inner_transformed={inner_trans}")
        msp.add_lwpolyline(inner_trans, dxfattribs={"layer": "CUT"})

        # Annotate inner rectangle dimensions
        top_y = inner_offset_y + inner_height + bending_height
        if isannotationRequired:
            DoorDrawingGenerator.add_dimension_line(msp, transform_point((inner_offset_x, top_y)), transform_point((inner_offset_x + inner_width, top_y)), f"{inner_width}", offset=20, angle=0, isannotationRequired=isannotationRequired)
            right_x = inner_offset_x + inner_width
            total_inner_height = inner_height + bending_height
            DoorDrawingGenerator.add_dimension_line(msp, transform_point((right_x, inner_offset_y)), transform_point((right_x, inner_offset_y + total_inner_height)), f"{total_inner_height}", offset=40, angle=90, isannotationRequired=isannotationRequired)

        # Draw circles (holes)
        circle_radius = DoorDrawingGenerator.DefaultCircleRadius
        left_circle_offset = DoorDrawingGenerator.DefaultLeftCircleOffset
        top_circle_offset = DoorDrawingGenerator.DefaultTopCircleOffset

        circle_center_x = inner_offset_x + left_circle_offset
        circle_center_y_top = inner_height - top_circle_offset + inner_offset_y + bend_adjust
        circle_center_y_bottom = top_circle_offset + inner_offset_y + bend_adjust
        circ_top = transform_point((circle_center_x, circle_center_y_top))
        circ_bottom = transform_point((circle_center_x, circle_center_y_bottom))
        print(f"[DEBUG door] circles_local=({circle_center_x},{circle_center_y_top}),({circle_center_x},{circle_center_y_bottom}) transformed=({circ_top},{circ_bottom})")
        msp.add_circle(circ_top, circle_radius, dxfattribs={"layer": "CUT"})
        msp.add_circle(circ_bottom, circle_radius, dxfattribs={"layer": "CUT"})

        # Annotate circle dimensions (horizontal and vertical for each)
        if isannotationRequired:
            DoorDrawingGenerator.add_dimension_line(msp, transform_point((inner_offset_x, circle_center_y_top)), transform_point((circle_center_x, circle_center_y_top)), f"{left_circle_offset}", offset=20, angle=0, text_offset=28, isannotationRequired=isannotationRequired)
            DoorDrawingGenerator.add_dimension_line(msp, transform_point((circle_center_x, inner_height)), transform_point((circle_center_x, circle_center_y_top)), f"{abs(inner_height - (circle_center_y_top - 0)):.0f}", offset=40, angle=90, text_offset=28, isannotationRequired=isannotationRequired)
            DoorDrawingGenerator.add_dimension_line(msp, transform_point((inner_offset_x, circle_center_y_bottom)), transform_point((circle_center_x, circle_center_y_bottom)), f"{left_circle_offset}", offset=20, angle=0, text_offset=38, isannotationRequired=isannotationRequired)
            DoorDrawingGenerator.add_dimension_line(msp, transform_point((circle_center_x, 0)), transform_point((circle_center_x, circle_center_y_bottom)), f"{abs((circle_center_y_bottom - 0)):.0f}", offset=40, angle=90, text_offset=38, isannotationRequired=isannotationRequired)

        # Draw center box cutout
        box_gap = DoorDrawingGenerator.DefaultBoxGap
        box_width = DoorDrawingGenerator.DefaultBoxWidth
        box_height = DoorDrawingGenerator.DefaultBoxHeight

        box_left_x = inner_offset_x + box_gap
        box_bottom_y = inner_offset_y + ((inner_height + bending_height - box_height) / 2.0)
        box_pts = [
            (box_left_x, box_bottom_y),
            (box_left_x + box_width, box_bottom_y),
            (box_left_x + box_width, box_bottom_y + box_height),
            (box_left_x, box_bottom_y + box_height),
            (box_left_x, box_bottom_y)
        ]
        msp.add_lwpolyline([transform_point(p) for p in box_pts], dxfattribs={"layer": "CUT"})

        # Annotate center box dimensions
        if isannotationRequired:
            DoorDrawingGenerator.add_dimension_line(msp, transform_point((inner_offset_x, box_bottom_y + box_height)), transform_point((box_left_x, box_bottom_y + box_height)), f"{box_gap}", offset=20, angle=0, isannotationRequired=isannotationRequired)
            DoorDrawingGenerator.add_dimension_line(msp, transform_point((box_left_x, box_bottom_y + box_height)), transform_point((box_left_x + box_width, box_bottom_y + box_height)), f"{box_width}", offset=20, angle=0, text_offset=28, isannotationRequired=isannotationRequired)
            DoorDrawingGenerator.add_dimension_line(msp, transform_point((box_left_x + box_width, box_bottom_y)), transform_point((box_left_x + box_width, box_bottom_y + box_height)), f"{box_height}", offset=40, angle=90, text_offset=18, isannotationRequired=isannotationRequired)
            top_of_box = box_bottom_y + box_height
            DoorDrawingGenerator.add_dimension_line(msp, transform_point((box_left_x + box_width, top_of_box)), transform_point((box_left_x + box_width, outer_height)), f"{abs((outer_height) - top_of_box):.0f}", offset=40, angle=90, text_offset=28, isannotationRequired=isannotationRequired)

        # Save file only if requested and not in bulk/bin mode
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
        isannotationRequired: bool = True
    ) -> None:
        """
        Draws a dimension line with extension lines, arrowheads, and text annotation if isannotationRequired is True.
        Uses class static variables for defaults if not provided.
        Args:
            msp: Modelspace object from ezdxf.
            p1, p2: Endpoints of the dimensioned feature.
            text: Dimension label.
            offset: Visual offset for the dimension line.
            angle: 0 for horizontal, 90 for vertical.
            text_offset: Offset for text placement.
            arrow_size: Size of arrowheads.
            isannotationRequired: Flag to control dimension annotation.
        """
        if not isannotationRequired:
            return
        if offset is None:
            offset = DoorDrawingGenerator.HorizontalDimVisualOffset if angle == 0 else DoorDrawingGenerator.VerticalDimVisualOffset
        if text_offset is None:
            text_offset = DoorDrawingGenerator.DimTextHeight * 2
        if arrow_size is None:
            arrow_size = DoorDrawingGenerator.DimArrowSize

        # Use ezdxf linear dimension entities for cleaner, standard dimensions.
        # Calculate a base point for the dimension line offset in the perpendicular
        # direction from the feature (p1->p2). ezdxf expects `base` to be a point
        # on the dimension line. We'll compute the midpoint and move it by the
        # offset along the edge normal. For horizontal (angle=0) the normal is
        # (0, 1) and for vertical (angle=90) the normal is (1, 0) when edges are
        # axis-aligned. For arbitrary edges this would require vector math but the
        # current usage is axis-aligned so we keep it simple.
        # Ensure text_offset influences the base point translation along the normal
        # direction so the dimension text appears with the requested gap.

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
            # set the text override if supported
            # For ezdxf linear_dim objects, the measurement text can be overridden
            # by setting `dim.dxf.text` or `dim.render()` followed by editing the
            # text elements. Simpler approach: set `dim.render()` then add a text
            # entity at the computed insertion point.
            dim.render()
        except Exception:
            # Fallback: if add_linear_dim is not available for some reason,
            # silently draw a simple text at the approximate location.
            txt = msp.add_text(text, dxfattribs={"layer": "DIMENSIONS", "height": DoorDrawingGenerator.DimTextHeight, "style": "Standard"})
            if angle == 0:
                txt.dxf.insert = (mid_x, mid_y + offset + text_offset)
                txt.dxf.halign = 2
                txt.dxf.valign = 2
            else:
                txt.dxf.insert = (mid_x + offset + text_offset, mid_y)
                txt.dxf.halign = 0
                txt.dxf.valign = 2
            return

        # Place the textual override near the dimension line if requested.
        # We'll try to position a text entity at a small offset from the base mid
        # point so it doesn't overlap the dimension line. If the dim object
        # supports direct text override, that would be preferable, but doing so
        # is implementation dependent across ezdxf versions.
        try:
            # calculate text insert point relative to base
            if angle == 0:
                text_insert = (mid_x, mid_y + offset + (text_offset if text_offset is not None else DoorDrawingGenerator.DimTextHeight * 2))
                halign = 2
            else:
                text_insert = (mid_x + offset + (text_offset if text_offset is not None else DoorDrawingGenerator.DimTextHeight * 2), mid_y)
                halign = 0

            txt = msp.add_text(text, dxfattribs={"layer": "DIMENSIONS", "height": DoorDrawingGenerator.DimTextHeight, "style": "Standard"})
            txt.dxf.insert = text_insert
            txt.dxf.halign = halign
            txt.dxf.valign = 2
        except Exception:
            # ignore text placement errors
            pass

    @staticmethod
    def add_center_label(msp, transform_point_func, outer_width: float, outer_height: float, source_label: Optional[str], rotated: bool) -> None:
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
        # For rotated doors, rotate text 90 degrees so it reads along the door's long axis
        text_rotation = 90 if rotated else 0
        # Create two single-line text entities (top: filename, bottom: WxH)
        line_spacing = DoorDrawingGenerator.DimTextHeight * 1.3
        top_local = (local_center_x, local_center_y + (line_spacing / 2.0))
        bot_local = (local_center_x, local_center_y - (line_spacing / 2.0))
        top_pos = transform_point_func(top_local)
        bot_pos = transform_point_func(bot_local)

        line1 = source_label if source_label is not None else ""
        line2 = f"{int(round(outer_width))} x {int(round(outer_height))}"

        t1 = msp.add_text(line1, dxfattribs={"layer": "DIMENSIONS", "height": DoorDrawingGenerator.DimTextHeight, "style": "Standard"})
        t1.dxf.insert = top_pos
        t1.dxf.halign = 2
        t1.dxf.valign = 2
        try:
            t1.dxf.rotation = text_rotation
        except Exception:
            pass

        t2 = msp.add_text(line2, dxfattribs={"layer": "DIMENSIONS", "height": DoorDrawingGenerator.DimTextHeight, "style": "Standard"})
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
        DoorDrawingGenerator.generate_door_dxf(
            width_measurement=600,
            height_measurement=1105,
            left_side_allowance_width=25,
            right_side_allowance_width=25,
            left_side_allowance_height=25,
            right_side_allowance_height=0,
            door_minus_measurement_width=68,
            door_minus_measurement_height=70,
            bending_width=31,
            bending_height=24,
            file_name="door_F14P2.dxf"
        )
    except Exception as e:
        print(f"Error: {e}")
