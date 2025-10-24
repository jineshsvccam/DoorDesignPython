from fastapi_app.schemas_output import Cutout
from .utilis import create_rounded_rect, dedupe_consecutive_points, create_rounded_box


def generate_cutouts(params, frames, handles):
    """Generate handle and optional glass/keybox cutouts."""
    door = params["door"]
    defaults = params["defaults"]
    cutouts = []

    # --- Handle cutouts ---
    if handles["left_handle"]:
        cutouts.append(Cutout(name="left_handle", layer="CUT", points=handles["left_handle"]))
    cutouts.append(Cutout(name="center_handle", layer="CUT", points=handles["right_handle"]))

    # --- Glass cutouts (supports Option1..Option5 for fire doors) ---
    # Minimal, local-coordinate implementation using existing helpers.
    inner_offset_x, inner_offset_y = frames["inner_offset"]
    inner_width = params["inner_width"]
    inner_height = params["inner_height"]
    is_double = params.get("is_double", False)
    leaf_width = params.get("leaf_width", inner_width)
    shift_left = frames.get("shift_left", 0.0)
    bend_adjust = params.get("bend_adjust", 0.0)

    # Determine final cutout(s) based on door info options
    door_info = door
    option_in = (door_info.option or "").strip()
    opt_normalized = None
    if option_in:
        lower = option_in.strip().lower()
        if lower in ("option1", "option 1", "1", "standard"):
            opt_normalized = "Option1"
        elif lower in ("option2", "option 2", "2", "topfixed"):
            opt_normalized = "Option2"
        elif lower in ("option3", "option 3", "3", "bottomfixed"):
            opt_normalized = "Option3"
        elif lower in ("standard_double", "standard-double", "standard double"):
            opt_normalized = "Option4"
        elif lower in ("fourglass", "four_glass", "four-glass", "4glass", "4_glass"):
            opt_normalized = "Option5"

    # Helper collections
    glass_cutouts_to_add = []
    add_standard_glass_cutout = True

    # small rounded fallback radius
    rounded_radius = min(defaults.box_height / 2.0, defaults.box_width / 2.0)

    def _eq_str(a, b):
        return (a or "").strip().lower() == (b or "").strip().lower()

    pts_box = None

    # Fire-door specific option handling
    if _eq_str(door_info.category, "single") and _eq_str(door_info.type, "fire"):
        left_margin = right_margin = defaults.fire_glass_lr_margin
        top_margin = defaults.fire_glass_top_margin
        bottom_margin = defaults.fire_glass_bottom_margin

        if opt_normalized == "Option1":
            pass
        elif opt_normalized == "Option2":
            bottom_margin = inner_height / 2.0
        elif opt_normalized == "Option3":
            top_margin = inner_height / 2.0
        elif opt_normalized == "Option4":
            top_margin = getattr(defaults, "fire_glass_top_margin_double", defaults.fire_glass_top_margin)
        elif opt_normalized == "Option5":
            left_margin = right_margin = defaults.fire_glass_lr_margin
            add_standard_glass_cutout = False

            def _make_panel(left_abs, bottom_abs, width_local, height_local):
                if width_local <= 0 or height_local <= 0:
                    return None
                radius_p = min(getattr(defaults, "glass_corner_radius", rounded_radius), width_local / 2.0 if width_local else 0.0, height_local / 2.0 if height_local else 0.0)
                return create_rounded_rect(left_abs, bottom_abs, width_local, height_local, radius_p, segments=getattr(defaults, "glass_segments", 8))

            if not is_double:
                glass_left_abs = inner_offset_x + left_margin
                glass_right_abs = inner_offset_x + inner_width - right_margin

                bottom1_abs = inner_offset_y + defaults.fire_glass_bottom_margin
                top1_abs = inner_offset_y + (inner_height / 2.0 - 50.0)
                panel1 = _make_panel(glass_left_abs, bottom1_abs, glass_right_abs - glass_left_abs, top1_abs - bottom1_abs)

                bottom2_abs = inner_offset_y + (inner_height / 2.0 + 50.0)
                top2_abs = inner_offset_y + inner_height - defaults.fire_glass_top_margin
                panel2 = _make_panel(glass_left_abs, bottom2_abs, glass_right_abs - glass_left_abs, top2_abs - bottom2_abs)

                if panel1 is None:
                    panel1 = create_rounded_box(inner_offset_x + (inner_width - defaults.box_width) / 2.0,
                                                inner_offset_y + (inner_height - defaults.box_height) / 2.0,
                                                defaults.box_width, defaults.box_height,
                                                min(defaults.box_height / 2.0, defaults.box_width / 2.0))
                if panel2 is None:
                    panel2 = create_rounded_box(inner_offset_x + (inner_width - defaults.box_width) / 2.0,
                                                inner_offset_y + (inner_height - defaults.box_height) / 2.0,
                                                defaults.box_width, defaults.box_height,
                                                min(defaults.box_height / 2.0, defaults.box_width / 2.0))

                glass_cutouts_to_add.append(dedupe_consecutive_points(panel1))
                glass_cutouts_to_add.append(dedupe_consecutive_points(panel2))
            else:
                for leaf_offset in (inner_offset_x, inner_offset_x - shift_left):
                    leaf_width_local = leaf_width
                    glass_left_abs = leaf_offset + left_margin
                    glass_right_abs = leaf_offset + leaf_width_local - right_margin

                    bottom1_abs = inner_offset_y + defaults.fire_glass_bottom_margin
                    top1_abs = inner_offset_y + (inner_height / 2.0 - 50.0)
                    p1 = _make_panel(glass_left_abs, bottom1_abs, glass_right_abs - glass_left_abs, top1_abs - bottom1_abs)

                    bottom2_abs = inner_offset_y + (inner_height / 2.0 + 50.0)
                    top2_abs = inner_offset_y + inner_height - defaults.fire_glass_top_margin
                    p2 = _make_panel(glass_left_abs, bottom2_abs, glass_right_abs - glass_left_abs, top2_abs - bottom2_abs)

                    if p1 is None:
                        p1 = create_rounded_box(leaf_offset + (leaf_width_local - defaults.box_width) / 2.0,
                                                inner_offset_y + (inner_height - defaults.box_height) / 2.0,
                                                defaults.box_width, defaults.box_height,
                                                min(defaults.box_height / 2.0, defaults.box_width / 2.0))
                    if p2 is None:
                        p2 = create_rounded_box(leaf_offset + (leaf_width_local - defaults.box_width) / 2.0,
                                                inner_offset_y + (inner_height - defaults.box_height) / 2.0,
                                                defaults.box_width, defaults.box_height,
                                                min(defaults.box_height / 2.0, defaults.box_width / 2.0))

                    glass_cutouts_to_add.append(dedupe_consecutive_points(p1))
                    glass_cutouts_to_add.append(dedupe_consecutive_points(p2))

    # Single-panel glass path (non-Option5) for fire doors
    if _eq_str(door_info.type, "fire") and opt_normalized != "Option5" and not (is_double and _eq_str(door_info.type, "fire") and opt_normalized in ("Option1", "Option4")):
        glass_left_local = locals().get("left_margin", defaults.box_gap)
        glass_right_local = inner_width - locals().get("right_margin", defaults.box_gap)
        glass_bottom_local = locals().get("bottom_margin", defaults.box_gap)
        glass_top_local = inner_height - locals().get("top_margin", defaults.box_gap)

        if glass_right_local <= glass_left_local or glass_top_local <= glass_bottom_local:
            glass_w = defaults.box_width
            glass_h = defaults.box_height
            glass_left_local = (inner_width - glass_w) / 2.0
            glass_bottom_local = (inner_height - glass_h) / 2.0
            glass_right_local = glass_left_local + glass_w
            glass_top_local = glass_bottom_local + glass_h
        else:
            glass_w = glass_right_local - glass_left_local
            glass_h = glass_top_local - glass_bottom_local

        glass_left = inner_offset_x + glass_left_local
        glass_bottom = inner_offset_y + glass_bottom_local
        glass_right = inner_offset_x + glass_right_local
        glass_top = inner_offset_y + glass_top_local

        glass_bottom += bend_adjust
        glass_top += bend_adjust

        radius = min(getattr(defaults, "glass_corner_radius", rounded_radius), glass_w / 2.0 if glass_w else 0.0, glass_h / 2.0 if glass_h else 0.0)
        pts_box = create_rounded_rect(glass_left, glass_bottom, glass_w, glass_h, radius, segments=getattr(defaults, "glass_segments", 8))
        pts_box = dedupe_consecutive_points(pts_box)

    # Double-door Option5: four panels
    elif is_double and _eq_str(door_info.type, "fire") and opt_normalized == "Option5":
        add_standard_glass_cutout = False

        def _make_panel_double(left_abs, bottom_abs, width_local, height_local):
            if width_local <= 0 or height_local <= 0:
                return None
            radius_p = min(getattr(defaults, "glass_corner_radius", rounded_radius), width_local / 2.0 if width_local else 0.0, height_local / 2.0 if height_local else 0.0)
            return create_rounded_rect(left_abs, bottom_abs, width_local, height_local, radius_p, segments=getattr(defaults, "glass_segments", 8))

        left_margin = right_margin = defaults.fire_glass_lr_margin
        for leaf_offset in (inner_offset_x, inner_offset_x - shift_left):
            leaf_width_local = leaf_width
            glass_left_abs = leaf_offset + left_margin
            glass_right_abs = leaf_offset + leaf_width_local - right_margin

            bottom1_abs = inner_offset_y + defaults.fire_glass_bottom_margin
            top1_abs = inner_offset_y + (inner_height / 2.0 - 50.0)
            p1 = _make_panel_double(glass_left_abs, bottom1_abs, glass_right_abs - glass_left_abs, top1_abs - bottom1_abs)

            bottom2_abs = inner_offset_y + (inner_height / 2.0 + 50.0)
            top2_abs = inner_offset_y + inner_height - defaults.fire_glass_top_margin
            p2 = _make_panel_double(glass_left_abs, bottom2_abs, glass_right_abs - glass_left_abs, top2_abs - bottom2_abs)

            if p1 is None:
                p1 = create_rounded_box(leaf_offset + (leaf_width_local - defaults.box_width) / 2.0,
                                        inner_offset_y + (inner_height - defaults.box_height) / 2.0,
                                        defaults.box_width, defaults.box_height,
                                        min(defaults.box_height / 2.0, defaults.box_width / 2.0))
            if p2 is None:
                p2 = create_rounded_box(leaf_offset + (leaf_width_local - defaults.box_width) / 2.0,
                                        inner_offset_y + (inner_height - defaults.box_height) / 2.0,
                                        defaults.box_width, defaults.box_height,
                                        min(defaults.box_height / 2.0, defaults.box_width / 2.0))

            glass_cutouts_to_add.append(dedupe_consecutive_points(p1))
            glass_cutouts_to_add.append(dedupe_consecutive_points(p2))

    # Double fire + Option1/4 single-panel spanning both leaves
    elif is_double and _eq_str(door_info.type, "fire") and opt_normalized in ("Option1", "Option4"):
        left_margin = right_margin = defaults.fire_glass_lr_margin
        if opt_normalized == "Option4":
            top_margin = getattr(defaults, "fire_glass_top_margin_double", defaults.fire_glass_top_margin)
        else:
            top_margin = defaults.fire_glass_top_margin
        bottom_margin = defaults.fire_glass_bottom_margin

        glass_left_local = left_margin
        glass_right_local = inner_width - right_margin
        glass_bottom_local = bottom_margin
        glass_top_local = inner_height - top_margin

        if glass_right_local <= glass_left_local or glass_top_local <= glass_bottom_local:
            glass_w = defaults.box_width
            glass_h = defaults.box_height
            glass_left_local = (inner_width - glass_w) / 2.0
            glass_bottom_local = (inner_height - glass_h) / 2.0
            glass_right_local = glass_left_local + glass_w
            glass_top_local = glass_bottom_local + glass_h
        else:
            glass_w = glass_right_local - glass_left_local
            glass_h = glass_top_local - glass_bottom_local

        base_inner_x = inner_offset_x - shift_left
        glass_left = base_inner_x + glass_left_local
        glass_bottom = inner_offset_y + glass_bottom_local
        glass_right = base_inner_x + glass_right_local
        glass_top = inner_offset_y + glass_top_local

        glass_bottom += bend_adjust
        glass_top += bend_adjust

        radius = min(getattr(defaults, "glass_corner_radius", rounded_radius), glass_w / 2.0 if glass_w else 0.0, glass_h / 2.0 if glass_h else 0.0)
        pts_box = create_rounded_rect(glass_left, glass_bottom, glass_w, glass_h, radius, segments=getattr(defaults, "glass_segments", 8))
        pts_box = dedupe_consecutive_points(pts_box)

    else:
        # Fallback behavior: use the right-handle box as the glass/handle box
        pts_box = handles.get("right_handle")

    # Ensure pts_box fallback
    if pts_box is None:
        pts_box = handles.get("right_handle")

    # Add glass cutouts to the returned list (local coords)
    if add_standard_glass_cutout:
        cutouts.append(Cutout(name="glass_cut", layer="CUT", points=pts_box))
    else:
        # names depend on single/double
        if not is_double:
            names = ["glass_bottom", "glass_top"]
        else:
            names = ["glass_bottom_right", "glass_top_right", "glass_bottom_left", "glass_top_left"]
        for i, poly in enumerate(glass_cutouts_to_add):
            name = names[i] if i < len(names) else f"glass_panel_{i+1}"
            cutouts.append(Cutout(name=name, layer="CUT", points=poly))




    # --- Optional keybox for fire doors ---
    if (door.type or "").strip().lower() == "fire":
        kb_w = defaults.keybox_width
        kb_h = defaults.keybox_height
        kb_offset = defaults.keybox_bottom_offset
        kb_center_x_local = params["inner_width"] / 2.0
        kb_left_local = kb_center_x_local - kb_w / 2.0
        kb_bottom_local = kb_offset + params["bend_adjust"]
        kb_left = inner_offset_x + kb_left_local
        kb_bottom = inner_offset_y + kb_bottom_local

        kb_pts = [
            (kb_left, kb_bottom),
            (kb_left + kb_w, kb_bottom),
            (kb_left + kb_w, kb_bottom + kb_h),
            (kb_left, kb_bottom + kb_h),
            (kb_left, kb_bottom),
        ]
        cutouts.append(Cutout(name="keybox", layer="CUT", points=kb_pts))

    return cutouts
