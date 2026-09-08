from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from build123d import export_gltf, export_step  # noqa: E402

from models.planter_v5 import build_planter  # noqa: E402


DIST = ROOT / "dist"
MODEL_DIR = DIST / "models"
DOWNLOAD_DIR = DIST / "downloads"
DATA_DIR = DIST / "data"
WEB_DIR = ROOT / "web"


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    if DIST.exists():
        shutil.rmtree(DIST)

    MODEL_DIR.mkdir(parents=True)
    DOWNLOAD_DIR.mkdir(parents=True)
    DATA_DIR.mkdir(parents=True)

    result = build_planter()

    solid_count = len(result.shape.solids())
    if solid_count < 30:
        raise RuntimeError(
            f"Planter export is unexpectedly small ({solid_count} solids); refusing to publish"
        )

    step_path = DOWNLOAD_DIR / "planter.step"
    glb_path = MODEL_DIR / "planter.glb"

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
            f"GLB is unexpectedly small ({glb_path.stat().st_size} bytes); refusing to publish"
        )

    write_json(DATA_DIR / "bom.json", result.bom)
    write_json(DATA_DIR / "metadata.json", result.metadata)

    shutil.copytree(WEB_DIR, DIST, dirs_exist_ok=True)

    print(f"Built {step_path.relative_to(ROOT)}")
    print(f"Built {glb_path.relative_to(ROOT)} ({glb_path.stat().st_size} bytes)")
    print(f"Built {DATA_DIR.relative_to(ROOT)}/{{bom,metadata}}.json")
    print(f"Web site ready at {DIST.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
