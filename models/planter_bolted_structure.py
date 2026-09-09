from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from build123d import Align, Box, Color, Compound, Pos

from .planter import ModelBuild, _group_bom, _hollow_tube


MIN_ALIGN = (Align.MIN, Align.MIN, Align.MIN)
PAINTED_STEEL = Color(0.94, 0.94, 0.93)
GALVANISED = Color(0.68, 0.70, 0.72)
POLYMER = Color(0.16, 0.17, 0.18)
RIVET = Color(0.52, 0.54, 0.56)

P_TUBE_40 = "obramat-tube-40"
P_ANGLE_40 = "angle-40x40x3-tbd"
P_CORNER_3D = "alberts-corner-50x50x70"
P_RIVET_64 = "structural-rivet-6-4"
P_CAP_40 = "plastic-cap-40"


@dataclass(frozen=True)
class BoltedStructureConfig:
    length: float = 600.0
    depth: float = 600.0
    body_height: float = 600.0
    post_size: float = 40.0
    post_wall: float = 1.5
    leg_clearance: float = 40.0
    angle_leg: float = 40.0
    angle_thickness: float = 3.0
    bracket_footprint: float = 50.0
    bracket_height: float = 70.0
    bracket_thickness: float = 1.5
    rivet_diameter: float = 6.4
    rivets_per_corner: int = 6
    cap_visible: float = 2.0


CFG_600 = BoltedStructureConfig()


def _angle_x(length: float, leg: float, t: float, *, rear: bool, shelf_top: bool):
    vertical_y = leg - t if rear else 0.0
    shelf_z = leg - t if shelf_top else 0.0
    return Compound(
        children=[
            Pos(0, vertical_y, 0) * Box(length, t, leg, align=MIN_ALIGN),
            Pos(0, 0, shelf_z) * Box(length, leg, t, align=MIN_ALIGN),
        ]
    )


def _angle_y(length: float, leg: float, t: float, *, right: bool, shelf_top: bool):
    vertical_x = leg - t if right else 0.0
    shelf_z = leg - t if shelf_top else 0.0
    return Compound(
        children=[
            Pos(vertical_x, 0, 0) * Box(t, length, leg, align=MIN_ALIGN),
            Pos(0, 0, shelf_z) * Box(leg, length, t, align=MIN_ALIGN),
        ]
    )


def _corner_connector(size: float, height: float, t: float, *, right: bool, rear: bool, upper: bool):
    """Symbolic three-plane corner connector.

    The real candidate is an Alberts-type 50x50x70 galvanised corner fitting.
    This solid intentionally shows the three-plane load path rather than trying
    to reproduce every bend and hole of one supplier stamping.
    """
    x_plate = size - t if right else 0.0
    y_plate = size - t if rear else 0.0
    horizontal_z = height - t if upper else 0.0
    return Compound(
        children=[
            Pos(x_plate, 0, 0) * Box(t, size, height, align=MIN_ALIGN),
            Pos(0, y_plate, 0) * Box(size, t, height, align=MIN_ALIGN),
            Pos(0, 0, horizontal_z) * Box(size, size, t, align=MIN_ALIGN),
        ]
    )


