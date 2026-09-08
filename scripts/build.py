from __future__ import annotations

import copy
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from build123d import Compound, Pos, export_gltf, export_step  # noqa: E402

from models.planter import build_planter  # noqa: E402


DIST = ROOT / "dist"
MODEL_DIR = DIST / "models"
DOWNLOAD_DIR = DIST / "downloads"
DATA_DIR = DIST / "data"
WEB_DIR = ROOT / "web"

# Logical-exploded offsets used by models.planter. The exported assembled model
# is reconstructed from shallow copies so no Shape instance has two parents.
BAG_EXPLODED_OFFSET = (-720.0, 0.0, 220.0)
TRAY_EXPLODED_OFFSET = (720.0, 0.0, 0.0)


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build_export_assembly(exploded_shape: Compound) -> Compound:
    """Reassemble logical exploded groups without sharing children between trees."""
    children = list(exploded_shape.children)
    if len(children) != 3:
        raise RuntimeError(
            f"Expected 3 logical exploded groups (body, bag, tray), got {len(children)}"
        )

    body, bag, tray = (copy.copy(child) for child in children)

    # Undo the logical exploded offsets. copy.copy() is intentional here:
    # build123d documents shallow Shape copies as the correct way to create
    # multiple assembly instances while keeping the same underlying CAD shape.
    bag = Pos(
        -BAG_EXPLODED_OFFSET[0],
        -BAG_EXPLODED_OFFSET[1],
        -BAG_EXPLODED_OFFSET[2],
    ) * bag
    tray = Pos(
        -TRAY_EXPLODED_OFFSET[0],
        -TRAY_EXPLODED_OFFSET[1],
        -TRAY_EXPLODED_OFFSET[2],
    ) * tray

    assembly = Compound(
        label="square-planter-600-v2-export",
        children=[body, bag, tray],
    )

    solid_count = len(assembly.solids())
    if solid_count < 20:
        raise RuntimeError(
            f"Assembled export is unexpectedly small ({solid_count} solids); refusing to publish"
        )

    return assembly


def main() -> None:
    if DIST.exists():
        shutil.rmtree(DIST)

    MODEL_DIR.mkdir(parents=True)
    DOWNLOAD_DIR.mkdir(parents=True)
    DATA_DIR.mkdir(parents=True)

    result = build_planter()

    # IMPORTANT: result.shape and result.exploded_shape were historically built
    # from shared Shape instances. A Shape can only belong to one assembly tree,
    # so constructing the exploded hierarchy re-parented children away from the
    # assembled hierarchy. Rebuild the export model from independent references.
    assembled_shape = build_export_assembly(result.exploded_shape)

    exploded_solid_count = len(result.exploded_shape.solids())
    if exploded_solid_count < 20:
        raise RuntimeError(
            f"Exploded export is unexpectedly small ({exploded_solid_count} solids); refusing to publish"
        )

    step_path = DOWNLOAD_DIR / "planter.step"
    assembled_glb_path = MODEL_DIR / "planter.glb"
    exploded_glb_path = MODEL_DIR / "planter-exploded.glb"

    export_step(assembled_shape, step_path)
    export_gltf(
        assembled_shape,
        assembled_glb_path,
        binary=True,
        linear_deflection=0.2,
        angular_deflection=0.1,
    )
    export_gltf(
        result.exploded_shape,
        exploded_glb_path,
        binary=True,
        linear_deflection=0.2,
        angular_deflection=0.1,
    )

    # File-size guard complements the topology check and catches exporter-level
    # regressions where a valid assembly would nevertheless produce a tiny GLB.
    if assembled_glb_path.stat().st_size < 100_000:
        raise RuntimeError(
            "Assembled GLB is unexpectedly small "
            f"({assembled_glb_path.stat().st_size} bytes); refusing to publish"
        )

    write_json(DATA_DIR / "bom.json", result.bom)
    write_json(DATA_DIR / "metadata.json", result.metadata)

    shutil.copytree(WEB_DIR, DIST, dirs_exist_ok=True)

    print(f"Built {step_path.relative_to(ROOT)}")
    print(
        f"Built {assembled_glb_path.relative_to(ROOT)} "
        f"({assembled_glb_path.stat().st_size} bytes)"
    )
    print(
        f"Built {exploded_glb_path.relative_to(ROOT)} "
        f"({exploded_glb_path.stat().st_size} bytes)"
    )
    print(f"Built {DATA_DIR.relative_to(ROOT)}/{{bom,metadata}}.json")
    print(f"Web site ready at {DIST.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
