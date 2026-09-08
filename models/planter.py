from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from build123d import Align, Box, Color, Compound, Pos

from .parameters import PlanterConfig


@dataclass
class ModelBuild:
    shape: Compound
    bom: list[dict[str, Any]]
    metadata: dict[str, Any]


METAL = Color(0.62, 0.65, 0.68)
WOOD = Color(0.55, 0.31, 0.15)
MIN_ALIGN = (Align.MIN, Align.MIN, Align.MIN)


def _hollow_tube(length: float, size: float, wall: float, axis: str, label: str):
    if wall <= 0 or wall * 2 >= size:
        raise ValueError("Tube wall must be greater than 0 and less than half the profile size")

    if axis == "x":
        outer_dims = (length, size, size)
        inner_dims = (length + 2, size - 2 * wall, size - 2 * wall)
        inner_pos = (-1, wall, wall)
    elif axis == "y":
        outer_dims = (size, length, size)
        inner_dims = (size - 2 * wall, length + 2, size - 2 * wall)
        inner_pos = (wall, -1, wall)
    elif axis == "z":
        outer_dims = (size, size, length)
        inner_dims = (size - 2 * wall, size - 2 * wall, length + 2)
        inner_pos = (wall, wall, -1)
    else:
        raise ValueError(f"Unsupported tube axis: {axis}")

    outer = Box(*outer_dims, align=MIN_ALIGN)
    inner = Pos(*inner_pos) * Box(*inner_dims, align=MIN_ALIGN)
    tube = outer - inner
    tube.label = label
    tube.color = METAL
    return tube


def _place(shape, x: float, y: float, z: float, label: str, color: Color):
    placed = Pos(x, y, z) * shape
    placed.label = label
    placed.color = color
    return placed


def _group_bom(parts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, float], dict[str, Any]] = {}
    for part in parts:
        key = (part["material"], part["profile"], part["length_mm"])
        if key not in groups:
            groups[key] = {
                "material": part["material"],
                "profile": part["profile"],
                "length_mm": part["length_mm"],
                "quantity": 0,
                "part_ids": [],
            }
        groups[key]["quantity"] += 1
        groups[key]["part_ids"].append(part["id"])
    return list(groups.values())


def build_planter(config: PlanterConfig | None = None) -> ModelBuild:
    cfg = config or PlanterConfig()
    p = cfg.frame_size

    if cfg.length <= 2 * p or cfg.depth <= 2 * p or cfg.body_height <= 2 * p:
        raise ValueError("Planter dimensions are too small for the selected frame profile")

    shapes = []
    parts: list[dict[str, Any]] = []

    def add_tube(
        part_id: str,
        name: str,
        length: float,
        size: float,
        wall: float,
        axis: str,
        position: tuple[float, float, float],
        category: str,
    ) -> None:
        profile = f"{size:g}x{size:g}x{wall:g}"
        tube = _hollow_tube(length, size, wall, axis, part_id)
        shapes.append(_place(tube, *position, label=part_id, color=METAL))
        parts.append(
            {
                "id": part_id,
                "name": name,
                "category": category,
                "material": "Aluminium EN AW-6060 T66",
                "profile": profile,
                "length_mm": round(length, 3),
            }
        )

    # Main planter frame: long rails span the full length; depth rails fit between them.
    rail_y = cfg.depth - p
    top_z = cfg.body_height - p
    depth_rail_length = cfg.depth - 2 * p
    upright_length = cfg.body_height - 2 * p

    frame_members = [
        ("F01", "Front bottom rail", cfg.length, "x", (0, 0, 0)),
        ("F02", "Rear bottom rail", cfg.length, "x", (0, rail_y, 0)),
        ("F03", "Front top rail", cfg.length, "x", (0, 0, top_z)),
        ("F04", "Rear top rail", cfg.length, "x", (0, rail_y, top_z)),
        ("F05", "Left bottom depth rail", depth_rail_length, "y", (0, p, 0)),
        ("F06", "Right bottom depth rail", depth_rail_length, "y", (cfg.length - p, p, 0)),
        ("F07", "Left top depth rail", depth_rail_length, "y", (0, p, top_z)),
        ("F08", "Right top depth rail", depth_rail_length, "y", (cfg.length - p, p, top_z)),
        ("F09", "Front-left upright", upright_length, "z", (0, 0, p)),
        ("F10", "Front-right upright", upright_length, "z", (cfg.length - p, 0, p)),
        ("F11", "Rear-left upright", upright_length, "z", (0, rail_y, p)),
        ("F12", "Rear-right upright", upright_length, "z", (cfg.length - p, rail_y, p)),
    ]

    for part_id, name, length, axis, position in frame_members:
        add_tube(part_id, name, length, p, cfg.frame_wall, axis, position, "frame")

    # Detachable trellis posts are deliberately shown behind the planter frame.
    tp = cfg.trellis_post_size
    trellis_y = cfg.depth + cfg.trellis_gap
    add_tube(
        "T01",
        "Left trellis post",
        cfg.trellis_height,
        tp,
        cfg.trellis_post_wall,
        "z",
        (0, trellis_y, 0),
        "trellis",
    )
    add_tube(
        "T02",
        "Right trellis post",
        cfg.trellis_height,
        tp,
        cfg.trellis_post_wall,
        "z",
        (cfg.length - tp, trellis_y, 0),
        "trellis",
    )

    # Simple front timber cladding. The exact fixing system will be designed later.
    pitch = cfg.slat_width + cfg.slat_gap
    slat_count = max(1, int((cfg.length + cfg.slat_gap) // pitch))
    occupied = slat_count * cfg.slat_width + (slat_count - 1) * cfg.slat_gap
    side_margin = (cfg.length - occupied) / 2

    for index in range(slat_count):
        part_id = f"W{index + 1:02d}"
        x = side_margin + index * pitch
        slat = Box(
            cfg.slat_width,
            cfg.slat_thickness,
            cfg.slat_height,
            align=MIN_ALIGN,
        )
        slat.label = part_id
        slat.color = WOOD
        shapes.append(
            _place(
                slat,
                x,
                -cfg.slat_thickness,
                cfg.slat_bottom_clearance,
                label=part_id,
                color=WOOD,
            )
        )
        parts.append(
            {
                "id": part_id,
                "name": f"Front timber slat {index + 1}",
                "category": "cladding",
                "material": "Timber (TBD)",
                "profile": f"{cfg.slat_width:g}x{cfg.slat_thickness:g}",
                "length_mm": round(cfg.slat_height, 3),
            }
        )

    assembly = Compound(label="planter-concept-v1", children=shapes)

    metadata = {
        "schema_version": 1,
        "model": "planter-concept-v1",
        "status": "concept / pipeline reference",
        "units": "mm",
        "parameters": asdict(cfg),
        "derived": {
            "slat_height_mm": cfg.slat_height,
            "slat_count": slat_count,
            "slat_side_margin_mm": round(side_margin, 3),
        },
        "parts": parts,
        "joints": [
            {
                "id": "J01",
                "name": "Left trellis post to planter",
                "parts": ["T01", "F11"],
                "type": "mechanical fixing",
                "status": "to design",
            },
            {
                "id": "J02",
                "name": "Right trellis post to planter",
                "parts": ["T02", "F12"],
                "type": "mechanical fixing",
                "status": "to design",
            },
        ],
        "notes": [
            "This first model validates the CAD-as-code and web-viewer pipeline.",
            "Trellis fixings, weld definitions, planter liner and final cladding details are intentionally not final yet.",
        ],
    }

    return ModelBuild(shape=assembly, bom=_group_bom(parts), metadata=metadata)
