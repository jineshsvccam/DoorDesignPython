from __future__ import annotations

from numpy import true_divide

"""DoorDrawingGenerator.py

Generate DXF files for door designs with annotated dimensions and cutouts.
Uses ezdxf for DXF creation.
"""

from ezdxf.filemanagement import new
from typing import Tuple, Optional, Union
from collections.abc import Iterable
from ezdxf.document import Drawing
from ezdxf.layouts.layout import Modelspace
from ezdxf.enums import TextEntityAlignment
from geometry.door_geometry import compute_door_geometry
from fastapi_app.schemas_input import DoorDXFRequest
from fastapi_app.schemas_output import SchemasOutput
import logging
from DoorDrawingPDF import DoorDrawingPDF
from annotation_styles import styles, CURRENT_STYLE_INDEX

logger = logging.getLogger(__name__)


def ensure_dimstyle(doc, name="DoorDimStyle"):
    try:
        # doc.dimstyles supports membership test and .new()
        if name not in doc.dimstyles:
            ds = doc.dimstyles.new(name)
            ds.dxf.dimtxsty = "Standard"   # link to text style
            ds.dxf.dimclrd = 7             # dimension line color
            ds.dxf.dimclre = 7             # extension line color
            ds.dxf.dimclrt = 7             # text color
            print(f"✅ Created new dimstyle '{name}'")
        return name
    except Exception as e:
        print(f"❌ Failed to create dimstyle '{name}':", e)
        return "Standard"

