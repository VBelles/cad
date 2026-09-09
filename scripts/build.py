from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from build123d import export_gltf, export_step  # noqa: E402

from models.planter_bolted_structure import (  # noqa: E402
    PRESETS as BOLTED_PRESETS,
    build_planter as build_bolted_structure,
)
from models.planter_v12 import (  # noqa: E402
    PRESETS as WELDED_PRESETS,
    build_planter as build_welded_planter,
)


DIST = ROOT / "dist"
MODEL_DIR = DIST / "models"
DOWNLOAD_DIR = DIST / "downloads"
DATA_DIR = DIST / "data"
WEB_DIR = ROOT / "web"


MODEL_SPECS: dict[str, tuple[str, object, Callable]] = {}
for model_id, (label, config) in WELDED_PRESETS.items():
    MODEL_SPECS[model_id] = (label, config, build_welded_planter)
for model_id, (label, config) in BOLTED_PRESETS.items():
    MODEL_SPECS[model_id] = (label, config, build_bolted_structure)


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    if DIST.exists():
        shutil.rmtree(DIST)

    MODEL_DIR.mkdir(parents=True)
    DOWNLOAD_DIR.mkdir(parents=True)
    DATA_DIR.mkdir(parents=True)

    manifest: list[dict[str, str]] = []

    for model_id, (label, config, builder) in MODEL_SPECS.items():
        result = builder(config, model_id=model_id)

        # Bind every metadata file to its own generated GLB. The viewer otherwise
        # falls back to ./models/planter.glb, which is intentionally just the
        # default welded 600x600 model and would make parallel variants display
        # the wrong geometry and break part selection/group explosion.
        result.metadata.setdefault("viewer", {})["model_src"] = f"./models/{model_id}.glb"

        solid_count = len(result.shape.solids())
        if solid_count < 30:
            raise RuntimeError(
                f"{model_id} export is unexpectedly small ({solid_count} solids); refusing to publish"
            )

        step_path = DOWNLOAD_DIR / f"{model_id}.step"
        glb_path = MODEL_DIR / f"{model_id}.glb"
        model_data_dir = DATA_DIR / model_id

        export_step(result.shape, step_path)
        export_gltf(
            result.shape,
            glb_path,
            binary=True,
            linear_deflection=0.2,
            angular_deflection=0.1,
        )

        if glb_path.stat().st_size < 100_000:
            raise RuntimeError(
                f"{model_id} GLB is unexpectedly small ({glb_path.stat().st_size} bytes); refusing to publish"
            )

        write_json(model_data_dir / "bom.json", result.bom)
        write_json(model_data_dir / "metadata.json", result.metadata)

        manifest.append(
            {
                "id": model_id,
                "label": label,
                "metadata": f"./data/{model_id}/metadata.json",
                "bom": f"./data/{model_id}/bom.json",
                "glb": f"./models/{model_id}.glb",
                "step": f"./downloads/{model_id}.step",
            }
        )
        print(f"Built {step_path.relative_to(ROOT)}")
        print(f"Built {glb_path.relative_to(ROOT)} ({glb_path.stat().st_size} bytes)")

    write_json(DATA_DIR / "models.json", manifest)

    default_id = "planter-600x600x600"
    shutil.copyfile(MODEL_DIR / f"{default_id}.glb", MODEL_DIR / "planter.glb")
    shutil.copyfile(DOWNLOAD_DIR / f"{default_id}.step", DOWNLOAD_DIR / "planter.step")
    shutil.copyfile(DATA_DIR / default_id / "metadata.json", DATA_DIR / "metadata.json")
    shutil.copyfile(DATA_DIR / default_id / "bom.json", DATA_DIR / "bom.json")

    shutil.copytree(WEB_DIR, DIST, dirs_exist_ok=True)
    print(f"Built {len(manifest)} planter variants")
    print(f"Web site ready at {DIST.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
