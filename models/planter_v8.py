from __future__ import annotations

import math
from dataclasses import asdict
from typing import Any

from build123d import Align, Box, Color, Compound, Cylinder, Pos

from .parameters import PlanterConfig
from .planter import (
    DRAIN,
    FASTENER,
    FOOT_CAP,
    GEOTEXTILE,
    ModelBuild,
    POLYMER,
    STEEL_ANGLE,
    STEEL_FLAT_30,
    STEEL_TUBE_20,
    STEEL_TUBE_40,
    P_ANGLE_20,
    P_DRAIN,
    P_FLAT_30,
    P_FOOT_CAP,
    P_TUBE_20,
    P_TUBE_40,
    _angle_x,
    _angle_y,
    _group_bom,
    _hollow_tube,
    _open_liner,
)

MIN_ALIGN = (Align.MIN, Align.MIN, Align.MIN)
CYLINDER_ALIGN = (Align.CENTER, Align.CENTER, Align.MIN)
PAINTED_STEEL = Color(0.94, 0.94, 0.93)
WOOD = Color(0.58, 0.38, 0.20)
PLASTIC_TRAY = Color(0.16, 0.17, 0.18)

DIVIDER_MATERIAL = "S275JR steel flat plate"
DIVIDER_PROFILE = "80x5 mm flat plate"


def _top_flap_rail_x(overall_length: float, size: float, wall: float, flap: float, label: str):
    body_length = overall_length - 2 * flap
    body = Pos(flap, 0, 0) * _hollow_tube(body_length, size, wall, "x", label)
    left_flap = Pos(0, 0, size - wall) * Box(flap, size, wall, align=MIN_ALIGN)
    right_flap = Pos(overall_length - flap, 0, size - wall) * Box(
        flap, size, wall, align=MIN_ALIGN
    )
    result = Compound(children=[body, left_flap, right_flap])
    result.label = label
    return result


def _flat_rect_ring(
    outer_x: float,
    outer_y: float,
    inner_x: float,
    inner_y: float,
    thickness: float,
    label: str,
):
    bx = (outer_x - inner_x) / 2
    by = (outer_y - inner_y) / 2
    outside = Box(outer_x, outer_y, thickness, align=MIN_ALIGN)
    inside = Pos(bx, by, -1) * Box(inner_x, inner_y, thickness + 2, align=MIN_ALIGN)
    result = outside - inside
    result.label = label
    return result


def _open_tray(width: float, depth: float, height: float, wall: float):
    return Compound(
        children=[
            Box(width, depth, wall, align=MIN_ALIGN),
            Pos(0, 0, wall) * Box(wall, depth, height - wall, align=MIN_ALIGN),
            Pos(width - wall, 0, wall)
            * Box(wall, depth, height - wall, align=MIN_ALIGN),
            Pos(wall, 0, wall)
            * Box(width - 2 * wall, wall, height - wall, align=MIN_ALIGN),
            Pos(wall, depth - wall, wall)
            * Box(width - 2 * wall, wall, height - wall, align=MIN_ALIGN),
        ]
    )


def _fastener_symbol(cfg: PlanterConfig):
    washer = Cylinder(
        cfg.clamp_washer_radius,
        cfg.clamp_washer_thickness,
        align=CYLINDER_ALIGN,
    )
    head = Pos(0, 0, cfg.clamp_washer_thickness) * Cylinder(
        cfg.clamp_head_radius,
        cfg.clamp_head_height,
        align=CYLINDER_ALIGN,
    )
    return Compound(children=[washer, head])


def _panel_screw_symbol(cfg: PlanterConfig):
    shaft = Cylinder(
        cfg.panel_mount_screw_diameter / 2,
        cfg.panel_mount_screw_length,
        align=CYLINDER_ALIGN,
    )
    head = Pos(0, 0, -cfg.panel_mount_head_thickness) * Cylinder(
        cfg.panel_mount_head_radius,
        cfg.panel_mount_head_thickness,
        align=CYLINDER_ALIGN,
    )
    return Compound(children=[shaft, head])


def _stock_qty(lengths_mm: list[float], stock_mm: float, kerf_mm: float = 3.0) -> int:
    bins: list[float] = []
    for raw_length in sorted(lengths_mm, reverse=True):
        length = raw_length + kerf_mm
        for i, remaining in enumerate(bins):
            if length <= remaining + 1e-6:
                bins[i] -= length
                break
        else:
            if raw_length > stock_mm + 1e-6:
                raise ValueError(f"{raw_length:g} mm part is longer than {stock_mm:g} mm stock")
            bins.append(stock_mm - length)
    return len(bins)


def _slat_layout(opening: float, cfg: PlanterConfig) -> tuple[int, float]:
    count = max(
        1,
        math.floor((opening + cfg.slat_gap) / (cfg.slat_width + cfg.slat_gap)),
    )
    occupied = count * cfg.slat_width + (count - 1) * cfg.slat_gap
    return count, (opening - occupied) / 2


def _batten_zs(cfg: PlanterConfig) -> list[float]:
    count = cfg.module_panel_batten_count
    first_center = cfg.module_panel_bottom_z + cfg.batten_edge_center_offset
    last_center = cfg.module_panel_top_z - cfg.batten_edge_center_offset
    if count == 2:
        centers = [first_center, last_center]
    else:
        step = (last_center - first_center) / (count - 1)
        centers = [first_center + i * step for i in range(count)]
    return [centre - cfg.batten_height / 2 for centre in centers]


