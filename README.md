# CAD

Parametric CAD-as-code workspace for fabrication-oriented projects.

The repository uses [build123d](https://build123d.readthedocs.io/) as the source of truth, exports STEP + GLB + JSON metadata, and publishes an interactive web viewer with GitHub Pages.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
python scripts/build.py
python -m http.server 8000 -d dist
```

Open `http://localhost:8000`.

## Repository layout

```text
models/                 Parametric CAD models and design parameters
scripts/build.py        Generates CAD and web artifacts
dist/                   Generated output (ignored by Git)
web/                    Static viewer source
.github/workflows/      CI + GitHub Pages deployment
```

## Generated artifacts

A build creates:

- `dist/models/planter.glb` — web visualization
- `dist/downloads/planter.step` — precise CAD exchange model
- `dist/data/bom.json` — bill of materials
- `dist/data/metadata.json` — model dimensions and semantic metadata

`dist/` is generated and must not be edited manually.

## First model

`models/planter.py` is intentionally a simple parametric planter/trellis reference model. It is not yet a final fabrication design; its purpose is to establish the CAD → artifacts → web pipeline before the real planter geometry and joints are iterated.
