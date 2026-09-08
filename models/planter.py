from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from build123d import Align, Box, Color, Compound, Cylinder, Pos

from .parameters import PlanterConfig


@dataclass
class ModelBuild:
    shape: Compound
    bom: list[dict[str, Any]]
    metadata: dict[str, Any]


RAW_STEEL = Color(0.34, 0.36, 0.38)
GALVANISED = Color(0.68, 0.70, 0.72)
WOOD = Color(0.58, 0.38, 0.20)
GEOTEXTILE = Color(0.20, 0.21, 0.22)
DRAIN = Color(0.12, 0.13, 0.14)
POLYMER = Color(0.08, 0.08, 0.09)
FASTENER = Color(0.72, 0.73, 0.74)

MIN_ALIGN = (Align.MIN, Align.MIN, Align.MIN)
CYLINDER_ALIGN = (Align.CENTER, Align.CENTER, Align.MIN)

STEEL_TUBE_40 = "Steel tube · Obramat 40x40x1.5"
STEEL_TUBE_20 = "Decapated steel tube · Obramat 20x20x1.5"
STEEL_ANGLE = "Steel angle · Obramat 20x20x3"
STEEL_FLAT_30 = "S275JR steel flat bar · Obramat 30x3"
TIMBER = "Laminated planed fir · Obramat 60x20"
TRAY_STEEL = "Galvanised steel sheet · Obramat 1 mm"
FOOT_CAP = "Plastic insert cap · Obramat 40x40"

P_TUBE_40 = "obramat-tube-40"
P_TUBE_20 = "obramat-tube-20"
P_ANGLE_20 = "obramat-angle-20"
P_FLAT_30 = "obramat-flat-30x3"
P_TIMBER = "obramat-timber-60x20"
P_TRAY_SHEET = "obramat-sheet-1mm"
P_FOOT_CAP = "obramat-foot-cap-40"
P_DRAIN = "leroy-bulkhead-20"


def _hollow_tube(length: float, size: float, wall: float, axis: str, label: str):
    if wall <= 0 or wall * 2 >= size:
        raise ValueError("Invalid square tube wall thickness")

    if axis == "x":
        outer_dims = (length, size, size)
        inner_dims = (length + 2, size - 2 * wall, size - 2 * wall)
        inner_pos = (-1, wall, wall)
    elif axis == "y":
        outer_dims = (size, length, size)
        inner_dims = (size - 2 * wall, length + 2, size - 2 * wall)
        inner_pos = (wall, -1, wall)
    elif axis == "z":
        outer_dims = (size, size, length)
        inner_dims = (size - 2 * wall, size - 2 * wall, length + 2)
        inner_pos = (wall, wall, -1)
    else:
        raise ValueError(f"Unsupported tube axis: {axis}")

    outer = Box(*outer_dims, align=MIN_ALIGN)
    inner = Pos(*inner_pos) * Box(*inner_dims, align=MIN_ALIGN)
    result = outer - inner
    result.label = label
    return result


def _top_flap_rail_x(overall_length: float, size: float, wall: float, flap: float, label: str):
    """40x40 rail with its top wall left as a closure flap at both ends.

    Fabrication: start from one `overall_length` blank. At each end remove the
    bottom and both side walls for `flap` mm, leaving only the top wall. The
    520 mm hollow body fits between posts while the two 40 mm top skins cover
    the open vertical tubes.
    """
    body_length = overall_length - 2 * flap
    body = Pos(flap, 0, 0) * _hollow_tube(body_length, size, wall, "x", label)
    left_flap = Pos(0, 0, size - wall) * Box(flap, size, wall, align=MIN_ALIGN)
    right_flap = Pos(overall_length - flap, 0, size - wall) * Box(
        flap, size, wall, align=MIN_ALIGN
    )
    result = Compound(children=[body, left_flap, right_flap])
    result.label = label
    return result


def _place(shape, position: tuple[float, float, float], label: str, color: Color):
    placed = Pos(*position) * shape
    placed.label = label
    placed.color = color
    return placed


def _angle_y(length: float, leg: float, wall: float, mirrored: bool = False, shelf_at_top: bool = True):
    shelf_z = leg - wall if shelf_at_top else 0
    shelf = Pos(0, 0, shelf_z) * Box(leg, length, wall, align=MIN_ALIGN)
    vertical_x = leg - wall if mirrored else 0
    vertical = Pos(vertical_x, 0, 0) * Box(wall, length, leg, align=MIN_ALIGN)
    return Compound(children=[shelf, vertical])


def _angle_x(length: float, leg: float, wall: float, mirrored: bool = False, shelf_at_top: bool = True):
    shelf_z = leg - wall if shelf_at_top else 0
    shelf = Pos(0, 0, shelf_z) * Box(length, leg, wall, align=MIN_ALIGN)
    vertical_y = leg - wall if mirrored else 0
    vertical = Pos(0, vertical_y, 0) * Box(length, wall, leg, align=MIN_ALIGN)
    return Compound(children=[shelf, vertical])


def _open_liner(width: float, depth: float, height: float, wall: float, label: str):
    outer = Box(width, depth, height, align=MIN_ALIGN)
    inner = Pos(wall, wall, wall) * Box(
        width - 2 * wall,
        depth - 2 * wall,
        height + 1,
        align=MIN_ALIGN,
    )
    result = outer - inner
    result.label = label
    return result


