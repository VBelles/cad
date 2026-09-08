from __future__ import annotations

import copy
from dataclasses import asdict
from typing import Any

from build123d import Align, Color, Compound, Cylinder, Pos

from .parameters import PlanterConfig
from .planter import (
    FASTENER,
    P_ANGLE_20,
    P_FLAT_30,
    RAW_STEEL,
    STEEL_ANGLE,
    ModelBuild,
    _angle_x,
    _angle_y,
    _group_bom,
    build_planter as build_planter_v4,
)


CYLINDER_ALIGN = (Align.CENTER, Align.CENTER, Align.MIN)


def _panel_screw_symbol(cfg: PlanterConfig):
    """Symbolic screw entering upward through the bracket into the batten."""
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


def _copy_and_shift_existing(child, cfg: PlanterConfig):
    """Copy one v4 child and apply the optional panel inset to timber only."""
    label = child.label or ""
    copied = copy.copy(child)
    inset = cfg.panel_outer_inset
    if inset == 0:
        return copied

    if label.startswith(("FW", "FB")):
        return Pos(0, inset, 0) * copied
    if label.startswith(("RW", "RB")):
        return Pos(0, -inset, 0) * copied
    if label.startswith(("LW", "LB")):
        return Pos(inset, 0, 0) * copied
    if label.startswith(("QW", "QB")):
        return Pos(-inset, 0, 0) * copied
    return copied


def _add_part(
    shapes: list[Any],
    parts: list[dict[str, Any]],
    viewer_nodes: list[str],
    part_id: str,
    name: str,
    shape,
    category: str,
    material: str,
    profile: str,
    cut: str,
    color: Color,
    product_id: str | None = None,
    **extra: Any,
) -> None:
    shape.label = part_id
    shape.color = color
    shapes.append(shape)
    viewer_nodes.append(part_id)

    part: dict[str, Any] = {
        "id": part_id,
        "name": name,
        "category": category,
        "material": material,
        "profile": profile,
        "cut": cut,
        "viewer_group": "panel_mounts",
    }
    if product_id:
        part["product_id"] = product_id
    part.update(extra)
    parts.append(part)


def _bracket_shape(
    cfg: PlanterConfig,
    face: str,
    batten_z: float,
    end: str,
):
    """Return one small L bracket at a batten end.

    The angle is oriented like a tiny shelf:
    - vertical leg against the inner face of the 40x40 upright;
    - horizontal leg directly under the timber batten;
    - its extrusion width follows the batten depth.

    Adjacent faces therefore use different faces of the same corner post and
    never occupy the same volume.
    """
    p = cfg.frame_size
    leg = cfg.panel_bracket_leg
    wall = cfg.panel_bracket_wall
    width = cfg.panel_bracket_width
    z = batten_z - leg

    front_depth = cfg.panel_batten_front_offset
    rear_depth = cfg.depth - cfg.panel_batten_front_offset - cfg.batten_thickness
    left_depth = cfg.panel_batten_front_offset
    right_depth = cfg.length - cfg.panel_batten_front_offset - cfg.batten_thickness

    if face == "front":
        y = front_depth
        if end == "left":
            return Pos(p, y, z) * _angle_y(width, leg, wall, False, True)
        return Pos(cfg.length - p - leg, y, z) * _angle_y(
            width, leg, wall, True, True
        )

    if face == "rear":
        y = rear_depth
        if end == "left":
            return Pos(p, y, z) * _angle_y(width, leg, wall, False, True)
        return Pos(cfg.length - p - leg, y, z) * _angle_y(
            width, leg, wall, True, True
        )

    if face == "left":
        x = left_depth
        if end == "front":
            return Pos(x, p, z) * _angle_x(width, leg, wall, False, True)
        return Pos(x, cfg.depth - p - leg, z) * _angle_x(
            width, leg, wall, True, True
        )

    if face == "right":
        x = right_depth
        if end == "front":
            return Pos(x, p, z) * _angle_x(width, leg, wall, False, True)
        return Pos(x, cfg.depth - p - leg, z) * _angle_x(
            width, leg, wall, True, True
        )

    raise ValueError(f"Unsupported panel face: {face}")