def build_planter(
    config: PlanterConfig | None = None,
    model_id: str = "planter-600x600x600",
) -> ModelBuild:
    cfg = config or PlanterConfig()
    p = cfg.frame_size
    s = cfg.support_size
    divider_t = getattr(cfg, "divider_plate_thickness", 5.0)
    divider_w = getattr(cfg, "divider_plate_width", 80.0)

    if cfg.bays_x < 1:
        raise ValueError("At least one grow module is required")
    if cfg.panel_outer_inset < 0:
        raise ValueError("v8 keeps timber within the exterior steel plane")
    if cfg.depth <= 2 * p:
        raise ValueError("Planter is too shallow for the 40x40 perimeter frame")

    divider_count = cfg.bays_x - 1
    bay_open = (
        cfg.length - 2 * p - divider_count * divider_t
    ) / cfg.bays_x
    inner_depth = cfg.depth - 2 * p
    inner_length = cfg.length - 2 * p

    if bay_open <= 0:
        raise ValueError("Requested length cannot fit the selected module count")
    if divider_w < 2 * (cfg.bag_frame_margin + s):
        raise ValueError(
            "Divider support plate is too narrow to share bearing between adjacent bag rims"
        )

    bag_outer_x = bay_open - 2 * cfg.bag_frame_margin
    bag_outer_y = inner_depth - 2 * cfg.bag_frame_margin
    bag_inner_x = bag_outer_x - 2 * s
    bag_inner_y = bag_outer_y - 2 * s
    if bag_inner_x <= 0 or bag_inner_y <= 0:
        raise ValueError("Grow module is too small for the current rim margins")

    bag_frame_top_z = cfg.body_height - cfg.bag_top_clearance
    bag_frame_z = bag_frame_top_z - s
    bag_support_top_z = bag_frame_top_z - cfg.soil_depth
    bag_support_z = bag_support_top_z - s
    if bag_support_z < cfg.bottom_frame_z:
        raise ValueError("Soil depth is too large for this body height")

    bag_clamp_outer_x = bag_outer_x + 2 * cfg.bag_clamp_overhang
    bag_clamp_outer_y = bag_outer_y + 2 * cfg.bag_clamp_overhang
    bag_clamp_z = bag_frame_top_z + cfg.bag_fold_thickness

    support_count = 2
    while (
        bag_inner_x - support_count * s
    ) / (support_count - 1) > cfg.support_max_clear_gap:
        support_count += 1
    support_gap = (bag_inner_x - support_count * s) / (support_count - 1)

    tray_w = min(cfg.tray_target_width, bay_open - 2 * cfg.tray_edge_margin)
    tray_d = min(cfg.tray_target_depth, inner_depth - 2 * cfg.tray_edge_margin)
    if tray_w <= 0 or tray_d <= 0:
        raise ValueError("Commercial tray placeholder does not fit")

    shapes: list[Any] = []
    parts: list[dict[str, Any]] = []
    groups = {
        name: []
        for name in (
            "top_closure",
            "divider_plates",
            "bag_support",
            "bag_clamp",
            "bag_frame",
            "bag_liner",
            "trays",
            "panel_mounts",
            "front_panel",
            "rear_panel",
            "left_panel",
            "right_panel",
        )
    }
    stock_cuts = {
        P_TUBE_40: [],
        P_TUBE_20: [],
        P_ANGLE_20: [],
        P_FLAT_30: [],
    }
    counters: dict[str, int] = {}

    def next_id(prefix: str) -> str:
        counters[prefix] = counters.get(prefix, 0) + 1
        return f"{prefix}{counters[prefix]:02d}"

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
        stock_cut_mm: float | None = None,
        **extra: Any,
    ) -> None:
        placed = Pos(*position) * shape
        placed.label = part_id
        placed.color = color
        shapes.append(placed)
        item: dict[str, Any] = {
            "id": part_id,
            "name": name,
            "category": category,
            "material": material,
            "profile": profile,
            "cut": cut,
        }
        if product_id:
            item["product_id"] = product_id
        if viewer_group:
            item["viewer_group"] = viewer_group
            groups[viewer_group].append(part_id)
        if stock_cut_mm is not None:
            item["length_mm"] = stock_cut_mm
            if product_id in stock_cuts:
                stock_cuts[product_id].append(stock_cut_mm)
        item.update(extra)
        parts.append(item)

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
            PAINTED_STEEL,
            product_id,
            viewer_group,
            length,
        )

    # --- Main frame: always four corner legs, regardless of length ----------
    for x in (0.0, cfg.length - p):
        for face, y in (("front", 0.0), ("rear", cfg.depth - p)):
            add_tube(
                next_id("U"),
                f"{face.title()} corner upright / leg",
                cfg.body_height,
                p,
                cfg.frame_wall,
                "z",
                (x, y, 0),
                "main_frame",
                STEEL_TUBE_40,
                P_TUBE_40,
            )
            add_shape(
                next_id("FC"),
                f"{face.title()} corner leg insert cap",
                Box(p, p, cfg.foot_cap_visible, align=MIN_ALIGN),
                (x, y, 0),
                "foot",
                FOOT_CAP,
                "40x40 insert cap",
                "1 pc",
                POLYMER,
                P_FOOT_CAP,
            )

    # Continuous lower front/rear rails.
    for face, y in (("front", 0.0), ("rear", cfg.depth - p)):
        add_tube(
            next_id("R"),
            f"Continuous {face} lower rail",
            inner_length,
            p,
            cfg.frame_wall,
            "x",
            (p, y, cfg.bottom_frame_z),
            "main_frame",
            STEEL_TUBE_40,
            P_TUBE_40,
        )

    # End lower transverse rails.
    for side, x in (("left", 0.0), ("right", cfg.length - p)):
        add_tube(
            next_id("R"),
            f"{side.title()} lower transverse rail",
            inner_depth,
            p,
            cfg.frame_wall,
            "y",
            (x, p, cfg.bottom_frame_z),
            "main_frame",
            STEEL_TUBE_40,
            P_TUBE_40,
        )

    # Continuous top front/rear rails close all four corner-post mouths.
    for face, y in (("front", 0.0), ("rear", cfg.depth - p)):
        closure_id = next_id("TC")
        add_shape(
            closure_id,
            f"Continuous {face} top rail with integral corner-closing flaps",
            _top_flap_rail_x(cfg.length, p, cfg.frame_wall, p, closure_id),
            (0, y, cfg.top_frame_z),
            "main_frame_top_closure",
            STEEL_TUBE_40,
            f"{p:g}x{p:g}x{cfg.frame_wall:g} mm tube · integral top-wall flaps",
            f"{cfg.length:g} mm blank",
            PAINTED_STEEL,
            P_TUBE_40,
            "top_closure",
            cfg.length,
        )

    for side, x in (("left", 0.0), ("right", cfg.length - p)):
        add_tube(
            next_id("R"),
            f"{side.title()} top transverse rail",
            inner_depth,
            p,
            cfg.frame_wall,
            "y",
            (x, p, cfg.top_frame_z),
            "main_frame",
            STEEL_TUBE_40,
            P_TUBE_40,
        )

    # --- Module positions and shared divider/support plates -----------------
    bay_starts = [
        p + bay * (bay_open + divider_t)
        for bay in range(cfg.bays_x)
    ]
    divider_starts = [
        p + i * bay_open + (i - 1) * divider_t
        for i in range(1, cfg.bays_x)
    ]

    def boundary_plate_x(boundary: int) -> float:
        if boundary == 0:
            return p
        if boundary == cfg.bays_x:
            return cfg.length - p - divider_w
        divider_start = divider_starts[boundary - 1]
        divider_centre = divider_start + divider_t / 2
        return divider_centre - divider_w / 2

    for boundary in range(cfg.bays_x + 1):
        x = boundary_plate_x(boundary)
        boundary_name = (
            "left end"
            if boundary == 0
            else "right end"
            if boundary == cfg.bays_x
            else f"internal division {boundary}"
        )

        add_shape(
            next_id("DP"),
            f"{boundary_name.title()} shared bag-rim support plate",
            Box(divider_w, inner_depth, divider_t, align=MIN_ALIGN),
            (x, p, bag_frame_z - divider_t),
            "module_support_plate",
            DIVIDER_MATERIAL,
            f"{divider_w:g}x{divider_t:g} mm flat plate",
            f"{inner_depth:g} mm",
            PAINTED_STEEL,
            viewer_group="divider_plates",
            boundary=boundary,
            note="shared horizontal bearing for the 20x20 grow-bag rim frame(s)",
        )

        # The 900 mm body raises the bag bottom well above the lower frame.
        # Add a second shared plate only when the lower 40x40 rail can no longer
        # support the 20x20 bearers directly.
        if bag_support_z > cfg.bottom_frame_z + p + 1e-6:
            add_shape(
                next_id("DP"),
                f"{boundary_name.title()} elevated bag-platform support plate",
                Box(divider_w, inner_depth, divider_t, align=MIN_ALIGN),
                (x, p, bag_support_z - divider_t),
                "module_support_plate",
                DIVIDER_MATERIAL,
                f"{divider_w:g}x{divider_t:g} mm flat plate",
                f"{inner_depth:g} mm",
                PAINTED_STEEL,
                viewer_group="divider_plates",
                boundary=boundary,
                note="supports the ends of the elevated 20x20 bag-platform bearers",
            )

        # Shared tray shelf. Two small 30x3 hanger straps tie it back to the
        # continuous lower rails; it is not a leg and never reaches the floor.
        tray_y = p + (inner_depth - tray_d) / 2
        tray_support_z = cfg.tray_target_z - divider_t
        add_shape(
            next_id("DP"),
            f"{boundary_name.title()} shared drain-tray support plate",
            Box(divider_w, tray_d, divider_t, align=MIN_ALIGN),
            (x, tray_y, tray_support_z),
            "tray_support_plate",
            DIVIDER_MATERIAL,
            f"{divider_w:g}x{divider_t:g} mm flat plate",
            f"{tray_d:g} mm",
            PAINTED_STEEL,
            viewer_group="trays",
            boundary=boundary,
            note="shared shelf for adjacent commercial plastic trays",
        )

        hanger_height = cfg.bottom_frame_z - (tray_support_z + divider_t)
        if hanger_height > 0:
            hanger_x = x + divider_w / 2 - cfg.bag_clamp_thickness / 2
            for face, y in (
                ("front", tray_y),
                ("rear", tray_y + tray_d - cfg.bag_clamp_width),
            ):
                add_shape(
                    next_id("TH"),
                    f"{boundary_name.title()} tray-shelf {face} hanger",
                    Box(
                        cfg.bag_clamp_thickness,
                        cfg.bag_clamp_width,
                        hanger_height,
                        align=MIN_ALIGN,
                    ),
                    (hanger_x, y, tray_support_z + divider_t),
                    "tray_support_hanger",
                    STEEL_FLAT_30,
                    f"{cfg.bag_clamp_width:g}x{cfg.bag_clamp_thickness:g} mm flat bar",
                    f"{hanger_height:g} mm",
                    PAINTED_STEEL,
                    P_FLAT_30,
                    "trays",
                    hanger_height,
                )

    # --- Independent grow modules -----------------------------------------
    clamp_fastener = _fastener_symbol(cfg)
    total_bag_volume = 0.0
    volume_each = bag_inner_x * bag_inner_y * cfg.soil_depth / 1_000_000

    for bay, bay_start in enumerate(bay_starts):
        bag_x = bay_start + cfg.bag_frame_margin
        bag_y = p + cfg.bag_frame_margin
        inner_x0 = bag_x + s

        # Front/rear longitudinal bearers. On 600-high designs they sit directly
        # on the continuous lower 40x40 rails; tall designs use the shared plates.
        add_tube(
            next_id("S"),
            f"Module {bay + 1} front bag-platform bearer",
            bay_open,
            s,
            cfg.support_wall,
            "x",
            (bay_start, p - s, bag_support_z),
            "bag_support",
            STEEL_TUBE_20,
            P_TUBE_20,
            "bag_support",
        )
        add_tube(
            next_id("S"),
            f"Module {bay + 1} rear bag-platform bearer",
            bay_open,
            s,
            cfg.support_wall,
            "x",
            (bay_start, cfg.depth - p, bag_support_z),
            "bag_support",
            STEEL_TUBE_20,
            P_TUBE_20,
            "bag_support",
        )

        pitch = (bag_inner_x - s) / (support_count - 1)
        for i in range(support_count):
            add_tube(
                next_id("S"),
                f"Module {bay + 1} bag bottom support rail {i + 1}",
                inner_depth,
                s,
                cfg.support_wall,
                "y",
                (inner_x0 + i * pitch, p, bag_support_z),
                "bag_support",
                STEEL_TUBE_20,
                P_TUBE_20,
                "bag_support",
            )

        side_cut = bag_outer_y - 2 * s
        add_tube(
            next_id("B"),
            f"Module {bay + 1} bag rim front",
            bag_outer_x,
            s,
            cfg.support_wall,
            "x",
            (bag_x, bag_y, bag_frame_z),
            "bag_frame",
            STEEL_TUBE_20,
            P_TUBE_20,
            "bag_frame",
        )
        add_tube(
            next_id("B"),
            f"Module {bay + 1} bag rim rear",
            bag_outer_x,
            s,
            cfg.support_wall,
            "x",
            (bag_x, bag_y + bag_outer_y - s, bag_frame_z),
            "bag_frame",
            STEEL_TUBE_20,
            P_TUBE_20,
            "bag_frame",
        )
        add_tube(
            next_id("B"),
            f"Module {bay + 1} bag rim left",
            side_cut,
            s,
            cfg.support_wall,
            "y",
            (bag_x, bag_y + s, bag_frame_z),
            "bag_frame",
            STEEL_TUBE_20,
            P_TUBE_20,
            "bag_frame",
        )
        add_tube(
            next_id("B"),
            f"Module {bay + 1} bag rim right",
            side_cut,
            s,
            cfg.support_wall,
            "y",
            (bag_x + bag_outer_x - s, bag_y + s, bag_frame_z),
            "bag_frame",
            STEEL_TUBE_20,
            P_TUBE_20,
            "bag_frame",
        )

        liner_id = next_id("G")
        add_shape(
            liner_id,
            f"Module {bay + 1} geotextile grow bag",
            _open_liner(
                bag_inner_x,
                bag_inner_y,
                cfg.soil_depth,
                cfg.bag_wall,
                liner_id,
            ),
            (bag_x + s, bag_y + s, bag_support_top_z),
            "liner",
            "Geotextile fabric",
            f"{bag_inner_x:g}x{bag_inner_y:g} mm useful section",
            f"{cfg.soil_depth:g} mm useful depth",
            GEOTEXTILE,
            viewer_group="bag_liner",
            module=bay + 1,
            volume_litres=round(volume_each, 1),
        )
        collar_id = next_id("G")
        add_shape(
            collar_id,
            f"Module {bay + 1} folded geotextile collar",
            _flat_rect_ring(
                bag_outer_x,
                bag_outer_y,
                bag_inner_x,
                bag_inner_y,
                cfg.bag_fold_thickness,
                collar_id,
            ),
            (bag_x, bag_y, bag_frame_top_z),
            "liner_clamp",
            "Doubled geotextile fabric",
            "continuous folded collar",
            f"{bag_outer_x:g}x{bag_outer_y:g} mm",
            GEOTEXTILE,
            viewer_group="bag_liner",
            module=bay + 1,
        )

        clamp_x = bag_x - cfg.bag_clamp_overhang
        clamp_y = bag_y - cfg.bag_clamp_overhang
        cox = bag_clamp_outer_x
        coy = bag_clamp_outer_y
        cw = cfg.bag_clamp_width
        ct = cfg.bag_clamp_thickness
        clamp_parts = [
            ((cox, cw, ct), (clamp_x, clamp_y, bag_clamp_z), cox, "front"),
            (
                (cox, cw, ct),
                (clamp_x, clamp_y + coy - cw, bag_clamp_z),
                cox,
                "rear",
            ),
            (
                (cw, coy - 2 * cw, ct),
                (clamp_x, clamp_y + cw, bag_clamp_z),
                coy - 2 * cw,
                "left",
            ),
            (
                (cw, coy - 2 * cw, ct),
                (clamp_x + cox - cw, clamp_y + cw, bag_clamp_z),
                coy - 2 * cw,
                "right",
            ),
        ]
        for dims, pos, length, side in clamp_parts:
            add_shape(
                next_id("C"),
                f"Module {bay + 1} {side} bag clamp bar",
                Box(*dims, align=MIN_ALIGN),
                pos,
                "bag_clamp",
                STEEL_FLAT_30,
                f"{cw:g}x{ct:g} mm flat bar",
                f"{length:g} mm",
                PAINTED_STEEL,
                P_FLAT_30,
                "bag_clamp",
                length,
            )

        fz = bag_clamp_z + ct
        for side in ("front", "rear"):
            y = clamp_y + s / 2 if side == "front" else clamp_y + coy - s / 2
            for i in range(cfg.bag_clamp_fasteners_per_side):
                x = clamp_x + (i + 1) * cox / (
                    cfg.bag_clamp_fasteners_per_side + 1
                )
                add_shape(
                    next_id("H"),
                    f"Module {bay + 1} {side} clamp M5 fastener",
                    clamp_fastener,
                    (x, y, fz),
                    "bag_clamp_fastener",
                    "Stainless M5 fastener + washer / rivnut",
                    "M5 symbolic fastener",
                    "1 pc",
                    FASTENER,
                    viewer_group="bag_clamp",
                )
        for side in ("left", "right"):
            x = clamp_x + s / 2 if side == "left" else clamp_x + cox - s / 2
            for i in range(cfg.bag_clamp_fasteners_per_side):
                y = clamp_y + (i + 1) * coy / (
                    cfg.bag_clamp_fasteners_per_side + 1
                )
                add_shape(
                    next_id("H"),
                    f"Module {bay + 1} {side} clamp M5 fastener",
                    clamp_fastener,
                    (x, y, fz),
                    "bag_clamp_fastener",
                    "Stainless M5 fastener + washer / rivnut",
                    "M5 symbolic fastener",
                    "1 pc",
                    FASTENER,
                    viewer_group="bag_clamp",
                )

        tray_x = bay_start + (bay_open - tray_w) / 2
        tray_y = p + (inner_depth - tray_d) / 2
        add_shape(
            next_id("TR"),
            f"Module {bay + 1} commercial plastic drain tray placeholder",
            _open_tray(
                tray_w,
                tray_d,
                cfg.tray_target_height,
                cfg.tray_target_wall,
            ),
            (tray_x, tray_y, cfg.tray_target_z),
            "drain_tray",
            "Commercial moulded plastic tray",
            "one-piece tray placeholder",
            f"target {tray_w:g}x{tray_d:g}x{cfg.tray_target_height:g} mm",
            PLASTIC_TRAY,
            viewer_group="trays",
        )
        add_shape(
            next_id("D"),
            f"Module {bay + 1} tray bulkhead fitting",
            Cylinder(
                8,
                max(cfg.tray_target_z - 15, 5),
                align=CYLINDER_ALIGN,
            ),
            (tray_x + tray_w - 35, tray_y + tray_d - 35, 15),
            "drainage",
            "20 mm / 1/2 in bulkhead fitting",
            "nominal fitting envelope",
            "1 pc",
            DRAIN,
            P_DRAIN,
            "trays",
        )
        total_bag_volume += volume_each

    # --- Timber: one continuous long panel; timber remains inside frame -----
    batten_zs = _batten_zs(cfg)
    panel_screw = _panel_screw_symbol(cfg)

    def add_panel(
        face: str,
        opening: float,
        start: float,
        group: str,
    ) -> None:
        count, margin = _slat_layout(opening, cfg)
        pitch = cfg.slat_width + cfg.slat_gap

        for i in range(count):
            offset = start + margin + i * pitch
            if face == "front":
                dims = (
                    cfg.slat_width,
                    cfg.slat_thickness,
                    cfg.module_panel_height,
                )
                pos = (offset, cfg.panel_outer_inset, cfg.module_panel_bottom_z)
            elif face == "rear":
                dims = (
                    cfg.slat_width,
                    cfg.slat_thickness,
                    cfg.module_panel_height,
                )
                pos = (
                    offset,
                    cfg.depth - cfg.panel_outer_inset - cfg.slat_thickness,
                    cfg.module_panel_bottom_z,
                )
            elif face == "left":
                dims = (
                    cfg.slat_thickness,
                    cfg.slat_width,
                    cfg.module_panel_height,
                )
                pos = (cfg.panel_outer_inset, offset, cfg.module_panel_bottom_z)
            else:
                dims = (
                    cfg.slat_thickness,
                    cfg.slat_width,
                    cfg.module_panel_height,
                )
                pos = (
                    cfg.length - cfg.panel_outer_inset - cfg.slat_thickness,
                    offset,
                    cfg.module_panel_bottom_z,
                )
            add_shape(
                next_id("W"),
                f"{face.title()} timber slat {i + 1}",
                Box(*dims, align=MIN_ALIGN),
                pos,
                "cladding",
                "Raw fir, ripped/planed in workshop",
                f"{cfg.slat_width:g}x{cfg.slat_thickness:g} mm finished slat",
                f"{cfg.module_panel_height:g} mm",
                WOOD,
                viewer_group=group,
            )

        for batten_no, z in enumerate(batten_zs, start=1):
            if face == "front":
                dims = (opening, cfg.batten_thickness, cfg.batten_height)
                pos = (start, cfg.panel_batten_front_offset, z)
                bracket_y = cfg.panel_batten_front_offset
                specs = [
                    (
                        _angle_y(
                            cfg.panel_bracket_width,
                            cfg.panel_bracket_leg,
                            cfg.panel_bracket_wall,
                            False,
                            True,
                        ),
                        (p, bracket_y, z - cfg.panel_bracket_leg),
                        (
                            p + cfg.panel_bracket_leg / 2,
                            bracket_y + cfg.panel_bracket_width / 2,
                            z - cfg.panel_bracket_wall,
                        ),
                    ),
                    (
                        _angle_y(
                            cfg.panel_bracket_width,
                            cfg.panel_bracket_leg,
                            cfg.panel_bracket_wall,
                            True,
                            True,
                        ),
                        (
                            cfg.length - p - cfg.panel_bracket_leg,
                            bracket_y,
                            z - cfg.panel_bracket_leg,
                        ),
                        (
                            cfg.length - p - cfg.panel_bracket_leg / 2,
                            bracket_y + cfg.panel_bracket_width / 2,
                            z - cfg.panel_bracket_wall,
                        ),
                    ),
                ]
            elif face == "rear":
                dims = (opening, cfg.batten_thickness, cfg.batten_height)
                pos = (
                    start,
                    cfg.depth - cfg.panel_batten_front_offset - cfg.batten_thickness,
                    z,
                )
                bracket_y = (
                    cfg.depth
                    - cfg.panel_batten_front_offset
                    - cfg.batten_thickness
                )
                specs = [
                    (
                        _angle_y(
                            cfg.panel_bracket_width,
                            cfg.panel_bracket_leg,
                            cfg.panel_bracket_wall,
                            False,
                            True,
                        ),
                        (p, bracket_y, z - cfg.panel_bracket_leg),
                        (
                            p + cfg.panel_bracket_leg / 2,
                            bracket_y + cfg.panel_bracket_width / 2,
                            z - cfg.panel_bracket_wall,
                        ),
                    ),
                    (
                        _angle_y(
                            cfg.panel_bracket_width,
                            cfg.panel_bracket_leg,
                            cfg.panel_bracket_wall,
                            True,
                            True,
                        ),
                        (
                            cfg.length - p - cfg.panel_bracket_leg,
                            bracket_y,
                            z - cfg.panel_bracket_leg,
                        ),
                        (
                            cfg.length - p - cfg.panel_bracket_leg / 2,
                            bracket_y + cfg.panel_bracket_width / 2,
                            z - cfg.panel_bracket_wall,
                        ),
                    ),
                ]
            elif face == "left":
                dims = (cfg.batten_thickness, opening, cfg.batten_height)
                pos = (cfg.panel_batten_front_offset, start, z)
                bracket_x = cfg.panel_batten_front_offset
                specs = [
                    (
                        _angle_x(
                            cfg.panel_bracket_width,
                            cfg.panel_bracket_leg,
                            cfg.panel_bracket_wall,
                            False,
                            True,
                        ),
                        (bracket_x, p, z - cfg.panel_bracket_leg),
                        (
                            bracket_x + cfg.panel_bracket_width / 2,
                            p + cfg.panel_bracket_leg / 2,
                            z - cfg.panel_bracket_wall,
                        ),
                    ),
                    (
                        _angle_x(
                            cfg.panel_bracket_width,
                            cfg.panel_bracket_leg,
                            cfg.panel_bracket_wall,
                            True,
                            True,
                        ),
                        (
                            bracket_x,
                            cfg.depth - p - cfg.panel_bracket_leg,
                            z - cfg.panel_bracket_leg,
                        ),
                        (
                            bracket_x + cfg.panel_bracket_width / 2,
                            cfg.depth - p - cfg.panel_bracket_leg / 2,
                            z - cfg.panel_bracket_wall,
                        ),
                    ),
                ]
            else:
                dims = (cfg.batten_thickness, opening, cfg.batten_height)
                pos = (
                    cfg.length
                    - cfg.panel_batten_front_offset
                    - cfg.batten_thickness,
                    start,
                    z,
                )
                bracket_x = (
                    cfg.length
                    - cfg.panel_batten_front_offset
                    - cfg.batten_thickness
                )
                specs = [
                    (
                        _angle_x(
                            cfg.panel_bracket_width,
                            cfg.panel_bracket_leg,
                            cfg.panel_bracket_wall,
                            False,
                            True,
                        ),
                        (bracket_x, p, z - cfg.panel_bracket_leg),
                        (
                            bracket_x + cfg.panel_bracket_width / 2,
                            p + cfg.panel_bracket_leg / 2,
                            z - cfg.panel_bracket_wall,
                        ),
                    ),
                    (
                        _angle_x(
                            cfg.panel_bracket_width,
                            cfg.panel_bracket_leg,
                            cfg.panel_bracket_wall,
                            True,
                            True,
                        ),
                        (
                            bracket_x,
                            cfg.depth - p - cfg.panel_bracket_leg,
                            z - cfg.panel_bracket_leg,
                        ),
                        (
                            bracket_x + cfg.panel_bracket_width / 2,
                            cfg.depth - p - cfg.panel_bracket_leg / 2,
                            z - cfg.panel_bracket_wall,
                        ),
                    ),
                ]

            add_shape(
                next_id("BT"),
                f"{face.title()} concealed batten {batten_no}",
                Box(*dims, align=MIN_ALIGN),
                pos,
                "cladding_batten",
                "Raw fir, ripped/planed in workshop",
                f"{cfg.batten_height:g}x{cfg.batten_thickness:g} mm batten",
                f"{opening:g} mm",
                WOOD,
                viewer_group=group,
            )

            for bracket_shape, bracket_pos, screw_pos in specs:
                add_shape(
                    next_id("PB"),
                    f"{face.title()} batten {batten_no} end bracket",
                    bracket_shape,
                    bracket_pos,
                    "panel_mount_bracket",
                    STEEL_ANGLE,
                    f"{cfg.panel_bracket_leg:g}x{cfg.panel_bracket_leg:g}x{cfg.panel_bracket_wall:g} mm angle",
                    f"{cfg.panel_bracket_width:g} mm",
                    PAINTED_STEEL,
                    P_ANGLE_20,
                    "panel_mounts",
                    cfg.panel_bracket_width,
                )
                add_shape(
                    next_id("PF"),
                    f"{face.title()} batten {batten_no} concealed M5 fastener",
                    panel_screw,
                    screw_pos,
                    "panel_mount_fastener",
                    "Stainless M5 screw + threaded wood insert",
                    "M5 symbolic screw / insert",
                    f"{cfg.panel_mount_screw_length:g} mm",
                    FASTENER,
                    viewer_group="panel_mounts",
                )

    add_panel("front", inner_length, p, "front_panel")
    add_panel("rear", inner_length, p, "rear_panel")
    add_panel("left", inner_depth, p, "left_panel")
    add_panel("right", inner_depth, p, "right_panel")

    assembly = Compound(label=model_id, children=shapes)

    stock_qty = {
        P_TUBE_40: _stock_qty(stock_cuts[P_TUBE_40], 3000),
        P_TUBE_20: _stock_qty(stock_cuts[P_TUBE_20], 3000),
        P_ANGLE_20: _stock_qty(stock_cuts[P_ANGLE_20], 1000),
        P_FLAT_30: _stock_qty(stock_cuts[P_FLAT_30], 3000),
    }
    products = [
        {
            "id": P_TUBE_40,
            "retailer": "Obramat",
            "ref": "10330425",
            "name": "Tubo cuadrado acero 40x40x1,5 mm · 3 m",
            "url": "https://www.obramat.es/productos/tubo-cuadrado-acero-40x40x1-5mm-3m-10330425.html",
            "stock": "3 m",
            "suggested_qty": stock_qty[P_TUBE_40],
        },
        {
            "id": P_TUBE_20,
            "retailer": "Obramat",
            "ref": "10362443",
            "name": "Tubo cuadrado acero decapado 20x20x1,5 mm · 3 m",
            "url": "https://www.obramat.es/productos/tubo-cuadrado-acero-decapado-20x20x1-5mm-3m-10362443.html",
            "stock": "3 m",
            "suggested_qty": stock_qty[P_TUBE_20],
        },
        {
            "id": P_ANGLE_20,
            "retailer": "Obramat",
            "ref": "10257156",
            "name": "Ángulo acero 20x20x3 mm · 1 m",
            "url": "https://www.obramat.es/productos/angulo-acero-20x20x3mm-1m-10257156.html",
            "stock": "1 m",
            "suggested_qty": stock_qty[P_ANGLE_20],
        },
        {
            "id": P_FLAT_30,
            "retailer": "Obramat",
            "ref": "10636696",
            "name": "Pletina acero S275JR 30x3 mm · 3 m",
            "url": "https://www.obramat.es/productos/pletina-acero-x275jr-30x3mm-3m-10636696.html",
            "stock": "3 m",
            "suggested_qty": stock_qty[P_FLAT_30],
        },
        {
            "id": P_FOOT_CAP,
            "retailer": "Obramat",
            "ref": "10424295",
            "name": "Contera plástico embutir 40x40 mm negra · 4 uds",
            "url": "https://www.obramat.es/productos/contera-plastico-embutir-40-x-40-mm-negra-4-uds-10424295.html",
            "stock": "pack of 4",
            "suggested_qty": 1,
        },
        {
            "id": P_DRAIN,
            "retailer": "Leroy Merlin",
            "ref": "83450729",
            "name": "Pasamuros roscado 1/2 in para depósitos · 20 mm",
            "url": "https://www.leroymerlin.es/productos/pasamuros-roscado-1-2-para-depositos-20-mm-83450729.html",
            "stock": "1 pc",
            "suggested_qty": cfg.bays_x,
        },
    ]

    scale = max(cfg.length, cfg.body_height)
    viewer_groups = [
        {
            "id": "top_closure",
            "label": "Top closure rails",
            "node_names": groups["top_closure"],
            "offset_mm": [0, 0, 250],
        },
        {
            "id": "divider_plates",
            "label": "Shared support plates",
            "node_names": groups["divider_plates"],
            "offset_mm": [0, 0, 220],
        },
        {
            "id": "bag_support",
            "label": "Bag support tubes",
            "node_names": groups["bag_support"],
            "offset_mm": [0, 0, -250],
        },
        {
            "id": "bag_clamp",
            "label": "Bag clamps",
            "node_names": groups["bag_clamp"],
            "offset_mm": [-0.55 * scale, 0, 300],
        },
        {
            "id": "bag_frame",
            "label": "Bag rim frames",
            "node_names": groups["bag_frame"],
            "offset_mm": [-0.55 * scale, 0, 130],
        },
        {
            "id": "bag_liner",
            "label": "Geotextile bags",
            "node_names": groups["bag_liner"],
            "offset_mm": [-0.55 * scale, 0, -80],
        },
        {
            "id": "trays",
            "label": "Drain trays / supports",
            "node_names": groups["trays"],
            "offset_mm": [0.55 * scale, 0, -100],
        },
        {
            "id": "panel_mounts",
            "label": "Panel end brackets",
            "node_names": groups["panel_mounts"],
            "offset_mm": [0, 0, 220],
        },
        {
            "id": "front_panel",
            "label": "Front timber panel",
            "node_names": groups["front_panel"],
            "offset_mm": [0, -300, 0],
        },
        {
            "id": "rear_panel",
            "label": "Rear timber panel",
            "node_names": groups["rear_panel"],
            "offset_mm": [0, 300, 0],
        },
        {
            "id": "left_panel",
            "label": "Left timber panel",
            "node_names": groups["left_panel"],
            "offset_mm": [-300, 0, 0],
        },
        {
            "id": "right_panel",
            "label": "Right timber panel",
            "node_names": groups["right_panel"],
            "offset_mm": [300, 0, 0],
        },
    ]

    metadata = {
        "schema_version": 8,
        "model": model_id,
        "status": "parametric fabrication design / v8",
        "units": "mm",
        "parameters": {**asdict(cfg), "divider_plate_thickness": divider_t, "divider_plate_width": divider_w},
        "derived": {
            "bay_count": cfg.bays_x,
            "corner_leg_count": 4,
            "intermediate_leg_count": 0,
            "divider_count": divider_count,
            "divider_visible_thickness_mm": divider_t,
            "divider_plate_width_mm": divider_w,
            "bay_opening_length_mm": round(bay_open, 1),
            "inner_depth_mm": round(inner_depth, 1),
            "leg_clearance_mm": cfg.leg_clearance,
            "bag_module_count": cfg.bays_x,
            "bag_useful_x_mm": round(bag_inner_x, 1),
            "bag_useful_y_mm": round(bag_inner_y, 1),
            "bag_useful_height_mm": cfg.soil_depth,
            "bag_volume_litres_each": round(volume_each, 1),
            "bag_volume_litres_total": round(total_bag_volume, 1),
            "bag_support_rail_count_each": support_count,
            "bag_support_clear_gap_mm": round(support_gap, 1),
            "bag_support_z_mm": round(bag_support_z, 1),
            "tray_target_width_mm": round(tray_w, 1),
            "tray_target_depth_mm": round(tray_d, 1),
            "tray_vertical_clearance_mm": round(
                cfg.bottom_frame_z
                - (cfg.tray_target_z + cfg.tray_target_height),
                1,
            ),
            "panel_height_mm": round(cfg.module_panel_height, 1),
            "panel_battens_each": len(batten_zs),
            "long_face_panel_count_each_side": 1,
            "top_open_posts_closed_by_integral_flaps": 4,
        },
        "parts": parts,
        "products": products,
        "viewer": {
            "model_src": f"./models/{model_id}.glb",
            "groups": viewer_groups,
            "selected_part_offset_mm": 300,
        },
        "assemblies": [
            {
                "id": "AS01",
                "name": "Four-leg continuous welded steel body",
                "contains": (
                    "4 corner uprights, continuous front/rear 40x40 rails, "
                    f"{divider_count} thin internal module division(s)"
                ),
            },
            {
                "id": "AS02",
                "name": "Independent grow modules",
                "contains": f"{cfg.bays_x} removable geotextile bag(s) with independent rim/clamp",
            },
            {
                "id": "AS03",
                "name": "Removable timber cladding",
                "contains": "one continuous panel per long face plus one panel on each end",
            },
            {
                "id": "AS04",
                "name": "Commercial drain trays",
                "contains": f"{cfg.bays_x} plastic tray placeholder(s) on shared flat-plate shelves",
            },
        ],
        "joints": [
            {
                "id": "J01",
                "type": "weld",
                "name": "Continuous 40x40 perimeter frame",
                "spec": (
                    "Only four corner legs reach the floor. Long front/rear rails remain "
                    "continuous through 1200 and 1800 mm variants."
                ),
            },
            {
                "id": "J02",
                "type": "weld",
                "name": "Thin shared module supports",
                "spec": (
                    f"Internal module separation is only {divider_t:g} mm. "
                    f"{divider_w:g}x{divider_t:g} horizontal plates share bearing between adjacent rims; "
                    "tall variants add matching elevated platform plates."
                ),
            },
            {
                "id": "J03",
                "type": "clamp",
                "name": "Geotextile rim",
                "spec": "folded liner is continuously compressed between the 20x20 rim and 30x3 clamp",
            },
            {
                "id": "J04",
                "type": "mechanical",
                "name": "Timber panels",
                "spec": "two small 20x20x3 L brackets per batten, only at the corner posts; long faces are continuous",
            },
        ],
        "service": {
            "bag_removal": "each grow module has an independent removable bag",
            "panel_removal": "long-face panel removes as one piece after releasing its concealed end brackets",
            "tray_removal": "each commercial tray remains independent",
        },
        "fabrication_notes": [
            "1200 and 1800 mm bodies intentionally have no intermediate legs or 40x40 intermediate posts.",
            f"Module division consumes only {divider_t:g} mm. The load-bearing plate is wider ({divider_w:g} mm) but lies horizontally beneath the adjacent components, so it does not create a wide visual gap.",
            "Front/rear 40x40 rails are continuous between the corner posts. This is the primary bending member; verify loaded deflection on the first long prototype before serial fabrication.",
            f"Soil depth remains independent from overall height at {cfg.soil_depth:g} mm. Tall bodies raise the bag platform rather than adding unnecessary soil.",
            "Timber returns to the protected in-frame position; 10 mm slats do not project outside the off-white steel perimeter.",
            "Long front/rear timber faces are continuous panels, eliminating the former central 40 mm post seam.",
            "Commercial plastic tray geometry remains a placeholder until the purchased tray is measured.",
            "80x5 shared support plate is currently a fabrication specification with supplier/product still TBD.",
            "Structural capacity is not certified. For the 1800 mm prototype, proof-load progressively and record mid-span deflection before reproducing it.",
        ],
        "notes": [
            "Steel renders off-white; timber, plastic, stainless hardware and geotextile remain visually distinct."
        ],
    }

    return ModelBuild(shape=assembly, bom=_group_bom(parts), metadata=metadata)


PRESETS: dict[str, tuple[str, PlanterConfig]] = {
    "planter-600x600x600": (
        "600 × 600 × 600 mm",
        PlanterConfig(
            length=600,
            depth=600,
            body_height=600,
            bays_x=1,
            panel_outer_inset=0,
        ),
    ),
    "planter-1200x400x600": (
        "1200 × 400 × 600 mm",
        PlanterConfig(
            length=1200,
            depth=400,
            body_height=600,
            bays_x=2,
            panel_outer_inset=0,
        ),
    ),
    "planter-1200x600x900": (
        "1200 × 600 × 900 mm",
        PlanterConfig(
            length=1200,
            depth=600,
            body_height=900,
            bays_x=2,
            panel_outer_inset=0,
        ),
    ),
    "planter-1800x600x600": (
        "1800 × 600 × 600 mm",
        PlanterConfig(
            length=1800,
            depth=600,
            body_height=600,
            bays_x=3,
            panel_outer_inset=0,
        ),
    ),
}
