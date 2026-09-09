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


def _top_flap_rail_y(overall_depth: float, size: float, wall: float, flap: float, label: str):
    body_length = overall_depth - 2 * flap
    body = Pos(0, flap, 0) * _hollow_tube(body_length, size, wall, "y", label)
    front_flap = Pos(0, 0, size - wall) * Box(size, flap, wall, align=MIN_ALIGN)
    rear_flap = Pos(0, overall_depth - flap, size - wall) * Box(size, flap, wall, align=MIN_ALIGN)
    result = Compound(children=[body, front_flap, rear_flap])
    result.label = label
    return result


def _flat_rect_ring(outer_x: float, outer_y: float, inner_x: float, inner_y: float, thickness: float, label: str):
    bx = (outer_x - inner_x) / 2
    by = (outer_y - inner_y) / 2
    outside = Box(outer_x, outer_y, thickness, align=MIN_ALIGN)
    inside = Pos(bx, by, -1) * Box(inner_x, inner_y, thickness + 2, align=MIN_ALIGN)
    result = outside - inside
    result.label = label
    return result


def _open_tray(width: float, depth: float, height: float, wall: float):
    return Compound(children=[
        Box(width, depth, wall, align=MIN_ALIGN),
        Pos(0, 0, wall) * Box(wall, depth, height - wall, align=MIN_ALIGN),
        Pos(width - wall, 0, wall) * Box(wall, depth, height - wall, align=MIN_ALIGN),
        Pos(wall, 0, wall) * Box(width - 2 * wall, wall, height - wall, align=MIN_ALIGN),
        Pos(wall, depth - wall, wall) * Box(width - 2 * wall, wall, height - wall, align=MIN_ALIGN),
    ])


def _fastener_symbol(cfg: PlanterConfig):
    washer = Cylinder(cfg.clamp_washer_radius, cfg.clamp_washer_thickness, align=CYLINDER_ALIGN)
    head = Pos(0, 0, cfg.clamp_washer_thickness) * Cylinder(cfg.clamp_head_radius, cfg.clamp_head_height, align=CYLINDER_ALIGN)
    return Compound(children=[washer, head])


def _panel_screw_symbol(cfg: PlanterConfig):
    shaft = Cylinder(cfg.panel_mount_screw_diameter / 2, cfg.panel_mount_screw_length, align=CYLINDER_ALIGN)
    head = Pos(0, 0, -cfg.panel_mount_head_thickness) * Cylinder(cfg.panel_mount_head_radius, cfg.panel_mount_head_thickness, align=CYLINDER_ALIGN)
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
    count = max(1, math.floor((opening + cfg.slat_gap) / (cfg.slat_width + cfg.slat_gap)))
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
    return [center - cfg.batten_height / 2 for center in centers]