class DoorDrawingGenerator:
    """
    Static class for generating door DXF files with dimensions and cutouts.
    """
    # Visual/geometry defaults moved to DefaultInfo in schemas_input

    @staticmethod
    def generate_door_dxf(
        request: Optional[DoorDXFRequest] = None,
        schema: Optional[SchemasOutput] = None,
        file_name: Optional[str] = None,
        label_name: Optional[str] = None,
        isannotationRequired: bool = True,
        offset: Tuple[float, float] = (0.0, 0.0),
        doc: Optional[Drawing] = None,
        msp: Optional[Modelspace] = None,
        save_file: bool = True,
        rotated: bool = False,
        save_pdf: bool = False,
    ) -> None:
        """Generate a DXF file for the door with annotations.

        The request is a `DoorDXFRequest` model. If `doc`/`msp` are not provided,
        a new ezdxf document will be created. If `save_file` is True and
        `file_name` is provided the DXF will be saved.
        """
        # Ensure we have either a schema or a request to compute one
        if schema is None and request is None:
            raise ValueError("Either 'request' or 'schema' must be provided to generate_door_dxf")

        # If schema not provided, compute it from the request using the offset/rotated flags
        if schema is None:
            # request is Optional[DoorDXFRequest] at type-level, but we already
            # validated above that at least one of request/schema is provided.
            # Guard for the type-checker and runtime with an assertion.
            assert request is not None, "request must be provided when schema is not"
            schema = compute_door_geometry(request, rotated=rotated, offset=offset)

        # Validate the computed / provided schema before drawing. Call the
        # centralized `validate_schema(schema)` function in `tools.validator`.
        # The validator performs all checks and prints a detailed JSON result
        # if validation fails. If validator is unavailable or raises an
        # exception we abort to avoid producing incorrect DXFs.
        try:
            try:
                from tools.validator import validate_schema
            except Exception:
                import runpy, os
                validator_path = os.path.join(os.path.dirname(__file__), "tools", "validator.py")
                validator_ns = runpy.run_path(validator_path)
                validate_schema = validator_ns.get("validate_schema")

            if not validate_schema:
                print("Validator not available; aborting DXF generation to avoid unsafe output.")
                return

            passed = bool(validate_schema(schema))
            passed = True
        except Exception as e:
            try:
                import traceback, json
                err = {"validation_error": str(e), "traceback": traceback.format_exc()}
                print(json.dumps(err, indent=2))
            except Exception:
                print("Validation failed and error details could not be serialized.")
            return

        if not passed:
            # Validator already printed the detailed JSON; abort drawing.
            return

        # Ensure we have a drawing document and modelspace to draw into
        if doc is None or msp is None:
            doc = new(dxfversion="R2010")
            # create common layers if not present
            try:
                doc.layers.new(name="CUT", dxfattribs={"color": 4})
            except Exception:
                pass
            try:
                doc.layers.new(name="DIMENSIONS", dxfattribs={"color": 1})
            except Exception:
                pass
            try:
                doc.layers.new(name="BIN", dxfattribs={"color": 2})
            except Exception:
                pass
            msp = doc.modelspace()

        # Ensure our dimension style exists and remember its name
        try:
            style_name = ensure_dimstyle(doc, "DoorDimStyle")
        except Exception:
            style_name = "Standard"

        # Visual defaults: prefer values from request.defaults if available
        defaults = None
        if request is not None:
            defaults = getattr(request, "defaults", None)
        dim_text_height = getattr(defaults, "dim_text_height", 8.0) if defaults is not None else 8.0
        dim_arrow_size = getattr(defaults, "dim_arrow_size", 6.0) if defaults is not None else 6.0
        horiz_dim_offset = getattr(defaults, "horizontal_dim_visual_offset", 20.0) if defaults is not None else 20.0
        vert_dim_offset = getattr(defaults, "vertical_dim_visual_offset", 40.0) if defaults is not None else 40.0

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

        # Draw all annotations
        draw_annotations(msp, schema, isannotationRequired=isannotationRequired, dim_text_height=3.0, transform_point_func=_t, dimstyle=style_name)
        
        # Draw labels from schema.geometry.labels using helper
        DoorDrawingGenerator.draw_label(msp, schema,transform_point_func=_t)

        # Save file only if requested
        if save_file and file_name is not None:
            doc.saveas(file_name)
            print(f"DXF file '{file_name}' created successfully.")

            # If user also wants a PDF, generate it
            if save_pdf:
                try:
                    pdf_name = file_name.replace(".dxf", ".pdf")
                    DoorDrawingPDF.export_to_pdf(doc, pdf_name)
                except Exception as e:
                    print(f"Failed to export PDF: {e}")

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

    @staticmethod
    def draw_label(msp, schema, transform_point_func=None) -> None:
        """
        Minimal label drawing method.
        Uses label attributes directly as defined in Label class.
        """
        try:
            labels = getattr(schema.geometry, "labels", []) or []
        except Exception:
            return

        _t = transform_point_func if transform_point_func else (lambda p: p)

        for label in labels:
            try:
                # Extract label properties
                ltext = getattr(label, "text", "") or ""
                lpos = getattr(label, "position", None)
                lalign = getattr(label, "align", None)
                lheight = getattr(label, "height", None)
                lstyle = getattr(label, "style", None)
                lrotation = getattr(label, "rotation", 0.0)
                llayer = getattr(label, "layer", None)
                loffset = getattr(label, "placement_offset", None)
                lcolor = getattr(label, "color", None)

                # Validate position
                if not isinstance(lpos, (list, tuple)):
                    continue

                # Apply optional offset
                x, y = float(lpos[0]), float(lpos[1])
                if loffset and isinstance(loffset, (list, tuple)):
                    x += float(loffset[0])
                    y += float(loffset[1])

                # Apply transform
                x, y = _t((x, y))

                # Create text entity
                dxf_attribs = {}
                if lheight: dxf_attribs["height"] = lheight
                if lstyle: dxf_attribs["style"] = lstyle
                if llayer: dxf_attribs["layer"] = llayer

                txt = msp.add_text(ltext, dxfattribs=dxf_attribs)

                if lcolor is not None:
                    txt.dxf.color = int(lcolor)

                if lrotation:
                    txt.dxf.rotation = float(lrotation)

                # Use tutorial-style placement
                if lalign:
                    try:
                        align_enum = getattr(TextEntityAlignment, lalign)
                        txt.set_placement((x, y), align=align_enum)
                    except AttributeError:
                        txt.set_placement((x, y))
                else:
                    txt.set_placement((x, y))

            except Exception:
                continue


def _as_point(pt):
    """Normalize various point representations to an (x, y) tuple of floats.

    Accepts tuples/lists, objects with .x/.y, dicts with x/y, or any
    sequence-like with two numeric entries. Falls back to (0.0, 0.0)
    on error.
    """
    if pt is None:
        return (0.0, 0.0)
    try:
        # direct sequence (tuple/list)
        if isinstance(pt, (list, tuple)):
            return (float(pt[0]), float(pt[1]))
        # pydantic models or objects with attributes
        if hasattr(pt, "x") and hasattr(pt, "y"):
            return (float(getattr(pt, "x")), float(getattr(pt, "y")))
        if isinstance(pt, dict) and ("x" in pt or "y" in pt):
            return (float(pt.get("x", 0)), float(pt.get("y", 0)))
        # try treating as sequence
        seq = list(pt)
        return (float(seq[0]), float(seq[1]))
    except Exception:
        return (0.0, 0.0)


