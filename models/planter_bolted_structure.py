from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from build123d import Align, Box, Color, Compound, Pos, Rot

from .planter import ModelBuild, _group_bom, _hollow_tube


MIN_ALIGN = (Align.MIN, Align.MIN, Align.MIN)
PAINTED_STEEL = Color(0.94, 0.94, 0.93)
GALVANISED = Color(0.68, 0.70, 0.72)
POLYMER = Color(0.16, 0.17, 0.18)
RIVET = Color(0.52, 0.54, 0.56)

P_TUBE_40 = "obramat-tube-40"
P_ANGLE_40 = "angle-40x40x3-tbd"
P_INTERNAL_BRACKET = "amazon-trapezoid-internal-bracket"
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
    bracket_diagonal: float = 63.0
    bracket_width: float = 22.0
    bracket_tab: float = 14.0
    bracket_thickness: float = 1.5
    bracket_inside_offset: float = 8.0
    rivet_diameter: float = 6.4
    rivets_per_bracket: int = 4
    bottom_cap_visible: float = 2.0


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


def _top_cover_angle_x(
    total_length: float,
    post_size: float,
    leg: float,
    t: float,
    *,
    rear: bool,
):
    """Upper front/rear angle with integral 40x40 post-cover tabs."""
    vertical_y = leg - t if rear else 0.0
    return Compound(
        children=[
            Pos(post_size, vertical_y, 0)
            * Box(total_length - 2 * post_size, t, leg, align=MIN_ALIGN),
            Pos(0, 0, leg - t) * Box(total_length, leg, t, align=MIN_ALIGN),
        ]
    )


def _internal_bracket_x(
    diagonal: float,
    width: float,
    tab: float,
    t: float,
    *,
    right_end: bool,
    upper: bool,
):
    """Symbolic reinforced internal bracket for a rail running in X.

    A thin diagonal web sits in the X/Z joint plane and terminates in one small
    vertical tab against the post and one horizontal tab on the angle shelf.
    The common furniture-style trapezoidal bracket is used only as the geometry
    concept; exact stamping dimensions remain to be measured before fabrication.
    """
    projected = diagonal / math.sqrt(2.0)
    if not right_end and not upper:
        web = Pos(0, 0, projected) * Rot(0, 45, 0) * Box(diagonal, width, t, align=MIN_ALIGN)
        post_tab = Box(t, width, tab, align=MIN_ALIGN)
        post_tab = Pos(0, 0, projected - tab) * post_tab
        rail_tab = Pos(projected - tab, 0, 0) * Box(tab, width, t, align=MIN_ALIGN)
    elif right_end and not upper:
        web = Pos(projected, 0, projected) * Rot(0, 135, 0) * Box(diagonal, width, t, align=MIN_ALIGN)
        post_tab = Pos(projected - t, 0, projected - tab) * Box(t, width, tab, align=MIN_ALIGN)
        rail_tab = Box(tab, width, t, align=MIN_ALIGN)
    elif not right_end and upper:
        web = Rot(0, -45, 0) * Box(diagonal, width, t, align=MIN_ALIGN)
        post_tab = Box(t, width, tab, align=MIN_ALIGN)
        rail_tab = Pos(projected - tab, 0, projected - t) * Box(tab, width, t, align=MIN_ALIGN)
    else:
        web = Pos(projected, 0, 0) * Rot(0, -135, 0) * Box(diagonal, width, t, align=MIN_ALIGN)
        post_tab = Pos(projected - t, 0, 0) * Box(t, width, tab, align=MIN_ALIGN)
        rail_tab = Pos(0, 0, projected - t) * Box(tab, width, t, align=MIN_ALIGN)
    return Compound(children=[web, post_tab, rail_tab])