def build_planter(
    config: BoltedStructureConfig | None = None,
    model_id: str = "planter-600x600x600-no-weld-structure",
) -> ModelBuild:
    cfg = config or CFG_600
    if cfg.length != 600 or cfg.depth != 600:
        raise ValueError("Initial no-weld study is intentionally limited to 600x600 mm")

    p = cfg.post_size
    rail_x = cfg.length - 2 * p
    rail_y = cfg.depth - 2 * p
    upper_z = cfg.body_height - cfg.angle_leg
    lower_z = cfg.leg_clearance

    shapes: list[Any] = []
    parts: list[dict[str, Any]] = []
    groups: dict[str, list[str]] = {
        "posts": [],
        "angle_rails": [],
        "corner_connectors": [],
        "structural_rivets": [],
        "caps": [],
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
        *,
        viewer_group: str,
        product_id: str | None = None,
        length_mm: float | None = None,
        **extra: Any,
    ) -> None:
        placed = Pos(*position) * shape
        placed.label = part_id
        placed.color = color
        shapes.append(placed)
        groups[viewer_group].append(part_id)
        item: dict[str, Any] = {
            "id": part_id,
            "name": name,
            "category": category,
            "material": material,
            "profile": profile,
            "cut": cut,
            "viewer_group": viewer_group,
        }
        if product_id:
            item["product_id"] = product_id
        if length_mm is not None:
            item["length_mm"] = length_mm
        item.update(extra)
        parts.append(item)

    # Four continuous 40x40x1.5 posts, exactly as in the welded design.
    for x_name, x in (("left", 0.0), ("right", cfg.length - p)):
        for y_name, y in (("front", 0.0), ("rear", cfg.depth - p)):
            post_id = next_id("P")
            add_shape(
                post_id,
                f"{y_name.title()} {x_name} continuous post",
                _hollow_tube(cfg.body_height, p, cfg.post_wall, "z", post_id),
                (x, y, 0.0),
                "main_post",
                "S235/S275 steel tube",
                f"{p:g}x{p:g}x{cfg.post_wall:g} mm square tube",
                f"{cfg.body_height:g} mm",
                PAINTED_STEEL,
                viewer_group="posts",
                product_id=P_TUBE_40,
                length_mm=cfg.body_height,
            )

            for end_name, z in (("bottom", 0.0), ("top", cfg.body_height - cfg.cap_visible)):
                cap_id = next_id("CAP")
                add_shape(
                    cap_id,
                    f"{y_name.title()} {x_name} {end_name} plastic post cap",
                    Box(p, p, cfg.cap_visible, align=MIN_ALIGN),
                    (x, y, z),
                    "post_cap",
                    "Paintable / colour-matched polymer",
                    "40x40 flush insert cap",
                    "1 pc",
                    POLYMER,
                    viewer_group="caps",
                    product_id=P_CAP_40,
                    note="upper cap replaces the folded/welded tube closure used by the welded design",
                )

    # Eight angle rails. Their external 40 mm vertical face preserves the same
    # visual band as the welded 40x40 tube frame.
    for level_name, z, shelf_top in (
        ("lower", lower_z, False),
        ("upper", upper_z, True),
    ):
        for face, y, rear in (
            ("front", 0.0, False),
            ("rear", cfg.depth - cfg.angle_leg, True),
        ):
            rail_id = next_id("A")
            add_shape(
                rail_id,
                f"{level_name.title()} {face} angle rail",
                _angle_x(rail_x, cfg.angle_leg, cfg.angle_thickness, rear=rear, shelf_top=shelf_top),
                (p, y, z),
                "angle_rail",
                "S235/S275 angle steel",
                f"L {cfg.angle_leg:g}x{cfg.angle_leg:g}x{cfg.angle_thickness:g} mm",
                f"{rail_x:g} mm",
                PAINTED_STEEL,
                viewer_group="angle_rails",
                product_id=P_ANGLE_40,
                length_mm=rail_x,
                note="vertical outer leg gives a 40 mm visual band; horizontal leg faces inward",
            )

        for side, x, right in (
            ("left", 0.0, False),
            ("right", cfg.length - cfg.angle_leg, True),
        ):
            rail_id = next_id("A")
            add_shape(
                rail_id,
                f"{level_name.title()} {side} angle rail",
                _angle_y(rail_y, cfg.angle_leg, cfg.angle_thickness, right=right, shelf_top=shelf_top),
                (x, p, z),
                "angle_rail",
                "S235/S275 angle steel",
                f"L {cfg.angle_leg:g}x{cfg.angle_leg:g}x{cfg.angle_thickness:g} mm",
                f"{rail_y:g} mm",
                PAINTED_STEEL,
                viewer_group="angle_rails",
                product_id=P_ANGLE_40,
                length_mm=rail_y,
                note="vertical outer leg gives a 40 mm visual band; horizontal leg faces inward",
            )

    # One 3D corner connector at every upper/lower corner. The connector is
    # deliberately shown slightly inboard of the post so its three planes remain
    # readable in the viewer; fabrication dimensions/holes must be confirmed on
    # the purchased stamping before drilling a jig.
    corner_positions = [
        ("front left", p - 10.0, p - 10.0, False, False),
        ("front right", cfg.length - p - 40.0, p - 10.0, True, False),
        ("rear left", p - 10.0, cfg.depth - p - 40.0, False, True),
        ("rear right", cfg.length - p - 40.0, cfg.depth - p - 40.0, True, True),
    ]

    for level_name, bracket_z, upper in (
        ("lower", lower_z, False),
        ("upper", cfg.body_height - cfg.bracket_height, True),
    ):
        for corner_name, x, y, right, rear in corner_positions:
            bracket_id = next_id("K")
            add_shape(
                bracket_id,
                f"{level_name.title()} {corner_name} 3D corner connector",
                _corner_connector(
                    cfg.bracket_footprint,
                    cfg.bracket_height,
                    cfg.bracket_thickness,
                    right=right,
                    rear=rear,
                    upper=upper,
                ),
                (x, y, bracket_z),
                "corner_connector",
                "Galvanised pressed steel",
                f"3-plane corner fitting · nominal {cfg.bracket_footprint:g}x{cfg.bracket_footprint:g}x{cfg.bracket_height:g} mm",
                "1 pc",
                GALVANISED,
                viewer_group="corner_connectors",
                product_id=P_CORNER_3D,
                note="symbolic Alberts-type corner fitting; verify exact stamping/hole pattern before fabrication",
            )

            # Six structural-rivet symbols per corner: two per load path/member.
            # They are visual/BOM placeholders, not a frozen drilling pattern.
            local_points = [
                (8.0, 1.6, 18.0),
                (8.0, 1.6, 48.0),
                (1.6, 8.0, 18.0),
                (1.6, 8.0, 48.0),
                (15.0, 15.0, cfg.bracket_height - 3.0 if upper else 0.0),
                (32.0, 32.0, cfg.bracket_height - 3.0 if upper else 0.0),
            ]
            for rivet_no, (rx, ry, rz) in enumerate(local_points, start=1):
                rivet_id = next_id("RV")
                # Small square-head symbol keeps the GLB lightweight and clearly visible.
                if rivet_no <= 2:
                    rivet_shape = Box(8.0, 3.0, 8.0, align=MIN_ALIGN)
                elif rivet_no <= 4:
                    rivet_shape = Box(3.0, 8.0, 8.0, align=MIN_ALIGN)
                else:
                    rivet_shape = Box(8.0, 8.0, 3.0, align=MIN_ALIGN)
                add_shape(
                    rivet_id,
                    f"{level_name.title()} {corner_name} structural rivet {rivet_no}",
                    rivet_shape,
                    (x + rx, y + ry, bracket_z + rz),
                    "structural_rivet",
                    "Steel structural blind rivet",
                    f"Ø{cfg.rivet_diameter:g} mm structural blind rivet",
                    "1 pc",
                    RIVET,
                    viewer_group="structural_rivets",
                    product_id=P_RIVET_64,
                    note="symbolic location only; final edge distances follow the purchased corner fitting hole pattern",
                )

    assembly = Compound(label=model_id, children=shapes)

    metadata: dict[str, Any] = {
        "schema_version": 1,
        "status": "parallel concept study · no-weld / riveted structure only",
        "design_scope": "structure-only",
        "variant_family": "no-weld",
        "parameters": {
            "length": cfg.length,
            "depth": cfg.depth,
            "body_height": cfg.body_height,
            "frame_size": cfg.post_size,
            "frame_wall": cfg.post_wall,
            "angle_leg": cfg.angle_leg,
            "angle_thickness": cfg.angle_thickness,
            "leg_clearance": cfg.leg_clearance,
            "rivet_diameter": cfg.rivet_diameter,
        },
        "derived": {
            "post_count": 4,
            "angle_rail_count": 8,
            "angle_rail_length_mm": rail_x,
            "corner_connector_count": 8,
            "structural_rivet_count": 8 * cfg.rivets_per_corner,
            "caps_count": 8,
            "weld_count": 0,
            "clear_span_mm": rail_x,
        },
        "parts": parts,
        "viewer": {
            "groups": [
                {"id": "posts", "label": "40x40 posts", "node_names": groups["posts"], "offset_mm": [0, 0, 0]},
                {"id": "angle_rails", "label": "40x40x3 angle rails", "node_names": groups["angle_rails"], "offset_mm": [0, 0, 180]},
                {"id": "corner_connectors", "label": "3D corner connectors", "node_names": groups["corner_connectors"], "offset_mm": [180, 180, 0]},
                {"id": "structural_rivets", "label": "Ø6.4 structural rivets", "node_names": groups["structural_rivets"], "offset_mm": [280, 280, 0]},
                {"id": "caps", "label": "40x40 post caps", "node_names": groups["caps"], "offset_mm": [0, 0, 280]},
            ]
        },
        "products": [
            {
                "id": P_TUBE_40,
                "retailer": "Obramat",
                "ref": "10330425",
                "name": "Tubo cuadrado acero 40x40x1.5 mm · 3 m",
                "url": "https://www.obramat.es/productos/tubo-cuadrado-acero-decapado-40x40x1-5mm-3m-10330425.html",
                "stock": "3 m",
                "suggested_qty": 1,
            },
            {
                "id": P_ANGLE_40,
                "retailer": "TBD",
                "ref": "TBD",
                "name": "Angular estructural acero 40x40x3 mm",
                "stock": "target 3-6 m bar",
                "suggested_qty": 2,
                "note": "Exact Spanish supplier/product intentionally left open for the concept study.",
            },
            {
                "id": P_CORNER_3D,
                "retailer": "BricoCentro / Alberts",
                "ref": "8217148",
                "name": "Escuadra/cantonera esquina galvanizada S 50x50x70 mm Alberts",
                "url": "https://www.bricocentrogamonal.es/producto/escuadra-esquina-galvanizada-s-50x50x70mm-alberts-8217148",
                "stock": "1 pc",
                "suggested_qty": 8,
                "note": "CAD geometry is symbolic until one physical fitting is measured.",
            },
            {
                "id": P_RIVET_64,
                "retailer": "TBD",
                "ref": "TBD",
                "name": "Structural blind rivet steel/steel Ø6.4 mm",
                "stock": "box",
                "suggested_qty": 48,
                "note": "Use a structural blind-rivet family, not a standard aluminium POP rivet.",
            },
            {
                "id": P_CAP_40,
                "retailer": "TBD",
                "ref": "TBD",
                "name": "Flush plastic insert cap 40x40 mm",
                "stock": "1 pc",
                "suggested_qty": 8,
                "note": "Prefer white/paintable UV-stable polymer for the four visible top caps.",
            },
        ],
        "assemblies": [
            {
                "id": "AS01",
                "name": "No-weld riveted outer structure",
                "contains": "4 continuous tube posts + 8 angle rails + 8 three-plane corner connectors + structural blind rivets",
            }
        ],
        "joints": [
            {
                "id": "J01",
                "type": "structural blind-riveted three-way corner",
                "name": "Post / two-angle corner node",
                "spec": "One 3D galvanised corner connector per upper/lower corner. Target six Ø6.4 steel structural blind rivets per connector, nominally two per load path/member; final drilling follows the measured commercial fitting.",
            }
        ],
        "fabrication_notes": [
            "Parallel concept only: this model intentionally contains the outer structure and permanent corner hardware, not the bag cassette, drainage or timber panels from the welded v12 design.",
            "There are zero welded joints. The four 40x40x1.5 posts remain continuous; all eight horizontal members become L40x40x3 angle rails.",
            "The vertical leg of every angle rail faces outward so the external silhouette remains close to the welded 40x40-tube version.",
            "Use a three-plane corner connector rather than a simple flat L bracket. One fitting links the post and both perpendicular rails at each upper/lower corner and greatly improves resistance to racking.",
            "The Alberts 50x50x70 fitting is represented symbolically. Buy/measure one before freezing hole positions, edge distances or a drilling jig.",
            "Rivets are specified conceptually as Ø6.4 mm steel structural blind rivets. Final grip range and exact family depend on the measured combined sheet stack of tube/angle/connector.",
            "Upper tube mouths use separate flush 40x40 polymer caps instead of the folded top-wall closure used in the welded design.",
        ],
    }

    return ModelBuild(shape=assembly, bom=_group_bom(parts), metadata=metadata)


PRESETS: dict[str, tuple[str, BoltedStructureConfig]] = {
    "planter-600x600x600-no-weld-structure": (
        "600 × 600 × 600 mm · no-weld structure",
        CFG_600,
    )
}
