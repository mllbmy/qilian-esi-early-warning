# Qilian Mountain Ecological Security Early-Warning (DPSIR–GM(1,1)–GeoDetector)

Reproducible analysis pipeline for the manuscript:

> **Ecological Security Early-Warning Assessment and Driving Factors of the Qilian Mountain Region: An Integrated DPSIR–GM(1,1)–GeoDetector Framework**
>
> Author-identifying metadata (names, affiliations, e-mail) is not included in this repository: the build
> scripts read it from a local, Git-ignored module (`author_local.py`). Data, analysis code and results are unaffected.

Target journal: *Journal of Mountain Science* (Springer).

## Data sources (all openly available)

| Dataset | Source | Use |
|---|---|---|
| Climate (temperature, precipitation) | CRU TS 4.10, 2005–2023 | `data/qilian_climate.csv` (processed) |
| Land cover (30 m) | CLCD v1.0.7 (Yang & Huang), 2005, 2010, 2015, 2020, 2023 | `data/qilian_landcover.csv` + county tables (processed) |
| Elevation | Copernicus DEM 90 m | Study-area masks (`download_cop90.py`) |
| River polylines (intermediate, optional) | OpenStreetMap | `_osm_rivers.json` (re-downloadable, not committed) |

All `data/results_*.csv` are the processed intermediate results that feed the figures and the manuscript tables; every number in the figures/tables is read from these CSVs (no hand-entered values).

### Inputs not committed (re-downloadable)

`make_dem_figure.py` (Figure 1) reads two additional inputs, which are Git-ignored:

| Input | Expected path | How to obtain |
|---|---|---|
| Natural Earth 1:50m admin-1 boundaries | `data/ne/ne_50m_admin_1_states_provinces.shp` (+ `.dbf`/`.shx`/`.prj`) | Download "Admin 1 – States, Provinces" (1:50m, Cultural) from <https://www.naturalearthdata.com/downloads/> and unzip into `data/ne/` |
| River polylines (OSM export) | `data/_osm_key_rivers.json` | Export the main river lines of the study area from OpenStreetMap (e.g. via the Overpass API) as GeoJSON |

The CRU TS 4.10 netCDF grids (`data/cru/`, ~2.4 GB) are likewise Git-ignored; the processed climate table `data/qilian_climate.csv` is committed and is what the analyses actually read.

Raw inputs read by the processing scripts live outside the committed tree. Point the environment variables at your own copies if they sit somewhere else:

| Variable | Default | Used by |
|---|---|---|
| `QILIAN_LC_DATA` | `<repo>/_raw/lc_data` | `process_clcd.py`, `run_county_geodetector.py` |
| `QILIAN_CRU_DATA` | `<repo>/_raw/cru_data` | `process_cru.py`, `run_county_geodetector.py` |
| `DOT_EXE` | `dot` (on `PATH`) | `make_figs_graphviz.py` |

## Environment

- Python 3.13 (Windows; paths use `\`)
- **Path-independent**: every script resolves the project directory from its own location (`__file__`), so the repository runs unchanged from any folder or drive — no absolute path is hard-coded.
- Requires: `pandas numpy scipy matplotlib python-docx Pillow` (install as needed; scripts import only what they use)
- LaTeX: `pdflatex` + `bibtex` + `elsarticle` bundle (`.cls`/`.bst` included in this repo)

## Reproduce (run from this directory)

### Authoritative entry point and run order

`rerun_pipeline_ahp.py` is the authoritative end-to-end pipeline: from the committed inputs it regenerates the
result tables that every manuscript number is read from (`data/results_weights.csv`,
`data/results_esi_regional.csv`, `data/results_alpha_sensitivity.csv`, `data/results_forecast_comparison.csv`, ...).

The single-step `run_*.py` scripts document how each block was computed, but several of them are exploratory and
overwrite shared outputs with partial tables (for example `run_ahp_weights.py` writes a two-column AHP weights
table). Run those on a copy of `data/`, and use `rerun_pipeline_ahp.py` to reproduce the published numbers.

Reproduction of the committed CSVs is exact for the weights, regional-ESI and alpha-sensitivity tables (checked
by `git diff` after a clean clone). The forecast table may differ in the last printed digit (+/-0.0001) under a
different `statsmodels` version, because floating-point ordering in the ARIMA fits is not fixed across releases.

1. **Figures** (sources + 600-dpi PNGs into `figures/`, Git-ignored):
   ```
   python make_fig_trends.py
   python make_fig_weights.py
   python make_fig_geodetector_q.py
   python make_fig_interaction.py
   python make_fig_obstacle.py
   python make_dem_figure.py
   python make_fig_framework.py        # needs Graphviz (dot) with Times-Roman font
   python make_fig2_fig8.py
   ```
2. **Manuscript PDF** (full LaTeX chain; the `.aux` is required by step 3):
   ```
   pdflatex -interaction=nonstopmode manuscript.tex
   bibtex manuscript
   pdflatex -interaction=nonstopmode manuscript.tex
   pdflatex -interaction=nonstopmode manuscript.tex
   ```
3. **Word deliverables** (JMS submission + Chinese working copy, into `out/jms/`):
   ```
   python build_word_jms.py
   python build_word_cn.py
   ```
4. **Publication-grade figures** (TIFF ≥ 600 dpi, JMS requirement, into `jms/figures_tiff/`):
   ```
   python jms\export_tiff.py
   ```
5. **Verification** (must all pass before submission):
   ```
   python jms\verify_jms.py       # 27 checks: compliance, anchors, structure
   python verify_v12.py           # CN/EN alignment, pixel/lock checks
   python polish_gate.py          # fact-layer drift gate vs 优化\baseline snapshot
   ```

## Directory layout

- `manuscript.tex/.bib` — source of the manuscript (elsarticle, author-year)
- `data/` — processed climate, land cover, county, and result CSVs
- `*.py` — figure builders, build scripts, verification gates
- `jms/` — JMS-specific exporters and verify script; `jms/refs_jms.txt`, `keywords_jms.txt`, `declarations_jms.txt` are the submission-form source texts
- `out/`, `figures/`, `jms/figures_tiff/` — build artifacts (Git-ignored, regenerate with the steps above)

## License

- Code (`.py`, `.tex`, `.cls`, `.bst`): MIT License, see `LICENSE`.
- Processed data (`data/*.csv`): derived from public sources (CRU, CLCD, Copernicus, OSM); redistribution permitted under the upstream terms. Cite the upstream datasets in any reuse.