def _internal_bracket_y(
    diagonal: float,
    width: float,
    tab: float,
    t: float,
    *,
    rear_end: bool,
    upper: bool,
):
    """Same reinforced internal bracket, rotated for a rail running in Y."""
    projected = diagonal / math.sqrt(2.0)
    if not rear_end and not upper:
        web = Pos(0, 0, projected) * Rot(-45, 0, 0) * Box(width, diagonal, t, align=MIN_ALIGN)
        post_tab = Pos(0, 0, projected - tab) * Box(width, t, tab, align=MIN_ALIGN)
        rail_tab = Pos(0, projected - tab, 0) * Box(width, tab, t, align=MIN_ALIGN)
    elif rear_end and not upper:
        web = Pos(0, projected, projected) * Rot(-135, 0, 0) * Box(width, diagonal, t, align=MIN_ALIGN)
        post_tab = Pos(0, projected - t, projected - tab) * Box(width, t, tab, align=MIN_ALIGN)
        rail_tab = Box(width, tab, t, align=MIN_ALIGN)
    elif not rear_end and upper:
        web = Rot(45, 0, 0) * Box(width, diagonal, t, align=MIN_ALIGN)
        post_tab = Box(width, t, tab, align=MIN_ALIGN)
        rail_tab = Pos(0, projected - tab, projected - t) * Box(width, tab, t, align=MIN_ALIGN)
    else:
        web = Pos(0, projected, 0) * Rot(135, 0, 0) * Box(width, diagonal, t, align=MIN_ALIGN)
        post_tab = Pos(0, projected - t, 0) * Box(width, t, tab, align=MIN_ALIGN)
        rail_tab = Pos(0, 0, projected - t) * Box(width, tab, t, align=MIN_ALIGN)
    return Compound(children=[web, post_tab, rail_tab])