def build_planter(config: PlanterConfig | None = None, model_id: str = "planter-600x600x600") -> ModelBuild:
    cfg = config or PlanterConfig()
    p = cfg.frame_size
    s = cfg.support_size
    if cfg.bays_x < 1:
        raise ValueError("At least one longitudinal bay is required")
    if cfg.bay_opening_length <= 0 or cfg.module_inner_depth <= 0:
        raise ValueError("Frame profiles do not fit inside the requested envelope")
    if cfg.module_bag_inner_x <= 0 or cfg.module_bag_inner_y <= 0:
        raise ValueError("Requested planter is too narrow for the current bag-frame margins")
    if cfg.module_bag_support_z < cfg.bottom_frame_z:
        raise ValueError("Soil depth is too large for this body height")
    if cfg.module_tray_width <= 0 or cfg.module_tray_depth <= 0 or cfg.module_tray_vertical_clearance <= 0:
        raise ValueError("Commercial tray placeholder does not fit")
    if cfg.panel_back_offset > cfg.frame_size:
        raise ValueError("Timber panel extends behind the inner face of the 40x40 frame")

    shapes: list[Any] = []
    parts: list[dict[str, Any]] = []
    groups = {name: [] for name in (
        "top_closure", "bag_support", "bag_clamp", "bag_frame", "bag_liner", "trays",
        "panel_mounts", "front_panels", "rear_panels", "left_panel", "right_panel"
    )}
    stock_cuts = {P_TUBE_40: [], P_TUBE_20: [], P_ANGLE_20: [], P_FLAT_30: []}
    counters: dict[str, int] = {}

    def next_id(prefix: str) -> str:
        counters[prefix] = counters.get(prefix, 0) + 1
        return f"{prefix}{counters[prefix]:02d}"

    def add_shape(part_id: str, name: str, shape, position: tuple[float, float, float], category: str,
                  material: str, profile: str, cut: str, color: Color, product_id: str | None = None,
                  viewer_group: str | None = None, stock_cut_mm: float | None = None, **extra: Any) -> None:
        placed = Pos(*position) * shape
        placed.label = part_id
        placed.color = color
        shapes.append(placed)
        item: dict[str, Any] = {"id": part_id, "name": name, "category": category, "material": material, "profile": profile, "cut": cut}
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

    def add_tube(part_id: str, name: str, length: float, size: float, wall: float, axis: str,
                 position: tuple[float, float, float], category: str, material: str, product_id: str,
                 viewer_group: str | None = None) -> None:
        add_shape(part_id, name, _hollow_tube(length, size, wall, axis, part_id), position, category,
                  material, f"{size:g}x{size:g}x{wall:g} mm square tube", f"{length:g} mm",
                  PAINTED_STEEL, product_id, viewer_group, length)

    station_xs = [i * cfg.bay_pitch for i in range(cfg.station_count)]
    for station, x in enumerate(station_xs):
        for face, y in (("front", 0.0), ("rear", cfg.depth - p)):
            add_tube(next_id("U"), f"Station {station + 1} {face} upright / leg", cfg.body_height, p,
                     cfg.frame_wall, "z", (x, y, 0), "main_frame", STEEL_TUBE_40, P_TUBE_40)
            add_shape(next_id("FC"), f"Station {station + 1} {face} leg insert cap",
                      Box(p, p, cfg.foot_cap_visible, align=MIN_ALIGN), (x, y, 0), "foot", FOOT_CAP,
                      "40x40 insert cap", "1 pc", POLYMER, P_FOOT_CAP)

    for bay in range(cfg.bays_x):
        x0 = station_xs[bay] + p
        for face, y in (("front", 0.0), ("rear", cfg.depth - p)):
            add_tube(next_id("R"), f"Bay {bay + 1} {face} lower rail", cfg.bay_opening_length, p,
                     cfg.frame_wall, "x", (x0, y, cfg.bottom_frame_z), "main_frame", STEEL_TUBE_40, P_TUBE_40)
            add_tube(next_id("R"), f"Bay {bay + 1} {face} top rail", cfg.bay_opening_length, p,
                     cfg.frame_wall, "x", (x0, y, cfg.top_frame_z), "main_frame", STEEL_TUBE_40, P_TUBE_40)

    for station, x in enumerate(station_xs):
        add_tube(next_id("R"), f"Station {station + 1} lower transverse rail", cfg.module_inner_depth, p,
                 cfg.frame_wall, "y", (x, p, cfg.bottom_frame_z), "main_frame", STEEL_TUBE_40, P_TUBE_40)
        closure_id = next_id("TC")
        add_shape(closure_id, f"Station {station + 1} top transverse rail with post-closing flaps",
                  _top_flap_rail_y(cfg.depth, p, cfg.frame_wall, p, closure_id), (x, 0, cfg.top_frame_z),
                  "main_frame_top_closure", STEEL_TUBE_40,
                  f"{p:g}x{p:g}x{cfg.frame_wall:g} mm tube · integral top-wall flaps",
                  f"{cfg.depth:g} mm blank", PAINTED_STEEL, P_TUBE_40, "top_closure", cfg.depth,
                  note="remove side and bottom walls for 40 mm at both ends; leave top wall over the two upright mouths")

    clamp_fastener = _fastener_symbol(cfg)
    support_count = cfg.module_support_crossbar_count
    support_gap = cfg.module_support_clear_gap
    total_bag_volume = 0.0

    for bay in range(cfg.bays_x):
        station_left = station_xs[bay]
        station_right = station_xs[bay + 1]
        bay_x = station_left + p
        bag_x = bay_x + cfg.bag_frame_margin
        bag_y = p + cfg.bag_frame_margin
        inner_x0 = bag_x + s

        add_tube(next_id("S"), f"Bay {bay + 1} front bag-support bearer", cfg.bay_opening_length, s,
                 cfg.support_wall, "x", (bay_x, p - s, cfg.module_bag_support_z), "bag_support",
                 STEEL_TUBE_20, P_TUBE_20, "bag_support")
        add_tube(next_id("S"), f"Bay {bay + 1} rear bag-support bearer", cfg.bay_opening_length, s,
                 cfg.support_wall, "x", (bay_x, cfg.depth - p, cfg.module_bag_support_z), "bag_support",
                 STEEL_TUBE_20, P_TUBE_20, "bag_support")
        pitch = (cfg.module_bag_inner_x - s) / (support_count - 1)
        for i in range(support_count):
            add_tube(next_id("S"), f"Bay {bay + 1} bag bottom support rail {i + 1}", cfg.module_inner_depth,
                     s, cfg.support_wall, "y", (inner_x0 + i * pitch, p, cfg.module_bag_support_z),
                     "bag_support", STEEL_TUBE_20, P_TUBE_20, "bag_support")

        centre_x = bay_x + cfg.bay_opening_length / 2
        centre_y = cfg.depth / 2
        ledges = [
            (_angle_x(cfg.bag_ledge_length, cfg.angle_leg, cfg.angle_wall, False, False),
             (centre_x - cfg.bag_ledge_length / 2, p, cfg.top_frame_z)),
            (_angle_x(cfg.bag_ledge_length, cfg.angle_leg, cfg.angle_wall, True, False),
             (centre_x - cfg.bag_ledge_length / 2, cfg.depth - p - cfg.angle_leg, cfg.top_frame_z)),
            (_angle_y(cfg.bag_ledge_length, cfg.angle_leg, cfg.angle_wall, False, False),
             (station_left + p, centre_y - cfg.bag_ledge_length / 2, cfg.top_frame_z)),
            (_angle_y(cfg.bag_ledge_length, cfg.angle_leg, cfg.angle_wall, True, False),
             (station_right - cfg.angle_leg, centre_y - cfg.bag_ledge_length / 2, cfg.top_frame_z)),
        ]
        for ledge, pos in ledges:
            add_shape(next_id("A"), f"Bay {bay + 1} bag-frame support ledge", ledge, pos,
                      "bag_frame_support", STEEL_ANGLE,
                      f"{cfg.angle_leg:g}x{cfg.angle_leg:g}x{cfg.angle_wall:g} mm angle",
                      f"{cfg.bag_ledge_length:g} mm", PAINTED_STEEL, P_ANGLE_20,
                      stock_cut_mm=cfg.bag_ledge_length)

        outer_x = cfg.module_bag_frame_outer_x
        outer_y = cfg.module_bag_frame_outer_y
        side_cut = outer_y - 2 * s
        add_tube(next_id("B"), f"Bay {bay + 1} bag rim front", outer_x, s, cfg.support_wall, "x",
                 (bag_x, bag_y, cfg.module_bag_frame_z), "bag_frame", STEEL_TUBE_20, P_TUBE_20, "bag_frame")
        add_tube(next_id("B"), f"Bay {bay + 1} bag rim rear", outer_x, s, cfg.support_wall, "x",
                 (bag_x, bag_y + outer_y - s, cfg.module_bag_frame_z), "bag_frame", STEEL_TUBE_20, P_TUBE_20, "bag_frame")
        add_tube(next_id("B"), f"Bay {bay + 1} bag rim left", side_cut, s, cfg.support_wall, "y",
                 (bag_x, bag_y + s, cfg.module_bag_frame_z), "bag_frame", STEEL_TUBE_20, P_TUBE_20, "bag_frame")
        add_tube(next_id("B"), f"Bay {bay + 1} bag rim right", side_cut, s, cfg.support_wall, "y",
                 (bag_x + outer_x - s, bag_y + s, cfg.module_bag_frame_z), "bag_frame", STEEL_TUBE_20, P_TUBE_20, "bag_frame")

        liner_id = next_id("G")
        add_shape(liner_id, f"Bay {bay + 1} geotextile grow bag",
                  _open_liner(cfg.module_bag_inner_x, cfg.module_bag_inner_y, cfg.soil_depth, cfg.bag_wall, liner_id),
                  (bag_x + s, bag_y + s, cfg.module_bag_support_top_z), "liner", "Geotextile fabric",
                  f"{cfg.module_bag_inner_x:g}x{cfg.module_bag_inner_y:g} mm useful section",
                  f"{cfg.soil_depth:g} mm useful depth", GEOTEXTILE, viewer_group="bag_liner",
                  bay=bay + 1, volume_litres=round(cfg.module_bag_volume_litres_each, 1),
                  note=f"bottom rests on {support_count} open 20x20 rails; clear gaps ≈ {support_gap:.1f} mm")
        collar_id = next_id("G")
        add_shape(collar_id, f"Bay {bay + 1} folded geotextile collar",
                  _flat_rect_ring(outer_x, outer_y, cfg.module_bag_inner_x, cfg.module_bag_inner_y,
                                  cfg.bag_fold_thickness, collar_id),
                  (bag_x, bag_y, cfg.module_bag_frame_top_z), "liner_clamp", "Doubled geotextile fabric",
                  "continuous folded collar", f"{outer_x:g}x{outer_y:g} mm", GEOTEXTILE,
                  viewer_group="bag_liner", bay=bay + 1)

        clamp_x = bag_x - cfg.bag_clamp_overhang
        clamp_y = bag_y - cfg.bag_clamp_overhang
        cox = cfg.module_bag_clamp_outer_x
        coy = cfg.module_bag_clamp_outer_y
        cw = cfg.bag_clamp_width
        ct = cfg.bag_clamp_thickness
        clamp_parts = [
            ((cox, cw, ct), (clamp_x, clamp_y, cfg.module_bag_clamp_z), cox, "front"),
            ((cox, cw, ct), (clamp_x, clamp_y + coy - cw, cfg.module_bag_clamp_z), cox, "rear"),
            ((cw, coy - 2 * cw, ct), (clamp_x, clamp_y + cw, cfg.module_bag_clamp_z), coy - 2 * cw, "left"),
            ((cw, coy - 2 * cw, ct), (clamp_x + cox - cw, clamp_y + cw, cfg.module_bag_clamp_z), coy - 2 * cw, "right"),
        ]
        for dims, pos, length, side in clamp_parts:
            add_shape(next_id("C"), f"Bay {bay + 1} {side} bag clamp bar", Box(*dims, align=MIN_ALIGN), pos,
                      "bag_clamp", STEEL_FLAT_30, f"{cw:g}x{ct:g} mm flat bar", f"{length:g} mm",
                      PAINTED_STEEL, P_FLAT_30, "bag_clamp", length)

        fz = cfg.module_bag_clamp_z + ct
        for side in ("front", "rear"):
            y = clamp_y + s / 2 if side == "front" else clamp_y + coy - s / 2
            for i in range(cfg.bag_clamp_fasteners_per_side):
                x = clamp_x + (i + 1) * cox / (cfg.bag_clamp_fasteners_per_side + 1)
                add_shape(next_id("H"), f"Bay {bay + 1} {side} clamp M5 fastener", clamp_fastener,
                          (x, y, fz), "bag_clamp_fastener", "Stainless M5 fastener + washer / rivnut",
                          "M5 symbolic fastener", "1 pc", FASTENER, viewer_group="bag_clamp")
        for side in ("left", "right"):
            x = clamp_x + s / 2 if side == "left" else clamp_x + cox - s / 2
            for i in range(cfg.bag_clamp_fasteners_per_side):
                y = clamp_y + (i + 1) * coy / (cfg.bag_clamp_fasteners_per_side + 1)
                add_shape(next_id("H"), f"Bay {bay + 1} {side} clamp M5 fastener", clamp_fastener,
                          (x, y, fz), "bag_clamp_fastener", "Stainless M5 fastener + washer / rivnut",
                          "M5 symbolic fastener", "1 pc", FASTENER, viewer_group="bag_clamp")
        total_bag_volume += cfg.module_bag_volume_litres_each

        tray_w = cfg.module_tray_width
        tray_d = cfg.module_tray_depth
        tray_x = bay_x + (cfg.bay_opening_length - tray_w) / 2
        tray_y = p + (cfg.module_inner_depth - tray_d) / 2
        add_shape(next_id("TR"), f"Bay {bay + 1} commercial plastic drain tray placeholder",
                  _open_tray(tray_w, tray_d, cfg.tray_target_height, cfg.tray_target_wall),
                  (tray_x, tray_y, cfg.tray_target_z), "drain_tray", "Commercial moulded plastic tray",
                  "one-piece tray placeholder", f"target {tray_w:g}x{tray_d:g}x{cfg.tray_target_height:g} mm",
                  PLASTIC_TRAY, viewer_group="trays",
                  note="measure the purchased tray bottom before welding final guide positions")
        guide_z = cfg.tray_target_z - cfg.angle_leg
        for x, mirrored in ((tray_x, False), (tray_x + tray_w - cfg.angle_leg, True)):
            add_shape(next_id("TG"), f"Bay {bay + 1} plastic tray guide",
                      _angle_y(tray_d, cfg.angle_leg, cfg.angle_wall, mirrored, True),
                      (x, tray_y, guide_z), "tray_guide", STEEL_ANGLE,
                      f"{cfg.angle_leg:g}x{cfg.angle_leg:g}x{cfg.angle_wall:g} mm angle",
                      f"{tray_d:g} mm", PAINTED_STEEL, P_ANGLE_20, "trays", tray_d)
        add_shape(next_id("D"), f"Bay {bay + 1} tray bulkhead fitting",
                  Cylinder(8, max(cfg.tray_target_z - 15, 5), align=CYLINDER_ALIGN),
                  (tray_x + tray_w - 35, tray_y + tray_d - 35, 15), "drainage",
                  "20 mm / 1/2 in bulkhead fitting", "nominal fitting envelope", "1 pc",
                  DRAIN, P_DRAIN, "trays")

    batten_zs = _batten_zs(cfg)
    panel_screw = _panel_screw_symbol(cfg)

    def add_panel(face: str, panel_index: int, start: float, opening: float,
                  left_station: float, right_station: float, group: str) -> None:
        count, margin = _slat_layout(opening, cfg)
        pitch = cfg.slat_width + cfg.slat_gap
        for i in range(count):
            offset = start + margin + i * pitch
            if face == "front":
                dims, pos = (cfg.slat_width, cfg.slat_thickness, cfg.module_panel_height), (offset, cfg.panel_outer_inset, cfg.module_panel_bottom_z)
            elif face == "rear":
                dims, pos = (cfg.slat_width, cfg.slat_thickness, cfg.module_panel_height), (offset, cfg.depth - cfg.panel_outer_inset - cfg.slat_thickness, cfg.module_panel_bottom_z)
            elif face == "left":
                dims, pos = (cfg.slat_thickness, cfg.slat_width, cfg.module_panel_height), (cfg.panel_outer_inset, offset, cfg.module_panel_bottom_z)
            else:
                dims, pos = (cfg.slat_thickness, cfg.slat_width, cfg.module_panel_height), (cfg.length - cfg.panel_outer_inset - cfg.slat_thickness, offset, cfg.module_panel_bottom_z)
            add_shape(next_id("W"), f"{face.title()} panel {panel_index} timber slat {i + 1}",
                      Box(*dims, align=MIN_ALIGN), pos, "cladding", "Raw fir, ripped/planed in workshop",
                      f"{cfg.slat_width:g}x{cfg.slat_thickness:g} mm finished slat",
                      f"{cfg.module_panel_height:g} mm", WOOD, viewer_group=group, panel=panel_index)

        for batten_no, z in enumerate(batten_zs, start=1):
            if face == "front":
                dims, pos = (opening, cfg.batten_thickness, cfg.batten_height), (start, cfg.panel_batten_front_offset, z)
            elif face == "rear":
                dims, pos = (opening, cfg.batten_thickness, cfg.batten_height), (start, cfg.depth - cfg.panel_batten_front_offset - cfg.batten_thickness, z)
            elif face == "left":
                dims, pos = (cfg.batten_thickness, opening, cfg.batten_height), (cfg.panel_batten_front_offset, start, z)
            else:
                dims, pos = (cfg.batten_thickness, opening, cfg.batten_height), (cfg.length - cfg.panel_batten_front_offset - cfg.batten_thickness, start, z)
            add_shape(next_id("BT"), f"{face.title()} panel {panel_index} concealed batten {batten_no}",
                      Box(*dims, align=MIN_ALIGN), pos, "cladding_batten", "Raw fir, ripped/planed in workshop",
                      f"{cfg.batten_height:g}x{cfg.batten_thickness:g} mm batten", f"{opening:g} mm",
                      WOOD, viewer_group=group, panel=panel_index)

            z_bracket = z - cfg.panel_bracket_leg
            if face in ("front", "rear"):
                y = cfg.panel_batten_front_offset if face == "front" else cfg.depth - cfg.panel_batten_front_offset - cfg.batten_thickness
                specs = [
                    (_angle_y(cfg.panel_bracket_width, cfg.panel_bracket_leg, cfg.panel_bracket_wall, False, True),
                     (left_station + p, y, z_bracket),
                     (left_station + p + cfg.panel_bracket_leg / 2, y + cfg.panel_bracket_width / 2, z - cfg.panel_bracket_wall)),
                    (_angle_y(cfg.panel_bracket_width, cfg.panel_bracket_leg, cfg.panel_bracket_wall, True, True),
                     (right_station - cfg.panel_bracket_leg, y, z_bracket),
                     (right_station - cfg.panel_bracket_leg / 2, y + cfg.panel_bracket_width / 2, z - cfg.panel_bracket_wall)),
                ]
            else:
                x = cfg.panel_batten_front_offset if face == "left" else cfg.length - cfg.panel_batten_front_offset - cfg.batten_thickness
                specs = [
                    (_angle_x(cfg.panel_bracket_width, cfg.panel_bracket_leg, cfg.panel_bracket_wall, False, True),
                     (x, p, z_bracket),
                     (x + cfg.panel_bracket_width / 2, p + cfg.panel_bracket_leg / 2, z - cfg.panel_bracket_wall)),
                    (_angle_x(cfg.panel_bracket_width, cfg.panel_bracket_leg, cfg.panel_bracket_wall, True, True),
                     (x, cfg.depth - p - cfg.panel_bracket_leg, z_bracket),
                     (x + cfg.panel_bracket_width / 2, cfg.depth - p - cfg.panel_bracket_leg / 2, z - cfg.panel_bracket_wall)),
                ]
            for bracket_shape, bracket_pos, screw_pos in specs:
                add_shape(next_id("PB"), f"{face.title()} panel {panel_index} batten {batten_no} end bracket",
                          bracket_shape, bracket_pos, "panel_mount_bracket", STEEL_ANGLE,
                          f"{cfg.panel_bracket_leg:g}x{cfg.panel_bracket_leg:g}x{cfg.panel_bracket_wall:g} mm angle",
                          f"{cfg.panel_bracket_width:g} mm", PAINTED_STEEL, P_ANGLE_20,
                          "panel_mounts", cfg.panel_bracket_width)
                add_shape(next_id("PF"), f"{face.title()} panel {panel_index} concealed M5 fastener",
                          panel_screw, screw_pos, "panel_mount_fastener",
                          "Stainless M5 screw + threaded wood insert", "M5 symbolic screw / insert",
                          f"{cfg.panel_mount_screw_length:g} mm", FASTENER, viewer_group="panel_mounts")

    for bay in range(cfg.bays_x):
        left_station = station_xs[bay]
        right_station = station_xs[bay + 1]
        start = left_station + p
        add_panel("front", bay + 1, start, cfg.bay_opening_length, left_station, right_station, "front_panels")
        add_panel("rear", bay + 1, start, cfg.bay_opening_length, left_station, right_station, "rear_panels")
    add_panel("left", 1, p, cfg.module_inner_depth, 0.0, cfg.depth - p, "left_panel")
    add_panel("right", 1, p, cfg.module_inner_depth, 0.0, cfg.depth - p, "right_panel")

    assembly = Compound(label=model_id, children=shapes)
    stock_qty = {
        P_TUBE_40: _stock_qty(stock_cuts[P_TUBE_40], 3000),
        P_TUBE_20: _stock_qty(stock_cuts[P_TUBE_20], 3000),
        P_ANGLE_20: _stock_qty(stock_cuts[P_ANGLE_20], 1000),
        P_FLAT_30: _stock_qty(stock_cuts[P_FLAT_30], 3000),
    }
    foot_packs = math.ceil((2 * cfg.station_count) / 4)
    products = [
        {"id": P_TUBE_40, "retailer": "Obramat", "ref": "10330425", "name": "Tubo cuadrado acero 40x40x1,5 mm · 3 m", "url": "https://www.obramat.es/productos/tubo-cuadrado-acero-40x40x1-5mm-3m-10330425.html", "stock": "3 m", "suggested_qty": stock_qty[P_TUBE_40]},
        {"id": P_TUBE_20, "retailer": "Obramat", "ref": "10362443", "name": "Tubo cuadrado acero decapado 20x20x1,5 mm · 3 m", "url": "https://www.obramat.es/productos/tubo-cuadrado-acero-decapado-20x20x1-5mm-3m-10362443.html", "stock": "3 m", "suggested_qty": stock_qty[P_TUBE_20]},
        {"id": P_ANGLE_20, "retailer": "Obramat", "ref": "10257156", "name": "Ángulo acero 20x20x3 mm · 1 m", "url": "https://www.obramat.es/productos/angulo-acero-20x20x3mm-1m-10257156.html", "stock": "1 m", "suggested_qty": stock_qty[P_ANGLE_20]},
        {"id": P_FLAT_30, "retailer": "Obramat", "ref": "10636696", "name": "Pletina acero S275JR 30x3 mm · 3 m", "url": "https://www.obramat.es/productos/pletina-acero-x275jr-30x3mm-3m-10636696.html", "stock": "3 m", "suggested_qty": stock_qty[P_FLAT_30]},
        {"id": P_FOOT_CAP, "retailer": "Obramat", "ref": "10424295", "name": "Contera plástico embutir 40x40 mm negra · 4 uds", "url": "https://www.obramat.es/productos/contera-plastico-embutir-40-x-40-mm-negra-4-uds-10424295.html", "stock": "pack of 4", "suggested_qty": foot_packs},
        {"id": P_DRAIN, "retailer": "Leroy Merlin", "ref": "83450729", "name": "Pasamuros roscado 1/2 in para depósitos · 20 mm", "url": "https://www.leroymerlin.es/productos/pasamuros-roscado-1-2-para-depositos-20-mm-83450729.html", "stock": "1 pc", "suggested_qty": cfg.bays_x},
    ]

    scale = max(cfg.length, cfg.body_height)
    viewer_groups = [
        {"id": "top_closure", "label": "Top closure rails", "node_names": groups["top_closure"], "offset_mm": [0, 0, 250]},
        {"id": "bag_support", "label": "Bag support tubes", "node_names": groups["bag_support"], "offset_mm": [0, 0, -250]},
        {"id": "bag_clamp", "label": "Bag clamps", "node_names": groups["bag_clamp"], "offset_mm": [-0.55 * scale, 0, 300]},
        {"id": "bag_frame", "label": "Bag rim frames", "node_names": groups["bag_frame"], "offset_mm": [-0.55 * scale, 0, 130]},
        {"id": "bag_liner", "label": "Geotextile bags", "node_names": groups["bag_liner"], "offset_mm": [-0.55 * scale, 0, -80]},
        {"id": "trays", "label": "Drain trays", "node_names": groups["trays"], "offset_mm": [0.55 * scale, 0, -100]},
        {"id": "panel_mounts", "label": "Panel end brackets", "node_names": groups["panel_mounts"], "offset_mm": [0, 0, 220]},
        {"id": "front_panels", "label": "Front timber panels", "node_names": groups["front_panels"], "offset_mm": [0, -300, 0]},
        {"id": "rear_panels", "label": "Rear timber panels", "node_names": groups["rear_panels"], "offset_mm": [0, 300, 0]},
        {"id": "left_panel", "label": "Left timber panel", "node_names": groups["left_panel"], "offset_mm": [-300, 0, 0]},
        {"id": "right_panel", "label": "Right timber panel", "node_names": groups["right_panel"], "offset_mm": [300, 0, 0]},
    ]
    metadata = {
        "schema_version": 6,
        "model": model_id,
        "status": "parametric fabrication design / v6",
        "units": "mm",
        "parameters": asdict(cfg),
        "derived": {
            "bay_count": cfg.bays_x,
            "station_count": cfg.station_count,
            "bay_opening_length_mm": round(cfg.bay_opening_length, 1),
            "inner_depth_mm": round(cfg.module_inner_depth, 1),
            "leg_clearance_mm": cfg.leg_clearance,
            "bag_module_count": cfg.bays_x,
            "bag_useful_x_mm": round(cfg.module_bag_inner_x, 1),
            "bag_useful_y_mm": round(cfg.module_bag_inner_y, 1),
            "bag_useful_height_mm": cfg.soil_depth,
            "bag_volume_litres_each": round(cfg.module_bag_volume_litres_each, 1),
            "bag_volume_litres_total": round(total_bag_volume, 1),
            "bag_support_rail_count_each": support_count,
            "bag_support_clear_gap_mm": round(support_gap, 1),
            "bag_support_z_mm": round(cfg.module_bag_support_z, 1),
            "tray_target_width_mm": round(cfg.module_tray_width, 1),
            "tray_target_depth_mm": round(cfg.module_tray_depth, 1),
            "tray_vertical_clearance_mm": round(cfg.module_tray_vertical_clearance, 1),
            "panel_height_mm": round(cfg.module_panel_height, 1),
            "panel_battens_each": len(batten_zs),
            "panel_brackets_per_batten": cfg.panel_brackets_per_batten,
            "long_face_panel_count_each_side": cfg.bays_x,
            "top_open_posts_closed_by_integral_flaps": 2 * cfg.station_count,
        },
        "parts": parts,
        "products": products,
        "viewer": {"model_src": f"./models/{model_id}.glb", "groups": viewer_groups, "selected_part_offset_mm": 300},
        "assemblies": [
            {"id": "AS01", "name": "Modular welded steel body", "contains": f"{cfg.bays_x} longitudinal bay(s), {cfg.station_count} transverse frame stations"},
            {"id": "AS02", "name": "Independent grow modules", "contains": f"{cfg.bays_x} removable geotextile bag(s) with independent rim/clamp"},
            {"id": "AS03", "name": "Removable timber panels", "contains": "one panel per structural bay on long faces; one panel on each end"},
            {"id": "AS04", "name": "Commercial drain trays", "contains": f"{cfg.bays_x} moulded-plastic tray placeholder(s)"},
        ],
        "joints": [
            {"id": "J01", "type": "weld", "name": "Modular 40x40 frame", "spec": "1200 mm designs use a central frame station, avoiding 1120 mm unsupported structural spans"},
            {"id": "J02", "type": "weld", "name": "Top post closures", "spec": "each transverse top rail uses integral 40 mm top-wall flaps over the front/rear upright mouths"},
            {"id": "J03", "type": "weld", "name": "Bag support", "spec": f"each bay uses two longitudinal 20x20 bearers plus {support_count} transverse rails; clear gaps ≈ {support_gap:.1f} mm"},
            {"id": "J04", "type": "clamp", "name": "Geotextile rim", "spec": "folded liner is continuously compressed between the 20x20 rim and 30x3 clamp"},
            {"id": "J05", "type": "mechanical", "name": "Timber panels", "spec": "two tiny 20x20x3 L brackets per batten, one at each post, one concealed M5 fastener per bracket"},
        ],
        "service": {
            "bag_removal": "each bay has an independent grow bag",
            "panel_removal": "remove concealed M5 fasteners; L brackets remain welded to posts",
            "tray_removal": "each tray slides independently below its bay",
        },
        "fabrication_notes": [
            "Length is modular: 600 mm uses one bay; 1200 mm uses two bays and one central transverse frame station. This keeps steel spans close to the original design.",
            f"Soil depth is independent from overall height and fixed at {cfg.soil_depth:g} mm. On a 900 mm body the bag platform rises to Z={cfg.module_bag_support_z:g} mm instead of creating an unnecessarily deep soil column.",
            "The 1200 mm versions use two independent bags rather than one ~1100 mm liner; this reduces handling load and lets the central station carry the structure directly.",
            "Timber slats are modelled at 10 mm finished thickness, intended to be ripped from raw fir boards. Battens remain 20 mm thick.",
            "Tall panels automatically gain a third horizontal batten when the configured spacing limit is exceeded.",
            "Drain trays are commercial-plastic placeholders: about 500x500 mm for 600 mm depth and 500x300 mm for 400 mm depth. Measure the real tray bottom before welding final guides.",
            "Structural capacity is not certified; validate welds and loaded deflection on the first prototype before reproducing the design.",
        ],
        "notes": ["Steel parts render in off-white; stainless, plastic and geotextile remain visually distinct."],
    }
    return ModelBuild(shape=assembly, bom=_group_bom(parts), metadata=metadata)


PRESETS: dict[str, tuple[str, PlanterConfig]] = {
    "planter-600x600x600": ("600 × 600 × 600 mm", PlanterConfig(length=600, depth=600, body_height=600, bays_x=1)),
    "planter-1200x400x600": ("1200 × 400 × 600 mm", PlanterConfig(length=1200, depth=400, body_height=600, bays_x=2)),
    "planter-1200x600x900": ("1200 × 600 × 900 mm", PlanterConfig(length=1200, depth=600, body_height=900, bays_x=2)),
}
