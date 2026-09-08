from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from build123d import Align, Box, Color, Compound, Cylinder, Pos

from .parameters import PlanterConfig


@dataclass
class ModelBuild:
    shape: Compound
    exploded_shape: Compound
    bom: list[dict[str, Any]]
    metadata: dict[str, Any]


RAW_STEEL = Color(0.34, 0.36, 0.38)
GALVANISED = Color(0.68, 0.70, 0.72)
WOOD = Color(0.58, 0.38, 0.20)
GEOTEXTILE = Color(0.20, 0.21, 0.22)
DRAIN = Color(0.12, 0.13, 0.14)
POLYMER = Color(0.08, 0.08, 0.09)

MIN_ALIGN = (Align.MIN, Align.MIN, Align.MIN)
CYLINDER_ALIGN = (Align.CENTER, Align.CENTER, Align.MIN)

STEEL_TUBE_40 = "Raw steel tube · Obramat 40x40x1.5"
STEEL_TUBE_20 = "Decapated steel tube · Obramat 20x20x1.5"
STEEL_ANGLE = "Raw steel angle · Obramat 20x20x3"
TIMBER = "Planed fir · Obramat 60x20"
TRAY_STEEL = "Galvanised steel sheet · 1 mm"
FOOT_CAP = "Polyethylene insert cap · 40x40"


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