def _flat_ring(outer: float, inner: float, thickness: float, label: str):
    border = (outer - inner) / 2
    outside = Box(outer, outer, thickness, align=MIN_ALIGN)
    inside = Pos(border, border, -1) * Box(inner, inner, thickness + 2, align=MIN_ALIGN)
    result = outside - inside
    result.label = label
    return result


def _fastener_symbol(washer_radius: float, washer_thickness: float, head_radius: float, head_height: float):
    washer = Cylinder(washer_radius, washer_thickness, align=CYLINDER_ALIGN)
    head = Pos(0, 0, washer_thickness) * Cylinder(
        head_radius, head_height, align=CYLINDER_ALIGN
    )
    return Compound(children=[washer, head])


def _group_bom(parts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, str | None], dict[str, Any]] = {}
    for part in parts:
        key = (part["material"], part["profile"], part["cut"], part.get("product_id"))
        if key not in groups:
            groups[key] = {
                "material": part["material"],
                "profile": part["profile"],
                "cut": part["cut"],
                "quantity": 0,
                "part_ids": [],
                "product_id": part.get("product_id"),
            }
        groups[key]["quantity"] += 1
        groups[key]["part_ids"].append(part["id"])
    return list(groups.values())


def build_planter(config: PlanterConfig | None = None) -> ModelBuild:
    cfg = config or PlanterConfig()
    p = cfg.frame_size
    s = cfg.support_size

    if cfg.length != cfg.depth:
        raise ValueError("This model represents the 600x600 square planter")
    if cfg.inner_opening <= 0:
        raise ValueError("Main frame profile does not fit the specified envelope")
    if cfg.bag_clamp_outer >= cfg.inner_opening:
        raise ValueError("Bag clamp requires clearance inside the main frame")
    if cfg.tray_width >= cfg.inner_opening or cfg.tray_depth >= cfg.inner_opening:
        raise ValueError("Drain tray must fit between the legs")
    if cfg.bag_support_clear_gap <= 0:
        raise ValueError("Bag support rail layout is invalid")
    if cfg.slat_side_margin < 0:
        raise ValueError("Cladding layout does not fit between the corner posts")
    if cfg.tray_to_bottom_frame_clearance <= 0:
        raise ValueError("Drain tray collides with the lower frame")

    all_shapes: list[Any] = []
    parts: list[dict[str, Any]] = []
    viewer_nodes: dict[str, list[str]] = {
        "top_closure": [],
        "bag_support": [],
        "bag_clamp": [],
        "bag_frame": [],
        "bag_liner": [],
        "tray": [],
        "panel_mounts": [],
        "front_panel": [],
        "rear_panel": [],
        "left_panel": [],
        "right_panel": [],
    }

    def record(
        part_id: str,
        name: str,
        category: str,
        material: str,
        profile: str,
        cut: str,
        product_id: str | None = None,
        viewer_group: str | None = None,
        **extra: Any,
    ) -> None:
        entry: dict[str, Any] = {
            "id": part_id,
            "name": name,
            "category": category,
            "material": material,
            "profile": profile,
            "cut": cut,
        }
        if product_id:
            entry["product_id"] = product_id
        if viewer_group:
            entry["viewer_group"] = viewer_group
            viewer_nodes[viewer_group].append(part_id)
        entry.update(extra)
        parts.append(entry)

    def add_shape(
        part_id: str,
        name: str,
        shape,
        position: tuple[float, float, float],
        category: str,
        material: str,
        profile: str,
        cut: str,
        color: Color,
        product_id: str | None = None,
        viewer_group: str | None = None,
        **extra: Any,
    ) -> None:
        all_shapes.append(_place(shape, position, part_id, color))
        record(
            part_id,
            name,
            category,
            material,
            profile,
            cut,
            product_id=product_id,
            viewer_group=viewer_group,
            **extra,
        )

    def add_tube(
        part_id: str,
        name: str,
        length: float,
        size: float,
        wall: float,
        axis: str,
        position: tuple[float, float, float],
        category: str,
        material: str,
        product_id: str,
        viewer_group: str | None = None,
    ) -> None:
        add_shape(
            part_id,
            name,
            _hollow_tube(length, size, wall, axis, part_id),
            position,
            category,
            material,
            f"{size:g}x{size:g}x{wall:g} mm square tube",
            f"{length:g} mm",
            RAW_STEEL,
            product_id=product_id,
            viewer_group=viewer_group,
            length_mm=length,
        )

    def add_box(
        part_id: str,
        name: str,
        dimensions: tuple[float, float, float],
        position: tuple[float, float, float],
        category: str,
        material: str,
        profile: str,
        cut: str,
        color: Color,
        product_id: str | None = None,
        viewer_group: str | None = None,
        **extra: Any,
    ) -> None:
        add_shape(
            part_id,
            name,
            Box(*dimensions, align=MIN_ALIGN),
            position,
            category,
            material,
            profile,
            cut,
            color,
            product_id=product_id,
            viewer_group=viewer_group,
            **extra,
        )

    # MAIN WELDED FRAME -------------------------------------------------
    uprights = [
        ("U01", "Front-left upright / leg", (0, 0, 0)),
        ("U02", "Front-right upright / leg", (cfg.length - p, 0, 0)),
        ("U03", "Rear-left upright / leg", (0, cfg.depth - p, 0)),
        ("U04", "Rear-right upright / leg", (cfg.length - p, cfg.depth - p, 0)),
    ]
    for part_id, name, position in uprights:
        add_tube(
            part_id, name, cfg.body_height, p, cfg.frame_wall, "z", position,
            "main_frame", STEEL_TUBE_40, P_TUBE_40
        )

    lower_rails = [
        ("R01", "Front lower rail", "x", (p, 0, cfg.bottom_frame_z)),
        ("R02", "Rear lower rail", "x", (p, cfg.depth - p, cfg.bottom_frame_z)),
        ("R03", "Left lower rail", "y", (0, p, cfg.bottom_frame_z)),
        ("R04", "Right lower rail", "y", (cfg.length - p, p, cfg.bottom_frame_z)),
    ]
    for part_id, name, axis, position in lower_rails:
        add_tube(
            part_id, name, cfg.frame_rail_length, p, cfg.frame_wall, axis, position,
            "main_frame", STEEL_TUBE_40, P_TUBE_40
        )

    # Front/rear top rails are cut from 600 mm blanks. Their hollow 520 mm body
    # fits between posts, while the top wall remains 40 mm long at each end and
    # closes the open upright from above. The flap is welded around its perimeter.
    for part_id, name, y in (
        ("R05", "Front top rail with post-closing flaps", 0.0),
        ("R06", "Rear top rail with post-closing flaps", cfg.depth - p),
    ):
        add_shape(
            part_id,
            name,
            _top_flap_rail_x(cfg.length, p, cfg.frame_wall, cfg.top_cap_flap_length, part_id),
            (0, y, cfg.top_frame_z),
            "main_frame_top_closure",
            STEEL_TUBE_40,
            f"{p:g}x{p:g}x{cfg.frame_wall:g} mm square tube · integral top-wall flaps",
            "600 mm blank; remove side+bottom walls for 40 mm at both ends",
            RAW_STEEL,
            product_id=P_TUBE_40,
            viewer_group="top_closure",
            blank_length_mm=cfg.length,
            flap_length_mm=cfg.top_cap_flap_length,
            note="leave the 1.5 mm top wall intact at each 40 mm end; it lies flat over the upright and is perimeter-welded",
        )

    for part_id, name, x in (
        ("R07", "Left top rail", 0.0),
        ("R08", "Right top rail", cfg.length - p),
    ):
        add_tube(
            part_id, name, cfg.frame_rail_length, p, cfg.frame_wall, "y",
            (x, p, cfg.top_frame_z), "main_frame", STEEL_TUBE_40, P_TUBE_40
        )

    for index, (x, y) in enumerate(
        ((0, 0), (cfg.length - p, 0), (0, cfg.depth - p), (cfg.length - p, cfg.depth - p)),
        start=1,
    ):
        add_box(
            f"FC{index:02d}", f"40x40 leg insert cap {index}",
            (p, p, cfg.foot_cap_visible), (x, y, 0),
            "foot", FOOT_CAP, "40x40 insert cap", "1 pc", POLYMER,
            product_id=P_FOOT_CAP,
            note="symbolic visible pad; insert body is inside the tube",
        )

    # BAG LOAD PLATFORM -------------------------------------------------
    # Two X bearers are welded to the lower frame. Five Y rails sit between them
    # and directly support the geotextile bottom. No perforated plate is used.
    add_tube(
        "S01", "Front bag-support bearer", cfg.inner_opening, s, cfg.support_wall,
        "x", (p, p - s, cfg.bag_support_z), "bag_support", STEEL_TUBE_20,
        P_TUBE_20, "bag_support"
    )
    add_tube(
        "S02", "Rear bag-support bearer", cfg.inner_opening, s, cfg.support_wall,
        "x", (p, cfg.depth - p, cfg.bag_support_z), "bag_support", STEEL_TUBE_20,
        P_TUBE_20, "bag_support"
    )

    for i in range(cfg.bag_support_crossbar_count):
        x = cfg.bag_xy + i * cfg.bag_support_pitch
        add_tube(
            f"S{i + 3:02d}",
            f"Bag bottom support rail {i + 1}",
            cfg.inner_opening,
            s,
            cfg.support_wall,
            "y",
            (x, p, cfg.bag_support_z),
            "bag_support",
            STEEL_TUBE_20,
            P_TUBE_20,
            "bag_support",
        )

    # BAG FRAME SUPPORT LEDGES -----------------------------------------
    ledge_z = cfg.top_frame_z
    ledges = [
        ("A01", "Front bag-frame ledge", _angle_x(cfg.bag_ledge_length, cfg.angle_leg, cfg.angle_wall, False, False), ((cfg.length - cfg.bag_ledge_length) / 2, p, ledge_z)),
        ("A02", "Rear bag-frame ledge", _angle_x(cfg.bag_ledge_length, cfg.angle_leg, cfg.angle_wall, True, False), ((cfg.length - cfg.bag_ledge_length) / 2, cfg.depth - p - cfg.angle_leg, ledge_z)),
        ("A03", "Left bag-frame ledge", _angle_y(cfg.bag_ledge_length, cfg.angle_leg, cfg.angle_wall, False, False), (p, (cfg.depth - cfg.bag_ledge_length) / 2, ledge_z)),
        ("A04", "Right bag-frame ledge", _angle_y(cfg.bag_ledge_length, cfg.angle_leg, cfg.angle_wall, True, False), (cfg.length - p - cfg.angle_leg, (cfg.depth - cfg.bag_ledge_length) / 2, ledge_z)),
    ]
    for part_id, name, shape, position in ledges:
        add_shape(
            part_id, name, shape, position, "bag_frame_support", STEEL_ANGLE,
            f"{cfg.angle_leg:g}x{cfg.angle_leg:g}x{cfg.angle_wall:g} mm angle",
            f"{cfg.bag_ledge_length:g} mm", RAW_STEEL,
            product_id=P_ANGLE_20, length_mm=cfg.bag_ledge_length,
        )

    # REMOVABLE BAG RIM FRAME ------------------------------------------
    bag_offset = (cfg.length - cfg.bag_frame_outer) / 2
    add_tube("B01", "Bag rim front rail", cfg.bag_frame_outer, s, cfg.support_wall, "x", (bag_offset, bag_offset, cfg.bag_frame_z), "bag_frame", STEEL_TUBE_20, P_TUBE_20, "bag_frame")
    add_tube("B02", "Bag rim rear rail", cfg.bag_frame_outer, s, cfg.support_wall, "x", (bag_offset, bag_offset + cfg.bag_frame_outer - s, cfg.bag_frame_z), "bag_frame", STEEL_TUBE_20, P_TUBE_20, "bag_frame")
    add_tube("B03", "Bag rim left rail", cfg.bag_frame_side_cut, s, cfg.support_wall, "y", (bag_offset, bag_offset + s, cfg.bag_frame_z), "bag_frame", STEEL_TUBE_20, P_TUBE_20, "bag_frame")
    add_tube("B04", "Bag rim right rail", cfg.bag_frame_side_cut, s, cfg.support_wall, "y", (bag_offset + cfg.bag_frame_outer - s, bag_offset + s, cfg.bag_frame_z), "bag_frame", STEEL_TUBE_20, P_TUBE_20, "bag_frame")

    bag_size = cfg.bag_inner_opening
    add_shape(
        "G01", "Geotextile grow bag body",
        _open_liner(bag_size, bag_size, cfg.bag_height, cfg.bag_wall, "G01"),
        (cfg.bag_xy, cfg.bag_xy, cfg.bag_bottom_z),
        "liner", "Geotextile fabric", f"nominal {bag_size:g}x{bag_size:g} mm",
        f"{cfg.bag_height:g} mm high", GEOTEXTILE,
        viewer_group="bag_liner",
        note=f"bottom rests directly on five 20x20 rails with about {cfg.bag_support_clear_gap:g} mm clear gaps; drainage remains fully open",
    )
    add_shape(
        "G02", "Folded geotextile clamping collar",
        _flat_ring(cfg.bag_frame_outer, cfg.bag_inner_opening, cfg.bag_fold_thickness, "G02"),
        (bag_offset, bag_offset, cfg.bag_frame_top_z),
        "liner_clamp", "Doubled geotextile fabric",
        f"{cfg.support_size:g} mm continuous folded collar",
        f"{cfg.bag_frame_outer:g} mm square", GEOTEXTILE,
        viewer_group="bag_liner",
        note="continuous fold lies on the 20x20 tube and is compressed by the 30x3 flat-bar frame",
    )

    # CONTINUOUS BAG CLAMP FRAME ---------------------------------------
    clamp_offset = (cfg.length - cfg.bag_clamp_outer) / 2
    cw = cfg.bag_clamp_width
    ct = cfg.bag_clamp_thickness
    co = cfg.bag_clamp_outer
    side_cut = cfg.bag_clamp_side_cut
    clamp_z = cfg.bag_clamp_z
    clamp_parts = [
        ("C01", "Front bag clamp bar", (co, cw, ct), (clamp_offset, clamp_offset, clamp_z), co),
        ("C02", "Rear bag clamp bar", (co, cw, ct), (clamp_offset, clamp_offset + co - cw, clamp_z), co),
        ("C03", "Left bag clamp bar", (cw, side_cut, ct), (clamp_offset, clamp_offset + cw, clamp_z), side_cut),
        ("C04", "Right bag clamp bar", (cw, side_cut, ct), (clamp_offset + co - cw, clamp_offset + cw, clamp_z), side_cut),
    ]
    for part_id, name, dims, pos, cut_length in clamp_parts:
        add_box(
            part_id, name, dims, pos, "bag_clamp", STEEL_FLAT_30,
            f"{cfg.bag_clamp_width:g}x{cfg.bag_clamp_thickness:g} mm flat bar",
            f"{cut_length:g} mm", RAW_STEEL,
            product_id=P_FLAT_30, viewer_group="bag_clamp", length_mm=cut_length,
        )

    fastener_shape = _fastener_symbol(
        cfg.clamp_washer_radius, cfg.clamp_washer_thickness,
        cfg.clamp_head_radius, cfg.clamp_head_height,
    )
    fastener_z = clamp_z + ct
    line_positions = (140.0, 300.0, 460.0)
    fastener_positions: list[tuple[float, float, float]] = []
    for x in line_positions:
        fastener_positions.append((x, bag_offset + s / 2, fastener_z))
        fastener_positions.append((x, bag_offset + cfg.bag_frame_outer - s / 2, fastener_z))
    for y in line_positions:
        fastener_positions.append((bag_offset + s / 2, y, fastener_z))
        fastener_positions.append((bag_offset + cfg.bag_frame_outer - s / 2, y, fastener_z))
    for index, pos in enumerate(fastener_positions, start=1):
        add_shape(
            f"H{index:02d}", f"Bag clamp M5 fastener {index}", fastener_shape, pos,
            "bag_clamp_fastener", "Stainless M5 fastener + washer / rivnut",
            "M5 symbolic fastener", "1 pc", FASTENER,
            viewer_group="bag_clamp",
            note="fastener provides clamp pressure; the liner is not suspended from isolated screw holes",
        )

    # DRAIN TRAY + GUIDES ----------------------------------------------
    tray_x = (cfg.length - cfg.tray_width) / 2
    tray_y = (cfg.depth - cfg.tray_depth) / 2
    t = cfg.tray_sheet
    h = cfg.tray_wall_height
    w = cfg.tray_width
    d = cfg.tray_depth
    tray = Compound(children=[
        Box(w, d, t, align=MIN_ALIGN),
        Pos(0, 0, t) * Box(t, d, h - t, align=MIN_ALIGN),
        Pos(w - t, 0, t) * Box(t, d, h - t, align=MIN_ALIGN),
        Pos(t, 0, t) * Box(w - 2 * t, t, h - t, align=MIN_ALIGN),
        Pos(t, d - t, t) * Box(w - 2 * t, t, h - t, align=MIN_ALIGN),
    ])
    add_shape(
        "TR01", "Removable drain tray", tray, (tray_x, tray_y, cfg.tray_z),
        "drain_tray", TRAY_STEEL, "1 mm folded galvanised sheet",
        f"finished {w:g}x{d:g}x{h:g} mm", GALVANISED,
        product_id=P_TRAY_SHEET, viewer_group="tray",
        blank_mm=[w + 2 * h, d + 2 * h],
        note="kept unchanged for now; final tray material and corner construction remain open",
    )

    guide_z = cfg.tray_z - cfg.angle_leg
    left_guide_x = p - 10.0
    right_guide_x = cfg.length - p - 10.0
    add_shape("TG01", "Left drain-tray guide", _angle_y(cfg.inner_opening, cfg.angle_leg, cfg.angle_wall, False, True), (left_guide_x, p, guide_z), "tray_guide", STEEL_ANGLE, f"{cfg.angle_leg:g}x{cfg.angle_leg:g}x{cfg.angle_wall:g} mm angle", f"{cfg.inner_opening:g} mm", RAW_STEEL, product_id=P_ANGLE_20, length_mm=cfg.inner_opening)
    add_shape("TG02", "Right drain-tray guide", _angle_y(cfg.inner_opening, cfg.angle_leg, cfg.angle_wall, True, True), (right_guide_x, p, guide_z), "tray_guide", STEEL_ANGLE, f"{cfg.angle_leg:g}x{cfg.angle_leg:g}x{cfg.angle_wall:g} mm angle", f"{cfg.inner_opening:g} mm", RAW_STEEL, product_id=P_ANGLE_20, length_mm=cfg.inner_opening)

    drain = Cylinder(8.0, cfg.tray_z - 20.0, align=CYLINDER_ALIGN)
    add_shape(
        "D01", "Controlled-drain bulkhead fitting", drain,
        (tray_x + cfg.drain_local_x, tray_y + cfg.drain_local_y, 20.0),
        "drainage", "20 mm / 1/2 in bulkhead fitting", "nominal fitting envelope",
        "1 pc", DRAIN, product_id=P_DRAIN, viewer_group="tray",
        note="verify the real fitting drill diameter before punching the tray",
    )

    # TIMBER SIDE PANELS ------------------------------------------------
    panel_defs = [
        ("F", "Front", "front", "front_panel"),
        ("R", "Rear", "rear", "rear_panel"),
        ("L", "Left", "left", "left_panel"),
        ("Q", "Right", "right", "right_panel"),
    ]
    opening_start = p + cfg.slat_side_margin
    pitch = cfg.slat_width + cfg.slat_gap

    for prefix, face_name, face, viewer_group in panel_defs:
        for i in range(cfg.slat_count_per_face):
            offset = opening_start + i * pitch
            if face == "front":
                dims, pos = (cfg.slat_width, cfg.slat_thickness, cfg.slat_height), (offset, 0, cfg.slat_z)
            elif face == "rear":
                dims, pos = (cfg.slat_width, cfg.slat_thickness, cfg.slat_height), (offset, cfg.depth - cfg.slat_thickness, cfg.slat_z)
            elif face == "left":
                dims, pos = (cfg.slat_thickness, cfg.slat_width, cfg.slat_height), (0, offset, cfg.slat_z)
            else:
                dims, pos = (cfg.slat_thickness, cfg.slat_width, cfg.slat_height), (cfg.length - cfg.slat_thickness, offset, cfg.slat_z)
            add_box(
                f"{prefix}W{i + 1:02d}", f"{face_name} timber slat {i + 1}", dims, pos,
                "cladding", TIMBER, f"{cfg.slat_width:g}x{cfg.slat_thickness:g} mm timber",
                f"{cfg.slat_height:g} mm", WOOD,
                product_id=P_TIMBER, viewer_group=viewer_group, panel=face_name,
            )

        for j, z in enumerate((cfg.batten_z_low, cfg.batten_z_high), start=1):
            if face == "front":
                dims, pos = (cfg.inner_opening, cfg.batten_thickness, cfg.batten_height), (p, cfg.slat_thickness, z)
            elif face == "rear":
                dims, pos = (cfg.inner_opening, cfg.batten_thickness, cfg.batten_height), (p, cfg.depth - cfg.slat_thickness - cfg.batten_thickness, z)
            elif face == "left":
                dims, pos = (cfg.batten_thickness, cfg.inner_opening, cfg.batten_height), (cfg.slat_thickness, p, z)
            else:
                dims, pos = (cfg.batten_thickness, cfg.inner_opening, cfg.batten_height), (cfg.length - cfg.slat_thickness - cfg.batten_thickness, p, z)
            add_box(
                f"{prefix}B{j:02d}", f"{face_name} concealed timber batten {j}", dims, pos,
                "cladding_batten", TIMBER,
                f"{cfg.batten_height:g}x{cfg.batten_thickness:g} mm timber",
                f"{cfg.inner_opening:g} mm", WOOD,
                product_id=P_TIMBER, viewer_group=viewer_group, panel=face_name,
                note="slats fixed from rear; D4 exterior adhesive plus stainless brads or short stainless screws",
            )

    # PANEL-TO-STEEL MOUNTS --------------------------------------------
    # Each panel gets four mounts: one near each end of each horizontal batten.
    # A 50x30x3 flat-bar tab overlaps the corner post by 20 mm and is welded to
    # its inner face. An M5x16 stainless screw is inserted from inside the planter
    # through a clearance hole in the tab into an M5 threaded insert set in the
    # rear face of the timber batten. Nothing is visible from the outside.
    tab_l = cfg.panel_tab_length
    tab_h = cfg.panel_tab_height
    tab_t = cfg.panel_tab_thickness
    overlap = cfg.panel_tab_post_overlap
    z_positions = [
        cfg.batten_z_low + (cfg.batten_height - tab_h) / 2,
        cfg.batten_z_high + (cfg.batten_height - tab_h) / 2,
    ]

    mount_index = 1
    for face in ("front", "rear", "left", "right"):
        for z in z_positions:
            for side in ("a", "b"):
                if face in ("front", "rear"):
                    x = p - overlap if side == "a" else cfg.length - p - (tab_l - overlap)
                    y = p if face == "front" else cfg.depth - p - tab_t
                    dims = (tab_l, tab_t, tab_h)
                    screw_x = p + (tab_l - overlap) / 2 if side == "a" else cfg.length - p - (tab_l - overlap) / 2
                    screw_y = p + tab_t if face == "front" else cfg.depth - p - tab_t - cfg.panel_mount_screw_length
                    screw_dims = (8.0, cfg.panel_mount_screw_length, 8.0)
                    screw_pos = (screw_x - 4.0, screw_y, z + tab_h / 2 - 4.0)
                else:
                    y = p - overlap if side == "a" else cfg.depth - p - (tab_l - overlap)
                    x = p if face == "left" else cfg.length - p - tab_t
                    dims = (tab_t, tab_l, tab_h)
                    screw_y = p + (tab_l - overlap) / 2 if side == "a" else cfg.depth - p - (tab_l - overlap) / 2
                    screw_x = p + tab_t if face == "left" else cfg.length - p - tab_t - cfg.panel_mount_screw_length
                    screw_dims = (cfg.panel_mount_screw_length, 8.0, 8.0)
                    screw_pos = (screw_x, screw_y - 4.0, z + tab_h / 2 - 4.0)

                add_box(
                    f"MT{mount_index:02d}", f"{face.title()} panel welded mounting tab {mount_index}",
                    dims, (x, y, z), "panel_mount_tab", STEEL_FLAT_30,
                    f"30x3 mm flat bar tab · {tab_l:g} mm long", f"{tab_l:g} mm",
                    RAW_STEEL, product_id=P_FLAT_30, viewer_group="panel_mounts",
                    note=f"20 mm overlaps the 40x40 corner post for welding; remaining 30 mm sits behind the timber batten",
                )
                add_box(
                    f"MH{mount_index:02d}", f"{face.title()} panel M5 concealed fastener {mount_index}",
                    screw_dims, screw_pos, "panel_mount_fastener",
                    "Stainless M5x16 screw + M5 threaded wood insert",
                    "symbolic screw/insert envelope", "1 set", FASTENER,
                    viewer_group="panel_mounts",
                    note="screw is accessed from inside the planter; it passes through the welded tab and threads into an insert in the 20 mm timber batten",
                )
                mount_index += 1

    assembly = Compound(label="square-planter-600-v4", children=all_shapes)

    products = [
        {"id": P_TUBE_40, "retailer": "Obramat", "ref": "10330425", "name": "Tubo cuadrado acero 40x40x1,5 mm · 3 m", "url": "https://www.obramat.es/productos/tubo-cuadrado-acero-40x40x1-5mm-3m-10330425.html", "stock": "3 m", "suggested_qty": 3},
        {"id": P_TUBE_20, "retailer": "Obramat", "ref": "10362443", "name": "Tubo cuadrado acero decapado 20x20x1,5 mm · 3 m", "url": "https://www.obramat.es/productos/tubo-cuadrado-acero-decapado-20x20x1-5mm-3m-10362443.html", "stock": "3 m", "suggested_qty": 2},
        {"id": P_ANGLE_20, "retailer": "Obramat", "ref": "10257156", "name": "Ángulo acero 20x20x3 mm · 1 m", "url": "https://www.obramat.es/productos/angulo-acero-20x20x3mm-1m-10257156.html", "stock": "1 m", "suggested_qty": 2},
        {"id": P_FLAT_30, "retailer": "Obramat", "ref": "10636696", "name": "Pletina acero S275JR 30x3 mm · 3 m", "url": "https://www.obramat.es/productos/pletina-acero-x275jr-30x3mm-3m-10636696.html", "stock": "3 m", "suggested_qty": 1, "note": "one bar supplies both the bag clamp frame and the 16 panel mounting tabs"},
        {"id": P_TIMBER, "retailer": "Obramat", "ref": "10786265", "name": "Listón abeto laminado cepillado 2500x60x20 mm", "url": "https://www.obramat.es/productos/liston-de-abeto-laminado-cepillado-2500x60x20mm-10786265.html", "stock": "2.5 m", "suggested_qty": 8, "note": "requires exterior treatment before installation"},
        {"id": P_TRAY_SHEET, "retailer": "Obramat", "ref": "10577532", "name": "Chapa acero galvanizada 2000x1000x1 mm", "url": "https://www.obramat.es/productos/chapa-de-acero-galvanizada-2000x1000x1mm-10577532.html", "stock": "2000x1000x1 mm sheet", "suggested_qty": 1},
        {"id": P_FOOT_CAP, "retailer": "Obramat", "ref": "10424295", "name": "Contera plástico embutir 40x40 mm negra · 4 uds", "url": "https://www.obramat.es/productos/contera-plastico-embutir-40-x-40-mm-negra-4-uds-10424295.html", "stock": "pack of 4", "suggested_qty": 1},
        {"id": P_DRAIN, "retailer": "Leroy Merlin", "ref": "83450729", "name": "Pasamuros roscado 1/2 in para depósitos · 20 mm", "url": "https://www.leroymerlin.es/productos/pasamuros-roscado-1-2-para-depositos-20-mm-83450729.html", "stock": "1 pc", "suggested_qty": 1},
    ]

    viewer_groups = [
        {"id": "top_closure", "label": "Top closure rails", "node_names": viewer_nodes["top_closure"], "offset_mm": [0, 0, 220]},
        {"id": "bag_support", "label": "Bag support tubes", "node_names": viewer_nodes["bag_support"], "offset_mm": [0, 0, -220]},
        {"id": "bag_clamp", "label": "Bag clamp", "node_names": viewer_nodes["bag_clamp"], "offset_mm": [-650, 0, 360]},
        {"id": "bag_frame", "label": "Bag rim frame", "node_names": viewer_nodes["bag_frame"], "offset_mm": [-650, 0, 190]},
        {"id": "bag_liner", "label": "Geotextile bag", "node_names": viewer_nodes["bag_liner"], "offset_mm": [-650, 0, -60]},
        {"id": "tray", "label": "Drain tray", "node_names": viewer_nodes["tray"], "offset_mm": [700, 0, -80]},
        {"id": "panel_mounts", "label": "Panel mounting hardware", "node_names": viewer_nodes["panel_mounts"], "offset_mm": [0, 0, 180]},
        {"id": "front_panel", "label": "Front timber panel", "node_names": viewer_nodes["front_panel"], "offset_mm": [0, -260, 0]},
        {"id": "rear_panel", "label": "Rear timber panel", "node_names": viewer_nodes["rear_panel"], "offset_mm": [0, 260, 0]},
        {"id": "left_panel", "label": "Left timber panel", "node_names": viewer_nodes["left_panel"], "offset_mm": [-260, 0, 0]},
        {"id": "right_panel", "label": "Right timber panel", "node_names": viewer_nodes["right_panel"], "offset_mm": [260, 0, 0]},
    ]

    metadata = {
        "schema_version": 4,
        "model": "square-planter-600-v4",
        "status": "fabrication design / v4",
        "units": "mm",
        "parameters": asdict(cfg),
        "derived": {
            "inner_opening_mm": cfg.inner_opening,
            "leg_clearance_mm": cfg.leg_clearance,
            "bottom_frame_z_mm": cfg.bottom_frame_z,
            "bag_useful_width_mm": cfg.bag_inner_opening,
            "bag_useful_height_mm": cfg.bag_height,
            "bag_volume_litres": round(cfg.bag_volume_litres, 1),
            "bag_support_rail_count": cfg.bag_support_crossbar_count,
            "bag_support_clear_gap_mm": cfg.bag_support_clear_gap,
            "bag_clamp_outer_mm": cfg.bag_clamp_outer,
            "bag_clamp_clearance_each_side_mm": (cfg.inner_opening - cfg.bag_clamp_outer) / 2,
            "tray_side_clearance_each_side_mm": cfg.tray_side_clearance,
            "tray_to_bottom_frame_vertical_clearance_mm": cfg.tray_to_bottom_frame_clearance,
            "slat_side_margin_mm": cfg.slat_side_margin,
            "panel_frame_fixings_each": 4,
            "panel_count": 4,
            "top_open_posts_closed_by_integral_flaps": 4,
        },
        "parts": parts,
        "products": products,
        "viewer": {
            "model_src": "./models/planter.glb",
            "groups": viewer_groups,
            "selected_part_offset_mm": 260,
        },
        "assemblies": [
            {"id": "AS01", "name": "Welded planter body", "contains": "40x40 main frame, integral post-closing top flaps, five-rail bag platform, bag ledges, tray guides and welded panel tabs"},
            {"id": "AS02", "name": "Four removable timber side panels", "contains": "7 vertical slats + 2 horizontal battens per face + 4 concealed M5 mounts"},
            {"id": "AS03", "name": "Removable geotextile bag assembly", "contains": "20x20 rim frame + folded liner collar + continuous 30x3 clamp frame"},
            {"id": "AS04", "name": "Removable drain tray", "contains": ["TR01", "D01"]},
        ],
        "joints": [
            {"id": "J01", "type": "weld", "name": "Main 40x40 frame", "spec": "square-cut butt joints; four continuous posts; lower rails and side top rails welded between posts"},
            {"id": "J02", "type": "weld", "name": "Top post closures", "spec": "front and rear top rails use 600 mm blanks; remove side and bottom walls for 40 mm at each end, leave the top wall as a flap over each upright and perimeter-weld it"},
            {"id": "J03", "type": "weld", "name": "Bag support grid", "spec": "two 20x20 bearers plus five 20x20 cross rails; geotextile rests directly on the rails with approximately 90 mm clear gaps"},
            {"id": "J04", "type": "weld", "name": "Bag-frame ledges", "spec": "4 x 100 mm 20x20x3 angle pieces welded to inner faces of top rails"},
            {"id": "J05", "type": "weld", "name": "Tray guides", "spec": "20x20x3 angle guides welded between front/rear legs"},
            {"id": "J06", "type": "clamp", "name": "Geotextile rim clamp", "spec": "folded geotextile is continuously compressed between 20x20 tube and 30x3 flat bar; M5 fasteners provide clamp pressure only"},
            {"id": "J07", "type": "wood-panel", "name": "Slats to timber battens", "spec": "fix from rear; D4 exterior adhesive plus stainless brads or short stainless screws"},
            {"id": "J08", "type": "mechanical", "name": "Timber panel to steel frame", "spec": "4 per panel: 50x30x3 welded flat-bar tab, 20 mm welded overlap on corner post, M5x16 stainless screw from inside into an M5 threaded insert in the rear face of the 60x20 timber batten"},
        ],
        "service": {
            "tray_removal": "slides rearward below the lower 40x40 frame",
            "panel_removal_required_for_tray": False,
            "panel_removal": "remove four M5 screws from inside; welded tabs remain on the steel frame",
            "bag_removal": "lift the bag assembly by the rigid rim only after removing enough substrate for a safe manual lift",
        },
        "purchases": [
            {"product_id": P_TUBE_40, "suggested_qty": 3},
            {"product_id": P_TUBE_20, "suggested_qty": 2},
            {"product_id": P_ANGLE_20, "suggested_qty": 2},
            {"product_id": P_FLAT_30, "suggested_qty": 1},
            {"product_id": P_TIMBER, "suggested_qty": 8},
            {"product_id": P_TRAY_SHEET, "suggested_qty": 1},
            {"product_id": P_FOOT_CAP, "suggested_qty": 1},
            {"product_id": P_DRAIN, "suggested_qty": 1},
        ],
        "fabrication_notes": [
            "The four 40x40 uprights are not left open at the top: the front/rear top rails carry integral 40 mm top-wall flaps that cover and weld to the upright mouths.",
            "The integral-flap solution uses a simple 600 mm blank and avoids separate caps or paired 45-degree corner flaps.",
            "The perforated load-spreader plate has been removed. Five 20x20 rails directly support the bag bottom with roughly 90 mm clear drainage gaps.",
            "The geotextile does not hang from individual screws: its folded rim is continuously clamped between the 20x20 tube frame and 30x3 flat bars.",
            "Each timber face is a removable panel: 7 slats on 2 concealed timber battens.",
            "Each timber panel uses four welded 30x3 steel tabs and four concealed M5 screws into threaded inserts in the battens; there are no visible exterior panel screws.",
            "The panel mounting tabs reuse offcuts from the same 30x3 flat bar specified for the bag clamp.",
            "Foot caps are represented symbolically; verify the purchased insert depth before final cutting/painting.",
        ],
        "notes": [
            "Exact weld bead size, paint system, geotextile specification and final M5 insert model should be frozen before fabrication drawings are issued.",
            "The drain tray is intentionally unchanged in this revision; its final material and corner construction remain open.",
            "The web viewer uses one GLB; exploded views are virtual node transforms driven by metadata and can be applied to groups or selected parts.",
        ],
    }

    return ModelBuild(shape=assembly, bom=_group_bom(parts), metadata=metadata)
