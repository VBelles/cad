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
P_CORNER_WRAP = "alberts-corner-50x50x70"
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
    bracket_leg: float = 50.0
    bracket_height: float = 70.0
    bracket_thickness: float = 1.5
    rivet_diameter: float = 6.4
    rivets_per_corner: int = 6
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
    """Upper front/rear angle with integral post-cover tabs.

    The horizontal 40 mm leg remains continuous across the full planter width.
    At both 40 mm ends the vertical leg is cut away, leaving two 40x40x3 tabs
    that sit directly on the shortened post mouths. The middle 520 mm remains a
    normal L40x40x3 structural rail.
    """
    vertical_y = leg - t if rear else 0.0
    return Compound(
        children=[
            Pos(post_size, vertical_y, 0)
            * Box(total_length - 2 * post_size, t, leg, align=MIN_ALIGN),
            Pos(0, 0, leg - t) * Box(total_length, leg, t, align=MIN_ALIGN),
        ]
    )


def _corner_wrap(leg: float, height: float, t: float, *, right: bool, rear: bool):
    """Actual two-plane Alberts 337254 corner-wrap geometry.

    The commercial part is a 90 degree folded strip: two 50 mm legs, 70 mm
    height/width along the bend and 1.5 mm material. It wraps the *outside* of
    the frame corner, bridging both perpendicular faces. It is not a three-plane
    shelf bracket. Local origin is the theoretical outside corner of the frame.
    """
    x_start = -leg if right else 0.0
    y_start = -leg if rear else 0.0
    front_rear_y = 0.0 if rear else -t
    left_right_x = 0.0 if right else -t
    return Compound(
        children=[
            Pos(x_start, front_rear_y, 0) * Box(leg, t, height, align=MIN_ALIGN),
            Pos(left_right_x, y_start, 0) * Box(t, leg, height, align=MIN_ALIGN),
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
    clear_x = cfg.length - 2 * p
    clear_y = cfg.depth - 2 * p
    upper_z = cfg.body_height - cfg.angle_leg
    lower_z = cfg.leg_clearance
    post_length = cfg.body_height - cfg.angle_thickness

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

    # The steel tabs are 3 mm thick and define the final Z=600 top plane, so the
    # four continuous posts finish at Z=597 instead of needing separate top caps.
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

            # Bottom remains a simple insert cap; the four visible upper plastic
            # caps from the first no-weld study have been eliminated.
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
                note="bottom only; upper closure is now integral steel",
            )

    # Lower frame: four conventional L40x40x3 rails between the posts.
    for face, y, rear in (
        ("front", 0.0, False),
        ("rear", cfg.depth - cfg.angle_leg, True),
    ):
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

    for side, x, right in (
        ("left", 0.0, False),
        ("right", cfg.length - cfg.angle_leg, True),
    ):
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

    # Upper front/rear rails are cut from 600 mm pieces. Their horizontal leg is
    # left intact at each end while the vertical leg is removed over the 40 mm
    # post width, creating four integral steel post-mouth covers.
    for face, y, rear in (
        ("front", 0.0, False),
        ("rear", cfg.depth - cfg.angle_leg, True),
    ):
        rail_id = next_id("A")
        add_shape(
            rail_id,
            f"Upper {face} angle rail with integral post-cover tabs",
            _top_cover_angle_x(
                cfg.length,
                p,
                cfg.angle_leg,
                cfg.angle_thickness,
                rear=rear,
            ),
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

    # Upper side rails remain conventional 520 mm L sections between posts and
    # meet the edges of the front/rear cover tabs without overlapping them.
    for side, x, right in (
        ("left", 0.0, False),
        ("right", cfg.length - cfg.angle_leg, True),
    ):
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

    # Alberts 337254 / Leroy 14959336 is a two-plane 90-degree corner wrap,
    # 50x50 legs x 70 high x 1.5 thick. It sits tightly over the *outside* faces
    # of each corner. Only its material thickness projects beyond the nominal
    # 600x600 envelope; the old artificial inward offset/third plane is gone.
    corners = [
        ("front left", 0.0, 0.0, False, False),
        ("front right", cfg.length, 0.0, True, False),
        ("rear left", 0.0, cfg.depth, False, True),
        ("rear right", cfg.length, cfg.depth, True, True),
    ]

    for level_name, bracket_z in (
        ("lower", lower_z),
        ("upper", cfg.body_height - cfg.bracket_height),
    ):
        for corner_name, x, y, right, rear in corners:
            bracket_id = next_id("K")
            add_shape(
                bracket_id,
                f"{level_name.title()} {corner_name} Alberts corner wrap",
                _corner_wrap(
                    cfg.bracket_leg,
                    cfg.bracket_height,
                    cfg.bracket_thickness,
                    right=right,
                    rear=rear,
                ),
                (x, y, bracket_z),
                "corner_wrap",
                "Sendzimir galvanised steel",
                f"90° wrap · 50x50 legs x {cfg.bracket_height:g} mm high x {cfg.bracket_thickness:g} mm",
                "1 pc",
                GALVANISED,
                viewer_group="corner_connectors",
                product_id=P_CORNER_WRAP,
                note="actual two-plane envelope of Alberts 337254; exact hole coordinates still to be measured on one physical fitting",
            )

            # Six symbolic Ø6.4 rivet heads: three on each wing. The outermost
            # point on each 50 mm wing lands on the adjacent angle rail while the
            # two inner points land on the 40 mm post. Exact holes will follow
            # the purchased fitting rather than this conceptual pattern.
            offsets = ((14.0, 16.0), (28.0, 36.0), (46.0, 56.0))
            for wing, wing_name in (("x", "front/rear wing"), ("y", "left/right wing")):
                for offset, z_offset in offsets:
                    rivet_id = next_id("RV")
                    if wing == "x":
                        center_x = x - offset if right else x + offset
                        head_y = y + cfg.bracket_thickness if rear else y - cfg.bracket_thickness - 3.0
                        rivet_shape = Box(8.0, 3.0, 8.0, align=MIN_ALIGN)
                        rivet_pos = (center_x - 4.0, head_y, bracket_z + z_offset - 4.0)
                    else:
                        head_x = x + cfg.bracket_thickness if right else x - cfg.bracket_thickness - 3.0
                        center_y = y - offset if rear else y + offset
                        rivet_shape = Box(3.0, 8.0, 8.0, align=MIN_ALIGN)
                        rivet_pos = (head_x, center_y - 4.0, bracket_z + z_offset - 4.0)

                    add_shape(
                        rivet_id,
                        f"{level_name.title()} {corner_name} {wing_name} structural rivet",
                        rivet_shape,
                        rivet_pos,
                        "structural_rivet",
                        "Steel structural blind rivet",
                        f"Ø{cfg.rivet_diameter:g} mm structural blind rivet",
                        "1 pc",
                        RIVET,
                        viewer_group="structural_rivets",
                        product_id=P_RIVET_64,
                        note="symbolic location only; final positions follow Alberts 337254 holes and verified edge distances",
                    )

    assembly = Compound(label=model_id, children=shapes)

    metadata: dict[str, Any] = {
        "schema_version": 2,
        "status": "parallel concept study · no-weld / riveted structure v2",
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
            "corner_wrap_leg": cfg.bracket_leg,
            "corner_wrap_height": cfg.bracket_height,
            "corner_wrap_thickness": cfg.bracket_thickness,
        },
        "derived": {
            "post_count": 4,
            "post_length_mm": post_length,
            "angle_rail_count": 8,
            "standard_angle_rail_count": 6,
            "integral_top_cover_rail_count": 2,
            "integral_steel_top_cap_count": 4,
            "corner_connector_count": 8,
            "structural_rivet_count": 8 * cfg.rivets_per_corner,
            "caps_count": 4,
            "plastic_top_cap_count": 0,
            "weld_count": 0,
            "clear_span_mm": clear_x,
            "corner_wrap_projection_outside_frame_mm": cfg.bracket_thickness,
        },
        "parts": parts,
        "viewer": {
            "groups": [
                {"id": "posts", "label": "40x40 posts", "node_names": groups["posts"], "offset_mm": [0, 0, 0]},
                {"id": "angle_rails", "label": "L40x40x3 rails + steel top tabs", "node_names": groups["angle_rails"], "offset_mm": [0, 0, 180]},
                {"id": "corner_connectors", "label": "Alberts 50x50x70 corner wraps", "node_names": groups["corner_connectors"], "offset_mm": [100, 100, 0]},
                {"id": "structural_rivets", "label": "Ø6.4 structural rivets", "node_names": groups["structural_rivets"], "offset_mm": [180, 180, 0]},
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
                "id": P_CORNER_WRAP,
                "retailer": "Leroy Merlin",
                "ref": "14959336",
                "name": "Cantonera metálica GAH Alberts acero galvanizado 50x50x70 mm",
                "url": "https://www.leroymerlin.es/productos/cantonera-metalica-en-acero-galvanizado-de-50-x-50-x-70-mm-14959336.html",
                "stock": "1 pc",
                "suggested_qty": 8,
                "note": "Alberts art. 337254; two 50 mm wings, 70 mm along bend, 1.5 mm thick, 6 x Ø6.5 mm holes.",
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
                "name": "Flush plastic insert cap 40x40 mm · bottom only",
                "stock": "1 pc",
                "suggested_qty": 4,
                "note": "Upper plastic caps eliminated; the two long upper angles provide four integral steel closures.",
            },
        ],
        "assemblies": [
            {
                "id": "AS01",
                "name": "No-weld riveted outer structure v2",
                "contains": "4 shortened continuous posts + 8 angle rails (2 with integral top tabs) + 8 external Alberts corner wraps + structural blind rivets",
            }
        ],
        "joints": [
            {
                "id": "J01",
                "type": "structural blind-riveted external corner wrap",
                "name": "Post / two-angle external corner node",
                "spec": "One Alberts 337254 folded 90-degree wrap per upper/lower corner. Its two 50 mm wings sit directly on the two exterior faces and bridge the 40 mm post into each perpendicular angle rail. Six Ø6.4 structural blind rivets are the current concept; freeze final positions only after measuring the commercial part.",
            },
            {
                "id": "J02",
                "type": "integral steel post closure",
                "name": "Upper angle / post-mouth cover",
                "spec": "Front and rear upper L40x40x3 blanks remain 600 mm long. Remove only the vertical leg over the first/last 40 mm; the untouched horizontal wing forms four 40x40x3 top tabs over posts cut to 597 mm. Seal the hairline perimeter with paintable exterior MS polymer before final paint.",
            },
        ],
        "fabrication_notes": [
            "Parallel concept only: this model intentionally contains the outer structure and permanent corner hardware, not the bag cassette, drainage or timber panels from the welded v12 design.",
            "There are zero welded joints. The four posts remain continuous but are cut to 597 mm so the 3 mm upper-angle tabs finish exactly at the 600 mm envelope.",
            "No plastic top caps: the upper front and rear L40x40x3 rails are 600 mm blanks. Cut away only their vertical leg over 40 mm at each end and leave the horizontal leg intact as the steel lid over each post.",
            "Seal the very small top-tab/post and rail/tab seams with a thin exterior paintable MS-polymer fillet, then paint the assembled frame.",
            "Correction from v1: Alberts 337254 is a two-plane 90-degree corner wrap, not a three-plane shelf bracket. The CAD now uses two 50 mm wings x 70 mm high x 1.5 mm and places them tightly around the exterior corner.",
            "The corner wrap now projects only its 1.5 mm material thickness beyond the nominal frame envelope; the previous artificial 10-40 mm inboard/protruding representation has been removed.",
            "The commercial wrap overlaps each 40 mm post by its full width and continues about 10 mm onto each adjacent angle rail. Confirm the real Ø6.5 hole positions and usable edge distances on one physical fitting before committing to Ø6.4 structural rivets.",
            "Rivet heads shown in the CAD are symbolic and intentionally easy to select. Final head geometry/grip range depends on the structural blind-rivet family chosen.",
        ],
    }

    return ModelBuild(shape=assembly, bom=_group_bom(parts), metadata=metadata)


PRESETS: dict[str, tuple[str, BoltedStructureConfig]] = {
    "planter-600x600x600-no-weld-structure": (
        "600 × 600 × 600 mm · no-weld structure",
        CFG_600,
    )
}