def _group_bom(parts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    for part in parts:
        key = (part["material"], part["profile"], part["cut"])
        if key not in groups:
            groups[key] = {
                "material": part["material"],
                "profile": part["profile"],
                "cut": part["cut"],
                "quantity": 0,
                "part_ids": [],
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
    if cfg.bag_frame_outer >= cfg.inner_opening:
        raise ValueError("Bag frame requires clearance inside the main frame")
    if cfg.tray_width >= cfg.inner_opening or cfg.tray_depth >= cfg.inner_opening:
        raise ValueError("Drain tray must fit between the legs")
    if cfg.slat_side_margin < 0:
        raise ValueError("Cladding layout does not fit between the corner posts")
    if cfg.tray_to_bottom_frame_clearance <= 0:
        raise ValueError("Drain tray collides with the lower frame")

    all_shapes: list[Any] = []
    exploded_groups: dict[str, list[Any]] = {"body": [], "bag": [], "tray": []}
    parts: list[dict[str, Any]] = []

    def record(
        part_id: str,
        name: str,
        category: str,
        material: str,
        profile: str,
        cut: str,
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
        group: str = "body",
        **extra: Any,
    ) -> None:
        placed = _place(shape, position, part_id, color)
        all_shapes.append(placed)
        exploded_groups[group].append(placed)
        record(part_id, name, category, material, profile, cut, **extra)

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
        group: str = "body",
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
            group=group,
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
        group: str = "body",
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
            group=group,
            **extra,
        )

    # MAIN FRAME --------------------------------------------------------
    # The four 600 mm posts are continuous: their lower 80 mm become the legs.
    uprights = [
        ("U01", "Front-left upright / leg", (0, 0, 0)),
        ("U02", "Front-right upright / leg", (cfg.length - p, 0, 0)),
        ("U03", "Rear-left upright / leg", (0, cfg.depth - p, 0)),
        ("U04", "Rear-right upright / leg", (cfg.length - p, cfg.depth - p, 0)),
    ]
    for part_id, name, position in uprights:
        add_tube(
            part_id, name, cfg.body_height, p, cfg.frame_wall, "z", position,
            "main_frame", STEEL_TUBE_40
        )

    rails = [
        ("R01", "Front lower rail", "x", (p, 0, cfg.bottom_frame_z)),
        ("R02", "Rear lower rail", "x", (p, cfg.depth - p, cfg.bottom_frame_z)),
        ("R03", "Left lower rail", "y", (0, p, cfg.bottom_frame_z)),
        ("R04", "Right lower rail", "y", (cfg.length - p, p, cfg.bottom_frame_z)),
        ("R05", "Front top rail", "x", (p, 0, cfg.top_frame_z)),
        ("R06", "Rear top rail", "x", (p, cfg.depth - p, cfg.top_frame_z)),
        ("R07", "Left top rail", "y", (0, p, cfg.top_frame_z)),
        ("R08", "Right top rail", "y", (cfg.length - p, p, cfg.top_frame_z)),
    ]
    for part_id, name, axis, position in rails:
        add_tube(
            part_id, name, cfg.frame_rail_length, p, cfg.frame_wall, axis, position,
            "main_frame", STEEL_TUBE_40
        )

    # Floor-protection caps are shown symbolically within the steel footprint.
    for index, (x, y) in enumerate(
        ((0, 0), (cfg.length - p, 0), (0, cfg.depth - p), (cfg.length - p, cfg.depth - p)),
        start=1,
    ):
        add_box(
            f"FC{index:02d}",
            f"40x40 leg insert cap {index}",
            (p, p, cfg.foot_cap_visible),
            (x, y, 0),
            "foot",
            FOOT_CAP,
            "40x40 insert cap",
            "1 pc",
            POLYMER,
            note="symbolic visible pad; insert body is inside the tube",
        )

    # BAG LOAD PLATFORM -------------------------------------------------
    # Front/rear 20x20 rails sit directly on the lower 40x40 rails.
    add_tube(
        "S01", "Front bag-support cross rail", cfg.inner_opening, s, cfg.support_wall,
        "x", (p, p - s, cfg.bag_support_z), "bag_support", STEEL_TUBE_20
    )
    add_tube(
        "S02", "Rear bag-support cross rail", cfg.inner_opening, s, cfg.support_wall,
        "x", (p, cfg.depth - p, cfg.bag_support_z), "bag_support", STEEL_TUBE_20
    )
    for index, x in enumerate((80.0, 290.0, 500.0), start=3):
        add_tube(
            f"S{index:02d}",
            ("Left" if index == 3 else "Centre" if index == 4 else "Right")
            + " bag-support rail",
            cfg.inner_opening,
            s,
            cfg.support_wall,
            "y",
            (x, p, cfg.bag_support_z),
            "bag_support",
            STEEL_TUBE_20,
        )

    # BAG FRAME SUPPORT LEDGES -----------------------------------------
    # Four short 20x20x3 angles are welded to the inner faces of the top rails.
    # Their shelf top is Z=563, so the removable 20x20 frame sits inside the
    # 40 mm top border and remains visually hidden from normal viewing angles.
    ledge_z = cfg.top_frame_z
    ledges = [
        (
            "A01", "Front bag-frame ledge",
            _angle_x(cfg.bag_ledge_length, cfg.angle_leg, cfg.angle_wall, False, False),
            ((cfg.length - cfg.bag_ledge_length) / 2, p, ledge_z),
        ),
        (
            "A02", "Rear bag-frame ledge",
            _angle_x(cfg.bag_ledge_length, cfg.angle_leg, cfg.angle_wall, True, False),
            ((cfg.length - cfg.bag_ledge_length) / 2, cfg.depth - p - cfg.angle_leg, ledge_z),
        ),
        (
            "A03", "Left bag-frame ledge",
            _angle_y(cfg.bag_ledge_length, cfg.angle_leg, cfg.angle_wall, False, False),
            (p, (cfg.depth - cfg.bag_ledge_length) / 2, ledge_z),
        ),
        (
            "A04", "Right bag-frame ledge",
            _angle_y(cfg.bag_ledge_length, cfg.angle_leg, cfg.angle_wall, True, False),
            (cfg.length - p - cfg.angle_leg, (cfg.depth - cfg.bag_ledge_length) / 2, ledge_z),
        ),
    ]
    for part_id, name, shape, position in ledges:
        add_shape(
            part_id, name, shape, position,
            "bag_frame_support", STEEL_ANGLE,
            f"{cfg.angle_leg:g}x{cfg.angle_leg:g}x{cfg.angle_wall:g} mm angle",
            f"{cfg.bag_ledge_length:g} mm",
            RAW_STEEL,
            length_mm=cfg.bag_ledge_length,
        )

    # REMOVABLE BAG + FRAME --------------------------------------------
    bag_offset = (cfg.length - cfg.bag_frame_outer) / 2
    add_tube(
        "B01", "Bag frame front rail", cfg.bag_frame_outer, s, cfg.support_wall,
        "x", (bag_offset, bag_offset, cfg.bag_frame_z),
        "bag_frame", STEEL_TUBE_20, group="bag"
    )
    add_tube(
        "B02", "Bag frame rear rail", cfg.bag_frame_outer, s, cfg.support_wall,
        "x", (bag_offset, bag_offset + cfg.bag_frame_outer - s, cfg.bag_frame_z),
        "bag_frame", STEEL_TUBE_20, group="bag"
    )
    add_tube(
        "B03", "Bag frame left rail", cfg.bag_frame_side_cut, s, cfg.support_wall,
        "y", (bag_offset, bag_offset + s, cfg.bag_frame_z),
        "bag_frame", STEEL_TUBE_20, group="bag"
    )
    add_tube(
        "B04", "Bag frame right rail", cfg.bag_frame_side_cut, s, cfg.support_wall,
        "y", (bag_offset + cfg.bag_frame_outer - s, bag_offset + s, cfg.bag_frame_z),
        "bag_frame", STEEL_TUBE_20, group="bag"
    )

    bag_size = cfg.bag_inner_opening
    bag_xy = (cfg.length - bag_size) / 2
    add_shape(
        "G01",
        "Geotextile grow bag",
        _open_liner(bag_size, bag_size, cfg.bag_height, cfg.bag_wall, "G01"),
        (bag_xy, bag_xy, cfg.support_top_z),
        "liner",
        "Geotextile fabric",
        f"nominal {bag_size:g}x{bag_size:g} mm",
        f"{cfg.bag_height:g} mm high",
        GEOTEXTILE,
        group="bag",
        note="nominal CAD envelope; sewing allowance and rim sleeve remain supplier-dependent",
    )

    # DRAIN TRAY + GUIDES ----------------------------------------------
    # The tray lives below the lower frame. It slides rearward between the legs,
    # so no timber panel needs to be removed for normal maintenance.
    tray_x = (cfg.length - cfg.tray_width) / 2
    tray_y = (cfg.depth - cfg.tray_depth) / 2
    t = cfg.tray_sheet
    h = cfg.tray_wall_height
    w = cfg.tray_width
    d = cfg.tray_depth
    tray = Compound(
        children=[
            Box(w, d, t, align=MIN_ALIGN),
            Pos(0, 0, t) * Box(t, d, h - t, align=MIN_ALIGN),
            Pos(w - t, 0, t) * Box(t, d, h - t, align=MIN_ALIGN),
            Pos(t, 0, t) * Box(w - 2 * t, t, h - t, align=MIN_ALIGN),
            Pos(t, d - t, t) * Box(w - 2 * t, t, h - t, align=MIN_ALIGN),
        ]
    )
    add_shape(
        "TR01", "Removable drain tray", tray, (tray_x, tray_y, cfg.tray_z),
        "drain_tray", TRAY_STEEL, "1 mm folded galvanised sheet",
        f"finished {w:g}x{d:g}x{h:g} mm",
        GALVANISED, group="tray",
        blank_mm=[w + 2 * h, d + 2 * h],
        note="correct bend allowance for the actual brake/tooling before cutting",
    )

    # Guides end against the front/rear legs and overlap the tray by 5 mm/side.
    guide_z = cfg.tray_z - cfg.angle_leg
    left_guide_x = p - 10.0
    right_guide_x = cfg.length - p - 10.0
    add_shape(
        "TG01", "Left drain-tray guide",
        _angle_y(cfg.inner_opening, cfg.angle_leg, cfg.angle_wall, False, True),
        (left_guide_x, p, guide_z),
        "tray_guide", STEEL_ANGLE,
        f"{cfg.angle_leg:g}x{cfg.angle_leg:g}x{cfg.angle_wall:g} mm angle",
        f"{cfg.inner_opening:g} mm", RAW_STEEL,
        length_mm=cfg.inner_opening,
    )
    add_shape(
        "TG02", "Right drain-tray guide",
        _angle_y(cfg.inner_opening, cfg.angle_leg, cfg.angle_wall, True, True),
        (right_guide_x, p, guide_z),
        "tray_guide", STEEL_ANGLE,
        f"{cfg.angle_leg:g}x{cfg.angle_leg:g}x{cfg.angle_wall:g} mm angle",
        f"{cfg.inner_opening:g} mm", RAW_STEEL,
        length_mm=cfg.inner_opening,
    )

    drain = Cylinder(8.0, cfg.tray_z - 20.0, align=CYLINDER_ALIGN)
    add_shape(
        "D01", "Controlled-drain bulkhead fitting", drain,
        (tray_x + cfg.drain_local_x, tray_y + cfg.drain_local_y, 20.0),
        "drainage", "20 mm / 1/2 in bulkhead fitting",
        "nominal fitting envelope", "1 pc", DRAIN, group="tray",
        note="verify the real fitting drill diameter before punching the tray",
    )

    # TIMBER SIDE PANELS ------------------------------------------------
    # Each face is a removable wood panel: seven vertical slats fixed from the
    # rear to two concealed horizontal 60x20 battens. The whole panel needs only
    # four concealed frame fixings (two per batten). Exact small bracket/rivnut
    # hardware remains selectable without changing the panel geometry.
    panel_defs = [
        ("F", "Front", "front"),
        ("R", "Rear", "rear"),
        ("L", "Left", "left"),
        ("Q", "Right", "right"),
    ]
    opening_start = p + cfg.slat_side_margin
    pitch = cfg.slat_width + cfg.slat_gap

    for prefix, face_name, face in panel_defs:
        for i in range(cfg.slat_count_per_face):
            offset = opening_start + i * pitch
            if face == "front":
                dims = (cfg.slat_width, cfg.slat_thickness, cfg.slat_height)
                pos = (offset, 0, cfg.slat_z)
            elif face == "rear":
                dims = (cfg.slat_width, cfg.slat_thickness, cfg.slat_height)
                pos = (offset, cfg.depth - cfg.slat_thickness, cfg.slat_z)
            elif face == "left":
                dims = (cfg.slat_thickness, cfg.slat_width, cfg.slat_height)
                pos = (0, offset, cfg.slat_z)
            else:
                dims = (cfg.slat_thickness, cfg.slat_width, cfg.slat_height)
                pos = (cfg.length - cfg.slat_thickness, offset, cfg.slat_z)

            add_box(
                f"{prefix}W{i + 1:02d}",
                f"{face_name} timber slat {i + 1}",
                dims, pos, "cladding", TIMBER,
                f"{cfg.slat_width:g}x{cfg.slat_thickness:g} mm timber",
                f"{cfg.slat_height:g} mm",
                WOOD,
                panel=face_name,
            )

        for j, z in enumerate((cfg.batten_z_low, cfg.batten_z_high), start=1):
            if face == "front":
                dims = (cfg.inner_opening, cfg.batten_thickness, cfg.batten_height)
                pos = (p, cfg.slat_thickness, z)
            elif face == "rear":
                dims = (cfg.inner_opening, cfg.batten_thickness, cfg.batten_height)
                pos = (p, cfg.depth - cfg.slat_thickness - cfg.batten_thickness, z)
            elif face == "left":
                dims = (cfg.batten_thickness, cfg.inner_opening, cfg.batten_height)
                pos = (cfg.slat_thickness, p, z)
            else:
                dims = (cfg.batten_thickness, cfg.inner_opening, cfg.batten_height)
                pos = (cfg.length - cfg.slat_thickness - cfg.batten_thickness, p, z)

            add_box(
                f"{prefix}B{j:02d}",
                f"{face_name} concealed timber batten {j}",
                dims, pos, "cladding_batten", TIMBER,
                f"{cfg.batten_height:g}x{cfg.batten_thickness:g} mm timber",
                f"{cfg.inner_opening:g} mm",
                WOOD,
                panel=face_name,
                note="slats fixed from rear; D4 exterior adhesive + stainless brads/screws recommended",
            )

    assembly = Compound(label="square-planter-600-v2", children=all_shapes)

    body_compound = Compound(label="planter-body", children=exploded_groups["body"])
    bag_compound = Compound(label="bag-and-frame", children=exploded_groups["bag"])
    tray_compound = Compound(label="tray-and-drain", children=exploded_groups["tray"])
    exploded = Compound(
        label="square-planter-600-logical-exploded",
        children=[
            body_compound,
            Pos(-720, 0, 220) * bag_compound,
            Pos(720, 0, 0) * tray_compound,
        ],
    )

    metadata = {
        "schema_version": 2,
        "model": "square-planter-600-v2",
        "status": "fabrication design / v2",
        "units": "mm",
        "parameters": asdict(cfg),
        "derived": {
            "inner_opening_mm": cfg.inner_opening,
            "leg_clearance_mm": cfg.leg_clearance,
            "bottom_frame_z_mm": cfg.bottom_frame_z,
            "bag_useful_width_mm": cfg.bag_inner_opening,
            "bag_useful_height_mm": cfg.bag_height,
            "bag_volume_litres": round(cfg.bag_volume_litres, 1),
            "bag_frame_clearance_each_side_mm": (cfg.inner_opening - cfg.bag_frame_outer) / 2,
            "tray_side_clearance_each_side_mm": cfg.tray_side_clearance,
            "tray_to_bottom_frame_vertical_clearance_mm": cfg.tray_to_bottom_frame_clearance,
            "slat_side_margin_mm": cfg.slat_side_margin,
            "panel_frame_fixings_each": 4,
            "panel_count": 4,
        },
        "parts": parts,
        "assemblies": [
            {
                "id": "AS01",
                "name": "Welded planter body",
                "contains": "main frame, bag load platform, bag ledges, tray guides, feet",
            },
            {
                "id": "AS02",
                "name": "Four timber side panels",
                "contains": "7 vertical slats + 2 horizontal battens per face",
            },
            {
                "id": "AS03",
                "name": "Removable geotextile bag and rim frame",
                "contains": ["B01", "B02", "B03", "B04", "G01"],
            },
            {
                "id": "AS04",
                "name": "Removable drain tray",
                "contains": ["TR01", "D01"],
            },
        ],
        "joints": [
            {
                "id": "J01",
                "type": "weld",
                "name": "Main 40x40 frame",
                "spec": "square-cut butt joints; continuous posts; rails welded between posts",
            },
            {
                "id": "J02",
                "type": "weld",
                "name": "Bag support grid",
                "spec": "20x20 support rails welded together and to the lower frame",
            },
            {
                "id": "J03",
                "type": "weld",
                "name": "Bag-frame ledges",
                "spec": "4 x 100 mm 20x20x3 angle pieces welded to inner faces of top rails",
            },
            {
                "id": "J04",
                "type": "weld",
                "name": "Tray guides",
                "spec": "20x20x3 angle guides welded between front/rear legs",
            },
            {
                "id": "J05",
                "type": "wood-panel",
                "name": "Slats to timber battens",
                "spec": "fix from rear; D4 exterior adhesive plus stainless brads or short stainless screws",
            },
            {
                "id": "J06",
                "type": "mechanical",
                "name": "Timber panel to steel frame",
                "spec": "4 concealed fixings per face; exact small bracket/rivnut hardware to select before drilling",
            },
        ],
        "service": {
            "tray_removal": "slides rearward below the lower 40x40 frame",
            "panel_removal_required_for_tray": False,
            "bag_removal": "lift complete geotextile bag by its removable 20x20 rim frame",
        },
        "purchases": [
            {"item": "40x40x1.5 raw steel tube", "stock": "3 m", "suggested_qty": 3},
            {"item": "20x20x1.5 steel tube", "stock": "3 m", "suggested_qty": 2},
            {"item": "20x20x3 steel angle", "stock": "1 m", "suggested_qty": 2},
            {"item": "60x20 planed fir", "stock": "2.5 m", "suggested_qty": 8},
            {"item": "1 mm galvanised sheet", "stock": "sheet", "suggested_qty": 1},
            {"item": "40x40 polyethylene insert caps", "stock": "pack of 4", "suggested_qty": 1},
        ],
        "fabrication_notes": [
            "Main lower frame is raised 80 mm; the four continuous uprights form the legs.",
            "Tray sits below the lower frame and is removable without touching the timber panels.",
            "The removable bag rim frame is hidden inside the 40 mm top border.",
            "The load platform carries the soil weight; the geotextile rim is not the sole structural support.",
            "Each timber face is built as one panel: 7 slats on 2 concealed horizontal timber battens.",
            "Only four concealed steel-frame fixings are required per timber panel.",
            "Foot caps are represented symbolically; verify the purchased insert depth before final cutting/painting.",
        ],
        "notes": [
            "Exact weld size, paint system, drain-hole diameter and panel mounting hardware should be frozen before fabrication drawings are issued.",
            "The exploded GLB separates the assembled planter body, bag+frame and tray+drain rather than exploding every individual part.",
        ],
    }

    return ModelBuild(
        shape=assembly,
        exploded_shape=exploded,
        bom=_group_bom(parts),
        metadata=metadata,
    )