def _msp_handles(msp):
    """Return a set of DXF handles for entities currently in modelspace.

    Some entities may not expose a dxf.handle; skip those.
    """
    handles = set()
    try:
        for ent in msp:
            try:
                h = ent.dxf.handle
            except Exception:
                h = None
            if h:
                handles.add(h)
    except Exception:
        # If iteration fails for some reason, return empty set
        return set()
    return handles


def _draw_manual_linear_dim(msp, p1, p2, angle, distance, text, dim_text_height=3.0, arrow_size=6.0, layer="DIMENSIONS"):
    """Draw a simple linear dimension manually into modelspace.

    This is a lightweight, portable fallback when ezdxf's dimension
    helper does not expose virtual entities or does not insert into
    modelspace. Supports axis-aligned (angle==0 horizontal, else vertical)
    dimensions only.
    """
    try:
        x1, y1 = float(p1[0]), float(p1[1])
        x2, y2 = float(p2[0]), float(p2[1])
    except Exception:
        return

    # Normalize ordering so p1 is the lesser along the primary axis
    if angle == 0:
        if x2 < x1:
            x1, x2 = x2, x1
        dim_y = (y1 + y2) / 2.0 + distance
        # dimension line
        msp.add_line((x1, dim_y), (x2, dim_y), dxfattribs={"layer": layer})
        # extension lines
        msp.add_line((x1, y1), (x1, dim_y), dxfattribs={"layer": layer})
        msp.add_line((x2, y2), (x2, dim_y), dxfattribs={"layer": layer})
        # ticks (small perpendicular lines)
        half_tick = arrow_size / 2.0
        msp.add_line((x1, dim_y - half_tick), (x1, dim_y + half_tick), dxfattribs={"layer": layer})
        msp.add_line((x2, dim_y - half_tick), (x2, dim_y + half_tick), dxfattribs={"layer": layer})
        # text centered
        mid_x = (x1 + x2) / 2.0
        txt = msp.add_text(text, dxfattribs={"layer": layer, "height": dim_text_height, "style": "Standard"})
        txt.dxf.insert = (mid_x, dim_y + dim_text_height)
        txt.dxf.halign = 2
        txt.dxf.valign = 2
    else:
        # vertical dimension
        if y2 < y1:
            y1, y2 = y2, y1
        dim_x = (x1 + x2) / 2.0 + distance
        msp.add_line((dim_x, y1), (dim_x, y2), dxfattribs={"layer": layer})
        msp.add_line((x1, y1), (dim_x, y1), dxfattribs={"layer": layer})
        msp.add_line((x2, y2), (dim_x, y2), dxfattribs={"layer": layer})
        half_tick = arrow_size / 2.0
        msp.add_line((dim_x - half_tick, y1), (dim_x + half_tick, y1), dxfattribs={"layer": layer})
        msp.add_line((dim_x - half_tick, y2), (dim_x + half_tick, y2), dxfattribs={"layer": layer})
        mid_y = (y1 + y2) / 2.0
        txt = msp.add_text(text, dxfattribs={"layer": layer, "height": dim_text_height, "style": "Standard"})
        txt.dxf.insert = (dim_x + dim_text_height, mid_y)
        txt.dxf.halign = 0
        txt.dxf.valign = 2


def _try_virtual_entities(dim, msp):
    """Render and extract virtual entities from dimension, then add them."""
    try:
        dim.render()                     # ensure geometry exists
        vlist = list(dim.virtual_entities()) or []
        for e in vlist:
            msp.add_entity(e.copy())     # use copy to detach from original doc
        return len(vlist)
    except Exception as ex:
        print("virtual_entities failed:", ex)
        return 0


def _try_renderer_render(dim, msp):
    """Attempt to obtain the renderer and render directly into modelspace.

    Returns number of new entities detected in msp after render (0 on failure).
    """
    get_r = getattr(dim, "get_renderer", None)
    if not callable(get_r):
        return 0
    try:
        before = _msp_handles(msp)
        renderer = dim.get_renderer()
        # renderer.render(block) inserts entities into the provided block/modelspace
        try:
            renderer.render(msp)
        except TypeError:
            # some renderers may require a different signature; fail silently
            return 0
        after = _msp_handles(msp)
        return len(after - before)
    except Exception:
        return 0


