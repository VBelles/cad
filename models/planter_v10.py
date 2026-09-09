from __future__ import annotations

import copy
import math
from typing import Any

from build123d import Align, Box, Color, Compound, Pos

from .parameters import PlanterConfig
from .planter import (
    FASTENER,
    GEOTEXTILE,
    ModelBuild,
    P_FLAT_30,
    P_TUBE_20,
    P_TUBE_40,
    STEEL_TUBE_20,
    _group_bom,
    _hollow_tube,
    _open_liner,
)
from .planter_v8 import _stock_qty
from .planter_v9 import PRESETS as V9_PRESETS, build_planter as build_planter_v9


MIN_ALIGN = (Align.MIN, Align.MIN, Align.MIN)
PAINTED_STEEL = Color(0.94, 0.94, 0.93)
GALVANISED_MESH = Color(0.58, 0.61, 0.63)
WEBBING = Color(0.08, 0.08, 0.09)

P_FLAT_40X4 = "obramat-flat-40x4"
P_MESH_50X50X4 = "aceropanel-mesh-50x50x4"

PLATE_WIDTH = 40.0
PLATE_THICKNESS = 4.0
MESH_PITCH = 50.0
MESH_ROD = 4.0
MESH_EDGE_INSET = 10.0
BAG_HEIGHT = 400.0
BAG_TOP_GAP = 12.0
WEBBING_WIDTH = 40.0
STRAP_WIDTH = 25.0
STRAP_THICKNESS = 2.0
EYELET_DROP = 10.0


def _mesh_panel(width: float, depth: float):
    """Symbolic 50x50x4 welded mesh using square rods for a lightweight GLB."""
    children = []
    nx = max(2, math.floor(width / MESH_PITCH) + 1)
    ny = max(2, math.floor(depth / MESH_PITCH) + 1)
    for i in range(nx):
        x = min(i * MESH_PITCH, width - MESH_ROD)
        children.append(Pos(x, 0, 0) * Box(MESH_ROD, depth, MESH_ROD, align=MIN_ALIGN))
    for i in range(ny):
        y = min(i * MESH_PITCH, depth - MESH_ROD)
        children.append(Pos(0, y, 0) * Box(width, MESH_ROD, MESH_ROD, align=MIN_ALIGN))
    return Compound(children=children)


def _top_webbing_band(width: float, depth: float, height: float = WEBBING_WIDTH):
    t = 2.0
    return Compound(
        children=[
            Box(width, t, height, align=MIN_ALIGN),
            Pos(0, depth - t, 0) * Box(width, t, height, align=MIN_ALIGN),
            Pos(0, t, 0) * Box(t, depth - 2 * t, height, align=MIN_ALIGN),
            Pos(width - t, t, 0) * Box(t, depth - 2 * t, height, align=MIN_ALIGN),
        ]
    )


