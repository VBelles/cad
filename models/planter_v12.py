from __future__ import annotations

import copy

from build123d import Align, Box, Color, Compound, Pos

from .parameters import PlanterConfig
from .planter import FASTENER, ModelBuild, P_TUBE_20, STEEL_TUBE_20, _group_bom, _hollow_tube
from .planter_v8 import _stock_qty
from .planter_v10 import (
    BAG_HEIGHT,
    BAG_TOP_GAP,
    MESH_ROD,
    P_FLAT_40X4,
    PLATE_THICKNESS,
    PLATE_WIDTH,
)
from .planter_v11 import MESH_SIDE_INSET, PRESETS, build_planter as build_planter_v11


MIN_ALIGN = (Align.MIN, Align.MIN, Align.MIN)
PAINTED_STEEL = Color(0.94, 0.94, 0.93)


def build_planter(
    config: PlanterConfig | None = None,
    model_id: str = "planter-600x600x600",
) -> ModelBuild:
    cfg = config or PRESETS["planter-600x600x600"][1]
    base = build_planter_v11(cfg, model_id=model_id)
    metadata = copy.deepcopy(base.metadata)
    original_parts = [dict(part) for part in metadata["parts"]]

    # v12 changes only the mesh-support architecture. Shared boundary plates
    # disappear: every grow module becomes one self-contained removable cassette
    # made from two 40x4 side plates + three 20x20 longitudinal bearers.
    remove_categories = {
        "mesh_support_plate",
        "mesh_support_tube",
        "mesh_support_fastener",
    }
    remove_ids = {
        part["id"] for part in original_parts if part.get("category") in remove_categories
    }

    shapes = [child for child in base.shape.children if child.label not in remove_ids]
    parts = [part for part in original_parts if part["id"] not in remove_ids]

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
        **extra,
    ) -> None:
        placed = Pos(*position) * shape
        placed.label = part_id
        placed.color = color
        shapes.append(placed)
        item = {
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

    def add_bom_only(
        part_id: str,
        name: str,
        category: str,
        material: str,
        profile: str,
        cut: str,
        **extra,
    ) -> None:
        item = {
            "id": part_id,
            "name": name,
            "category": category,
            "material": material,
            "profile": profile,
            "cut": cut,
        }
        item.update(extra)
        parts.append(item)

    p = cfg.frame_size
    s = cfg.support_size
    divider_t = 5.0
    divider_count = cfg.bays_x - 1
    bay_open = (cfg.length - 2 * p - divider_count * divider_t) / cfg.bays_x
    inner_depth = cfg.depth - 2 * p
    bay_starts = [p + bay * (bay_open + divider_t) for bay in range(cfg.bays_x)]

    cassette_w = bay_open - 2 * MESH_SIDE_INSET
    cassette_d = inner_depth - 2 * MESH_SIDE_INSET
    cassette_y = p + MESH_SIDE_INSET

    bag_top_z = cfg.top_frame_z - BAG_TOP_GAP
    mesh_top_z = bag_top_z - BAG_HEIGHT
    mesh_bottom_z = mesh_top_z - MESH_ROD
    bearer_z = mesh_bottom_z - s
    plate_z = bearer_z - PLATE_THICKNESS

    cassette_ids: list[str] = []

    for bay, bay_start in enumerate(bay_starts):
        cassette_x = bay_start + MESH_SIDE_INSET

        # Each cassette has its own left and right plate. Adjacent bags never
        # share a plate, so a module can be assembled and handled independently.
        for side, x in (
            ("left", cassette_x),
            ("right", cassette_x + cassette_w - PLATE_WIDTH),
        ):
            plate_id = next_id("CP")
            add_shape(
                plate_id,
                f"Module {bay + 1} {side} cassette side plate",
                Box(PLATE_WIDTH, cassette_d, PLATE_THICKNESS, align=MIN_ALIGN),
                (x, cassette_y, plate_z),
                "cassette_side_plate",
                "S275JR steel flat bar",
                "40x4 mm flat bar",
                f"{cassette_d:g} mm",
                PAINTED_STEEL,
                product_id=P_FLAT_40X4,
                viewer_group="mesh_support",
                stock_cut_mm=cassette_d,
                module=bay + 1,
                note="belongs only to this bag cassette; never shared with the adjacent module",
            )
            cassette_ids.append(plate_id)

        rail_ys = [
            cassette_y,
            cassette_y + cassette_d / 2 - s / 2,
            cassette_y + cassette_d - s,
        ]
        for rail_no, y in enumerate(rail_ys, start=1):
            rail_id = next_id("CR")
            add_shape(
                rail_id,
                f"Module {bay + 1} cassette bearer {rail_no}",
                _hollow_tube(cassette_w, s, cfg.support_wall, "x", rail_id),
                (cassette_x, y, bearer_z),
                "cassette_support_tube",
                STEEL_TUBE_20,
                f"{s:g}x{s:g}x{cfg.support_wall:g} mm square tube",
                f"{cassette_w:g} mm",
                PAINTED_STEEL,
                product_id=P_TUBE_20,
                viewer_group="mesh_support",
                stock_cut_mm=cassette_w,
                module=bay + 1,
                note="part of the removable cassette; vertical load bears directly onto the side plates",
            )
            cassette_ids.append(rail_id)

            # One vertical M6 screw/rivnut at each tube end clamps the tube to
            # its plate. The joint is not asked to carry soil load in shear: the
            # tube sits directly on the plate.
            for side in ("left", "right"):
                add_bom_only(
                    next_id("CB"),
                    f"Module {bay + 1} bearer {rail_no} {side} plate fixing",
                    "cassette_fastener",
                    "Zinc-plated/stainless M6 screw + steel rivnut",
                    "M6 vertical cassette fixing",
                    "1 set",
                    module=bay + 1,
                )

    assembly = Compound(label=model_id, children=shapes)

    mesh_support_group = next(
        (group for group in metadata["viewer"]["groups"] if group["id"] == "mesh_support"),
        None,
    )
    if mesh_support_group:
        mesh_support_group["label"] = "Independent bolt-together bag cassettes"
        mesh_support_group["node_names"] = cassette_ids
        mesh_support_group["offset_mm"] = [0, 0, -180]

    # Recompute stock quantities affected by the cassette change.
    stock_lengths: dict[str, list[float]] = {P_TUBE_20: [], P_FLAT_40X4: []}
    for part in parts:
        product_id = part.get("product_id")
        length = part.get("length_mm")
        if product_id in stock_lengths and isinstance(length, (int, float)):
            stock_lengths[product_id].append(float(length))

    product_qty = {
        P_TUBE_20: _stock_qty(stock_lengths[P_TUBE_20], 3000.0) if stock_lengths[P_TUBE_20] else 0,
        P_FLAT_40X4: _stock_qty(stock_lengths[P_FLAT_40X4], 3000.0) if stock_lengths[P_FLAT_40X4] else 0,
    }
    for product in metadata.get("products", []):
        if product.get("id") in product_qty:
            product["suggested_qty"] = product_qty[product["id"]]

    metadata["schema_version"] = 12
    metadata["status"] = "parametric fabrication design / v12"
    metadata["parameters"] = dict(metadata["parameters"])
    metadata["parameters"].update(
        {
            "mesh_support_architecture": "independent cassette per bag",
            "cassette_side_plates_each": 2,
            "cassette_bearers_each": 3,
            "cassette_plate_to_tube_joint": "6 x M6 screw/rivnut per module",
        }
    )
    metadata["derived"].update(
        {
            "mesh_support_shared_between_modules": False,
            "cassette_count": cfg.bays_x,
            "cassette_side_plate_count_total": 2 * cfg.bays_x,
            "cassette_bearer_count_total": 3 * cfg.bays_x,
            "cassette_fastener_count_total": 6 * cfg.bays_x,
            "cassette_width_mm": round(cassette_w, 1),
            "cassette_depth_mm": round(cassette_d, 1),
        }
    )
    metadata["parts"] = parts

    metadata["assemblies"] = [
        assembly_item
        for assembly_item in metadata.get("assemblies", [])
        if assembly_item.get("id") != "AS02"
    ]
    metadata["assemblies"].insert(
        1,
        {
            "id": "AS02",
            "name": "Independent bolt-together bag cassettes",
            "contains": (
                f"{cfg.bays_x} independent cassette(s); each has two 40x4 side plates, "
                "three 20x20 bearers and one welded-mesh panel"
            ),
        },
    )

    metadata["joints"] = [
        joint for joint in metadata.get("joints", []) if joint.get("id") != "J02"
    ] + [
        {
            "id": "J02",
            "type": "bolt-together cassette",
            "name": "Independent bag platform",
            "spec": (
                "Each bag has its own two 40x4 transverse side plates and three longitudinal 20x20 bearers. "
                "Each bearer is clamped directly to both plates with one M6 screw/rivnut per end. "
                "No side plate is shared by neighbouring bags."
            ),
        }
    ]

    metadata["service"] = dict(metadata.get("service", {}))
    metadata["service"]["mesh_removal"] = (
        "release/remove the bag, lift its mesh and withdraw the complete two-plate/three-tube cassette; "
        "adjacent grow modules remain untouched"
    )
    metadata["fabrication_notes"] = list(metadata.get("fabrication_notes", [])) + [
        "v12 deliberately duplicates the side plate at every internal bag boundary. The small material penalty makes each grow platform a completely independent pre-assemblable cassette.",
        "Assemble each cassette on the bench: bolt three 20x20 bearers between its own two 40x4 plates, then place/retain the cut welded-mesh panel on top. No alignment with the neighbouring bag is required.",
        "The M6 plate-to-tube fasteners clamp and locate the cassette. Vertical soil load is transferred by direct steel-on-steel bearing from the 20x20 tube ends into the 40x4 plates.",
    ]

    return ModelBuild(shape=assembly, bom=_group_bom(parts), metadata=metadata)
