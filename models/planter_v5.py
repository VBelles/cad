from __future__ import annotations

import copy
from dataclasses import asdict
from typing import Any

from build123d import Align, Box, Color, Compound, Cylinder, Pos, Rot

from .parameters import PlanterConfig
from .planter import (
    FASTENER,
    P_ANGLE_20,
    P_FLAT_30,
    RAW_STEEL,
    STEEL_ANGLE,
    ModelBuild,
    _group_bom,
    build_planter as build_planter_v4,
)


MIN_ALIGN = (Align.MIN, Align.MIN, Align.MIN)
CYLINDER_ALIGN = (Align.CENTER, Align.CENTER, Align.MIN)


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


def _copy_and_shift_existing(child, cfg: PlanterConfig):
    """Copy one v4 child and apply the optional panel inset to timber only."""
    label = child.label or ""
    copied = copy.copy(child)
    inset = cfg.panel_outer_inset
    if inset == 0:
        return copied

    # Timber parts are named FW/FB, RW/RB, LW/LB and QW/QB. Do not move
    # structural Rxx rails or any other similarly prefixed part.
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
    level: str,
):
    """Create one 20x20x3 angle bracket in its final absolute position."""
    length = cfg.panel_bracket_length
    leg = cfg.panel_bracket_leg
    wall = cfg.panel_bracket_wall
    start = (cfg.length - length) / 2

    lower_z = cfg.bottom_frame_z + cfg.frame_size
    if level == "lower":
        vertical_z = lower_z
        shelf_z = lower_z
    else:
        vertical_z = cfg.top_frame_z - leg
        shelf_z = cfg.top_frame_z - wall

    front_back = cfg.panel_back_offset
    rear_back = cfg.depth - cfg.panel_back_offset
    left_back = cfg.panel_back_offset
    right_back = cfg.length - cfg.panel_back_offset

    if face == "front":
        shelf = Pos(start, front_back - leg, shelf_z) * Box(
            length, leg, wall, align=MIN_ALIGN
        )
        vertical = Pos(start, front_back, vertical_z) * Box(
            length, wall, leg, align=MIN_ALIGN
        )
    elif face == "rear":
        shelf = Pos(start, rear_back, shelf_z) * Box(
            length, leg, wall, align=MIN_ALIGN
        )
        vertical = Pos(start, rear_back - wall, vertical_z) * Box(
            length, wall, leg, align=MIN_ALIGN
        )
    elif face == "left":
        shelf = Pos(left_back - leg, start, shelf_z) * Box(
            leg, length, wall, align=MIN_ALIGN
        )
        vertical = Pos(left_back, start, vertical_z) * Box(
            wall, length, leg, align=MIN_ALIGN
        )
    elif face == "right":
        shelf = Pos(right_back, start, shelf_z) * Box(
            leg, length, wall, align=MIN_ALIGN
        )
        vertical = Pos(right_back - wall, start, vertical_z) * Box(
            wall, length, leg, align=MIN_ALIGN
        )
    else:
        raise ValueError(f"Unsupported panel face: {face}")

    return Compound(children=[shelf, vertical])


def _screw_shapes_for_bracket(
    cfg: PlanterConfig,
    face: str,
    level: str,
):
    screw = _panel_screw_symbol(cfg)
    half_spacing = cfg.panel_bracket_screw_spacing / 2
    centre = cfg.length / 2
    along = (centre - half_spacing, centre + half_spacing)
    z = (
        cfg.bottom_frame_z + cfg.frame_size + cfg.panel_bracket_leg / 2
        if level == "lower"
        else cfg.top_frame_z - cfg.panel_bracket_leg / 2
    )
    wall = cfg.panel_bracket_wall

    front_back = cfg.panel_back_offset
    rear_back = cfg.depth - cfg.panel_back_offset
    left_back = cfg.panel_back_offset
    right_back = cfg.length - cfg.panel_back_offset

    result = []
    if face == "front":
        for x in along:
            result.append(Pos(x, front_back + wall, z) * Rot(90, 0, 0) * screw)
    elif face == "rear":
        for x in along:
            result.append(Pos(x, rear_back - wall, z) * Rot(-90, 0, 0) * screw)
    elif face == "left":
        for y in along:
            result.append(Pos(left_back + wall, y, z) * Rot(0, -90, 0) * screw)
    elif face == "right":
        for y in along:
            result.append(Pos(right_back - wall, y, z) * Rot(0, 90, 0) * screw)
    return result