def build_planter(
    config: PlanterConfig | None = None,
    model_id: str = "planter-600x600x600",
) -> ModelBuild:
    cfg = config or V9_PRESETS["planter-600x600x600"][1]
    p = cfg.frame_size
    s = cfg.support_size
    divider_t = 5.0

    base = build_planter_v9(cfg, model_id=model_id)
    metadata = copy.deepcopy(base.metadata)
    original_parts = [dict(part) for part in metadata["parts"]]

    # v10 removes the fabricated grow-bag rim/clamp and the dense 20x20 floor
    # grid. It also replaces the oversized 80x5 horizontal support plates with
    # lighter 40x4 plates. The main 40x40 body, hidden trays/drainage and timber
    # panels remain as in v9.
    remove_categories = {
        "bag_support",
        "bag_frame",
        "bag_clamp",
        "bag_clamp_fastener",
        "liner",
        "liner_clamp",
        "module_support_plate",
        "tray_support_plate",
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

    def add_bom_only(
        part_id: str,
        name: str,
        category: str,
        material: str,
        profile: str,
        cut: str,
        **extra: Any,
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

    divider_count = cfg.bays_x - 1
    bay_open = (cfg.length - 2 * p - divider_count * divider_t) / cfg.bays_x
    inner_depth = cfg.depth - 2 * p
    inner_length = cfg.length - 2 * p
    bay_starts = [p + bay * (bay_open + divider_t) for bay in range(cfg.bays_x)]
    divider_starts = [p + i * bay_open + (i - 1) * divider_t for i in range(1, cfg.bays_x)]

    bag_w = bay_open - 2 * MESH_EDGE_INSET
    bag_d = inner_depth - 2 * MESH_EDGE_INSET
    bag_top_z = cfg.top_frame_z - BAG_TOP_GAP
    mesh_top_z = bag_top_z - BAG_HEIGHT
    mesh_bottom_z = mesh_top_z - MESH_ROD
    bearer_z = mesh_bottom_z - s
    support_plate_z = bearer_z - PLATE_THICKNESS

    if support_plate_z - (cfg.tray_target_z + cfg.tray_target_height) < 35:
        raise ValueError("v10 requires at least 35 mm tray service lift below the mesh support plate")

    def boundary_plate_x(boundary: int) -> float:
        if boundary == 0:
            return p
        if boundary == cfg.bays_x:
            return cfg.length - p - PLATE_WIDTH
        divider_start = divider_starts[boundary - 1]
        return divider_start + divider_t / 2 - PLATE_WIDTH / 2

    mesh_support_ids: list[str] = []
    tray_support_ids: list[str] = []
    mesh_ids: list[str] = []
    bag_ids: list[str] = []
    bag_anchor_ids: list[str] = []

    # One shared 40x4 plate per module boundary supports the bolt-on 20x20
    # bearers and the left/right edges of adjacent mesh panels.
    for boundary in range(cfg.bays_x + 1):
        x = boundary_plate_x(boundary)
        support_id = next_id("MP")
        add_shape(
            support_id,
            f"Mesh support boundary plate {boundary + 1}",
            Box(PLATE_WIDTH, inner_depth, PLATE_THICKNESS, align=MIN_ALIGN),
            (x, p, support_plate_z),
            "mesh_support_plate",
            "S275JR steel flat bar",
            "40x4 mm flat bar",
            f"{inner_depth:g} mm",
            PAINTED_STEEL,
            product_id=P_FLAT_40X4,
            viewer_group="mesh_support",
            stock_cut_mm=inner_depth,
            note="shared bearing for adjacent mesh panels and tube ends",
        )
        mesh_support_ids.append(support_id)

        # The tray needs much less structure than v9's 80x5 shelf. A matching
        # 40x4 strip at each module boundary plus the existing 30x3 centre strip
        # is sufficient for the shallow commercial tray placeholder.
        tray_id = next_id("TP")
        add_shape(
            tray_id,
            f"Light tray boundary support {boundary + 1}",
            Box(PLATE_WIDTH, inner_depth, PLATE_THICKNESS, align=MIN_ALIGN),
            (x, p, cfg.tray_target_z - PLATE_THICKNESS),
            "tray_support_plate_light",
            "S275JR steel flat bar",
            "40x4 mm flat bar",
            f"{inner_depth:g} mm",
            PAINTED_STEEL,
            product_id=P_FLAT_40X4,
            viewer_group="trays",
            stock_cut_mm=inner_depth,
            note="lighter replacement for v9 80x5 tray shelf",
        )
        tray_support_ids.append(tray_id)

    # Three longitudinal 20x20 rails per module: front, centre and rear. They
    # rest on the boundary plates; M6 bolts only locate them, so fasteners do not
    # carry the vertical bag load.
    for bay, bay_start in enumerate(bay_starts):
        mesh_x = bay_start + MESH_EDGE_INSET
        mesh_y = p + MESH_EDGE_INSET
        rail_ys = [
            mesh_y,
            p + inner_depth / 2 - s / 2,
            mesh_y + bag_d - s,
        ]
        for rail_no, y in enumerate(rail_ys, start=1):
            rail_id = next_id("MR")
            add_shape(
                rail_id,
                f"Module {bay + 1} removable mesh bearer {rail_no}",
                _hollow_tube(bay_open, s, cfg.support_wall, "x", rail_id),
                (bay_start, y, bearer_z),
                "mesh_support_tube",
                STEEL_TUBE_20,
                f"{s:g}x{s:g}x{cfg.support_wall:g} mm square tube",
                f"{bay_open:g} mm",
                PAINTED_STEEL,
                product_id=P_TUBE_20,
                viewer_group="mesh_support",
                stock_cut_mm=bay_open,
                note="rests on 40x4 boundary plates; two M6 retaining bolts locate each rail",
            )
            mesh_support_ids.append(rail_id)
            for end in ("left", "right"):
                add_bom_only(
                    next_id("MB"),
                    f"Module {bay + 1} bearer {rail_no} {end} M6 retaining bolt",
                    "mesh_support_fastener",
                    "Zinc-plated/stainless M6 bolt + locknut",
                    "M6 through-bolt",
                    "1 set",
                )

        mesh_id = next_id("WM")
        add_shape(
            mesh_id,
            f"Module {bay + 1} welded mesh bag platform",
            _mesh_panel(bag_w, bag_d),
            (mesh_x, mesh_y, mesh_bottom_z),
            "welded_mesh_platform",
            "Galvanised welded steel mesh",
            "50x50x4 mm rigid welded mesh",
            f"{bag_w:g}x{bag_d:g} mm",
            GALVANISED_MESH,
            product_id=P_MESH_50X50X4,
            viewer_group="mesh_platform",
            area_m2=round(bag_w * bag_d / 1_000_000, 4),
            note="cut/deburr flush; repair cut zinc coating with zinc-rich paint",
        )
        mesh_ids.append(mesh_id)

        # Custom self-supporting bag. The entire soil load sits on the mesh;
        # upper straps only keep the mouth square and taut.
        bag_x = mesh_x
        bag_y = mesh_y
        bag_id = next_id("GB")
        add_shape(
            bag_id,
            f"Module {bay + 1} custom geotextile grow bag",
            _open_liner(bag_w, bag_d, BAG_HEIGHT, 2.0, bag_id),
            (bag_x, bag_y, mesh_top_z),
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
        bag_ids.append(bag_id)

        band_id = next_id("WB")
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
        bag_anchor_ids.append(band_id)

        strap_h = max(cfg.top_frame_z - EYELET_DROP - bag_top_z, 6.0)
        strap_xs = [bag_x + 18.0, bag_x + bag_w - STRAP_WIDTH - 18.0]
        for face, y in (("front", bag_y), ("rear", bag_y + bag_d - STRAP_THICKNESS)):
            for corner_no, x in enumerate(strap_xs, start=1):
                strap_id = next_id("WS")
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
                bag_anchor_ids.append(strap_id)

                add_bom_only(
                    next_id("EA"),
                    f"Module {bay + 1} {face} strap M6 eye anchor",
                    "bag_eye_anchor",
                    "Stainless/zinc-plated M6 eye + steel rivnut",
                    "M6 eye anchor into downward face of top 40x40 tube",
                    "1 set",
                )

    # v9 magnetic target tabs remain geometrically correct; they become bolt-on
    # instead of welded. Add one M6 rivnut/screw set per target tab.
    target_parts = [part for part in parts if part.get("category") == "panel_magnet_target"]
    for target in target_parts:
        target["name"] = target["name"].replace("magnetic target tab", "bolt-on magnetic target tab")
        target["note"] = "30x3 target tab fixed with one M6 screw into a rivnut in the 40x40 post; no welding"
        add_bom_only(
            next_id("PMB"),
            f"Fastener for {target['name']}",
            "panel_target_fastener",
            "Zinc-plated/stainless M6 screw + steel rivnut",
            "M6 panel-target fastener",
            "1 set",
        )

    assembly = Compound(label=model_id, children=shapes)

    # Replace / append viewer groups.
    metadata["viewer"]["groups"] = [
        group
        for group in metadata["viewer"]["groups"]
        if group["id"] not in {"bag_support", "bag_frame", "bag_clamp", "divider_plates"}
    ]
    metadata["viewer"]["groups"].append(
        {
            "id": "mesh_support",
            "label": "Bolt-on mesh supports",
            "node_names": mesh_support_ids,
            "offset_mm": [0, 0, -180],
        }
    )
    metadata["viewer"]["groups"].append(
        {
            "id": "mesh_platform",
            "label": "Welded mesh platforms",
            "node_names": mesh_ids,
            "offset_mm": [0, 0, -280],
        }
    )
    metadata["viewer"]["groups"].append(
        {
            "id": "bag_retention",
            "label": "Bag webbing / anchors",
            "node_names": bag_anchor_ids,
            "offset_mm": [0, 0, 220],
        }
    )

    tray_group = next((g for g in metadata["viewer"]["groups"] if g["id"] == "trays"), None)
    if tray_group:
        tray_group["node_names"] = [name for name in tray_group.get("node_names", []) if name not in remove_ids]
        tray_group["node_names"].extend(tray_support_ids)
        tray_group["label"] = "Hidden drain trays / light supports"

    bag_group = next((g for g in metadata["viewer"]["groups"] if g["id"] == "bag_liner"), None)
    if bag_group:
        bag_group["node_names"] = bag_ids
        bag_group["label"] = "Custom geotextile bags"

    panel_group = next((g for g in metadata["viewer"]["groups"] if g["id"] == "panel_mounts"), None)
    if panel_group:
        panel_group["label"] = "Bolt-on magnetic panel mounts"

    # Recompute stock quantities for the products inherited from v9 plus 40x4.
    stock_lengths: dict[str, list[float]] = {
        P_TUBE_40: [],
        P_TUBE_20: [],
        P_FLAT_30: [],
        P_FLAT_40X4: [],
    }
    for part in parts:
        product_id = part.get("product_id")
        length = part.get("length_mm")
        if product_id in stock_lengths and isinstance(length, (int, float)):
            stock_lengths[product_id].append(float(length))
    stock_mm = {
        P_TUBE_40: 3000.0,
        P_TUBE_20: 3000.0,
        P_FLAT_30: 3000.0,
        P_FLAT_40X4: 3000.0,
    }
    product_qty = {
        product_id: (_stock_qty(lengths, stock_mm[product_id]) if lengths else 0)
        for product_id, lengths in stock_lengths.items()
    }
    for product in metadata.get("products", []):
        if product["id"] in product_qty:
            product["suggested_qty"] = product_qty[product["id"]]

    metadata["products"] = [
        product for product in metadata.get("products", []) if product.get("id") != "obramat-angle-20"
    ]
    metadata["products"].extend(
        [
            {
                "id": P_FLAT_40X4,
                "retailer": "Obramat",
                "ref": "10636703",
                "name": "Pletina acero S275JR 40x4 mm · 3 m",
                "url": "https://www.obramat.es/productos/pletina-acero-s275jr-40x4mm-3m-10636703.html",
                "stock": "3 m",
                "suggested_qty": product_qty[P_FLAT_40X4],
            },
            {
                "id": P_MESH_50X50X4,
                "retailer": "Aceropanel",
                "ref": "1401-1319",
                "name": "Malla electro-soldada galvanizada 50x50x4 mm · 2.6x1.5 m",
                "url": "https://aceropanel.es/cerramientos-rigidos/1319-malla-electro-soldada-50x50x4mm-med26x15m-gl",
                "stock": "2600x1500 mm panel",
                "suggested_qty": 1,
                "note": "One full panel is enough for any single current planter preset; optimise multiple planters together.",
            },
        ]
    )

    total_volume = bag_w * bag_d * BAG_HEIGHT * cfg.bays_x / 1_000_000
    total_mesh_area = bag_w * bag_d * cfg.bays_x / 1_000_000
    total_webbing_mm = cfg.bays_x * (2 * (bag_w + bag_d) + 4 * max(cfg.top_frame_z - EYELET_DROP - bag_top_z, 6.0))

    metadata["schema_version"] = 10
    metadata["status"] = "parametric fabrication design / v10"
    metadata["parameters"] = dict(metadata["parameters"])
    metadata["parameters"].update(
        {
            "bag_system": "self-supporting custom geotextile bag + reinforced top webbing",
            "bag_height_mm": BAG_HEIGHT,
            "bag_top_gap_to_upper_rail_mm": BAG_TOP_GAP,
            "welded_mesh_pitch_mm": MESH_PITCH,
            "welded_mesh_rod_mm": MESH_ROD,
            "mesh_support_plate": "40x4 mm",
            "mesh_bearers_per_module": 3,
        }
    )
    metadata["derived"].update(
        {
            "bag_useful_x_mm": round(bag_w, 1),
            "bag_useful_y_mm": round(bag_d, 1),
            "bag_useful_height_mm": BAG_HEIGHT,
            "bag_volume_litres_each": round(bag_w * bag_d * BAG_HEIGHT / 1_000_000, 1),
            "bag_volume_litres_total": round(total_volume, 1),
            "bag_support_z_mm": round(mesh_top_z, 1),
            "bag_support_rail_count_each": 3,
            "bag_support_clear_gap_mm": round((bag_d - 3 * s) / 2, 1),
            "mesh_area_m2_total": round(total_mesh_area, 3),
            "bag_webbing_length_m_total": round(total_webbing_mm / 1000, 2),
            "bag_top_retaining_points_each": 4,
            "bag_rim_frame_removed": True,
            "bag_clamp_removed": True,
            "mesh_support_mount": "gravity bearing + M6 bolt retention",
            "panel_target_mount": "single M6 screw + rivnut; no weld",
            "tray_support_profile": "40x4 boundary plates + existing 30x3 centre strip",
        }
    )
    metadata["parts"] = parts
    metadata["assemblies"] = [
        {
            "id": "AS01",
            "name": "Four-leg continuous welded steel body",
            "contains": "only the main 40x40 body and essential fixed structural plates are welded",
        },
        {
            "id": "AS02",
            "name": "Bolt-on mesh grow platforms",
            "contains": f"{cfg.bays_x} rigid 50x50x4 mesh panel(s), each on three removable 20x20 bearers",
        },
        {
            "id": "AS03",
            "name": "Custom tensioned geotextile bags",
            "contains": f"{cfg.bays_x} self-supporting sewn bag(s), each with perimeter webbing and four top retaining straps",
        },
        {
            "id": "AS04",
            "name": "Magnetically removable timber cladding",
            "contains": "panels rest on lower rail; magnet target tabs are now bolted to rivnuts instead of welded",
        },
        {
            "id": "AS05",
            "name": "Hidden tray and common gravity drain",
            "contains": "v9 drainage retained, but tray boundary supports reduced from 80x5 to 40x4",
        },
    ]
    metadata["joints"] = [
        joint
        for joint in metadata.get("joints", [])
        if joint.get("id") not in {"J02", "J03", "J04"}
    ] + [
        {
            "id": "J02",
            "type": "bolt-on / gravity bearing",
            "name": "Mesh platform supports",
            "spec": "Three 20x20 rails per module rest on 40x4 shared plates; two M6 bolts per rail only locate the tube and do not carry vertical soil load.",
        },
        {
            "id": "J03",
            "type": "sewn + lightly tensioned",
            "name": "Custom grow bag",
            "spec": "300 g/m²-class UV-stable geotextile, reinforced upper perimeter with 40 mm polyester webbing, four short straps to M6 eye/rivnut anchors under the upper 40x40 rails.",
        },
        {
            "id": "J04",
            "type": "magnetic + bolt-on target",
            "name": "Timber panels",
            "spec": "Recessed magnets remain in timber battens; each 30x3 steel target tab uses one M6 screw/rivnut instead of a weld.",
        },
    ]
    metadata["service"] = dict(metadata.get("service", {}))
    metadata["service"].update(
        {
            "bag_removal": "release four top straps and lift the empty/lightened bag from the mesh; no steel rim or clamp to undo",
            "mesh_removal": "remove bag, lift mesh panel, then undo the M6 retaining bolts if a 20x20 bearer itself needs replacement",
            "panel_mount_service": "magnetic target tabs can be repositioned/replaced by undoing one M6 screw each",
        }
    )
    metadata["fabrication_notes"] = [
        note
        for note in metadata.get("fabrication_notes", [])
        if not any(word in note.lower() for word in ("clamp", "80x5", "magnetic target"))
    ] + [
        "v10 deletes the complete 20x20 upper bag rim and all 30x3 bag clamp bars / clamp fasteners. Soil weight is carried entirely by the mesh platform.",
        "Use rigid flat welded mesh around 50x50x4 mm, not thin rolled fencing mesh. Cut next to a cross wire, deburr every cut and repair exposed zinc with zinc-rich paint.",
        "Three removable 20x20 bearers are retained per module. The centre bearer limits the mesh free span to roughly 200-230 mm; perimeter-only support was rejected as too flexible for 4 mm wire under wet-soil load.",
        "Custom bag target is approximately 300 g/m² UV-stable non-woven geotextile. Use bonded UV-resistant high-tenacity polyester thread and reinforce the upper perimeter with 40 mm polyester webbing.",
        "Four short upper straps only square/tension the bag mouth. They must never carry soil weight; all vertical load goes directly into mesh, support tubes, shared plates and the main frame.",
        "Panel magnet target tabs change from welded to one M6 screw + rivnut each. This makes alignment adjustable and removes many small welds.",
        "Mesh bearers are also bolt-retained. Their ends bear directly on the horizontal 40x4 plates, so retaining bolts are lightly loaded.",
        "Tray boundary shelves reduce from 80x5 to 40x4; the existing 30x3 centre strip remains under each shallow tray.",
    ]

    return ModelBuild(shape=assembly, bom=_group_bom(parts), metadata=metadata)


PRESETS = V9_PRESETS