def _try_post_render_scan(before_handles, msp):
    """Compare before_handles with current modelspace handles and return number of new entities."""
    try:
        after = _msp_handles(msp)
        return len(after - before_handles)
    except Exception:
        return 0
def draw_annotations(msp, schema, isannotationRequired=True, dim_text_height=3.0, transform_point_func=None, dimstyle: str = "Standard"):
    """
    Draws all annotations (dimensions, notes, leaders) from schema.geometry.annotations.

    Args:
        msp: ezdxf modelspace object
        schema: object containing metadata and geometry (with annotations list)
        isannotationRequired (bool): whether annotations are enabled globally
        dim_text_height (float): text height for dimension labels
    """
    is_schema_annotation_enabled = (
        getattr(schema.metadata, "is_annotation_required", False) and isannotationRequired
    )

    if not is_schema_annotation_enabled:
        return

    # Define the transformation function if not provided
    _t = transform_point_func if transform_point_func else lambda p: p

    # select active style from annotation_styles (ensure non-None dict)
    style = styles.get(CURRENT_STYLE_INDEX) or styles.get(0) or {"dimtxt": dim_text_height, "dimasz": 2.0, "dimexe": 1.0, "dimexo": 1.0, "dimtad": 1, "dimtofl": 1, "text_height": dim_text_height, "text_style": "Standard", "color": 7}

    # --- Apply global or dynamic scaling ---
    # tweak ANNOTATION_SCALE here for global enlargement, or set
    # schema.metadata.annotation_scale to override per-schema
    ANNOTATION_SCALE = 2.0
    try:
        # allow per-schema override if present and numeric
        meta_scale = float(getattr(schema.metadata, "annotation_scale", ANNOTATION_SCALE) or ANNOTATION_SCALE)
    except Exception:
        meta_scale = ANNOTATION_SCALE

    # operate on a copy so we don't mutate the module-level styles
    scaled_style = dict(style) if isinstance(style, dict) else {}
    try:
        scale = meta_scale
        for key in ["dimtxt", "dimasz", "dimexe", "dimexo", "text_height"]:
            if key in scaled_style and isinstance(scaled_style[key], (int, float)):
                scaled_style[key] = scaled_style[key] * scale
    except Exception:
        # if scaling fails, fall back to original style
        scaled_style = dict(style)

    # annotations are grouped in a dict: { category: [Annotation,...] }
    anns_by_group = getattr(schema.geometry, "annotations", {}) or {}
    for group_name, ann_list in (anns_by_group.items() if isinstance(anns_by_group, dict) else []):
        for ann in ann_list or []:
            try:
                atype = getattr(ann, "type", "dimension").lower()

                # --- 📏 DIMENSION ---
                if atype == "dimension":
                    raw_from = getattr(ann, "from_", getattr(ann, "from", (0.0, 0.0)))
                    raw_to = getattr(ann, "to", (0.0, 0.0))

                    # Normalize points and apply optional transform
                    p1_local = _as_point(raw_from)
                    p2_local = _as_point(raw_to)
                    p1 = _t(p1_local)
                    p2 = _t(p2_local)

                    angle = float(getattr(ann, "angle", 0) or 0)
                    distance = float(getattr(ann, "offset", 10) or 10)
                    dim_text = getattr(ann, "text", "")

                    # Pre-extract category and owner so they are available for
                    # conditional checks below (owner may include a '_circle' suffix).
                    category = (getattr(ann, "category", "") or "").strip().lower()
                    owner_name = (getattr(ann, "owner", "") or "").strip()
                    base_owner = owner_name[:-7] if (isinstance(owner_name, str) and owner_name.endswith("_circle")) else owner_name

                    # Compute offset base point for dimension line
                    if angle == 0:   # horizontal
                        base = (p1[0], p1[1] + distance)
                    elif angle == 90:  # vertical
                        base = (p1[0] + distance, p1[1])
                    else:
                        base = p1

                    try:
                        # If this dimension represents a hole (circle), create a diameter dimension
                        if category == "hole" and ((isinstance(owner_name, str) and owner_name != base_owner) or (isinstance(dim_text, str) and dim_text.strip().startswith("Ø"))):
                          
                            ann_base = raw_from
                            ann_to = raw_to
                            # Require both base and to-point on the annotation; otherwise skip
                            if not ann_base or not ann_to:
                                continue

                            hc = _t(_as_point(ann_base))                          
                            try:
                                radius_val = float(ann_to[0])
                            except Exception:
                                continue

                            # create diameter dimension using annotation-provided geometry
                            dim = msp.add_diameter_dim(
                                center=(float(hc[0]), float(hc[1])),
                                radius=radius_val,
                                angle=45,
                                dimstyle="EZ_RADIUS",
                                override={"dimtih": 1},
                            )
                            try:
                                dim.render()
                            except Exception:
                                # rendering errors are non-fatal; skip further handling
                                pass
                            try:
                                if hasattr(dim, "dimension"):
                                    dim.dimension.dxf.layer = "DIMENSIONS"
                                else:
                                    dim.dxf.layer = "DIMENSIONS"
                            except Exception:
                                pass
                            # done with hole diameter dimension
                            continue

                        else:
                            # use style overrides when creating linear dimension
                            dim = msp.add_linear_dim(
                                base=base,
                                p1=p1,
                                p2=p2,
                                angle=angle,
                                dimstyle=dimstyle,
                                override={
                                    "dimtxt": scaled_style.get("dimtxt"),
                                    "dimasz": scaled_style.get("dimasz"),
                                    "dimexe": scaled_style.get("dimexe"),
                                    "dimexo": scaled_style.get("dimexo"),
                                    "dimtad": scaled_style.get("dimtad"),
                                    "dimtofl": scaled_style.get("dimtofl"),
                                },
                            )
                            # try to render and set location similar to prior behaviour
                            try:
                                dim.render()
                            except Exception as e:
                                print(f"⚠️ Dimension render failed: {e}")

                            offset_dir = (0, distance) if angle == 0 else (distance, 0)
                            try:
                                dim.set_location(offset_dir, relative=True)
                            except Exception:
                                pass
                            try:
                                # set layer on created linear-dimension entity if available
                                if hasattr(dim, "dimension"):
                                    dim.dimension.dxf.layer = "DIMENSIONS"
                                else:
                                    dim.dxf.layer = "DIMENSIONS"
                            except Exception:
                                pass

                    except Exception as e:
                        print("❌ Dimension creation failed:", e)

                # --- 📝 NOTE ---
                elif atype == "note":
                    raw_pos = getattr(ann, "to", getattr(ann, "from", (0.0, 0.0)))
                    pos = _t(_as_point(raw_pos))
                    note_text = getattr(ann, "text", "")
                    txt = msp.add_text(
                        note_text,
                        dxfattribs={
                            "layer": "DIMENSIONS",
                            "height": scaled_style.get("text_height", dim_text_height),
                            "style": scaled_style.get("text_style", "Standard"),
                            "color": scaled_style.get("color", 7),
                        },
                    )
                    txt.dxf.insert = pos
                    txt.dxf.halign = 0
                    txt.dxf.valign = 2

                # --- ➤ LEADER ---
                elif atype == "leader":
                    raw_from = getattr(ann, "from_", getattr(ann, "from", (0.0, 0.0)))
                    raw_to = getattr(ann, "to", (0.0, 0.0))
                    p_from = _t(_as_point(raw_from))
                    p_to = _t(_as_point(raw_to))
                    leader_text = getattr(ann, "text", "")
                    msp.add_line(p_from, p_to, dxfattribs={"layer": "DIMENSIONS"})
                    txt = msp.add_text(
                        leader_text,
                        dxfattribs={
                            "layer": "DIMENSIONS",
                            "height": scaled_style.get("text_height", dim_text_height),
                            "style": scaled_style.get("text_style", "Standard"),
                            "color": scaled_style.get("color", 7),
                        },
                    )
                    txt.dxf.insert = p_to
                    txt.dxf.halign = 0
                    txt.dxf.valign = 2

            except Exception as e:
                logger.exception("Annotation failed: %s", e)
                continue

   # Example usage
if __name__ == "__main__":
    try:
        from fastapi_app.schemas_input import DoorDXFRequest, DoorInfo, DimensionInfo, DefaultInfo
        from fastapi_app.schemas_output import Metadata as OutMeta

        req = DoorDXFRequest(
            mode="single",
            door=DoorInfo(category="Single", type="Normal", option=None, hole_offset="150x40", default_allowance="standard"),
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

        # save_pdf is a parameter on generate_door_dxf (not part of metadata)
        DoorDrawingGenerator.generate_door_dxf(req, file_name="door_F14P2.dxf", save_pdf=True)
    except Exception as e:
        print(f"Error: {e}")