def build_planter(config: PlanterConfig | None = None) -> ModelBuild:
    cfg = config or PlanterConfig()

    if cfg.panel_brackets_per_face != 2:
        raise ValueError("v5 models exactly two panel brackets per face")
    if cfg.panel_bracket_fasteners_each != 2:
        raise ValueError("v5 models exactly two fasteners per panel bracket")
    if cfg.panel_back_offset > cfg.frame_size:
        raise ValueError(
            "Timber panel inner face lies behind the inner steel face; adjust panel_outer_inset"
        )
    if cfg.panel_back_offset < cfg.panel_bracket_leg:
        raise ValueError("Panel is too shallow for the selected angle-bracket leg")

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
    for face in ("front", "rear", "left", "right"):
        for level in ("lower", "upper"):
            bracket_id = f"PB{bracket_index:02d}"
            bracket = _bracket_shape(cfg, face, level)
            _add_part(
                shapes,
                parts,
                panel_mount_nodes,
                bracket_id,
                f"{face.title()} panel {level} centred mounting bracket",
                bracket,
                "panel_mount_bracket",
                STEEL_ANGLE,
                f"{cfg.panel_bracket_leg:g}x{cfg.panel_bracket_leg:g}x{cfg.panel_bracket_wall:g} mm angle",
                f"{cfg.panel_bracket_length:g} mm",
                RAW_STEEL,
                product_id=P_ANGLE_20,
                face=face,
                level=level,
                note=(
                    "centred on this face, far from both corners; one leg is welded to the "
                    "horizontal 40x40 rail and the other bears against the timber batten"
                ),
            )

            for screw_shape in _screw_shapes_for_bracket(cfg, face, level):
                fastener_id = f"PF{fastener_index:02d}"
                _add_part(
                    shapes,
                    parts,
                    panel_mount_nodes,
                    fastener_id,
                    f"{face.title()} panel {level} concealed M5 fastener {fastener_index}",
                    screw_shape,
                    "panel_mount_fastener",
                    "Stainless M5 screw + threaded wood insert",
                    "M5 symbolic screw / insert",
                    f"{cfg.panel_mount_screw_length:g} mm screw",
                    FASTENER,
                    face=face,
                    level=level,
                    note=(
                        "accessed from inside; passes through the angle vertical leg into a "
                        "threaded insert in the horizontal timber batten"
                    ),
                )
                fastener_index += 1

            bracket_index += 1

    assembly = Compound(label="square-planter-600-v5", children=shapes)

    metadata = copy.deepcopy(base.metadata)
    metadata["schema_version"] = 5
    metadata["model"] = "square-planter-600-v5"
    metadata["status"] = "fabrication design / v5"
    metadata["parameters"] = asdict(cfg)
    metadata["parts"] = parts

    derived = metadata["derived"]
    derived["panel_frame_fixings_each"] = (
        cfg.panel_brackets_per_face * cfg.panel_bracket_fasteners_each
    )
    derived["panel_brackets_each"] = cfg.panel_brackets_per_face
    derived["panel_outer_inset_mm"] = cfg.panel_outer_inset
    derived["panel_total_depth_mm"] = cfg.panel_total_depth
    derived["panel_back_offset_mm"] = cfg.panel_back_offset

    for group in metadata["viewer"]["groups"]:
        if group["id"] == "panel_mounts":
            group["label"] = "Panel mounting brackets"
            group["node_names"] = panel_mount_nodes
            group["offset_mm"] = [0, 0, 180]

    for product in metadata["products"]:
        if product["id"] == P_ANGLE_20:
            product["note"] = (
                "also supplies 8 centred 60 mm timber-panel brackets; total angle use is "
                "about 1.92 m before kerf"
            )
        elif product["id"] == P_FLAT_30:
            product["note"] = "used for the continuous geotextile clamp frame"

    for assembly_meta in metadata["assemblies"]:
        if assembly_meta["id"] == "AS01":
            assembly_meta["contains"] = (
                "40x40 main frame, integral post-closing top flaps, five-rail bag platform, "
                "bag ledges, tray guides and centred panel brackets"
            )
        elif assembly_meta["id"] == "AS02":
            assembly_meta["contains"] = (
                "7 vertical slats + 2 horizontal battens per face + 2 centred angle brackets "
                "+ 4 concealed M5 fasteners"
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
                "2 centred 20x20x3 angle brackets per panel: lower bracket welded to the "
                "top of that face's lower 40x40 rail, upper bracket welded under that face's "
                "top 40x40 rail; each bracket uses 2 concealed M5 screws into threaded "
                "inserts in the corresponding timber batten. Bracket depth follows the "
                "panel back plane, so slat thickness/alignment can change without corner interference."
            ),
        }
    )

    metadata["service"]["panel_removal"] = (
        "remove four M5 screws from inside; the two centred angle brackets remain welded to "
        "that face's horizontal steel rails"
    )

    notes = [
        note
        for note in metadata["fabrication_notes"]
        if "four welded 30x3 steel tabs" not in note
        and "panel mounting tabs reuse" not in note.lower()
    ]
    notes.extend(
        [
            "Each timber panel now uses only two small centred angle brackets: one on its lower horizontal steel rail and one under its upper horizontal steel rail; no mounting hardware enters either corner.",
            "Each bracket carries two concealed M5 screws into the matching timber batten, so there are four removable fasteners per panel.",
            "Panel depth is parameterised independently from slat thickness. With panel_outer_inset=0 the timber is outer-flush; if thinner slats are later used, the brackets simply move in depth to meet the batten back face.",
        ]
    )
    metadata["fabrication_notes"] = notes

    metadata["notes"] = [
        note.replace(
            "final M5 insert model",
            "final M5 insert model and preferred panel flush position",
        )
        for note in metadata["notes"]
    ]

    return ModelBuild(
        shape=assembly,
        bom=_group_bom(parts),
        metadata=metadata,
    )
