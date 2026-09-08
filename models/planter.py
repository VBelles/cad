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
MIN_ALIGN = (Align.MIN, Align.MIN, Align.MIN)
CYLINDER_ALIGN = (Align.CENTER, Align.CENTER, Align.MIN)

STEEL_TUBE_40 = "Raw steel tube · Obramat 40x40x1.5"
STEEL_TUBE_20 = "Decapated steel tube · Obramat 20x20x1.5"
STEEL_ANGLE = "Raw steel angle · Obramat 20x20x3"
STEEL_FLAT = "Raw steel flat bar · Obramat 20x4"
TIMBER = "Planed laminated fir · Obramat 60x20"
TRAY_STEEL = "Galvanised steel sheet · 1 mm"


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


def _angle_y(
    length: float,
    leg: float,
    wall: float,
    mirrored: bool = False,
    shelf_at_top: bool = True,
):
    """L angle running along Y. shelf_at_top=False is used for upward ledges."""
    shelf_z = leg - wall if shelf_at_top else 0
    shelf = Pos(0, 0, shelf_z) * Box(leg, length, wall, align=MIN_ALIGN)
    vertical_x = leg - wall if mirrored else 0
    vertical = Pos(vertical_x, 0, 0) * Box(wall, length, leg, align=MIN_ALIGN)
    return Compound(children=[shelf, vertical])