def build_planter(
    config: BoltedStructureConfig | None = None,
    model_id: str = "planter-600x600x600-no-weld-structure",
) -> ModelBuild:
    cfg = config or CFG_600
    if cfg.length != 600 or cfg.depth != 600:
        raise ValueError("Initial no-weld study is intentionally limited to 600x600 mm")

    p = cfg.post_size
    clear_x = cfg.length - 2 * p
    clear_y = cfg.depth - 2 * p
    upper_z = cfg.body_height - cfg.angle_leg
    lower_z = cfg.leg_clearance
    post_length = cfg.body_height - cfg.angle_thickness
    bracket_projection = cfg.bracket_diagonal / math.sqrt(2.0)

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

    # 597 mm posts + 3 mm integral steel tabs keep the final envelope at 600 mm.
    for x_name, x in (("left", 0.0), ("right", cfg.length - p)):
        for y_name, y in (("front", 0.0), ("rear", cfg.depth - p)):
            post_id = next_id("P")
            add_shape(
                post_id,
                f"{y_name.title()} {x_name} continuous post",
                _hollow_tube(post_length, p, cfg.post_wall, "z", post_id),
                (x, y, 0.0),
                "main_post",
                "S235/S275 steel tube",
                f"{p:g}x{p:g}x{cfg.post_wall:g} mm square tube",
                f"{post_length:g} mm",
                PAINTED_STEEL,
                viewer_group="posts",
                product_id=P_TUBE_40,
                length_mm=post_length,
                note="top mouth is closed by the integral 40x40x3 tab of the upper front/rear angle",
            )
            cap_id = next_id("CAP")
            add_shape(
                cap_id,
                f"{y_name.title()} {x_name} bottom post cap",
                Box(p, p, cfg.bottom_cap_visible, align=MIN_ALIGN),
                (x, y, 0.0),
                "bottom_post_cap",
                "UV-stable polymer",
                "40x40 flush insert cap",
                "1 pc",
                POLYMER,
                viewer_group="caps",
                product_id=P_CAP_40,
                note="bottom only; upper closure is integral steel",
            )

    # Lower frame: four conventional L40x40x3 rails between posts.
    for face, y, rear in (("front", 0.0, False), ("rear", cfg.depth - cfg.angle_leg, True)):
        rail_id = next_id("A")
        add_shape(
            rail_id,
            f"Lower {face} angle rail",
            _angle_x(clear_x, cfg.angle_leg, cfg.angle_thickness, rear=rear, shelf_top=False),
            (p, y, lower_z),
            "angle_rail",
            "S235/S275 angle steel",
            f"L {cfg.angle_leg:g}x{cfg.angle_leg:g}x{cfg.angle_thickness:g} mm",
            f"{clear_x:g} mm",
            PAINTED_STEEL,
            viewer_group="angle_rails",
            product_id=P_ANGLE_40,
            length_mm=clear_x,
            note="vertical outer leg gives the same 40 mm visual band as the welded frame",
        )

    for side, x, right in (("left", 0.0, False), ("right", cfg.length - cfg.angle_leg, True)):
        rail_id = next_id("A")
        add_shape(
            rail_id,
            f"Lower {side} angle rail",
            _angle_y(clear_y, cfg.angle_leg, cfg.angle_thickness, right=right, shelf_top=False),
            (x, p, lower_z),
            "angle_rail",
            "S235/S275 angle steel",
            f"L {cfg.angle_leg:g}x{cfg.angle_leg:g}x{cfg.angle_thickness:g} mm",
            f"{clear_y:g} mm",
            PAINTED_STEEL,
            viewer_group="angle_rails",
            product_id=P_ANGLE_40,
            length_mm=clear_y,
        )

    # Upper front/rear rails are 600 mm blanks whose horizontal wings also cap
    # the post mouths. Only the vertical wing is removed over each 40 mm end.
    for face, y, rear in (("front", 0.0, False), ("rear", cfg.depth - cfg.angle_leg, True)):
        rail_id = next_id("A")
        add_shape(
            rail_id,
            f"Upper {face} angle rail with integral post-cover tabs",
            _top_cover_angle_x(cfg.length, p, cfg.angle_leg, cfg.angle_thickness, rear=rear),
            (0.0, y, upper_z),
            "top_cover_angle_rail",
            "S235/S275 angle steel",
            f"L {cfg.angle_leg:g}x{cfg.angle_leg:g}x{cfg.angle_thickness:g} mm",
            f"{cfg.length:g} mm blank · remove vertical leg over 40 mm at each end",
            PAINTED_STEEL,
            viewer_group="angle_rails",
            product_id=P_ANGLE_40,
            length_mm=cfg.length,
            note="horizontal leg remains continuous and forms two 40x40x3 steel post caps; seal hairline joints with paintable exterior MS polymer",
        )

    for side, x, right in (("left", 0.0, False), ("right", cfg.length - cfg.angle_leg, True)):
        rail_id = next_id("A")
        add_shape(
            rail_id,
            f"Upper {side} angle rail",
            _angle_y(clear_y, cfg.angle_leg, cfg.angle_thickness, right=right, shelf_top=True),
            (x, p, upper_z),
            "angle_rail",
            "S235/S275 angle steel",
            f"L {cfg.angle_leg:g}x{cfg.angle_leg:g}x{cfg.angle_thickness:g} mm",
            f"{clear_y:g} mm",
            PAINTED_STEEL,
            viewer_group="angle_rails",
            product_id=P_ANGLE_40,
            length_mm=clear_y,
        )

    # One internal reinforced bracket per rail/post joint: 8 rails x 2 ends = 16.
    # Nothing wraps around or projects beyond the four exterior corners.
    bracket_nodes: list[tuple[str, str, tuple[float, float, float], str, bool, bool]] = []
    # tuple: label, axis, position, end_is_far, upper, rear_or_right_face
    for level_name, upper in (("lower", False), ("upper", True)):
        if upper:
            base_z = (upper_z + cfg.angle_leg - cfg.angle_thickness) - bracket_projection
        else:
            base_z = lower_z + cfg.angle_thickness

        front_y = cfg.bracket_inside_offset
        rear_y = cfg.depth - cfg.bracket_inside_offset - cfg.bracket_width
        for face, y, is_rear in (("front", front_y, False), ("rear", rear_y, True)):
            bracket_nodes.extend(
                [
                    (f"{level_name} {face} left rail/post", "x", (p, y, base_z), False, upper, is_rear),
                    (
                        f"{level_name} {face} right rail/post",
                        "x",
                        (cfg.length - p - bracket_projection, y, base_z),
                        True,
                        upper,
                        is_rear,
                    ),
                ]
            )

        left_x = cfg.bracket_inside_offset
        right_x = cfg.length - cfg.bracket_inside_offset - cfg.bracket_width
        for side, x, is_right in (("left", left_x, False), ("right", right_x, True)):
            bracket_nodes.extend(
                [
                    (f"{level_name} {side} front rail/post", "y", (x, p, base_z), False, upper, is_right),
                    (
                        f"{level_name} {side} rear rail/post",
                        "y",
                        (x, cfg.depth - p - bracket_projection, base_z),
                        True,
                        upper,
                        is_right,
                    ),
                ]
            )

    for bracket_name, axis, position, far_end, upper, _face_flag in bracket_nodes:
        bracket_id = next_id("K")
        bracket_shape = (
            _internal_bracket_x(
                cfg.bracket_diagonal,
                cfg.bracket_width,
                cfg.bracket_tab,
                cfg.bracket_thickness,
                right_end=far_end,
                upper=upper,
            )
            if axis == "x"
            else _internal_bracket_y(
                cfg.bracket_diagonal,
                cfg.bracket_width,
                cfg.bracket_tab,
                cfg.bracket_thickness,
                rear_end=far_end,
                upper=upper,
            )
        )
        add_shape(
            bracket_id,
            f"Internal reinforced bracket · {bracket_name}",
            bracket_shape,
            position,
            "internal_corner_bracket",
            "Corrosion-resistant steel",
            f"trapezoidal/gusset bracket · conceptual {cfg.bracket_diagonal:g}x{cfg.bracket_width:g}x{cfg.bracket_tab:g} mm envelope",
            "1 pc",
            GALVANISED,
            viewer_group="corner_connectors",
            product_id=P_INTERNAL_BRACKET,
            note="one bracket belongs to one L/post joint; completely inside the planter envelope",
        )

        # Four structural rivets per bracket: two into the post-side tab and two
        # into the angle-side tab. Locations are symbolic until the chosen
        # commercial stamping is physically measured.
        for fixing_no in range(1, cfg.rivets_per_bracket + 1):
            rivet_id = next_id("RV")
            add_shape(
                rivet_id,
                f"{bracket_name} structural rivet {fixing_no}",
                Box(6.0, 6.0, 3.0, align=MIN_ALIGN),
                (
                    position[0] + 5.0 + (fixing_no % 2) * 9.0,
                    position[1] + 5.0 + ((fixing_no // 2) % 2) * 9.0,
                    position[2] + (3.0 if fixing_no <= 2 else bracket_projection - 6.0),
                ),
                "structural_rivet",
                "Steel structural blind rivet",
                f"Ø{cfg.rivet_diameter:g} mm structural blind rivet",
                "1 pc",
                RIVET,
                viewer_group="structural_rivets",
                product_id=P_RIVET_64,
                note="symbolic head only; final positions use the actual bracket holes and verified edge distances",
            )

    assembly = Compound(label=model_id, children=shapes)

    metadata: dict[str, Any] = {
        "schema_version": 3,
        "status": "parallel concept study · no-weld / riveted structure v3",
        "design_scope": "structure-only",
        "variant_family": "no-weld",
        "parameters": {
            "length": cfg.length,
            "depth": cfg.depth,
            "body_height": cfg.body_height,
            "frame_size": cfg.post_size,
            "frame_wall": cfg.post_wall,
            "post_cut_length": post_length,
            "angle_leg": cfg.angle_leg,
            "angle_thickness": cfg.angle_thickness,
            "leg_clearance": cfg.leg_clearance,
            "rivet_diameter": cfg.rivet_diameter,
            "bracket_diagonal_mm": cfg.bracket_diagonal,
            "bracket_width_mm": cfg.bracket_width,
            "bracket_tab_mm": cfg.bracket_tab,
        },
        "derived": {
            "post_count": 4,
            "post_length_mm": post_length,
            "angle_rail_count": 8,
            "standard_angle_rail_count": 6,
            "integral_top_cover_rail_count": 2,
            "integral_steel_top_cap_count": 4,
            "internal_bracket_count": 16,
            "brackets_per_rail": 2,
            "structural_rivet_count": 16 * cfg.rivets_per_bracket,
            "caps_count": 4,
            "plastic_top_cap_count": 0,
            "weld_count": 0,
            "clear_span_mm": clear_x,
            "corner_hardware_outside_envelope_mm": 0,
        },
        "parts": parts,
        "viewer": {
            "groups": [
                {"id": "posts", "label": "40x40 posts", "node_names": groups["posts"], "offset_mm": [0, 0, 0]},
                {"id": "angle_rails", "label": "L40x40x3 rails + steel top tabs", "node_names": groups["angle_rails"], "offset_mm": [0, 0, 180]},
                {"id": "corner_connectors", "label": "Internal reinforced L/post brackets", "node_names": groups["corner_connectors"], "offset_mm": [80, 80, 0]},
                {"id": "structural_rivets", "label": "Ø6.4 structural rivets", "node_names": groups["structural_rivets"], "offset_mm": [150, 150, 0]},
                {"id": "caps", "label": "Bottom 40x40 caps", "node_names": groups["caps"], "offset_mm": [0, 0, -120]},
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
                "note": "Two upper front/rear blanks are 600 mm because their horizontal wings also close the post tops.",
            },
            {
                "id": P_INTERNAL_BRACKET,
                "retailer": "Amazon.es",
                "ref": "B0GVZ8KRXG",
                "name": "Escuadra metálica trapezoidal reforzada para esquina",
                "url": "https://www.amazon.es/Escuadras-Metalicas-Trapezoidal-Tornillos-Metalicos/dp/B0GVZ8KRXG",
                "stock": "pack / exact count to verify",
                "suggested_qty": 16,
                "note": "Geometry candidate only. Amazon did not expose a reliable technical sheet to the CAD build; the model uses the common ~63x22x14 mm trapezoidal-bracket envelope pending measurement of one purchased part.",
            },
            {
                "id": P_RIVET_64,
                "retailer": "TBD",
                "ref": "TBD",
                "name": "Structural blind rivet steel/steel Ø6.4 mm",
                "stock": "box",
                "suggested_qty": 64,
                "note": "Use a structural blind-rivet family, not a standard aluminium POP rivet. Verify bracket hole diameter before purchase.",
            },
            {
                "id": P_CAP_40,
                "retailer": "TBD",
                "ref": "TBD",
                "name": "Flush plastic insert cap 40x40 mm · bottom only",
                "stock": "1 pc",
                "suggested_qty": 4,
                "note": "Upper plastic caps eliminated; the two long upper angles provide four integral steel closures.",
            },
        ],
        "assemblies": [
            {
                "id": "AS01",
                "name": "No-weld riveted outer structure v3",
                "contains": "4 shortened continuous posts + 8 angle rails (2 with integral top tabs) + 16 internal reinforced rail/post brackets + structural blind rivets",
            }
        ],
        "joints": [
            {
                "id": "J01",
                "type": "internal reinforced blind-riveted L/post joint",
                "name": "Individual angle-rail / post connection",
                "spec": "Each end of each L40x40 rail has its own reinforced internal bracket. The bracket sits entirely inside the planter, with one attachment tab on the post and one on the angle shelf; target four Ø6.4 structural blind rivets per joint (two per attached member). There is no shared or exterior corner wrap.",
            },
            {
                "id": "J02",
                "type": "integral steel post closure",
                "name": "Upper angle / post-mouth cover",
                "spec": "Front and rear upper L40x40x3 blanks remain 600 mm long. Remove only the vertical leg over the first/last 40 mm; the untouched horizontal wing forms four 40x40x3 top tabs over posts cut to 597 mm. Seal the hairline perimeter with paintable exterior MS polymer before final paint.",
            },
        ],
        "fabrication_notes": [
            "Parallel concept only: outer structure and permanent joint hardware only; bag cassette, drainage and timber panels remain intentionally absent.",
            "Correction from v2: all connector hardware is inside the planter. Nothing wraps around the four visible exterior corners.",
            "There are 16 independent rail/post joints: every one of the 8 L rails gets one reinforced internal bracket at each end. The two rails meeting at a geometric corner do not share a bracket.",
            "The Amazon B0GVZ8KRXG trapezoidal bracket is a geometry candidate because its bent tabs + diagonal web suit this internal joint much better than the previous exterior Alberts wrap. Exact dimensions, steel thickness and hole pattern must be measured before the drilling jig/rivet grip range are frozen.",
            "The current CAD envelope (63x22x14 mm) represents the common size of this bracket family and is explicitly not asserted as the exact Amazon SKU dimension.",
            "Use four structural blind rivets conceptually per bracket: two into the post-side tab and two into the angle-side tab. The rendered rivet heads are intentionally symbolic rather than a final drilling pattern.",
            "The four posts are 597 mm so the 3 mm integral upper-angle tabs finish exactly at Z=600. No plastic top caps are used.",
            "Seal the small top-tab/post and rail/tab seams with exterior paintable MS polymer, then paint the assembled frame.",
        ],
    }

    return ModelBuild(shape=assembly, bom=_group_bom(parts), metadata=metadata)


PRESETS: dict[str, tuple[str, BoltedStructureConfig]] = {
    "planter-600x600x600-no-weld-structure": (
        "600 × 600 × 600 mm · no-weld structure",
        CFG_600,
    )
}