def _screw_shape_for_bracket(
    cfg: PlanterConfig,
    face: str,
    batten_z: float,
    end: str,
):
    """Place one vertical screw through the horizontal bracket leg."""
    p = cfg.frame_size
    leg = cfg.panel_bracket_leg
    width = cfg.panel_bracket_width
    wall = cfg.panel_bracket_wall
    screw = _panel_screw_symbol(cfg)

    z = batten_z - wall

    front_depth = cfg.panel_batten_front_offset
    rear_depth = cfg.depth - cfg.panel_batten_front_offset - cfg.batten_thickness
    left_depth = cfg.panel_batten_front_offset
    right_depth = cfg.length - cfg.panel_batten_front_offset - cfg.batten_thickness

    if face in ("front", "rear"):
        x = p + leg / 2 if end == "left" else cfg.length - p - leg / 2
        y0 = front_depth if face == "front" else rear_depth
        y = y0 + width / 2
        return Pos(x, y, z) * screw

    x0 = left_depth if face == "left" else right_depth
    x = x0 + width / 2
    y = p + leg / 2 if end == "front" else cfg.depth - p - leg / 2
    return Pos(x, y, z) * screw


def build_planter(config: PlanterConfig | None = None) -> ModelBuild:
    cfg = config or PlanterConfig()

    if cfg.panel_brackets_per_batten != 2:
        raise ValueError("This revision models exactly two brackets per timber batten")
    if cfg.panel_battens_per_face != 2:
        raise ValueError("This revision models exactly two battens per timber face")
    if cfg.panel_bracket_width > cfg.batten_thickness:
        raise ValueError("Panel bracket width cannot exceed the timber batten depth")
    if cfg.panel_back_offset > cfg.frame_size:
        raise ValueError(
            "Timber panel inner face lies behind the inner steel face; adjust panel_outer_inset"
        )
    if cfg.panel_batten_front_offset < 0:
        raise ValueError("Invalid timber panel depth offset")

    base = build_planter_v4(cfg)

    # Remove the v4 corner-post MT/MH hardware and make independent copies of
    # everything else. Optional panel inset is applied only to timber nodes.
    shapes: list[Any] = []
    for child in base.shape.children:
        label = child.label or ""
        if label.startswith(("MT", "MH")):
            continue
        shapes.append(_copy_and_shift_existing(child, cfg))

    parts = [
        dict(part)
        for part in base.metadata["parts"]
        if not part["id"].startswith(("MT", "MH"))
    ]
    panel_mount_nodes: list[str] = []

    bracket_index = 1
    fastener_index = 1

    faces_and_ends = {
        "front": ("left", "right"),
        "rear": ("left", "right"),
        "left": ("front", "rear"),
        "right": ("front", "rear"),
    }

    for face, ends in faces_and_ends.items():
        for level, batten_z in (
            ("lower", cfg.batten_z_low),
            ("upper", cfg.batten_z_high),
        ):
            for end in ends:
                bracket_id = f"PB{bracket_index:02d}"
                bracket = _bracket_shape(cfg, face, batten_z, end)
                _add_part(
                    shapes,
                    parts,
                    panel_mount_nodes,
                    bracket_id,
                    f"{face.title()} {level} batten {end} end bracket",
                    bracket,
                    "panel_mount_bracket",
                    STEEL_ANGLE,
                    (
                        f"{cfg.panel_bracket_leg:g}x{cfg.panel_bracket_leg:g}x"
                        f"{cfg.panel_bracket_wall:g} mm angle"
                    ),
                    f"{cfg.panel_bracket_width:g} mm",
                    RAW_STEEL,
                    product_id=P_ANGLE_20,
                    face=face,
                    level=level,
                    end=end,
                    note=(
                        "small vertical L at the batten end: one leg is welded to the "
                        "40x40 upright and the horizontal leg sits directly under the "
                        "timber batten"
                    ),
                )

                fastener_id = f"PF{fastener_index:02d}"
                screw_shape = _screw_shape_for_bracket(cfg, face, batten_z, end)
                _add_part(
                    shapes,
                    parts,
                    panel_mount_nodes,
                    fastener_id,
                    f"{face.title()} {level} batten {end} concealed fastener",
                    screw_shape,
                    "panel_mount_fastener",
                    "Stainless M5 screw + threaded wood insert",
                    "M5 symbolic screw / insert",
                    f"{cfg.panel_mount_screw_length:g} mm screw",
                    FASTENER,
                    face=face,
                    level=level,
                    end=end,
                    note=(
                        "inserted upward from inside through the bracket shelf into the "
                        "underside of the horizontal timber batten; bracket remains welded "
                        "to the steel post when the panel is removed"
                    ),
                )

                bracket_index += 1
                fastener_index += 1

    assembly = Compound(label="square-planter-600-v5", children=shapes)

    metadata = copy.deepcopy(base.metadata)
    metadata["schema_version"] = 5
    metadata["model"] = "square-planter-600-v5"
    metadata["status"] = "fabrication design / v5"
    metadata["parameters"] = asdict(cfg)
    metadata["parts"] = parts

    derived = metadata["derived"]
    derived["panel_frame_fixings_each"] = cfg.panel_bracket_count_per_face
    derived["panel_brackets_each"] = cfg.panel_bracket_count_per_face
    derived["panel_brackets_per_batten"] = cfg.panel_brackets_per_batten
    derived["panel_outer_inset_mm"] = cfg.panel_outer_inset
    derived["panel_total_depth_mm"] = cfg.panel_total_depth
    derived["panel_back_offset_mm"] = cfg.panel_back_offset

    for group in metadata["viewer"]["groups"]:
        if group["id"] == "panel_mounts":
            group["label"] = "Panel end brackets"
            group["node_names"] = panel_mount_nodes
            group["offset_mm"] = [0, 0, 180]

    for product in metadata["products"]:
        if product["id"] == P_ANGLE_20:
            product["note"] = (
                "also supplies 16 x 20 mm timber-panel end brackets; total angle use "
                "is about 1.76 m before cutting kerf"
            )
        elif product["id"] == P_FLAT_30:
            product["note"] = "used for the continuous geotextile clamp frame"

    for assembly_meta in metadata["assemblies"]:
        if assembly_meta["id"] == "AS01":
            assembly_meta["contains"] = (
                "40x40 main frame, integral post-closing top flaps, five-rail bag "
                "platform, bag ledges, tray guides and small post-mounted panel brackets"
            )
        elif assembly_meta["id"] == "AS02":
            assembly_meta["contains"] = (
                "7 vertical slats + 2 horizontal battens per face + 2 end brackets "
                "per batten + 4 concealed removable fasteners"
            )

    metadata["joints"] = [
        joint for joint in metadata["joints"] if joint["id"] != "J08"
    ]
    metadata["joints"].append(
        {
            "id": "J08",
            "type": "mechanical",
            "name": "Timber panel to steel frame",
            "spec": (
                "4 small 20x20x3 angle brackets per panel, two per horizontal batten. "
                "Each bracket is located at a batten end: its vertical leg is welded to "
                "the corresponding 40x40 upright and its horizontal leg sits under the "
                "batten. One concealed M5 screw goes upward into a threaded insert in "
                "the batten. Adjacent faces use different post faces, so their brackets "
                "do not collide. Bracket depth follows the timber panel position."
            ),
        }
    )

    metadata["service"]["panel_removal"] = (
        "remove four concealed M5 screws from inside; the four small L brackets remain "
        "welded to the two vertical steel posts"
    )

    notes = [
        note
        for note in metadata["fabrication_notes"]
        if "four welded 30x3 steel tabs" not in note
        and "panel mounting tabs reuse" not in note.lower()
        and "small centred angle brackets" not in note.lower()
        and "each bracket carries two concealed" not in note.lower()
        and "panel depth is parameterised" not in note.lower()
    ]
    notes.extend(
        [
            "Each horizontal timber batten is held by two tiny end brackets, one at each vertical 40x40 post; there are four brackets per panel.",
            "Each bracket is a 20 mm cut of 20x20x3 angle: vertical leg welded to the post, horizontal leg directly under the batten, with one concealed upward M5 fastener.",
            "Perpendicular faces no longer share bracket volume: each face uses its own faces of the vertical posts, so the corner remains geometrically clean.",
            "Panel depth remains parameterised. Changing slat thickness or the desired flush position only moves these small brackets along the post depth; their basic geometry does not change.",
        ]
    )
    metadata["fabrication_notes"] = notes

    return ModelBuild(
        shape=assembly,
        bom=_group_bom(parts),
        metadata=metadata,
    )