def _angle_x(
    length: float,
    leg: float,
    wall: float,
    mirrored: bool = False,
    shelf_at_top: bool = True,
):
    """L angle running along X. shelf_at_top=False is used for upward ledges."""
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
        raise ValueError("Drain tray must fit through the rear frame opening")
    if cfg.slat_side_margin < 0:
        raise ValueError("Cladding layout does not fit between the corner posts")

    shapes = []
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
    ) -> None:
        shape = _hollow_tube(length, size, wall, axis, part_id)
        shapes.append(_place(shape, position, part_id, RAW_STEEL))
        record(
            part_id,
            name,
            category,
            material,
            f"{size:g}x{size:g}x{wall:g} mm square tube",
            f"{length:g} mm",
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
        **extra: Any,
    ) -> None:
        shape = Box(*dimensions, align=MIN_ALIGN)
        shapes.append(_place(shape, position, part_id, color))
        record(part_id, name, category, material, profile, cut, **extra)

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
        **extra: Any,
    ) -> None:
        shapes.append(_place(shape, position, part_id, color))
        record(part_id, name, category, material, profile, cut, **extra)

    # MAIN WELDED FRAME -------------------------------------------------
    # Full-height corner posts define the 600x600x600 envelope. Every 520 mm
    # rail is square-cut and butts against a post face; no main members overlap.
    uprights = [
        ("U01", "Front-left upright", (0, 0, 0)),
        ("U02", "Front-right upright", (cfg.length - p, 0, 0)),
        ("U03", "Rear-left upright", (0, cfg.depth - p, 0)),
        ("U04", "Rear-right upright", (cfg.length - p, cfg.depth - p, 0)),
    ]
    for part_id, name, position in uprights:
        add_tube(
            part_id,
            name,
            cfg.body_height,
            p,
            cfg.frame_wall,
            "z",
            position,
            "main_frame",
            STEEL_TUBE_40,
        )

    top_z = cfg.body_height - p
    rails = [
        ("R01", "Front bottom rail", "x", (p, 0, 0)),
        ("R02", "Rear bottom rail", "x", (p, cfg.depth - p, 0)),
        ("R03", "Left bottom rail", "y", (0, p, 0)),
        ("R04", "Right bottom rail", "y", (cfg.length - p, p, 0)),
        ("R05", "Front top rail", "x", (p, 0, top_z)),
        ("R06", "Rear top rail", "x", (p, cfg.depth - p, top_z)),
        ("R07", "Left top rail", "y", (0, p, top_z)),
        ("R08", "Right top rail", "y", (cfg.length - p, p, top_z)),
    ]
    for part_id, name, axis, position in rails:
        add_tube(
            part_id,
            name,
            cfg.frame_rail_length,
            p,
            cfg.frame_wall,
            axis,
            position,
            "main_frame",
            STEEL_TUBE_40,
        )

    # LOAD PLATFORM FOR THE BAG ---------------------------------------
    # Cross rails sit partly within the Y footprint of the front/rear posts, so
    # their 20x20 end faces genuinely butt against the X=40 / X=560 post faces.
    # Three longitudinal rails then butt between the two cross rails.
    support_cross_y_front = p - s
    support_cross_y_rear = cfg.depth - p
    add_tube(
        "S01",
        "Front bag-support cross rail",
        cfg.frame_rail_length,
        s,
        cfg.support_wall,
        "x",
        (p, support_cross_y_front, cfg.bag_support_z),
        "bag_support",
        STEEL_TUBE_20,
    )
    add_tube(
        "S02",
        "Rear bag-support cross rail",
        cfg.frame_rail_length,
        s,
        cfg.support_wall,
        "x",
        (p, support_cross_y_rear, cfg.bag_support_z),
        "bag_support",
        STEEL_TUBE_20,
    )

    longitudinal_start_y = support_cross_y_front + s
    longitudinal_length = support_cross_y_rear - longitudinal_start_y
    for index, x in enumerate((80.0, 290.0, 500.0), start=3):
        add_tube(
            f"S{index:02d}",
            ("Left" if index == 3 else "Centre" if index == 4 else "Right")
            + " bag-support rail",
            longitudinal_length,
            s,
            cfg.support_wall,
            "y",
            (x, longitudinal_start_y, cfg.bag_support_z),
            "bag_support",
            STEEL_TUBE_20,
        )

    # REMOVABLE UPPER BAG FRAME ---------------------------------------
    # 500 mm outside dimension leaves 10 mm clearance per side in the 520 mm
    # opening. The side rails are 460 mm to avoid overlap with front/rear rails.
    bag_offset = (cfg.length - cfg.bag_frame_outer) / 2
    add_tube(
        "B01",
        "Bag frame front rail",
        cfg.bag_frame_outer,
        s,
        cfg.support_wall,
        "x",
        (bag_offset, bag_offset, cfg.bag_frame_z),
        "bag_frame",
        STEEL_TUBE_20,
    )
    add_tube(
        "B02",
        "Bag frame rear rail",
        cfg.bag_frame_outer,
        s,
        cfg.support_wall,
        "x",
        (bag_offset, bag_offset + cfg.bag_frame_outer - s, cfg.bag_frame_z),
        "bag_frame",
        STEEL_TUBE_20,
    )
    add_tube(
        "B03",
        "Bag frame left rail",
        cfg.bag_frame_side_cut,
        s,
        cfg.support_wall,
        "y",
        (bag_offset, bag_offset + s, cfg.bag_frame_z),
        "bag_frame",
        STEEL_TUBE_20,
    )
    add_tube(
        "B04",
        "Bag frame right rail",
        cfg.bag_frame_side_cut,
        s,
        cfg.support_wall,
        "y",
        (bag_offset + cfg.bag_frame_outer - s, bag_offset + s, cfg.bag_frame_z),
        "bag_frame",
        STEEL_TUBE_20,
    )

    # Eight 100 mm L-angle ledges. The shelf is the lower leg: its upper face is
    # Z=550, while the vertical leg continues upward to Z=567 and reaches the
    # inner face of the top 40 mm frame (Z=560..600) for a real weld connection.
    ledge_z = cfg.bag_frame_z - cfg.angle_wall
    angle_positions = [
        ("A01", "Front-left bag-frame ledge", "x", False, (90, p, ledge_z)),
        ("A02", "Front-right bag-frame ledge", "x", False, (410, p, ledge_z)),
        ("A03", "Rear-left bag-frame ledge", "x", True, (90, cfg.depth - p - cfg.angle_leg, ledge_z)),
        ("A04", "Rear-right bag-frame ledge", "x", True, (410, cfg.depth - p - cfg.angle_leg, ledge_z)),
        ("A05", "Left-front bag-frame ledge", "y", False, (p, 90, ledge_z)),
        ("A06", "Left-rear bag-frame ledge", "y", False, (p, 410, ledge_z)),
        ("A07", "Right-front bag-frame ledge", "y", True, (cfg.length - p - cfg.angle_leg, 90, ledge_z)),
        ("A08", "Right-rear bag-frame ledge", "y", True, (cfg.length - p - cfg.angle_leg, 410, ledge_z)),
    ]
    for part_id, name, axis, mirrored, position in angle_positions:
        angle = (
            _angle_x(
                cfg.upper_support_length,
                cfg.angle_leg,
                cfg.angle_wall,
                mirrored,
                shelf_at_top=False,
            )
            if axis == "x"
            else _angle_y(
                cfg.upper_support_length,
                cfg.angle_leg,
                cfg.angle_wall,
                mirrored,
                shelf_at_top=False,
            )
        )
        add_shape(
            part_id,
            name,
            angle,
            position,
            "bag_frame_support",
            STEEL_ANGLE,
            f"{cfg.angle_leg:g}x{cfg.angle_leg:g}x{cfg.angle_wall:g} mm angle",
            f"{cfg.upper_support_length:g} mm",
            RAW_STEEL,
            length_mm=cfg.upper_support_length,
        )

    # Nominal geotextile envelope. The liner reaches the top frame sleeve and
    # stops on the load platform, so its weight is not carried only by the rim.
    bag_size = cfg.bag_inner_opening
    bag = _open_liner(bag_size, bag_size, cfg.bag_height, cfg.bag_wall, "G01")
    bag_xy = (cfg.length - bag_size) / 2
    add_shape(
        "G01",
        "Geotextile planting bag",
        bag,
        (bag_xy, bag_xy, cfg.bag_bottom_z),
        "liner",
        "Custom geotextile fabric",
        "open liner with upper frame sleeve",
        f"useful envelope approx. {bag_size:g}x{bag_size:g}x{cfg.bag_height:g} mm",
        GEOTEXTILE,
        note="sewing allowance and exact sleeve construction remain supplier-dependent",
    )

    # REMOVABLE DRAIN TRAY --------------------------------------------
    # 480 mm width gives 20 mm side clearance to the 520 mm rear opening. The
    # top lip is Z=120; the load platform begins at Z=125, leaving 5 mm while
    # sliding TR01 rearward below S02.
    tray_x = (cfg.length - cfg.tray_width) / 2
    tray_y = 55.0
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
        "TR01",
        "Removable drain tray",
        tray,
        (tray_x, tray_y, cfg.tray_z),
        "drainage",
        TRAY_STEEL,
        "1 mm folded sheet",
        (
            f"nominal blank {cfg.tray_blank_width:g}x{cfg.tray_blank_depth:g} mm; "
            f"finished {w:g}x{d:g}x{h:g} mm"
        ),
        GALVANISED,
        note="bend allowance must be corrected for actual brake/tooling before cutting",
    )

    # The guide shelves have their upper face at Z=110 and span Y=40..560.
    # Their end faces butt directly against the front/rear 40 mm uprights.
    guide_z = cfg.tray_z - cfg.angle_leg
    add_shape(
        "TG01",
        "Left drain-tray guide",
        _angle_y(cfg.inner_opening, cfg.angle_leg, cfg.angle_wall, False, True),
        (p, p, guide_z),
        "tray_guide",
        STEEL_ANGLE,
        f"{cfg.angle_leg:g}x{cfg.angle_leg:g}x{cfg.angle_wall:g} mm angle",
        f"{cfg.inner_opening:g} mm",
        RAW_STEEL,
        length_mm=cfg.inner_opening,
    )
    add_shape(
        "TG02",
        "Right drain-tray guide",
        _angle_y(cfg.inner_opening, cfg.angle_leg, cfg.angle_wall, True, True),
        (cfg.length - p - cfg.angle_leg, p, guide_z),
        "tray_guide",
        STEEL_ANGLE,
        f"{cfg.angle_leg:g}x{cfg.angle_leg:g}x{cfg.angle_wall:g} mm angle",
        f"{cfg.inner_opening:g} mm",
        RAW_STEEL,
        length_mm=cfg.inner_opening,
    )

    # Symbolic envelope for the controlled drain fitting. The catalogue's
    # nominal 20 mm is not assumed to be its drill diameter.
    drain = Cylinder(8.0, 28.0, align=CYLINDER_ALIGN)
    add_shape(
        "D01",
        "Controlled-drain bulkhead fitting",
        drain,
        (
            tray_x + cfg.drain_local_x,
            tray_y + cfg.drain_local_y,
            cfg.tray_z - 18.0,
        ),
        "drainage",
        "20 mm / 1/2 in bulkhead fitting",
        "nominal fitting envelope",
        "verify purchased fitting before drilling",
        DRAIN,
        nominal_mm=cfg.drain_nominal_diameter,
    )

    # TIMBER CLADDING --------------------------------------------------
    # The slats are flush with the 600 mm envelope and sit only in the 520 mm
    # openings. Seven 60 mm slats + six 12.5 mm gaps = 495 mm, leaving 12.5 mm
    # between the outer slats and each 40 mm corner post.
    slat_positions = [
        cfg.frame_size + cfg.slat_side_margin + i * (cfg.slat_width + cfg.slat_gap)
        for i in range(cfg.slat_count_per_face)
    ]

    slat_number = 1
    for face in ("front", "rear", "left", "right"):
        for position in slat_positions:
            part_id = f"W{slat_number:02d}"
            if face == "front":
                dims = (cfg.slat_width, cfg.slat_thickness, cfg.slat_height)
                pos = (position, 0, cfg.slat_z)
            elif face == "rear":
                dims = (cfg.slat_width, cfg.slat_thickness, cfg.slat_height)
                pos = (position, cfg.depth - cfg.slat_thickness, cfg.slat_z)
            elif face == "left":
                dims = (cfg.slat_thickness, cfg.slat_width, cfg.slat_height)
                pos = (0, position, cfg.slat_z)
            else:
                dims = (cfg.slat_thickness, cfg.slat_width, cfg.slat_height)
                pos = (cfg.length - cfg.slat_thickness, position, cfg.slat_z)

            add_box(
                part_id,
                f"{face.capitalize()} timber slat {slat_number}",
                dims,
                pos,
                "cladding_service_panel" if face == "rear" else "cladding_fixed",
                TIMBER,
                f"{cfg.slat_width:g}x{cfg.slat_thickness:g} mm timber slat",
                f"{cfg.slat_height:g} mm",
                WOOD,
                length_mm=cfg.slat_height,
                face=face,
                removable=(face == "rear"),
            )
            slat_number += 1

    # Fixed faces use welded 20x4 backing straps. Rear straps belong to the
    # removable service panel and are screwed to the timber instead of welded.
    strap_zs = (cfg.cladding_strap_z_low, cfg.cladding_strap_z_high)
    strap_id = 1
    for face in ("front", "rear", "left", "right"):
        for z in strap_zs:
            part_id = f"P{strap_id:02d}"
            if face == "front":
                dims = (cfg.inner_opening, cfg.flat_thickness, cfg.flat_width)
                pos = (p, cfg.slat_thickness, z)
            elif face == "rear":
                dims = (cfg.inner_opening, cfg.flat_thickness, cfg.flat_width)
                pos = (p, cfg.depth - cfg.slat_thickness - cfg.flat_thickness, z)
            elif face == "left":
                dims = (cfg.flat_thickness, cfg.inner_opening, cfg.flat_width)
                pos = (cfg.slat_thickness, p, z)
            else:
                dims = (cfg.flat_thickness, cfg.inner_opening, cfg.flat_width)
                pos = (cfg.length - cfg.slat_thickness - cfg.flat_thickness, p, z)

            add_box(
                part_id,
                f"{face.capitalize()} cladding backing strap",
                dims,
                pos,
                "service_panel_backing" if face == "rear" else "cladding_backing",
                STEEL_FLAT,
                f"{cfg.flat_width:g}x{cfg.flat_thickness:g} mm flat bar",
                f"{cfg.inner_opening:g} mm",
                RAW_STEEL,
                length_mm=cfg.inner_opening,
                face=face,
                welded_to_frame=(face != "rear"),
            )
            strap_id += 1

    # Four tabs are welded to the rear uprights. Their faces touch the rear
    # service-panel backing straps, allowing four hidden M5 fasteners.
    tab_specs = [
        ("MT01", p, cfg.cladding_strap_z_low),
        ("MT02", cfg.length - p - cfg.service_mount_tab_length, cfg.cladding_strap_z_low),
        ("MT03", p, cfg.cladding_strap_z_high),
        ("MT04", cfg.length - p - cfg.service_mount_tab_length, cfg.cladding_strap_z_high),
    ]
    for part_id, x, z in tab_specs:
        add_box(
            part_id,
            "Rear service-panel mounting tab",
            (cfg.service_mount_tab_length, cfg.flat_thickness, cfg.flat_width),
            (x, cfg.depth - cfg.slat_thickness - 2 * cfg.flat_thickness, z),
            "service_panel_mount",
            STEEL_FLAT,
            f"{cfg.flat_width:g}x{cfg.flat_thickness:g} mm flat bar",
            f"{cfg.service_mount_tab_length:g} mm",
            RAW_STEEL,
            length_mm=cfg.service_mount_tab_length,
            drilling="M5 clearance hole after dry fit",
        )

    joints: list[dict[str, Any]] = []
    rail_to_uprights = {
        "R01": ("U01", "U02"),
        "R02": ("U03", "U04"),
        "R03": ("U01", "U03"),
        "R04": ("U02", "U04"),
        "R05": ("U01", "U02"),
        "R06": ("U03", "U04"),
        "R07": ("U01", "U03"),
        "R08": ("U02", "U04"),
    }
    joint_index = 1
    for rail_id, upright_ids in rail_to_uprights.items():
        for upright_id in upright_ids:
            joints.append(
                {
                    "id": f"J{joint_index:03d}",
                    "type": "welded butt joint",
                    "parts": [rail_id, upright_id],
                    "fit": "0 mm nominal gap; square-cut rail end to upright face",
                    "weld": "continuous fillet around accessible perimeter; final size by fabricator",
                }
            )
            joint_index += 1

    joints.extend(
        [
            {
                "id": "JB01",
                "type": "welded support-grid assembly",
                "parts": ["S01", "S02", "S03", "S04", "S05", "U01", "U02", "U03", "U04"],
                "fit": "S01/S02 20x20 ends fully contact upright faces; S03-S05 butt between S01/S02",
                "weld": "fillet weld at every tube end; no tube overlap",
            },
            {
                "id": "JB02",
                "type": "removable gravity-supported bag frame",
                "parts": ["B01", "B02", "B03", "B04", "A01", "A02", "A03", "A04", "A05", "A06", "A07", "A08"],
                "fit": "500 mm frame inside 520 mm opening = 10 mm clearance per side; ledge shelf top Z=550",
                "weld": "A01-A08 welded to top frame; B01-B04 welded only to each other",
            },
            {
                "id": "JD01",
                "type": "sliding removable tray",
                "parts": ["TR01", "TG01", "TG02"],
                "fit": "10 mm tray overlap per guide; 5 mm vertical extraction clearance below bag-support grid",
                "weld": "TG01/TG02 butt-welded at ends to front/rear uprights; tray remains removable",
            },
            {
                "id": "JC01",
                "type": "fixed cladding screws",
                "parts": ["W01-W07", "W15-W28", "P01", "P02", "P05", "P06", "P07", "P08"],
                "fastener": "2 concealed timber-to-steel screws per slat, one at each backing strap",
            },
            {
                "id": "JC02",
                "type": "removable rear service panel",
                "parts": ["W08-W14", "P03", "P04", "MT01", "MT02", "MT03", "MT04"],
                "fastener": "rear slats screwed to P03/P04; complete panel fixed to MT01-MT04 with 4 removable M5 fasteners",
            },
            {
                "id": "JD02",
                "type": "controlled drainage",
                "parts": ["TR01", "D01"],
                "fit": "bulkhead near rear-right tray corner for hose/tap access behind service panel",
                "critical": "measure the purchased bulkhead; do not drill from nominal 20 mm catalogue size",
            },
        ]
    )

    assembly = Compound(label="square-planter-600-fabrication-v1", children=shapes)

    metadata = {
        "schema_version": 2,
        "model": "square-planter-600-fabrication-v1",
        "status": "fabrication design v1",
        "units": "mm",
        "parameters": asdict(cfg),
        "derived": {
            "inner_opening_mm": cfg.inner_opening,
            "bag_frame_clearance_each_side_mm": (cfg.inner_opening - cfg.bag_frame_outer) / 2,
            "bag_useful_width_mm": bag_size,
            "bag_useful_height_mm": cfg.bag_height,
            "tray_side_clearance_each_side_mm": (cfg.inner_opening - cfg.tray_width) / 2,
            "tray_to_support_vertical_clearance_mm": cfg.bag_support_z - (cfg.tray_z + cfg.tray_wall_height),
            "slat_margin_to_posts_mm": cfg.slat_side_margin,
            "support_longitudinal_cut_mm": longitudinal_length,
        },
        "parts": parts,
        "joints": joints,
        "service": {
            "service_face": "rear",
            "tray_removal_direction": "+Y / rearward",
            "procedure": [
                "Remove the four concealed M5 service-panel fasteners.",
                "Lift/remove the complete rear timber panel.",
                "Disconnect or cap the drain hose/fitting as required.",
                "Slide TR01 rearward along TG01/TG02 beneath the bag-support grid.",
            ],
        },
        "fabrication_notes": [
            "Main 40x40 rails are square-cut to 520 mm and butt between full-height 600 mm corner posts.",
            "S01/S02 are positioned for full 20x20 end-face contact with the corner uprights; S03-S05 butt between them.",
            "The removable bag frame is 500 mm outside dimension and bears on eight upward-facing L-angle ledges.",
            "The tray is removable and drained; its 10 mm wall is intentionally low to preserve extraction clearance.",
            "Galvanised tray bend allowance and drain drilling diameter must be finalised from the actual sheet-metal tooling and purchased fitting.",
            "Raw-steel parts require corrosion preparation, primer and topcoat after welding and before timber/geotextile installation.",
        ],
        "purchase_references": [
            {"item": "40x40x1.5 raw steel tube, 3 m", "supplier": "Obramat"},
            {"item": "20x20x1.5 decapated steel tube, 3 m", "supplier": "Obramat"},
            {"item": "20x20x3 raw steel angle, 1 m", "supplier": "Obramat"},
            {"item": "20x4 raw steel flat bar, 1 m", "supplier": "Obramat"},
            {"item": "60x20x2500 planed laminated fir slat", "supplier": "Obramat"},
            {"item": "1 mm galvanised steel sheet", "supplier": "Obramat"},
            {"item": "20 mm / 1/2 in bulkhead fitting", "supplier": "Leroy Merlin"},
        ],
        "notes": [
            "The trellis is intentionally excluded from this model.",
            "All rear decorative slats form one removable service panel, keeping the tray hidden in normal use.",
            "Weld beads and final drilled fastener holes are specified semantically rather than represented as final solids in v1.",
        ],
    }

    return ModelBuild(shape=assembly, bom=_group_bom(parts), metadata=metadata)
