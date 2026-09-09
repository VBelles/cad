from __future__ import annotations

import copy

from build123d import Align, Box, Color, Compound, Pos

from .parameters import PlanterConfig
from .planter import GEOTEXTILE, ModelBuild, _group_bom, _open_liner
from .planter_v9 import PRESETS
from .planter_v10 import (
    BAG_HEIGHT,
    BAG_TOP_GAP,
    EYELET_DROP,
    STRAP_THICKNESS,
    STRAP_WIDTH,
    WEBBING,
    WEBBING_WIDTH,
    _top_webbing_band,
    build_planter as build_planter_v10,
)


MIN_ALIGN = (Align.MIN, Align.MIN, Align.MIN)
BAG_SIDE_CLEARANCE = 20.0
MESH_SIDE_INSET = 10.0


def build_planter(
    config: PlanterConfig | None = None,
    model_id: str = "planter-600x600x600",
) -> ModelBuild:
    cfg = config or PRESETS["planter-600x600x600"][1]
    base = build_planter_v10(cfg, model_id=model_id)
    metadata = copy.deepcopy(base.metadata)
    original_parts = [dict(part) for part in metadata["parts"]]

    replace_categories = {"custom_grow_bag", "bag_top_webbing", "bag_retaining_strap"}
    remove_ids = {
        part["id"] for part in original_parts if part.get("category") in replace_categories
    }
    shapes = [child for child in base.shape.children if child.label not in remove_ids]
    parts = [part for part in original_parts if part["id"] not in remove_ids]

    p = cfg.frame_size
    divider_t = 5.0
    divider_count = cfg.bays_x - 1
    bay_open = (cfg.length - 2 * p - divider_count * divider_t) / cfg.bays_x
    inner_depth = cfg.depth - 2 * p
    bay_starts = [p + bay * (bay_open + divider_t) for bay in range(cfg.bays_x)]

    mesh_w = bay_open - 2 * MESH_SIDE_INSET
    mesh_d = inner_depth - 2 * MESH_SIDE_INSET
    bag_w = bay_open - 2 * BAG_SIDE_CLEARANCE
    bag_d = inner_depth - 2 * BAG_SIDE_CLEARANCE
    bag_top_z = cfg.top_frame_z - BAG_TOP_GAP
    bag_bottom_z = bag_top_z - BAG_HEIGHT

    if bag_w <= 0 or bag_d <= 0:
        raise ValueError("Bag clearance leaves no usable grow-bag footprint")
    if bag_w > mesh_w or bag_d > mesh_d:
        raise ValueError("Grow bag must remain fully supported by the mesh platform")

    new_bag_ids: list[str] = []
    new_retention_ids: list[str] = []

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
        item.update(extra)
        parts.append(item)

    strap_h = max(cfg.top_frame_z - EYELET_DROP - bag_top_z, 6.0)
    for bay, bay_start in enumerate(bay_starts):
        # Centre the slightly smaller bag over the larger mesh platform. This
        # leaves 20 mm nominal clearance to the surrounding structure/wood and
        # 10 mm of mesh visible around the bag footprint.
        bag_x = bay_start + BAG_SIDE_CLEARANCE
        bag_y = p + BAG_SIDE_CLEARANCE

        bag_id = f"GBN{bay + 1:02d}"
        add_shape(
            bag_id,
            f"Module {bay + 1} custom geotextile grow bag with side clearance",
            _open_liner(bag_w, bag_d, BAG_HEIGHT, 2.0, bag_id),
            (bag_x, bag_y, bag_bottom_z),
            "custom_grow_bag",
            "UV-stable non-woven geotextile",
            "custom rectangular sewn bag",
            f"{bag_w:g}x{bag_d:g}x{BAG_HEIGHT:g} mm",
            GEOTEXTILE,
            viewer_group="bag_liner",
            module=bay + 1,
            fabric_gsm=300,
            useful_volume_l=round(bag_w * bag_d * BAG_HEIGHT / 1_000_000, 1),
        )
        new_bag_ids.append(bag_id)

        band_id = f"WBN{bay + 1:02d}"
        add_shape(
            band_id,
            f"Module {bay + 1} reinforced top webbing band",
            _top_webbing_band(bag_w, bag_d),
            (bag_x, bag_y, bag_top_z - WEBBING_WIDTH),
            "bag_top_webbing",
            "High-tenacity UV-stable polyester webbing",
            f"{WEBBING_WIDTH:g} mm perimeter webbing",
            f"≈{2 * (bag_w + bag_d):.0f} mm",
            WEBBING,
            viewer_group="bag_retention",
            webbing_length_mm=2 * (bag_w + bag_d),
        )
        new_retention_ids.append(band_id)

        strap_xs = [bag_x + 18.0, bag_x + bag_w - STRAP_WIDTH - 18.0]
        for face_no, (face, y) in enumerate(
            (("front", bag_y), ("rear", bag_y + bag_d - STRAP_THICKNESS)), start=1
        ):
            for corner_no, x in enumerate(strap_xs, start=1):
                strap_id = f"WSN{bay + 1:02d}{face_no}{corner_no}"
                add_shape(
                    strap_id,
                    f"Module {bay + 1} {face} top retaining strap {corner_no}",
                    Box(STRAP_WIDTH, STRAP_THICKNESS, strap_h, align=MIN_ALIGN),
                    (x, y, bag_top_z),
                    "bag_retaining_strap",
                    "High-tenacity UV-stable polyester webbing",
                    f"{STRAP_WIDTH:g} mm webbing strap",
                    f"≈{strap_h:.0f} mm",
                    WEBBING,
                    viewer_group="bag_retention",
                    webbing_length_mm=strap_h,
                    note="retains shape only; never carries soil weight",
                )
                new_retention_ids.append(strap_id)

    for group in metadata["viewer"]["groups"]:
        group["node_names"] = [name for name in group.get("node_names", []) if name not in remove_ids]
        if group["id"] == "bag_liner":
            group["node_names"] = new_bag_ids
        elif group["id"] == "bag_retention":
            group["node_names"] = new_retention_ids

    total_volume = bag_w * bag_d * BAG_HEIGHT * cfg.bays_x / 1_000_000
    total_webbing_mm = cfg.bays_x * (
        2 * (bag_w + bag_d) + 4 * strap_h
    )

    metadata["schema_version"] = 11
    metadata["status"] = "parametric fabrication design / v11"
    metadata["parameters"] = dict(metadata["parameters"])
    metadata["parameters"].update(
        {
            "soil_depth": BAG_HEIGHT,
            "bag_height_mm": BAG_HEIGHT,
            "bag_side_clearance_mm": BAG_SIDE_CLEARANCE,
            "mesh_side_inset_mm": MESH_SIDE_INSET,
        }
    )
    metadata["derived"].update(
        {
            "bag_useful_x_mm": round(bag_w, 1),
            "bag_useful_y_mm": round(bag_d, 1),
            "bag_useful_height_mm": BAG_HEIGHT,
            "bag_volume_litres_each": round(bag_w * bag_d * BAG_HEIGHT / 1_000_000, 1),
            "bag_volume_litres_total": round(total_volume, 1),
            "bag_side_clearance_mm": BAG_SIDE_CLEARANCE,
            "mesh_overhang_beyond_bag_each_side_mm": BAG_SIDE_CLEARANCE - MESH_SIDE_INSET,
            "bag_webbing_length_m_total": round(total_webbing_mm / 1000, 2),
        }
    )
    metadata["parts"] = parts
    metadata["fabrication_notes"] = list(metadata.get("fabrication_notes", [])) + [
        "Bag footprint is intentionally 20 mm clear of the surrounding frame/cladding on every side. The mesh extends 10 mm farther than the bag on each side, so normal fabric bulging does not immediately load the removable magnetic timber panels."
    ]

    assembly = Compound(label=model_id, children=shapes)
    return ModelBuild(shape=assembly, bom=_group_bom(parts), metadata=metadata)
