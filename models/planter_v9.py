from __future__ import annotations

import copy
import math
from dataclasses import replace
from typing import Any

from build123d import Align, Box, Color, Compound, Pos

from .parameters import PlanterConfig
from .planter import ModelBuild, P_ANGLE_20, P_FLAT_30, P_TUBE_20, P_TUBE_40, _group_bom
from .planter_v8 import _batten_zs, _stock_qty, build_planter as build_planter_v8


MIN_ALIGN = (Align.MIN, Align.MIN, Align.MIN)
PAINTED_STEEL = Color(0.94, 0.94, 0.93)
MAGNET = Color(0.18, 0.19, 0.21)
HOSE = Color(0.07, 0.08, 0.09)
VALVE = Color(0.12, 0.13, 0.14)

MAGNET_SIZE = 20.0
MAGNET_DEPTH = 3.0
TARGET_WIDTH = 30.0
TARGET_THICKNESS = 3.0
TRAY_SHELF_WIDTH = 80.0
TRAY_SHELF_THICKNESS = 5.0
DRAIN_HOSE_OD = 12.0
VALVE_LENGTH = 36.0
VALVE_WIDTH = 22.0
VALVE_HEIGHT = 20.0


def _v9_config(config: PlanterConfig | None) -> PlanterConfig:
    if config is None:
        return PlanterConfig(
            leg_clearance=40,
            soil_depth=430,
            tray_target_z=45,
            panel_vertical_clearance=0,
        )
    return config


