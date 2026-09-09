from __future__ import annotations

import copy
import math

from build123d import Align, Box, Color, Compound, Pos

from .parameters import PlanterConfig
from .planter import ModelBuild, _group_bom
from .planter_v6 import build_planter as build_planter_v6


MIN_ALIGN = (Align.MIN, Align.MIN, Align.MIN)
WOOD = Color(0.58, 0.38, 0.20)
MAGNET = Color(0.28, 0.29, 0.31)


def _cover_magnet_count(cfg: PlanterConfig) -> int:
    return max(3, math.ceil(cfg.module_panel_height / 250.0))


def build_planter(config: PlanterConfig | None = None, model_id: str = "planter-600x600x600") -> ModelBuild:
    cfg = config or PlanterConfig(panel_outer_inset=-10.0)
    base = build_planter_v6(cfg, model_id=model_id)

    # v7 keeps the v6 structural module untouched. Timber is moved outward by
    # one slat thickness so its rear face sits on the exterior steel plane. This
    # lets a normal-width timber slat pass in front of intermediate 40x40 posts.
    if abs(cfg.panel_outer_inset + cfg.slat_thickness) > 1e-6:
        raise ValueError(
            "v7 centre-post covers require panel_outer_inset == -slat_thickness "
            "so the timber cladding clears the steel face"
        )

    shapes = list(base.shape.children)
    metadata = copy.deepcopy(base.metadata)
    parts = [dict(part) for part in metadata["parts"]]
    cover_nodes: list[str] = []

    cover_index = 1
    magnet_index = 1
    magnet_count = _cover_magnet_count(cfg)
    cover_width = cfg.slat_width
    cover_height = cfg.module_panel_height
    cover_z = cfg.module_panel_bottom_z

    # Only intermediate stations need visual covers. End posts stay visible as
    # the intentional off-white perimeter frame.
    for station in range(1, cfg.station_count - 1):
        station_x = station * cfg.bay_pitch
        cover_x = station_x + (cfg.frame_size - cover_width) / 2

        for face in ("front", "rear"):
            cover_id = f"CW{cover_index:02d}"
            y = cfg.panel_outer_inset if face == "front" else cfg.depth
            cover = Pos(cover_x, y, cover_z) * Box(
                cover_width,
                cfg.slat_thickness,
                cover_height,
                align=MIN_ALIGN,
            )
            cover.label = cover_id
            cover.color = WOOD
            shapes.append(cover)
            cover_nodes.append(cover_id)
            parts.append(
                {
                    "id": cover_id,
                    "name": f"{face.title()} intermediate-post removable timber cover",
                    "category": "cladding_post_cover",
                    "material": "Raw fir, ripped/planed in workshop",
                    "profile": f"{cover_width:g}x{cfg.slat_thickness:g} mm finished slat",
                    "cut": f"{cover_height:g} mm",
                    "viewer_group": "centre_post_covers",
                    "station": station + 1,
                    "face": face,
                    "note": (
                        "normal-width decorative slat centred on the 40x40 intermediate post; "
                        "removable before either neighbouring panel"
                    ),
                }
            )

            # Symbolic recessed magnets. They sit inside the rear 3 mm of the
            # timber cover and contact the painted steel post; they are not
            # structural and should be epoxy-sealed for exterior use.
            if magnet_count == 1:
                magnet_zs = [cover_z + cover_height / 2]
            else:
                edge = min(70.0, cover_height / 5)
                step = (cover_height - 2 * edge) / (magnet_count - 1)
                magnet_zs = [cover_z + edge + i * step for i in range(magnet_count)]

            for magnet_z in magnet_zs:
                magnet_id = f"CM{magnet_index:02d}"
                magnet_y = -3.0 if face == "front" else cfg.depth
                magnet = Pos(
                    station_x + cfg.frame_size / 2 - 6.0,
                    magnet_y,
                    magnet_z - 6.0,
                ) * Box(12.0, 3.0, 12.0, align=MIN_ALIGN)
                magnet.label = magnet_id
                magnet.color = MAGNET
                shapes.append(magnet)
                cover_nodes.append(magnet_id)
                parts.append(
                    {
                        "id": magnet_id,
                        "name": f"{face.title()} post-cover sealed magnet",
                        "category": "post_cover_magnet",
                        "material": "Epoxy-sealed neodymium magnet (symbolic)",
                        "profile": "12x12x3 mm symbolic recess",
                        "cut": "1 pc",
                        "viewer_group": "centre_post_covers",
                        "station": station + 1,
                        "face": face,
                        "note": "recess into the rear of the timber cover; verify real magnet pull force and corrosion protection",
                    }
                )
                magnet_index += 1

            cover_index += 1

    assembly = Compound(label=model_id, children=shapes)

    metadata["schema_version"] = 7
    metadata["status"] = "parametric fabrication design / v7"
    metadata["parts"] = parts
    metadata["parameters"] = dict(metadata["parameters"])
    metadata["parameters"]["panel_outer_inset"] = cfg.panel_outer_inset

    metadata["derived"]["timber_proud_of_steel_mm"] = cfg.slat_thickness
    metadata["derived"]["intermediate_post_cover_count"] = 2 * max(cfg.station_count - 2, 0)
    metadata["derived"]["post_cover_magnets_each"] = magnet_count if cfg.station_count > 2 else 0

    metadata["viewer"]["groups"].append(
        {
            "id": "centre_post_covers",
            "label": "Centre post timber covers",
            "node_names": cover_nodes,
            "offset_mm": [0, 0, 280],
        }
    )

    for assembly_meta in metadata["assemblies"]:
        if assembly_meta["id"] == "AS03":
            assembly_meta["contains"] = (
                "one removable panel per structural bay on long faces; one panel on each end; "
                "intermediate front/rear posts receive separate removable timber cover slats"
            )

    metadata["joints"].append(
        {
            "id": "J06",
            "type": "magnetic trim",
            "name": "Intermediate-post timber covers",
            "spec": (
                f"{cover_width:g}x{cfg.slat_thickness:g} mm timber cover slat centred on each "
                "intermediate front/rear 40x40 post. Timber cladding sits 10 mm proud of steel; "
                f"cover uses {magnet_count} recessed sealed magnets and is removed before adjacent panels."
            ),
        }
    )

    metadata["service"]["centre_post_cover_removal"] = (
        "pull the magnetic timber cover outward first; then remove either neighbouring bay panel normally"
    )

    metadata["fabrication_notes"].extend(
        [
            "Timber cladding is moved outward by one 10 mm slat thickness. The rear face of each slat is therefore flush with the exterior steel plane while the timber face sits 10 mm proud.",
            "On 1200 mm models a standard 60 mm timber slat is centred over each 40 mm intermediate post. With the current 540 mm bays this preserves the 12.5 mm visual gap to the neighbouring panel slats exactly.",
            "The intermediate-post cover is independent and magnetically removable so it does not trap either adjacent timber panel. Recess and seal exterior-grade magnets in the cover rear face.",
        ]
    )

    return ModelBuild(shape=assembly, bom=_group_bom(parts), metadata=metadata)


PRESETS: dict[str, tuple[str, PlanterConfig]] = {
    "planter-600x600x600": (
        "600 × 600 × 600 mm",
        PlanterConfig(length=600, depth=600, body_height=600, bays_x=1, panel_outer_inset=-10),
    ),
    "planter-1200x400x600": (
        "1200 × 400 × 600 mm",
        PlanterConfig(length=1200, depth=400, body_height=600, bays_x=2, panel_outer_inset=-10),
    ),
    "planter-1200x600x900": (
        "1200 × 600 × 900 mm",
        PlanterConfig(length=1200, depth=600, body_height=900, bays_x=2, panel_outer_inset=-10),
    ),
}