def build_planter(
    config: PlanterConfig | None = None,
    model_id: str = "planter-600x600x600",
) -> ModelBuild:
    cfg = _v9_config(config)
    p = cfg.frame_size
    divider_t = 5.0
    divider_w = TRAY_SHELF_WIDTH

    if cfg.panel_vertical_clearance != 0:
        raise ValueError("v9 magnetic panels are intended to rest directly on the lower 40x40 rail")
    if cfg.tray_target_z < cfg.bottom_frame_z:
        raise ValueError("Hidden tray bottom must not sit below the lower rail bottom")
    if cfg.tray_target_z + cfg.tray_target_height > cfg.bottom_frame_z + p:
        raise ValueError("Hidden tray must fit behind the 40x40 lower rail")

    # Build v8 with the new service geometry dimensions, then replace only the
    # panel fastening and tray-support details. The main continuous four-leg
    # structure and independent grow modules remain unchanged.
    base = build_planter_v8(cfg, model_id=model_id)
    metadata = copy.deepcopy(base.metadata)
    original_parts = [dict(part) for part in metadata["parts"]]

    remove_categories = {
        "panel_mount_bracket",
        "panel_mount_fastener",
        "tray_support_plate",
        "tray_support_hanger",
    }
    remove_ids = {
        part["id"] for part in original_parts if part.get("category") in remove_categories
    }

    shapes = [child for child in base.shape.children if child.label not in remove_ids]
    parts = [part for part in original_parts if part["id"] not in remove_ids]

    # Clean removed node ids from existing viewer groups before adding v9 ones.
    for group in metadata["viewer"]["groups"]:
        group["node_names"] = [name for name in group.get("node_names", []) if name not in remove_ids]

    counters: dict[str, int] = {}
    for part in parts:
        prefix = "".join(ch for ch in part["id"] if ch.isalpha())
        suffix = "".join(ch for ch in part["id"] if ch.isdigit())
        if prefix and suffix:
            counters[prefix] = max(counters.get(prefix, 0), int(suffix))

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
        *,
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
        if stock_cut_mm is not None:
            item["length_mm"] = stock_cut_mm
        item.update(extra)
        parts.append(item)

    # --- Hidden tray shelves ------------------------------------------------
    divider_count = cfg.bays_x - 1
    bay_open = (cfg.length - 2 * p - divider_count * divider_t) / cfg.bays_x
    inner_depth = cfg.depth - 2 * p
    inner_length = cfg.length - 2 * p
    tray_w = min(cfg.tray_target_width, bay_open - 2 * cfg.tray_edge_margin)
    tray_d = min(cfg.tray_target_depth, inner_depth - 2 * cfg.tray_edge_margin)
    bay_starts = [p + bay * (bay_open + divider_t) for bay in range(cfg.bays_x)]
    divider_starts = [
        p + i * bay_open + (i - 1) * divider_t for i in range(1, cfg.bays_x)
    ]

    def boundary_plate_x(boundary: int) -> float:
        if boundary == 0:
            return p
        if boundary == cfg.bays_x:
            return cfg.length - p - divider_w
        divider_start = divider_starts[boundary - 1]
        return divider_start + divider_t / 2 - divider_w / 2

    tray_support_ids: list[str] = []
    shelf_z = cfg.tray_target_z - TRAY_SHELF_THICKNESS
    for boundary in range(cfg.bays_x + 1):
        part_id = next_id("TS")
        add_shape(
            part_id,
            f"Tray shared shelf boundary {boundary + 1}",
            Box(divider_w, inner_depth, TRAY_SHELF_THICKNESS, align=MIN_ALIGN),
            (boundary_plate_x(boundary), p, shelf_z),
            "tray_support_plate",
            "S275JR steel flat plate",
            f"{divider_w:g}x{TRAY_SHELF_THICKNESS:g} mm flat plate",
            f"{inner_depth:g} mm",
            PAINTED_STEEL,
            viewer_group="trays",
            note="spans the full inner depth and welds directly to the continuous lower front/rear rails",
        )
        tray_support_ids.append(part_id)

    # A light 30x3 centre strip under each tray prevents a shallow moulded
    # saucer from sagging if several litres accumulate before draining.
    for bay, bay_start in enumerate(bay_starts):
        part_id = next_id("TS")
        centre_x = bay_start + bay_open / 2 - cfg.bag_clamp_width / 2
        add_shape(
            part_id,
            f"Module {bay + 1} tray centre support strip",
            Box(cfg.bag_clamp_width, inner_depth, cfg.bag_clamp_thickness, align=MIN_ALIGN),
            (centre_x, p, cfg.tray_target_z - cfg.bag_clamp_thickness),
            "tray_support_strip",
            "S275JR steel flat bar",
            f"{cfg.bag_clamp_width:g}x{cfg.bag_clamp_thickness:g} mm flat bar",
            f"{inner_depth:g} mm",
            PAINTED_STEEL,
            product_id=P_FLAT_30,
            viewer_group="trays",
            stock_cut_mm=inner_depth,
        )
        tray_support_ids.append(part_id)

    # --- Magnetic removable timber panels ----------------------------------
    # Slats sit directly on the lower rail; therefore magnets only resist
    # outward removal/rattle. They do not carry panel dead weight.
    batten_zs = _batten_zs(cfg)
    magnetic_ids: list[str] = []

    def add_magnetic_pair(face: str, batten_no: int, z: float, end: str) -> None:
        target_id = next_id("MT")
        magnet_id = next_id("MG")
        magnet_z = z + (cfg.batten_height - MAGNET_SIZE) / 2
        target_z = z + (cfg.batten_height - TARGET_WIDTH) / 2

        if face == "front":
            left = end == "left"
            target_x = p if left else cfg.length - p - TARGET_WIDTH
            magnet_x = target_x + (TARGET_WIDTH - MAGNET_SIZE) / 2
            target_pos = (target_x, cfg.panel_batten_front_offset + cfg.batten_thickness, target_z)
            magnet_pos = (magnet_x, cfg.panel_batten_front_offset + cfg.batten_thickness - MAGNET_DEPTH, magnet_z)
            target_shape = Box(TARGET_WIDTH, TARGET_THICKNESS, TARGET_WIDTH, align=MIN_ALIGN)
            magnet_shape = Box(MAGNET_SIZE, MAGNET_DEPTH, MAGNET_SIZE, align=MIN_ALIGN)
        elif face == "rear":
            left = end == "left"
            target_x = p if left else cfg.length - p - TARGET_WIDTH
            magnet_x = target_x + (TARGET_WIDTH - MAGNET_SIZE) / 2
            batten_y = cfg.depth - cfg.panel_batten_front_offset - cfg.batten_thickness
            target_pos = (target_x, batten_y - TARGET_THICKNESS, target_z)
            magnet_pos = (magnet_x, batten_y, magnet_z)
            target_shape = Box(TARGET_WIDTH, TARGET_THICKNESS, TARGET_WIDTH, align=MIN_ALIGN)
            magnet_shape = Box(MAGNET_SIZE, MAGNET_DEPTH, MAGNET_SIZE, align=MIN_ALIGN)
        elif face == "left":
            front = end == "front"
            target_y = p if front else cfg.depth - p - TARGET_WIDTH
            magnet_y = target_y + (TARGET_WIDTH - MAGNET_SIZE) / 2
            target_pos = (cfg.panel_batten_front_offset + cfg.batten_thickness, target_y, target_z)
            magnet_pos = (cfg.panel_batten_front_offset + cfg.batten_thickness - MAGNET_DEPTH, magnet_y, magnet_z)
            target_shape = Box(TARGET_THICKNESS, TARGET_WIDTH, TARGET_WIDTH, align=MIN_ALIGN)
            magnet_shape = Box(MAGNET_DEPTH, MAGNET_SIZE, MAGNET_SIZE, align=MIN_ALIGN)
        else:
            front = end == "front"
            target_y = p if front else cfg.depth - p - TARGET_WIDTH
            magnet_y = target_y + (TARGET_WIDTH - MAGNET_SIZE) / 2
            batten_x = cfg.length - cfg.panel_batten_front_offset - cfg.batten_thickness
            target_pos = (batten_x - TARGET_THICKNESS, target_y, target_z)
            magnet_pos = (batten_x, magnet_y, magnet_z)
            target_shape = Box(TARGET_THICKNESS, TARGET_WIDTH, TARGET_WIDTH, align=MIN_ALIGN)
            magnet_shape = Box(MAGNET_DEPTH, MAGNET_SIZE, MAGNET_SIZE, align=MIN_ALIGN)

        add_shape(
            target_id,
            f"{face.title()} batten {batten_no} {end} magnetic target tab",
            target_shape,
            target_pos,
            "panel_magnet_target",
            "S275JR steel flat bar",
            "30x3 mm flat-bar target tab",
            "30 mm",
            PAINTED_STEEL,
            product_id=P_FLAT_30,
            viewer_group="panel_mounts",
            stock_cut_mm=30.0,
            note="simple welded target tab; no drilling, rivnut or threaded insert",
        )
        add_shape(
            magnet_id,
            f"{face.title()} batten {batten_no} {end} recessed magnet",
            magnet_shape,
            magnet_pos,
            "panel_magnet",
            "Epoxy-sealed neodymium magnet",
            "20x20x3 mm symbolic magnet recess",
            "1 pc",
            MAGNET,
            viewer_group="panel_mounts",
            note="recess flush into rear of timber batten; seal pocket with exterior epoxy",
        )
        magnetic_ids.extend((target_id, magnet_id))

    for batten_no, z in enumerate(batten_zs, start=1):
        for end in ("left", "right"):
            add_magnetic_pair("front", batten_no, z, end)
            add_magnetic_pair("rear", batten_no, z, end)
        for end in ("front", "rear"):
            add_magnetic_pair("left", batten_no, z, end)
            add_magnetic_pair("right", batten_no, z, end)

    # --- Gravity drain manifold --------------------------------------------
    # Keep each v8 bottom bulkhead. Add a short branch to a common rear header,
    # then one low hidden valve. Real hose should be 12-16 mm ID and clipped with
    # a continuous fall to the valve; the rectangular solids are schematic.
    drainage_ids: list[str] = []
    manifold_y = cfg.depth - p - 16.0
    manifold_z = 18.0
    branch_xs: list[float] = []
    for bay, bay_start in enumerate(bay_starts):
        tray_x = bay_start + (bay_open - tray_w) / 2
        tray_y = p + (inner_depth - tray_d) / 2
        fitting_x = tray_x + tray_w - 35
        fitting_y = tray_y + tray_d - 35
        branch_xs.append(fitting_x)
        branch_len = max(manifold_y - fitting_y, DRAIN_HOSE_OD)
        branch_id = next_id("DH")
        add_shape(
            branch_id,
            f"Module {bay + 1} drain hose branch",
            Box(DRAIN_HOSE_OD, branch_len, DRAIN_HOSE_OD, align=MIN_ALIGN),
            (fitting_x - DRAIN_HOSE_OD / 2, fitting_y, manifold_z),
            "drain_hose",
            "Flexible drain hose",
            "12 mm OD symbolic hose · use 12-16 mm ID in fabrication",
            f"≈{branch_len:.0f} mm",
            HOSE,
            viewer_group="drainage_system",
            note="use removable barb/quick connection at tray for service",
        )
        drainage_ids.append(branch_id)

    manifold_x0 = p + 20.0
    manifold_x1 = cfg.length - p - 20.0
    manifold_id = next_id("DM")
    add_shape(
        manifold_id,
        "Common gravity drain manifold",
        Box(manifold_x1 - manifold_x0, DRAIN_HOSE_OD, DRAIN_HOSE_OD, align=MIN_ALIGN),
        (manifold_x0, manifold_y - DRAIN_HOSE_OD / 2, manifold_z),
        "drain_manifold",
        "Flexible drain hose / irrigation tube",
        "12 mm OD symbolic header · use 12-16 mm ID",
        f"≈{manifold_x1 - manifold_x0:.0f} mm",
        HOSE,
        viewer_group="drainage_system",
        note="clip to the inside of the lower rear rail with 1-2% fall toward valve",
    )
    drainage_ids.append(manifold_id)

    valve_id = next_id("DV")
    valve_x = p + 6.0
    add_shape(
        valve_id,
        "Hidden drain mini ball valve",
        Box(VALVE_LENGTH, VALVE_WIDTH, VALVE_HEIGHT, align=MIN_ALIGN),
        (valve_x, manifold_y - VALVE_WIDTH / 2, 12.0),
        "drain_valve",
        "Plastic/brass mini ball valve",
        "1/2 in compact valve envelope",
        "1 pc",
        VALVE,
        viewer_group="drainage_system",
        note="locate just inboard of a short side so it is reachable from below without removing a panel",
    )
    drainage_ids.append(valve_id)

    assembly = Compound(label=model_id, children=shapes)

    # Rebuild viewer groups.
    panel_group = next((g for g in metadata["viewer"]["groups"] if g["id"] == "panel_mounts"), None)
    if panel_group:
        panel_group["label"] = "Magnetic panel mounts"
        panel_group["node_names"] = magnetic_ids
        panel_group["offset_mm"] = [0, 0, 220]

    tray_group = next((g for g in metadata["viewer"]["groups"] if g["id"] == "trays"), None)
    if tray_group:
        existing = [name for name in tray_group["node_names"] if name not in remove_ids]
        tray_group["label"] = "Hidden drain trays / shelves"
        tray_group["node_names"] = existing + tray_support_ids

    metadata["viewer"]["groups"].append(
        {
            "id": "drainage_system",
            "label": "Drain manifold / valve",
            "node_names": drainage_ids,
            "offset_mm": [0, 250, -120],
        }
    )

    # Recompute purchased stock quantities after removing angle brackets and
    # adding simple 30x3 target tabs / tray strips.
    stock_lengths: dict[str, list[float]] = {P_TUBE_40: [], P_TUBE_20: [], P_ANGLE_20: [], P_FLAT_30: []}
    for part in parts:
        product_id = part.get("product_id")
        length = part.get("length_mm")
        if product_id in stock_lengths and isinstance(length, (int, float)):
            stock_lengths[product_id].append(float(length))
    stock_mm = {P_TUBE_40: 3000.0, P_TUBE_20: 3000.0, P_ANGLE_20: 1000.0, P_FLAT_30: 3000.0}
    product_qty = {
        product_id: (_stock_qty(lengths, stock_mm[product_id]) if lengths else 0)
        for product_id, lengths in stock_lengths.items()
    }
    for product in metadata.get("products", []):
        if product["id"] in product_qty:
            product["suggested_qty"] = product_qty[product["id"]]

    metadata["schema_version"] = 9
    metadata["status"] = "parametric fabrication design / v9"
    metadata["parameters"] = dict(metadata["parameters"])
    metadata["parameters"].update(
        {
            "leg_clearance": cfg.leg_clearance,
            "soil_depth": cfg.soil_depth,
            "tray_target_z": cfg.tray_target_z,
            "panel_vertical_clearance": cfg.panel_vertical_clearance,
            "panel_magnet_symbolic_size": MAGNET_SIZE,
            "drain_hose_nominal_id_mm": "12-16",
        }
    )
    metadata["derived"].update(
        {
            "leg_clearance_mm": cfg.leg_clearance,
            "bag_useful_height_mm": cfg.soil_depth,
            "bag_support_z_mm": round(metadata["derived"]["bag_support_z_mm"], 1),
            "tray_hidden_behind_lower_rail": True,
            "tray_lift_to_clear_lower_rail_mm": round(cfg.bottom_frame_z + p - cfg.tray_target_z, 1),
            "tray_free_space_above_mm": round(metadata["derived"]["bag_support_z_mm"] - (cfg.tray_target_z + cfg.tray_target_height), 1),
            "panel_mount_type": "magnetic retention + lower-rail gravity support",
            "panel_magnet_count": len([part for part in parts if part.get("category") == "panel_magnet"]),
            "common_drain_valve_count": 1,
        }
    )
    metadata["parts"] = parts
    metadata["assemblies"] = [
        {
            "id": "AS01",
            "name": "Four-leg continuous welded steel body",
            "contains": "4 corner uprights, continuous long rails, thin shared grow-module supports",
        },
        {
            "id": "AS02",
            "name": "Independent grow modules",
            "contains": f"{cfg.bays_x} geotextile bag(s) with independent rim/clamp",
        },
        {
            "id": "AS03",
            "name": "Magnetically removable timber cladding",
            "contains": "one continuous panel per face; panel weight rests on lower rail, magnets only retain it",
        },
        {
            "id": "AS04",
            "name": "Hidden tray and gravity drain system",
            "contains": f"{cfg.bays_x} hidden tray(s), individual hose branches, common header and one valve",
        },
    ]
    metadata["joints"] = [joint for joint in metadata["joints"] if joint.get("id") != "J04"]
    metadata["joints"].extend(
        [
            {
                "id": "J04",
                "type": "magnetic removable panel",
                "name": "Timber service panels",
                "spec": (
                    "Slats rest on the lower 40x40 rail. Each batten uses one recessed sealed magnet at each end, "
                    "attracting a simple 30x3 welded flat-bar target tab. No panel screws, rivnuts or threaded inserts."
                ),
            },
            {
                "id": "J05",
                "type": "gravity drainage",
                "name": "Common tray drain",
                "spec": (
                    "Each tray retains its low bulkhead, connects via removable 12-16 mm ID hose to a common rear header, "
                    "and drains through one compact low-point ball valve."
                ),
            },
        ]
    )
    metadata["service"] = {
        "panel_removal": "pull panel outward to release magnets; its dead weight is carried by the lower rail, not the magnets",
        "tray_drain": "place a container at the hidden low-point valve and open it; all tray branches drain to the common header",
        "tray_removal": (
            "remove magnetic panel, release tray hose connection, lift tray roughly "
            f"{cfg.bottom_frame_z + p - cfg.tray_target_z:.0f} mm to clear the lower rail, then tilt/pull it out"
        ),
        "bag_removal": "each grow module remains independently removable from above",
    }
    metadata["fabrication_notes"] = [
        note
        for note in metadata.get("fabrication_notes", [])
        if "panel" not in note.lower() and "tray" not in note.lower()
    ] + [
        "Leg clearance is reduced to 40 mm. The 30 mm-high tray placeholder sits at Z=45..75 mm, fully hidden behind the 40x40 lower rail at Z=40..80 mm.",
        "Useful soil depth is reduced slightly from 443 to 430 mm. This raises the bag platform enough to create service clearance above the hidden tray while losing only about 3% soil depth.",
        "Timber panels sit directly on the lower steel rail, with top/bottom end grain protected by the surrounding steel frame. Magnets only provide outward retention and anti-rattle force.",
        "Use a shallow Forstner/router pocket in each batten for an exterior-sealed magnet. Keep the magnet face flush with the timber rear face; avoid leaving wood between magnet and steel target because pull force drops quickly with gap.",
        "The magnetic target is only a 30 mm offcut of the existing 30x3 flat bar welded behind the batten end. This replaces the former L bracket + M5 screw + threaded insert assembly.",
        "Drain hose geometry is schematic. Use approximately 12-16 mm internal diameter, removable barb/quick connections at trays, corrosion-resistant clamps, and clip the header with continuous fall toward the valve.",
        "The drain valve should be tucked just inside a short side / under the lower rail so it is normally invisible but reachable without removing a panel.",
        "Tray removal is a service operation, not normal drainage: pull off the magnetic panel, disconnect hose, lift the tray above the lower rail and tilt it out.",
    ]

    return ModelBuild(shape=assembly, bom=_group_bom(parts), metadata=metadata)


PRESETS: dict[str, tuple[str, PlanterConfig]] = {
    "planter-600x600x600": (
        "600 × 600 × 600 mm",
        PlanterConfig(
            length=600,
            depth=600,
            body_height=600,
            bays_x=1,
            leg_clearance=40,
            soil_depth=430,
            tray_target_z=45,
            panel_vertical_clearance=0,
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
            leg_clearance=40,
            soil_depth=430,
            tray_target_z=45,
            panel_vertical_clearance=0,
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
            leg_clearance=40,
            soil_depth=430,
            tray_target_z=45,
            panel_vertical_clearance=0,
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
            leg_clearance=40,
            soil_depth=430,
            tray_target_z=45,
            panel_vertical_clearance=0,
            panel_outer_inset=0,
        ),
    ),
}
