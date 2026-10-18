# Qilian Mountain Ecological Security Early-Warning (DPSIR–GM(1,1)–GeoDetector)

Reproducible analysis pipeline for the manuscript:

> **Ecological security early warning in the Qilian Mountain region, China: temporal dynamics, forecasts, and spatial drivers**

Author-identifying metadata (names, affiliations, e-mail) is not included in this repository: the build
scripts read it from a local, Git-ignored module (`author_local.py`). Data, analysis code and results are unaffected.

Target journal: *Journal of Mountain Science* (Springer).

> **R22 reproducibility hardening (2026-10-04).** This README was rewritten so that a reviewer can follow it
> end to end. The core claims below have been re-verified on the raw data: CLCD land-cover sampling
> 1914/1914 points identical, climate→ESI identical to 4 stored decimals (19/19 regional, 11/11 county),
> county ESI from a direct CLCD read identical to the archived table (max |Δ| = 0). §9.1 lists the inputs
> that sit outside this repository.

---

## 0. TL;DR — the three one-shot self-checks

```powershell
cd <this-repo>
python run_clcd_verify.py     # CLCD land-cover chain   → expect: 一致率 1914/1914 = 100.00%, 判定: PASS
python run_cru_verify.py      # CRU climate → ESI chain → expect: 19/19 & 11/11 identical at 4 dp
python data_audit.py          # manuscript numbers ↔ data/*.csv → expect: 结论：65 项全部找到
```

Expected output of the two verification scripts (frozen numbers):

| check | expected |
|---|---|
| CLCD raster integrity | bytes `810739687`, md5 `1274285BB18F9B1D443A3CC906B1310C` |
| CLCD point sampling vs `data/spatial_samples.csv` | **1914 / 1914 = 100.00 %** identical, category counts all identical |
| County land-cover (±0.1° centroid window) vs `data/qilian_county_landcover.csv` | max \|Δ\| = **0.000000** pp |
| CRU monthly completeness 2005-01…2023-12 | **228 / 228 months, 0 missing, 0 duplicated** |
| Rebuilt climate series vs `data/qilian_climate.csv` (228 rows) | precip max \|Δ\| = **5.684e-14 mm**, temp max \|Δ\| = **8.882e-16 °C**, 228/228 rows \|Δ\| < 1e-10 |
| Rebuilt regional ESI vs `data/results_esi_regional.csv` | max \|Δ\| = **4.675e-05**; **identical to 4 dp 19/19**; peak year **2010**; warning levels identical |
| Rebuilt county ESI vs `data/results_county_esi.csv` | max \|Δ\| = **4.600e-05**; **identical to 4 dp 11/11**; Aksai stays 0.067 |
| direct CLCD → county ESI vs `data/results_county_esi.csv` | max \|Δ\| = **0.000000** |
| every manuscript number vs `data/*.csv` (`data_audit.py`, tolerance 0.003) | **65 / 65 found** |

The 4–5 × 10⁻⁵ residuals are **not** model error: the archived CSVs store 4 decimals (max rounding error 5e-5).
`run_cru_verify.py` proves this with a control experiment (archived climate in → 4.675e-05; rebuilt climate in → 1.110e-16).

The md5 snapshot tooling used while the archives were frozen (`_hardening_backup/snapshot_md5.py`) is not part
of this repository; the md5 values it recorded are reproduced verbatim in §7.3 and §7.4, and §6 records what
changed in the code.

---

## 1. Data preconditions (what a reviewer must obtain)

Nothing in `§1.2` or `§1.3` is committed; `_raw/` and `data/cru/` are Git-ignored because of size/licence.
`data/*.csv` (the **processed** tables that feed every figure and table number) **are** committed.

### 1.1 Committed processed tables — no action needed

`data/*.csv`, in particular: `qilian_climate.csv`, `qilian_landcover.csv`, `qilian_county_landcover.csv`,
`results_weights.csv`, `results_esi_regional.csv`, `results_alpha_sensitivity.csv`,
`results_forecast_comparison.csv`, `results_county_esi.csv`, `results_county_esi_details.csv`,
`spatial_samples.csv`, `spatial_esi_points.csv`, `results_geodetector_pvalues.csv`,
`results_geodetector_exogenous.csv`, `results_geodetector_loo.csv`, `results_interaction_detector.csv`,
`results_obstacle.csv`, `results_indicators.csv`, `results_ahp_criteria.csv`, `results_ahp_consistency.csv`,
`ahp_weights.csv`, `_aux_terrain_points.csv`.

### 1.2 CLCD v1.0.7 land cover, 30 m (required for `run_clcd_verify.py`, `run_county_geodetector.py`, `process_clcd.py`)

| item | value |
|---|---|
| product | **CLCD v01** (Yang & Huang, *ESSD* 2021), 30 m, Albers equal-area (`lon_0=105°`, `sp=25°/47°`) |
| record | CLCD 2020 tile used here: Zenodo record **8176941** — <https://zenodo.org/records/8176941>; the full 1985–2023 annual collection cited by the manuscript is Zenodo record **12779975** — <https://doi.org/10.5281/zenodo.12779975> (CC-BY-4.0, accessed 2026-10-07) |
| file | `CLCD_v01_2020_albert.tif` |
| expected bytes | **810,739,687** |
| expected md5 | **1274285BB18F9B1D443A3CC906B1310C** |
| expected path | `<repo>/_raw/lc_data/CLCD_v01_2020_albert.tif` (override with `QILIAN_LC_DATA`) |

Class codes used: `1` cropland, `2` forest, `3` shrub, `4` grassland, `5` water, `6` snow/ice,
`7` barren, `8` impervious, `9` wetland, `0` nodata.

> Historical epochs (2005/2010/2015/2020/2023) are needed **only** to regenerate `data/qilian_landcover.csv`
> (the five-epoch regional table used by the nine-indicator matrix). See §9.1 item A below.

### 1.3 CRU TS 4.10 climate grids (required for `process_cru.py`, `run_county_geodetector.py`, `run_exogenous_geodetector.py`)

| item | value |
|---|---|
| product | CRU TS 4.10 monthly, 0.5° (lat 360 × lon 720), NetCDF3 classic |
| source | <https://crudata.uea.ac.uk/cru/data/hrg/cru_ts_4.10/cru_ts4.10.1901.2025/> |
| expected path | `<repo>/data/cru/` (override with `QILIAN_CRU_DATA`) |

| file | bytes | md5 |
|---|---|---|
| `cru_ts4.10.2001.2010.pre.dat.nc` | 497,670,564 | `1744ae57933198b09245ae9c93c9721d` |
| `cru_ts4.10.2001.2010.tmp.dat.nc` | 497,670,584 | `e3c68a9acb6393cd14babdc7a9f75188` |
| `cru_ts4.10.2011.2020.pre.dat.nc` | 497,670,564 | `89e10b4c2ab3741bb2ceeb619ccbd4d3` |
| `cru_ts4.10.2011.2020.tmp.dat.nc` | 497,670,584 | `1e8967a7a5d86f78e0caad57ff75601a` |
| `cru_ts4.10.2021.2025.pre.dat.nc` | 248,838,324 | `b2cc7093f47e69a391c1e2e3c3b6455e` |
| `cru_ts4.10.2021.2025.tmp.dat.nc` | 248,838,344 | `9b11c013272a5b6a0676d1a27b5c261d` |

`cru_ts4.10.1901.1910.pre.dat.nc.gz` is **unused** (outside the study period, precipitation only, and
excluded by the `process_cru.py` filename whitelist).

### 1.4 Optional inputs (figure 1 only)

| input | expected path | how to obtain |
|---|---|---|
| Copernicus DEM GLO-90 tiles | `data/cop90/` | `python download_cop90.py` (AWS S3, re-downloadable) |
| Natural Earth 1:50m admin-1 boundaries | `data/ne/ne_50m_admin_1_states_provinces.shp` (+ `.dbf`/`.shx`/`.prj`) | <https://www.naturalearthdata.com/downloads/> → "Admin 1 – States, Provinces", 1:50m, unzip into `data/ne/` |
| Qilian National Park outline | `data/qmn_park_digitized.geojson` | **committed** |
| Lake outlines | `data/lakes_region.json` | **committed** |

---

## 2. Environment

Verified working combination (this is the configuration the numbers below were produced with):

| component | version |
|---|---|
| OS / Python | Windows 11 / **Python 3.13.9** |
| numpy | 2.4.3 |
| pandas | 2.3.3 |
| scipy | 1.17.1 |
| xarray | 2026.7.0 |
| netCDF4 | 1.7.4 |
| rasterio | 1.5.1 |
| pyproj | 3.7.2 |
| matplotlib | 3.11.1 |
| statsmodels | 0.14.6 |
| python-docx | 1.2.0 |
| pillow | 12.3.0 |
| LaTeX | MiKTeX-pdfTeX 4.23 (MiKTeX 25.12), `elsarticle` bundle (`.cls`/`.bst` in-repo) |

```powershell
python -m pip install numpy pandas scipy xarray netCDF4 rasterio pyproj matplotlib statsmodels python-docx pillow pyshp
```

- No output path is hard-coded and no input path is machine-specific: every script resolves the project
  directory from `__file__` and writes inside the repository (or into the Git-ignored `out/` /
  `figures/` / `reports/` trees). The one external **input** that a cold clone lacks — the GADM boundary
  file read by `run_county_support_sensitivity.py` — is now resolved from the `QILIAN_GADM` environment
  variable, falling back to `data/gadm41_CHN_3.json` inside the repository (§9.1 item F).
- **Windows note:** `pdflatex` is available, but **Perl is not** — do **not** use `latexmk`, run `pdflatex` directly (see §3).
- **Non-ASCII path note:** see §5, item 1. If the clone lives under a CJK path (e.g. `<含中文的目录>/<repo>`),
  that is exactly the case the engine fallback was written for.

---

## 3. Exact run order

All commands are run **from the repository root** `<repo>` = `paper-code/`.
CSV reading is done with `encoding="utf-8-sig"` throughout (files carry a BOM).

### Stage 0 — self-checks (read-only, ~3.5 min, no output overwritten)

```powershell
python run_clcd_verify.py     # ~170 s: raster md5/bytes, national class areas, 1914-point rebuild, county windows
python run_cru_verify.py      # ~30 s : CRU inventory, 228-month completeness, climate+ESI rebuild
```

New files (`data/cru_verify_*.csv`, `data/results_clcd2020_*.csv`). **No committed file is touched.**

### Stage 1 — raw data → processed climate and land-cover tables

```powershell
# CRU TS 4.10 -> data/qilian_climate.csv (12 units x 19 years = 228 rows)
# byte-identical reproduction of the committed file (md5 1BA81D5502EF4A769E5D10B1A3C1CCC2 verified)
python process_cru.py
```

`process_clcd.py` is **guarded**: it refuses to overwrite `data/qilian_landcover.csv` unless all five
CLCD epochs (2005/2010/2015/2020/2023) are present, redirecting to
`data/results_landcover_partial_<years>.csv` otherwise (§9.1 item A).

```powershell
python process_clcd.py           # needs the 5 CLCD epochs; otherwise writes a *_partial_* file
python run_county_geodetector.py # CLCD + CRU -> data/qilian_county_landcover.csv (protected!)
```

> `run_county_geodetector.py` **overwrites** `qilian_county_landcover.csv`, `spatial_samples.csv`,
> `spatial_esi_points.csv` and creates `results_county_esi_from_clcd.csv`. Its outputs were verified
> byte-identical to the committed files (see §7.2). Back up `data/` first if you only want to inspect:
> `Copy-Item data\*.csv _hardening_backup\data\ -Force`.

### Stage 2 — AHP weights and the authoritative regional pipeline

```powershell
python run_ahp_weights.py        # criterion matrix -> data/ahp_weights.csv, results_ahp_criteria.csv,
                                 #                   results_ahp_consistency.csv
python rerun_pipeline_ahp.py     # *** AUTHORITATIVE *** end-to-end pipeline
```

`rerun_pipeline_ahp.py` regenerates these tables on this machine (exactness in §7.2):

| file | note |
|---|---|
| `data/results_esi_regional.csv` | regional ESI 2005–2023 + GM(1,1) forecast + warning levels |
| `data/results_weights.csv` | entropy / AHP / combined (α = 0.4) weights of the 9 indicators |
| `data/results_alpha_sensitivity.csv` | α ∈ [0, 1] sensitivity, 0.1 step |
| `data/results_forecast_comparison.csv` | GM(1,1) / NGBM / ARIMA 2024–2028 |

Verified in a clean sandbox: `max |Δ| = 0.0` for the first three files (11-decimal exactness);
`≤ 1e-4` for the forecast table (statsmodels ARIMA last-digit drift, documented).

### Stage 3 — county ESI and spatial attribution

```powershell
python run_county_esi.py                  # data/results_county_esi.csv (+ _details.csv) — Table 6 source
python run_geodetector_pvalues.py         # q and permutation p for 4 single factors + 6 pairs
python run_exogenous_geodetector.py       # Fig. 8b exogenous q (precip/temp/elev/slope)
python run_interaction_detector.py        # interaction detector
python run_geodetector_loo.py             # leave-one-out GeoDetector
python run_robustness_loo_indicators.py   # indicator-overlap robustness (writes results_robustness_loo_indicators.csv)
python run_forecast_comparison.py         # results_forecast_accuracy.csv + results_forecast_ci.csv
                                          # (also rewrites results_forecast_comparison.csv, see §9.2 item 2)
```

### Stage 4 — figures (into `figures/`, Git-ignored)

> **Note 2026-10-17:** `figures/` stays Git-ignored for regenerated outputs, but the **ten figure PDFs that
> `manuscript.tex` includes are now tracked** (force-added against `.gitignore`) so that a clone compiles the
> manuscript without running Stage 4 first. See §9.1 item D. Re-running any Stage 4 step rewrites the tracked
> files in place; `git status` will then show them as modified.

```powershell
# Fig. 1  study area      -> figures/fig1_study_area.pdf
python download_cop90.py          # only if data/cop90/ is absent
python make_dem_figure.py         # needs data/ne/ (§9.1 item B), data/cop90/, data/lakes_region.json

# Fig. 2  DPSIR framework -> figures/fig_dpsir_framework.pdf   (authoritative: make_fig2_redesign.py)
python make_fig2_redesign.py      # authoritative for Fig. 2; figures/fig_dpsir_framework.dot remains the semantic baseline
#         beautify_framework.py (v18) and make_fig_framework.py write the SAME filename and are superseded —
#         running either one after make_fig2_redesign.py overwrites the Fig. 2 that manuscript.tex includes.

# Fig. 3  indicator trends -> figures/fig_indicator_trends.pdf (+ rewrites data/results_indicators.csv)
python make_fig_trends.py

# Fig. 4  ESI time series + forecast -> figures/fig3_esi_timeseries.pdf
python make_fig3_clean.py

# Fig. 5  alpha sensitivity -> figures/fig4_alpha_sensitivity.pdf
python make_figures.py            # produces fig4_alpha_sensitivity.* and fig5_spatial_esi.png

# Fig. 6  indicator spatial maps -> figures/fig_spatial_maps.pdf   (§9.1 item C)
#         make_fig_indicator_maps.py writes 投稿前优化\图件\定稿\Fig06_indicator_spatial_final.{pdf,png}
#         — the file actually included by manuscript.tex (figures/fig_spatial_maps.pdf) has NO generator in this repo.

# Fig. 7  weights -> figures/fig_weights.pdf
python make_fig_weights.py

# Fig. 8  single-factor q -> figures/fig_geodetector_q.pdf   (v2 is the version used, 2 panels)
python make_fig_geodetector_q_v2.py     # run AFTER run_geodetector_pvalues.py / run_exogenous_geodetector.py

# Fig. 9  interaction -> figures/fig_interaction.pdf
python make_fig_interaction.py

# Fig. 10 obstacle degree -> figures/fig_obstacle.pdf
python make_fig_obstacle.py
```

### Stage 5 — manuscript PDF (English)

**Canonical order — always run all four steps.** `bibtex` regenerates the bibliography, so this sequence is
correct whether or not `manuscript.bbl` is present, and it is required whenever `manuscript.bib` or the
citation set changes:

```powershell
pdflatex -interaction=nonstopmode -halt-on-error manuscript.tex   # pass 1 -> manuscript.aux (citation keys)
bibtex manuscript                                                 # pass 2 -> manuscript.bib -> manuscript.bbl
pdflatex -interaction=nonstopmode -halt-on-error manuscript.tex   # pass 3 -> typesets the fresh .bbl
pdflatex -interaction=nonstopmode -halt-on-error manuscript.tex   # pass 4 -> resolves \ref/\label and \bibcite
```

Expected: every pass exits `0`; the final pass reports **0 `LaTeX Warning`** and **22 pages**,
`manuscript.pdf` 10,340,644 B (the 2.0 manuscript adds the Table 1 terrain row and the leave-one-target /
fractional-cover sentences, which pushed the build from 21 to 22 pages).

Measured chain, empty directory, current source (`manuscript.tex` md5
`AF55563B0C27ADE689F32FECAA891BA3`, `manuscript.bib` md5 `143E9487E76878FFA1AB78D0F555E429`); every pass
exits `0`:

| step | pages | bytes | `Citation … undefined` | undefined `\ref` | `LaTeX Warning` | `Label(s) may have changed` |
|---|---|---|---|---|---|---|
| pass 1 `pdflatex` | 19 | 10,329,520 | 49 (24 distinct keys) | 26 | 28 | yes |
| `bibtex manuscript` | — | `.bbl` 13,026 B, md5 `F89C9CDE0354B9D2ECD2F1A535C6DBD3` | — | — | — | — |
| pass 2 `pdflatex` | 21 | 10,340,763 | 49 (24 distinct keys) | 0 | 0 | no |
| pass 3 `pdflatex` | 22 | 10,340,644 | 0 | 0 | 1 | yes |
| pass 4 `pdflatex` | 22 | 10,340,644 | 0 | 0 | 0 | no |

- **Two `pdflatex` passes alone are not enough.** With no `manuscript.bbl`, pass 1 gives **19 pages** with 49
  `Citation … undefined` warnings over 24 distinct keys (plus 26 undefined `\ref`); pass 2 clears the `\ref`
  warnings and resolves nothing else, so all 49 citation warnings remain and the bibliography is silently
  missing — 19 pages, not 22. (The value previously recorded here, "45 undefined references", did not
  reproduce; the measured count is 49 natbib warning occurrences over 24 distinct keys.)
- Pass 2 of the sequence above grows the document to 21 pages — the bibliography now typesets — and still
  warns about all 24 keys, because `\bibcite` is written into `manuscript.aux` only **during** that pass.
- Pass 3 reaches the final **22 pages / 0 undefined** but still prints
  `LaTeX Warning: Label(s) may have changed. Rerun to get cross-references right.`; pass 4 is the first
  fully clean log. `Overfull \hbox` 1 and `Underfull \hbox` 2 appear in **every** pass from pass 1 on — they
  are pre-existing and are not symptoms of an unresolved build.

**`manuscript.bbl` is now tracked** — added 2026-10-17 with `git add -f` (`.gitignore` line 31, `*.bbl`,
still lists it, hence the forced add), 13,026 B, md5 `F89C9CDE0354B9D2ECD2F1A535C6DBD3`. A cold clone
therefore carries the bibliography and compiles **without** `bibtex`; measured on a cold clone: pass 1 →
21 pages, pass 2 → **22 pages, 0 undefined** (`Citation` and `\ref` both 0), with the same
`Label(s) may have changed` note in pass 2 that a third pass clears. Keep `bibtex` in the recipe anyway: it is
what makes the build independent of the committed `.bbl` and it is mandatory as soon as the bibliography
changes.

> **Trap — verify in an empty directory, never inside the repository.** `pdflatex -output-directory=<dir>`
> redirects only where files are **written**; TeX still **reads** `manuscript.aux` (and `manuscript.bbl`) from
> the current, i.e. repository, directory. Measured: a directory holding `manuscript.tex`/`.bib` plus a stale
> `manuscript.aux` carrying 24 `\bibcite` entries and **no `.bbl` at all**, compiled with
> `-output-directory=out`, exits `0`, reports **0 undefined citations and 0 undefined `\ref`** and writes
> **20 pages** — it silently resolved every citation from the old aux instead of building the bibliography.
> A build inside the repository therefore cannot validate the source. Export to an empty directory first
> (`git archive --format=tar -o head.tar HEAD`, unpack, then run the sequence above); the first build in a
> fresh directory needs the extra pass to clear `Label(s) may have changed`.

### Stage 6 — Word deliverables (JMS submission + Chinese working copy)

```powershell
python build_word_jms.py     # out/jms/ ... (author identity comes from author_local.py; neutral placeholders if absent)
python build_word_cn.py      # out/论文_CN_latest.docx — the Chinese-manuscript entry point
python jms\export_tiff.py    # jms/figures_tiff/ — TIFF ≥ 600 dpi, JMS requirement
```

`build_word_cn.py` is the committed Chinese-manuscript entry point. A local `build_word_cn_final.py`
exists on the author's machine but is an **outdated snapshot** and is not part of this repository; it is
not a supported way to produce the Chinese manuscript (§9.1 item E).

### Stage 7 — submission gates

```powershell
python jms\verify_jms.py     # 30 checks (compliance, anchors, structure)  → verified PASS
python verify_v12.py         # CN/EN alignment, pixel/lock checks          → needs 交付\投稿材料\ (§9.1 item B)
python data_audit.py         # every key number in the text found in data/*.csv → verified PASS (65/65)
python polish_gate.py        # fact-layer drift gate vs 优化\baseline snapshot  → needs 优化\baseline (§9.1 item B)
```

---

## 4. Traceability: every manuscript number → script → CSV

| manuscript item | value(s) | produced by | read from |
|---|---|---|---|
| Table 1 data sources | 2005–2023, CRU TS 4.10 + CLCD 30 m | — (descriptive) | — |
| Table 2 DPSIR indicator system | 9 indicators, directions | — (descriptive) | `data/results_weights.csv` (`direction` column) |
| Table 3 criterion AHP matrix + weights | Driving/Pressure 0.081385, State 0.438373, Impact 0.148627, Response 0.250231 | `run_ahp_weights.py` | `data/results_ahp_criteria.csv` |
| Table 3 consistency | λmax = 5.015284, CI = 0.003821, RI = 1.12, **CR = 0.003412** | `run_ahp_weights.py` (hard-coded 5×5 Saaty matrix in the script) | `data/results_ahp_consistency.csv` |
| Table 4 indicator weights | entropy / AHP / combined, α = 0.4 | `rerun_pipeline_ahp.py` (reads `ahp_weights.csv`) | `data/results_weights.csv` |
| Fig. 7 weight bar chart | same as Table 4 | `make_fig_weights.py` | `data/results_weights.csv` |
| Table 5 forecast comparison | GM(1,1) / NGBM / ARIMA, RMSE/MAE/C/P | `rerun_pipeline_ahp.py` (+ `run_forecast_comparison.py` for `results_forecast_accuracy.csv`) | `data/results_forecast_comparison.csv`, `data/results_forecast_accuracy.csv` |
| Fig. 4 ESI series + forecast | ESI 2005–2023, forecast 2024–2028, warning bands | `make_fig3_clean.py` | `data/results_esi_regional.csv`, `data/results_forecast_comparison.csv`, `data/results_forecast_ci.csv` |
| Fig. 5 α sensitivity | 2023 ESI vs α | `make_figures.py` | `data/results_alpha_sensitivity.csv` |
| **Table 6 static county ESI (2020)** | Sunan 0.5578 … Aksai 0.0673 | **`run_county_esi.py`** | `data/results_county_esi.csv` (`_details.csv` = intermediate) |
| Fig. 6 indicator spatial maps | precip/temp fields, 2020 grass/forest/barren, point ESI | `make_fig_indicator_maps.py` (§9.1 item C) | `data/spatial_samples.csv`, `data/spatial_esi_points.csv` |
| Fig. 8b exogenous q | precip 0.506, temp 0.170, elev 0.090, slope 0.065 | `run_exogenous_geodetector.py` | `data/results_geodetector_exogenous.csv` |
| Fig. 8a compositional q | barren 0.802, grass 0.708, precip 0.506, temp 0.170 | `run_geodetector_pvalues.py` (+ `run_county_geodetector.py` for the point ESI) | `data/results_geodetector_pvalues.csv` |
| Table 7 / Fig. 9 interaction | q for 6 factor pairs, all enhancing | `run_interaction_detector.py` | `data/results_interaction_detector.csv` |
| Fig. 10 obstacle degree | 9 indicators × 19 years, sum = 1 | (committed input table; no generator script in this repo) | `data/results_obstacle.csv` |
| Supporting §: point-scale ESI | 1914 grid points, 2020 | `run_county_geodetector.py` | `data/spatial_esi_points.csv` |
| Supporting §: indicator trends | 9 indicators × 19 years | `make_fig_trends.py` | `data/results_indicators.csv` |
| Supporting §: leave-one-out | Δq for each factor | `run_geodetector_loo.py` | `data/results_geodetector_loo.csv` |
| Supporting §: indicator-overlap robustness | reweight / merge scenario ESI | `run_robustness_loo_indicators.py` | `data/results_robustness_loo_indicators.csv` |
| §4.x 3×3 window / multi-scale window caveats | ±0.05/0.1/0.2/0.3° | `run_county_window_sensitivity.py` | `data/results_county_window_*.csv` |
| §4.x polygon-vs-point support | ESI by support type | `run_county_support_sensitivity.py` | `data/results_county_support_sensitivity.csv`, `results_county_window_truncation.csv`, `results_county_window_vs_polygon.csv` |

`data/results_backtest.csv`, `results_moran.csv`, `results_trend_test.csv` are auxiliary / historical
tables kept for provenance.

### 4.1 Numbers added in the 2.0 manuscript → output file → generating script

Added by the R23 round (leave-one-target attribution, strictly exogenous control, fractional-cover
recheck, centroid-window sensitivity). Every value below is read from a committed CSV at run time;
none of them is hard-coded in the manuscript or in the scripts.

| manuscript value (2.0) | value(s) | produced by | read from |
|---|---|---|---|
| Leave-one-target $q$ (abstract, §4.5, §6) | barren/degraded 0.802431 → 0.711426; precipitation 0.506016 → 0.381115; grassland 0.707710 → 0.366430; temperature 0.169739 → 0.273763 (all $p=0.001$) | `run_geodetector_loo.py` | `data/results_geodetector_loo.csv` (variant `loo_primary`) |
| Fractional-cover leave-one-target $q$ (§5.4) | grassland 0.584235 → 0.282836 (−51.59 %); barren/degraded 0.838492 → 0.691006 (−17.59 %); precipitation 0.600399 → 0.462091; temperature 0.178157 → 0.302838 (all $p=0.001$) | `run_fractional_cover_loo.py` | `data/results_fractional_cover_loo.csv` (scheme `fractional_sigma1`) |
| Point-scale sparse-class weight share (§5.4: "forest (15 samples) and water (34 samples) together carry 0.609 … 2.6 % of the samples carry 60.9 %") | forest combined weight **0.326387** + water **0.282556** = **0.608943**; sparse-class samples 15 + 34 = **49** of 1 914 = **2.5601 %** | **derived, not written by any generator** — recomputed with `eco_security.eco_security.minmax_normalize` + `entropy_weights` over the six point-scale ESI inputs (`temp`, `precip`, `grass`, `forest`, `water`, and `barren_neg = 1 − grass − forest − water`), AHP weights equal across the six, combination weight $\alpha=0.4$ | `data/spatial_samples.csv` (inputs and sample counts); the reconstructed point ESI matches the committed `data/spatial_esi_points.csv` to $1.2\times10^{-14}$. **No committed CSV stores the weight sum itself** |
| $r$(grassland, barren) = −0.884 as window-area fractions (§5.4) | −0.8836 | `run_fractional_cover_loo.py` | `data/results_fractional_cover_points.csv` |
| `barren/degraded` factor vs the `barren_neg` ESI input differ at 81 points (§3.5) | 81 = 75 cropland + 6 snow/ice | `run_geodetector_loo.py` | `data/spatial_samples.csv` |
| Terrain $q$: elevation 0.0904, slope 0.0647 (Fig. 8b, §4.5) | 0.090367 / 0.064680 | `run_exogenous_geodetector.py` | `data/results_geodetector_exogenous.csv` |
| Indicator-overlap (leave-one-indicator) robustness (§5.4) | baseline vs reduced indicator sets | `run_robustness_loo_indicators.py` | `data/results_robustness_loo_indicators.csv` |
| Four centroid windows ±0.05/0.10/0.20/0.30° (§5.4) | Spearman vs the ±0.10° baseline 0.6818 / 0.5091 / 0.4909; 1 of 11 counties keeps its rank; 7 of 11 span ≥ 3 positions; Delingha 1 → 4 → 10 → 9 | `run_county_window_sensitivity.py` | `data/results_county_window_multiscale.csv`, `data/results_county_window_stability.csv` |
| Gangcha water fraction by window (§5.4) | ±0.10° 0.046 %, ±0.20° 16.29 %, ±0.30° 24.17 % | `run_county_window_sensitivity.py` | `data/results_county_window_landcover.csv` |
| County-ESI support definition / window truncation | three support definitions (A/B/C), truncation shares | `run_county_support_sensitivity.py` | `data/results_county_support_sensitivity.csv`, `data/results_county_window_truncation.csv`, `data/results_county_window_vs_polygon.csv` |
| Table 6 static county ESI (2020) | Sunan 0.5578 … Aksai 0.0673 | `run_county_esi.py` | `data/results_county_esi.csv` |

Remaining committed intermediates behind the 2.0 numbers: `data/results_fractional_cover_windows.csv`,
`data/results_county_point_support_check.csv`, `data/results_county_window_weights.csv`,
`data/_aux_terrain_points.csv` (the Copernicus DEM samples behind Fig. 8b and
`run_exogenous_geodetector.py`), and the self-check outputs `data/cru_verify_*.csv` /
`data/results_clcd2020_*.csv`.

### 4.2 R28 sensitivity tables (`data/r28_*.csv`, 43 files)

Every number added in the R28 revision comes from one of these files, all of which are
produced by the 20 committed generators `run_r28_*.py` (shared helpers `r28_core.py`,
`r28_trend.py`). They are the traceability layer for the de-redundancy section, the
five validation schemes, the bootstrap intervals, the mechanical-share evidence, the
independent-target check and the six Appendix tables. Run order: `run_r28_t1` →
`run_r28_t8`, then the `run_r28_*` refinement scripts in any order.

| File | One-line purpose |
|---|---|
| `r28_identity_recheck.csv` | Residuals of the three exact identities (X9, X8, X6) against the archived series |
| `r28_identity_series.csv` | Year-by-year residual series behind those identities |
| `r28_deredundancy_comparison.csv` | Six indicator specifications: rank correlation, max year-wise difference, peak year, grade changes, 2023 value/grade |
| `r28_deredundancy_series.csv` | The year-by-year ESI and grade series of those six specifications |
| `r28_interp_weight_sensitivity.csv` | Entropy/AHP/combined weights under four interpolation schemes of the five land-cover epochs |
| `r28_esi_decomposition.csv` | Exact decomposition ΔESI = Σ w_j Δx′_j by segment, indicator and DPSIR layer |
| `r28_esi_variance_decomposition.csv` | Point-scale variance shares (land-cover block 0.93 vs climate block 0.07) |
| `r28_esi_leakage_channel.csv` | Effect of the second leakage channel (full-period normalisation and entropy weights) on model ranking |
| `r28_ngbm_gamma_curve.csv` | γ grid with training-period, full-series and holdout SSE/RMSE (leakage diagnostic) |
| `r28_ngbm_gamma_leakage.csv` | Selected γ and resulting accuracy under each γ-selection window and index construction |
| `r28_rolling_origin.csv` | Rolling one-step (from 2013 and 2015) and five-step summary accuracy of the three models |
| `r28_rolling_origin_detail.csv` | Fold-level observations, predictions and errors behind the rolling-origin runs |
| `r28_loocv.csv` | Leave-one-out cross-validation summary for the three models |
| `r28_loocv_detail.csv` | Fold-level leave-one-out details |
| `r28_forecast_uncertainty.csv` | Bootstrap 95% intervals for 2024–2028 under parameter-only, iid-innovation and block-innovation scopes |
| `r28_grade_probabilities.csv` | Five-grade probability of each forecast year under each model and uncertainty scope |
| `r28_threshold_perturbation.csv` | Grade migration over the eight ±0.05 threshold-perturbation scenarios |
| `r28_threshold_sensitivity.csv` | Effect of moving a single threshold on the 2023 and 2028 grades |
| `r28_alpha_grade_matrix.csv` | Full 11 × 19 α matrix of ESI values and grades for both specifications |
| `r28_alpha_grade_summary.csv` | Grade composition, number of changed years and rank correlation against α = 0.4 |
| `r28_temperature_direction.csv` | Year-by-year ESI and grade with temperature positive, negative and dropped |
| `r28_trend_tests.csv` | Mann–Kendall, Hamed–Rao, TFPW, Sen slope and CI for every specification and segment |
| `r28_trend_break.csv` | Pettitt change point and segmented trends per specification |
| `r28_moran_k_sensitivity.csv` | Moran's I and permutation p over 36 spatial weight definitions (k = 4–50, three distance schemes) |
| `r28_spatial_weights.csv` | Moran's I, mean neighbours and residual R² per weight matrix |
| `r28_stratification_sensitivity.csv` | Six stratification schemes × each factor: level counts, stratum sizes, q stability |
| `r28_sampling_sensitivity.csv` | 200 bootstrap replicates and 1,500/1,000-point subsamples: q distribution and ranking stability |
| `r28_exogenous_recheck.csv` | Strictly exogenous factors (elevation, slope): stratified q, joint q, OLS R² and partial correlations |
| `r28_blockwise_q_matrix.csv` | Block-wise cross-detection q matrix used for the mechanical-share shares |
| `r28_forest_small_sample.csv` | Forest factor (15 dominant points): degenerate stratification, binary/zero-inflated q and intervals |
| `r28_interaction_uncertainty.csv` | Six factor pairs: interaction q, mechanical share and permutation excess |
| `r28_pointscale_complement.csv` | Point-scale barren/degraded complement and the 81 cropland- or snow-dominated samples it misclassifies |
| `r28_external_ndvi_points_2020.csv` | Independent target: growing-season NDVI at the 1,914 points, 2020 (NOAA CDR AVHRR/VIIRS) |
| `r28_external_ndvi_annual.csv` | Independent target: regional annual growing-season NDVI, 2005–2023 |
| `r28_external_ndvi_annual_commonmask.csv` | The same annual series under a common clear-pixel mask (sensor-continuity control) |
| `r28_external_ndvi_point_trends.csv` | Point-level NDVI trends and their correlation with the static 2020 index |
| `r28_external_ndvi_manifest.csv` | The 133 NOAA CDR source files with URL, version and access date (reproducible download list) |
| `r28_external_validation.csv` | Independent-target summary: spatial r/ρ, two-way stratified q, NDVI-target attribution and interannual correlation |
| `r28_obstacle_formula_check.csv` | Obstacle-degree formula check (row sums = 1) per indicator and year |
| `r28_obstacle_sensitivity.csv` | Obstacle degrees under four weighting schemes, two phases, with ranks and leading-obstacle years |
| `r28_county_uncertainty.csv` | County ranking across the 64 window × weight × source configurations, rank spans and area weighting |
| `r28_county_window_audit.csv` | Pixel counts and class shares per window half-width (water entering and leaving the Qinghai Lake window) |
| `r28_cru_box_sensitivity.csv` | Three climate boxes (current, declared domain, cosine-weighted) compared year by year |

---

## 5. Frozen conventions and traps (read before trusting a number)

1. **CJK path breaks the netCDF4 engine.** xarray's default backend is netCDF4/HDF5, whose C library cannot
   open paths containing non-ASCII characters; it raises
   `FileNotFoundError: [Errno 2] No such file or directory: '...\<CJK 目录>\...'` although the file exists.
   CRU TS 4.10 is NetCDF3 classic, so the **scipy** engine (pure Python) works. All scripts now go through
   `io_utils.open_netcdf()`, which tries `netcdf4 → scipy → h5netcdf → xarray default` and returns the first
   engine that succeeds, raising a combined error with every engine's message if all fail.
   `data/cru_verify_env_and_notes.csv` records the engine actually used (`scipy` on this machine).
2. **Data-directory fallback.** The documented default `_raw/cru_data` does not exist here. `io_utils`
   resolves, in order: `QILIAN_CRU_DATA` → `<repo>/_raw/cru_data` → `<repo>/data/cru` → bounded recursive
   search; likewise `QILIAN_LC_DATA` → `<repo>/_raw/lc_data` → recursive search. **No environment variable
   needs to be set** for the default layout.
3. **Study period is 2005–2023 (19 years).** `run_esi_regional.py` sets
   `YEARS = list(range(2005, 2024))`. The `2001` / `2025` in the CRU filenames are just NetCDF segment
   boundaries, not the study period.
4. **Two AHP conventions apply at different scales.**
   * **Regional (9 indicators)** uses the **real criterion-level judgement matrix**:
     λmax = 5.015284, CI = 0.003821, CR = 0.003412, propagated to indicators in `data/ahp_weights.csv`.
     Authoritative scripts: `run_ahp_weights.py` → `rerun_pipeline_ahp.py`.
   * **County (6 indicators)** uses **equal AHP weights**: `run_county_esi.py` line 55,
     `w_ahp = np.ones(6)/6`. This is the convention behind Table 6.
   For the regional series the equal-weight variant differs from the archive by max \|Δ\| =
   **4.906e-02**, flips the 2007 warning grade (轻警 vs 较安全), and matches the archive at 0/19 points.
5. **Authoritative source of `data/results_esi_regional.csv`.** The archived file is produced by the
   **real-AHP** pipeline `rerun_pipeline_ahp.py`. `run_esi_regional.py` computes the same quantity with
   **equal** AHP weights and previously wrote to the *same* filename, overwriting the archive
   (R22 fix, see §7).
6. **Manuscript numeric provenance.** Every published number is read from a CSV in `data/` (see §4)
   or, for the criterion AHP matrix, is a literal inside `run_ahp_weights.py` whose derived λmax/CI/CR are
   written to `data/results_ahp_consistency.csv`. `data_audit.py` (65/65 PASS) and `jms/verify_jms.py`
   (58 numeric anchors + 30 checks) check that correspondence.
7. **`results_county_esi.csv` exists in two lineages.** The Git `HEAD` version
   (Sunan 0.46616203586085775 / Aksai 0.07406172156023644) predates the current land-cover table; the
   working-tree version (Sunan 0.5578 / Aksai 0.0673) is the one reproduced by both the committed
   land-cover table and a direct CLCD read. §8 lists the `git add` commands.
8. **Forecast digits move with the `statsmodels` release.** The ARIMA fit's floating-point ordering can
   shift the last printed digit (±0.0001). Everything else (weights, regional ESI, α sensitivity,
   county ESI, GeoDetector q/p) reproduces exactly.
9. **The `±0.02°` sampling window is 136 × 134 pixels.** The longitude/latitude box transformed to
   Albers and read with `rasterio.windows.from_bounds` yields a rectangle of **136 × 134 pixels**
   (≈16.9 km², ~2,000× a 3×3 block) because the bounding rectangle of a rotated meridian box is larger.
   The 1914-point reproduction in `run_clcd_verify.py` uses this same window and matches the archived
   `data/spatial_samples.csv` at 1914/1914; the window is documented in-code as
   `lat/lon ± 0.02°` (`run_county_geodetector.py` L110–113).
10. **`qilian_landcover.csv` needs five CLCD epochs.** Only the 2020 tile is present locally, so
    `process_clcd.py` cannot regenerate the committed five-epoch table here (guard prevents silent
    overwrite). This file **is** committed, so the published numbers remain reproducible.

---

## 6. R22 hardening change log (what changed in the code, and why)

| file | change | rationale |
|---|---|---|
| **`io_utils.py` (new)** | shared `resolve_cru_dir()` / `resolve_lc_dir()` / `open_netcdf()` / `cru_file()` / `clcd_file()` | one implementation of directory fallback + netCDF engine fallback (traps 1–2) |
| `process_cru.py` | L11–17 resolution via `io_utils`; L47 `xr.open_dataset(path)` → `io_utils.open_netcdf(path)[0]` | CJK-path crash + non-existent default dir |
| `run_county_geodetector.py` | L18–25 resolution via `io_utils`; L83–90 `xr.open_dataset(...)` → `io_utils.open_netcdf(...)` | same |
| `run_clcd_verify.py`, `run_cru_verify.py`, `run_county_window_sensitivity.py`, `run_fractional_cover_loo.py` | `LC_DIR`/`CRU_DIR` resolution via `io_utils` | same, and consistent resolution across the pipeline |
| `run_exogenous_geodetector.py` | `find_cru_dir()` delegates to `io_utils.resolve_cru_dir()`; `_open()` delegates to `io_utils.open_netcdf()` | deduplicate the existing inline fallback |
| `process_clcd.py` | resolution via `io_utils`; **new guard** at L65–78: if the local CLCD epochs ≠ {2005, 2010, 2015, 2020, 2023}, write `data/results_landcover_partial_<years>.csv` instead of overwriting `data/qilian_landcover.csv` | prevents a silent, wrong five-epoch table from poisoning every downstream ESI value |
| `run_esi_regional.py` | output moved to `data/results_esi_regional_equalweight.csv` + `data/results_weights_equalweight.csv`; docstring warning added | **was silently overwriting the authoritative archive** with an equal-AHP variant (trap 5) |
| `run_alpha_sensitivity.py` | output moved to `data/results_alpha_sensitivity_equalweight.csv`; docstring warning added | same collision (equal-AHP α table vs the published one) |
| `README.md` | rewritten (this file) | end-to-end executable reproduction guide + provenance + traps |

**Not changed:** any algorithm, weight, window, threshold, direction, formula, random seed, or data value.
Only I/O resolution and output filenames were touched. The manuscript (`.tex`/`.bib`/`.bbl`/`.pdf`), the two
`.docx` deliverables and all figure images were not modified (md5 evidence in §7).

`_hardening_backup/` holds: `md5_before.csv`, `md5_after.csv`, `md5_table.md`, byte copies of every
`data/*.csv` as of the start of this work (`_hardening_backup/data/`), the pre-edit scripts
(`_hardening_backup/py_orig/`), run logs, and two audit tools (`snapshot_md5.py`, `audit_output_targets.py`).

---

## 7. Verification evidence (R22)

### 7.1 Default-path runs (no environment variables set)

```
[io_utils] CLCD 目录 = <repo>\_raw\lc_data  (默认回退)
[io_utils] CRU 目录  = <repo>\data\cru      (默认回退)
```

`<repo>` abbreviates the clone directory (the sample lines above are log output; the directory
resolution itself is relative to `__file__`, so a clone prints its own path here).

* `process_cru.py` (in a sandbox copy) → `data/qilian_climate.csv` **byte-identical** to the committed file
  (md5 `1BA81D5502EF4A769E5D10B1A3C1CCC2`), `max |Δ|` = 0 for both precip and temp.
* `run_county_geodetector.py` (in place, 26.2 s, exit 0) → q values `temp 0.1697 / precip 0.5060 /
  grass 0.7077 / forest 0.0000 / barren 0.8024` (identical to the archived `results_geodetector_pvalues.csv`);
  all four regenerated protected CSVs **UNCHANGED** (byte-identical).
* `run_clcd_verify.py` (170 s, exit 0) → **PASS**, 1914/1914.
* `run_cru_verify.py` (29 s, exit 0) → 228/228 months present, climate 228/228 \|Δ\| < 1e-10,
  regional ESI 19/19 and county ESI 11/11 identical at 4 dp, engine actually used = `scipy`.

### 7.2 Byte-for-byte reproduction of the authoritative CSVs

Reproduced in a clean sandbox (`rerun_pipeline_ahp.py`, `run_county_esi.py`, `run_geodetector_pvalues.py`,
`run_exogenous_geodetector.py`):

| file | `max |Δ|` numeric |
|---|---|
| `results_esi_regional.csv` | **0.0** |
| `results_weights.csv` | **0.0** |
| `results_alpha_sensitivity.csv` | **0.0** |
| `results_county_esi.csv` | **0.0** |
| `results_county_esi_details.csv` | **0.0** |
| `results_geodetector_pvalues.csv` (999 permutations, seed 42) | **0.0** |
| `results_geodetector_exogenous.csv` | **0.0** |
| `results_forecast_comparison.csv` | ≤ **1.0e-04** (last printed digit; statsmodels ARIMA) |

### 7.3 Protected archives — md5 before vs after

Full table in `_hardening_backup/md5_table.md`. Summary: **54 UNCHANGED, 3 CHANGED, 5 NEW**.

The 3 CHANGED files are the *R21 verification outputs* of `run_cru_verify.py`. This round generated
`data/results_county_esi_from_clcd.csv`, so the script compares against that file as well: a wider report
(42 summary rows, one extra comparison column), with no change to any archived value table:

| file | before | after |
|---|---|---|
| `data/cru_verify_summary.csv` | `826CBE77D6F3DC4B9EEA1025D4B8C3C1` | `DAD59DAF3F2D4B5FD6D454841F8AA708` |
| `data/cru_verify_env_and_notes.csv` | `057AD375F58E0B20014AF3800806688D` | `BB5C32FE2CE6A9C2302409552A8D6BF5` |
| `data/cru_verify_county_esi.csv` | `DC863D39D77924F7491020C2D27EF7D9` | `BBCF62FBD0F697D0E4D09A0274CF8576` |

New files (all new names, nothing overwritten):

| file | md5 |
|---|---|
| `data/results_county_esi_from_clcd.csv` | `8E6091F56ED42C577DA6A1D35E8E10C4` |
| `data/results_esi_regional_equalweight.csv` | `FB0457B4563E660B8D0D2D62B264ADBD` |
| `data/results_weights_equalweight.csv` | `D18C0C3B4F565CC4E4E651CB44E34AFC` |
| `data/results_alpha_sensitivity_equalweight.csv` | `AFF2DCDFBE75A018CCFFD9CC8E4A647E` |
| `data/_output_targets_audit.csv` | `08ED8DCA8C2914ACBE8A0406C80EBC3E` |

Every archived value table is **UNCHANGED**, including `results_county_esi.csv`
(`8E6091F56ED42C577DA6A1D35E8E10C4`), `results_esi_regional.csv` (`5EE1876B3C1B7CFAA874EBFD50400F7D`),
`qilian_climate.csv` (`1BA81D5502EF4A769E5D10B1A3C1CCC2`), `qilian_county_landcover.csv`
(`7955744B30C2D07D7250F65995BE9549`), `spatial_samples.csv` (`38DCFB5129F72C619261F2F617E63F55`),
`spatial_esi_points.csv` (`383CC30DEFCF7BBFDE6B4196C5624651`), `results_weights.csv`
(`E76BCE6025C2F0EDFCAF92BE3B25666A`), `results_geodetector_pvalues.csv`
(`BC85C8CAA71EBFAFE4EE542A32C29833`).

### 7.4 Manuscript source and deliverables

| file | md5 |
|---|---|
| `paper-code/manuscript.tex` | `AF55563B0C27ADE689F32FECAA891BA3` |
| `paper-code/manuscript.bib` | `143E9487E76878FFA1AB78D0F555E429` |
| `paper-code/manuscript.bbl` | `F89C9CDE0354B9D2ECD2F1A535C6DBD3` (**tracked** since 2026-10-17, 13,026 B) |
| `paper-code/manuscript.pdf` | `19DD5A37917DCFBE087AF193110143C1` (22 pages, 10,340,644 B; Git-ignored, see the `/ModDate` caveat below) |
| `投稿前优化/JMS CN 论文_R17修订版.docx` | `23122CF77EB6E71DA5A6CA6397A4F2DB` |
| `交付/2.0版本/JMS CN 论文_2.0版本.docx` | `23122CF77EB6E71DA5A6CA6397A4F2DB` |

`manuscript.bib` carries the md5 recorded earlier; `manuscript.tex`, `manuscript.bbl`, the two `.docx`
copies and `manuscript.pdf` were re-hashed on 2026-10-17 against the working tree (values in the table
above; both `.docx` copies are byte-identical, 26,886,783 B). Earlier in the same lineage `manuscript.tex`
was `C0E49A5C8E8F549FF5E8E307227CD878` and both `.docx` copies were
`69D7325E6D650CC6407A6C8BD631F0D6`.

`manuscript.pdf` (Git-ignored, so Git holds no version of it) was **rebuilt on 2026-10-17** in an empty
directory from the current `manuscript.tex` by the §7.5 sequence: **22 pages, 10,340,644 B**, md5
`19DD5A37917DCFBE087AF193110143C1` (page count confirmed independently with `pypdf`: 22). The file it
replaced was `50804CAC60AA5D31752015DCCDAF3803` (22 pages, 10,339,019 B) and predated the last
`manuscript.tex` edits, so it did not correspond to the committed source; it was overwritten without being
archived. **A PDF md5 is not a stable fingerprint of the source:** pdfTeX stamps a fresh `/ModDate` (and
with it a fresh `/ID`) into every build, so two consecutive `pdflatex` runs on an already-settled tree give
the same page count and the same byte count but different md5 — measured on the current source:
`6296614359CD811E14E924EEEFD1BC5F` and `CFBC625498A7E6B121DD7347AA3772F2`, whose only byte difference is the
`/ModDate`/`/ID` region. Use **22 pages / 10,340,644 B / 0 undefined citations and 0 undefined `\ref`** as
the reproducible checks. A byte-reproducible md5 needs a pinned clock: with
`$env:SOURCE_DATE_EPOCH='1780000000'` the same source twice produced
`00427DB708D163E2A154AB0CB3B835E6` at 10,340,632 B.

### 7.5 LaTeX build

```
pdflatex -interaction=nonstopmode -halt-on-error manuscript.tex   (pass 1, exit 0)
pdflatex -interaction=nonstopmode -halt-on-error manuscript.tex   (pass 2, exit 0)
warnings in pass 2: 0        Output written on manuscript.pdf (21 pages, 10334465 bytes)
```

2.0 rebuild (R23 round; `manuscript.tex` md5 `2B2ED6C5B14136CB64A1D8DD3168F437`):

```
pdflatex -interaction=nonstopmode -halt-on-error manuscript.tex   (pass 1, exit 0)
pdflatex -interaction=nonstopmode -halt-on-error manuscript.tex   (pass 2, exit 0)
warnings in pass 2: 0        Output written on manuscript.pdf (22 pages, 10339079 bytes)
manuscript.pdf md5: B3259A06F9AA4347047118C5FE8F782B
```

Rebuild after the §5.4 edit (`manuscript.tex` md5 `6A4FD2F472600117542DD6EA2082CAA8`):

```
pdflatex -interaction=nonstopmode -halt-on-error manuscript.tex   (pass 1, exit 0)
pdflatex -interaction=nonstopmode -halt-on-error manuscript.tex   (pass 2, exit 0)
warnings in pass 2: 0        Output written on manuscript.pdf (22 pages, 10339019 bytes)
manuscript.pdf md5: 50804CAC60AA5D31752015DCCDAF3803
```

Current rebuild (2026-10-17; `manuscript.tex` md5 `AF55563B0C27ADE689F32FECAA891BA3`), empty directory,
`bibtex` included — the same per-pass table is in §3 Stage 5:

```
pdflatex -interaction=nonstopmode -halt-on-error manuscript.tex   (pass 1, exit 0)   19 pages, 10329520 bytes
bibtex manuscript                                                 (exit 0)            manuscript.bbl 13026 bytes, md5 F89C9CDE0354B9D2ECD2F1A535C6DBD3
pdflatex -interaction=nonstopmode -halt-on-error manuscript.tex   (pass 2, exit 0)   21 pages, 10340763 bytes, 49 citation warnings
pdflatex -interaction=nonstopmode -halt-on-error manuscript.tex   (pass 3, exit 0)   22 pages, 10340644 bytes, 0 undefined, 1 LaTeX Warning (Label(s) may have changed)
pdflatex -interaction=nonstopmode -halt-on-error manuscript.tex   (pass 4, exit 0)   22 pages, 10340644 bytes, 0 LaTeX Warning
manuscript.pdf md5: 19DD5A37917DCFBE087AF193110143C1      (22 pages re-checked with pypdf)
```

The first three records above are historical two-pass builds kept verbatim; the current rebuild needed four
`pdflatex` passes plus `bibtex`, and the repository `manuscript.pdf` now holds pass 4's output. Every build
listed in this section carries the same `Overfull \hbox` 1 / `Underfull \hbox` 2 count.

---

## 8. The stale `results_county_esi.csv` (historical author action, now applied)

`data/results_county_esi.csv` **was** on the stale lineage (Sunan 0.46616203586085775, Aksai
0.07406172156023644); the reproduced file carries Sunan 0.5578, Aksai 0.0673, and is
byte-identical to `data/results_county_esi_from_clcd.csv`, md5 `8E6091F56ED42C577DA6A1D35E8E10C4`.

**Status:** this fix has since been **applied and committed** — `data/results_county_esi.csv` in the
current `HEAD` already reads Aksai `0.0673` and hashes to the md5 above, and every script listed below
is now tracked. The commands are kept verbatim as the historical record of that author action.

```powershell
cd <repo>
git add data/results_county_esi.csv
git add data/results_county_esi_details.csv
git add data/results_county_esi_from_clcd.csv
git add io_utils.py
git add process_cru.py process_clcd.py run_county_geodetector.py
git add run_esi_regional.py run_alpha_sensitivity.py run_forecast_comparison.py
git add run_clcd_verify.py run_cru_verify.py run_county_window_sensitivity.py run_fractional_cover_loo.py
git add run_exogenous_geodetector.py
git add README.md
git status --short          # review before committing
```

**No commit was made by that hardening round itself** — the commit came afterwards, with the file list
shown above. `run_esi_regional.py`, `run_alpha_sensitivity.py` and `run_forecast_comparison.py` were
untracked at that time and are tracked now.

---

## 9. Known gaps and residual uncertainties

### 9.1 Inputs a cold clone lacks

| id | item | detail |
|---|---|---|
| A | CLCD epochs other than 2020 | `data/qilian_landcover.csv` is the five-epoch (2005/2010/2015/2020/2023) regional table driving indicators X3–X9. Only the 2020 tile is present locally, so `process_clcd.py` writes `data/results_landcover_partial_2020.csv` there. Regenerating the committed five-epoch table from raw data needs the remaining epochs from Zenodo record 8176941. |
| B | verification inputs outside the repo | `verify_v12.py` reads `交付\投稿材料\Highlights.txt` (or `交付\JNC_投稿材料\`); `polish_gate.py` reads the `优化\baseline` snapshot. With those absent, `verify_v12.py` stops with `FileNotFoundError` and `polish_gate.py` reports drift against the 2026-09-24 baseline. `make_dem_figure.py` additionally needs `data/ne/` (Natural Earth 1:50m) and `data/cop90/`. |
| C | Fig. 6 generator | `manuscript.tex` includes `figures/fig_spatial_maps.pdf`; no script in this repository writes that filename. `make_fig_indicator_maps.py` writes `投稿前优化\图件\定稿\Fig06_indicator_spatial_final.{pdf,png}`. The `fig_spatial_maps.pdf` build step lives outside the repo, so Fig. 6 requires that external step. |
| D | Git-ignored figure tree | **Updated 2026-10-17:** the **ten figure PDFs that `manuscript.tex` includes are now tracked** (added with `git add -f` against `.gitignore`), so a clone already contains them and `pdflatex` runs without Stage 4. `figures/` itself stays Git-ignored, so the other ~18 regeneration products (preview PNG/PDF combos, `.dot`, intermediate rasters) remain untracked. All figure inputs that are committed allow nine of the ten figures to be rebuilt; **Fig. 6** still needs the external step in item C. |
| E | Optional **local** tools that are not in this repository | Four files are used locally but are **not** committed, so a cold clone does not contain them: `make_fig4_combo.py`, `build_word_cn_final.py`, `make_paste_doc.py`, and a root-level `refs_jms.txt`. They are optional local tools only: missing them does **not** affect any manuscript number, any of the ten included figures, or any table. Replacements, all committed: Fig. 4 comes from `make_fig3_clean.py` (traceability table §4); the Chinese-manuscript entry point is `build_word_cn.py` (Stage 6, writes `out/论文_CN_latest.docx`); the submission-form source texts are the committed `jms/refs_jms.txt`, `jms/keywords_jms.txt`, `jms/declarations_jms.txt`. `build_word_cn_final.py` is an **outdated 2026-09-24 snapshot** whose output is not the current Chinese manuscript — it must **not** be used as the Chinese-manuscript generation entry point. `make_fig4_combo.py` only re-renders preview PNG/PDF combos, and `make_paste_doc.py` emits a convenience `.docx` of Chinese paragraphs; neither changes a number or a figure. The root-level `refs_jms.txt` is a local variant and is not byte-identical to the committed `jms/refs_jms.txt`; use the committed one. |
| F | External GADM boundary file | `run_county_support_sensitivity.py` reads a GADM county (level-3) polygon file, `gadm41_CHN_3.json` (**~10 MB**, not committed). The script now resolves it from the `QILIAN_GADM` environment variable, falling back to `data/gadm41_CHN_3.json` inside the repository: set `QILIAN_GADM` (or drop your copy at that relative path) before running that one script; no other script in this repository reads it. Without that data the script cannot run, but this does not affect any committed `data/results_county_*.csv` value or its md5 — the county-centroid-support sensitivity re-run is the only thing gated by it. |

### 9.2 Residual uncertainties

1. **Scope of this round's execution.** The `≥ 600 dpi` TIFF export (`jms/export_tiff.py`) and the Word
   builds (`build_word_*.py`) write into Git-ignored output directories and were outside the requested
   verification scope, so they were not run. Their inputs are unchanged.
2. **`results_forecast_comparison.csv` has two writers.** `rerun_pipeline_ahp.py` computes GM(1,1) inline;
   `run_forecast_comparison.py` calls `eco_security.gm11_forecast`. Both write the same filename and differ
   by max \|Δ\| = 1e-4 in the last printed digit. The file is not on the protected list and is read by
   `make_fig3_clean.py` / `make_fig4_combo.py` (local tool, not in this repository — §9.1 item E) /
   `make_figures.py` / the Word builders, so the filename was
   kept: re-running Stage 3 after Stage 2 rewrites it at the 4th decimal.
3. **`run_county_geodetector.py` writes four protected tables.** `qilian_county_landcover.csv`,
   `spatial_samples.csv`, `spatial_esi_points.csv` and `results_county_esi_from_clcd.csv` are its documented
   outputs; the run in §7 wrote them and they came out byte-identical to the committed copies. Copy `data/`
   before re-running if the copies matter. A `--dry-run` flag was kept out to hold the change set to I/O.
4. **Working notes.** `data/_output_targets_audit.csv` and `_hardening_backup/*` are working notes rather
   than submission artifacts. They are not Git-ignored; add them to a release commit only if you want them
   public.
5. **Engine coverage actually exercised.** The fallback order is `netcdf4 → scipy → h5netcdf → default`. On
   this machine `scipy` opens the CRU NetCDF3 files and `h5netcdf` is absent, so a NetCDF4/HDF5 input on a
   CJK path would need `h5py` + `h5netcdf`, or relocation to an ASCII path; that combination was not run.

---

## 10. Directory layout

- `manuscript.tex/.bib/.bbl` — manuscript source (elsarticle, author-year); all three are tracked, so a
  clone compiles without `bibtex` (build order and traps: §3 Stage 5, evidence: §7.5); `manuscript.pdf` is
  Git-ignored
- `data/` — processed climate, land cover, county and result CSVs (the numeric source of every figure/table)
- `data/cru/` — CRU TS 4.10 raw grids (Git-ignored, ~2.4 GB)
- `_raw/lc_data/` — CLCD 30 m GeoTIFF (Git-ignored, ~810 MB)
- `io_utils.py` — shared data-directory resolution + netCDF engine fallback
- `eco_security/` — frozen method functions (`minmax_normalize`, `entropy_weights`, `combined_weights`,
  `esi_series`, `gm11_forecast`, `classify_warning`, `geodetector_q`); imported via `sys.path`
- `*.py` — processing scripts, figure builders, build scripts, verification gates
- `jms/` — JMS-specific exporters and `verify_jms.py`; `refs_jms.txt`, `keywords_jms.txt`,
  `declarations_jms.txt` are the submission-form source texts (all committed under `jms/`; a
  root-level `refs_jms.txt` may exist locally but is **not** in this repository — §9.1 item E)
- `reports/` — in-repo landing point for generated Chinese reports (`run_robustness_loo_indicators.py`
  writes `reports/robustness_loo_indicators.md` there; the directory is created on demand)
- `figures/`, `out/`, `jms/figures_tiff/` — build artifacts (Git-ignored, regenerate with §3)
- `_hardening_backup/` — R22 backups, md5 snapshots and audit tools

## License

- Code (`.py`, `.tex`, `.cls`, `.bst`): MIT License, see `LICENSE`.
- Processed data (`data/*.csv`): derived from public sources (CRU, CLCD, Copernicus, OSM); redistribution
  permitted under the upstream terms. Cite the upstream datasets in any reuse.

## R28 change log (code, provenance and one known discrepancy)

Added in the R28 revision; every item is reproducible from the committed files in §4.2.

1. **`run_county_esi.py` line 48 — residual-barren fix.** The point-scale barren/degraded
column is now derived as the residual `100 − grass − forest − water − cropland` instead of
being read from CLCD class 7. The two definitions agree on 1,914 − 81 = 1,833 of the sampled
points and are rank-identical at the regional scale (Spearman ρ = 1.0000); the 81 differing
points are cropland- (75) or snow/ice-dominated (6) samples that the residual counts as
barren (`data/r28_pointscale_complement.csv`). The change affects the point-scale tables only;
the regional five-epoch series in `data/qilian_landcover.csv` is unchanged.
2. **Identity de-duplication.** `run_r28_t1_identity.py` / `run_r28_t2_deredundancy.py` establish
that ecological-land proportion = grass + forest + water, that the grassland change rate is the
differenced grassland proportion with a 2005 convention, and that barren/degraded = 100 − the
other four land-cover columns (all residuals exactly 0, `data/r28_identity_recheck.csv`), and
that dropping the duplicate column (`drop_X9`, the manuscript's primary specification) leaves all
19 grades unchanged while the other specifications move the peak year
(`data/r28_deredundancy_comparison.csv`).
3. **Obstacle table provenance gap — known and stated.** The phase means printed in the
manuscript reproduce the archived `data/results_obstacle.csv` to the third decimal, but **no
generating script for that archived table is present in this repository**. An independent
reimplementation reproduces it to within 0.014 (largest difference: the derived grassland change
rate and the ecological-land proportion; `data/r28_obstacle_sensitivity.csv`,
`data/r28_obstacle_formula_check.csv`). The manuscript quotes the archived values (0.233 / 0.221 /
0.151 and 0.364 / 0.206) and states the 0.014 agreement; the recomputed values are 0.2323 /
0.2217 / 0.1438 and 0.3511 / 0.2092. Treat the archived table as an intermediate whose
generator is missing, not as an independently verified result.
4. **Second leakage channel.** Normalising the indicators and estimating entropy weights over the
full 2005–2023 period is a second, less obvious leakage channel when the models are validated on
that period; the strictly leakage-free variant reverses the model ranking
(`data/r28_esi_leakage_channel.csv`, `data/r28_ngbm_gamma_leakage.csv`). The archived γ = 0.10
(holdout RMSE 0.034) is reproducible only when the exponent is selected with the evaluation
period in view; the manuscript therefore reports the training-only γ = 0.25.
5. **New scripts.** 20 `run_r28_*.py` generators plus `r28_core.py` and `r28_trend.py`; the
independent NDVI target uses `run_r28_independent_target.py`, which downloads 133 NOAA CDR
AVHRR/VIIRS files (list and access dates in `data/r28_external_ndvi_manifest.csv`). No network
access is needed to reproduce any committed table.
6. **`_r28_report_readouts.py` is deliberately not committed** (scratch read-out helper used
while writing the manuscript).
7. **`data/results_backtest.csv` — kept, with a provenance note.** This archived backtest table
has **no generating script in this repository** (the archived accuracy table comes from
`run_forecast_comparison.py`, but the backtest file itself does not). Its NGBM row corresponds to
a power exponent selected with the evaluation period in view (γ = 0.10), a claim the manuscript has
**withdrawn**: under training-only selection the NGBM holdout error rises from 0.034 to 0.0687 and
the model ranking reverses (see `data/r28_ngbm_gamma_leakage.csv`,
`data/r28_esi_leakage_channel.csv`). The file is retained for transparency about the earlier
revision and must not be used as evidence of forecast skill.
8. **`run_forecast_comparison.py` — γ = 1.0 guard added.** The NGBM solution contains a
1/(1−γ) exponent, so γ = 1 is degenerate; the original code let NumPy return an infinite
expression that collapsed to a spuriously small residual sum of squares (SSE = 4.25) which the
grid search could select. The function now skips γ = 1 and rejects any non-finite solution.

## Repository

- Code and processed tables: <https://github.com/mllbmy/qilian-esi-early-warning>
  (default branch `main`; tags `v1.0` and `v1.1`; MIT licence for code, CC-BY-4.0 for the derived
  tables).
- Archived release with a concept DOI: <https://doi.org/10.5281/zenodo.23011183>.
- Every table and figure in the manuscript names the file that produces it; the run order is
  Stage 0–7 above.

## Land-cover provenance (CLCD)

| Item | Value |
|---|---|
| Dataset article | Yang J, Huang X (2021) *Earth Syst Sci Data* 13(8): 3907–3925, <https://doi.org/10.5194/essd-13-3907-2021> |
| Deposit used here | Yang J, Huang X (2024) CLCD 30 m annual land cover 1985–2023, **version 1.0.3**, <https://doi.org/10.5281/zenodo.12779975> |
| Tile record for the 2020 epoch | **version 1.0.2**, record <https://doi.org/10.5281/zenodo.8176941> |
| Raw tile re-processed here | `_raw/lc_data/CLCD_v01_2020_albert.tif`, 810,739,687 bytes, md5 `1274285BB18F9B1D443A3CC906B1310C` |
| Archived regional table | `data/qilian_landcover.csv`, 590 bytes, md5 `e58520f8cdc9ce6ace77366b947da20a`, sha256 `c0213af8…` |

Version note: the 30 m product line is published as a versioned deposit; the regional table used in
the manuscript was derived from the 2020 tile of the 1.0.2 record, while the current deposit
version is 1.0.3. Both are named above so that the difference is visible rather than silently
resolved. The 2005, 2010, 2015 and 2023 epochs are **not** re-derivable from the raw tile inside
this package: they are supplied as the archived regional table, and only the 2020 epoch can be
re-processed end to end. The exact download date of the tile is not recorded in this repository and
is therefore not claimed.

## Change log — R29 revision

1. **Primary specification is now the eight-indicator DPSI set.** The exactly duplicated
   ecological-land column is removed from the weighted indicator system and the Response layer is
   retained as an **unweighted policy-background layer** (qualitative). All headline numbers —
   abstract, Table 4, Tables 7–9, Figures 2/4/5, the Discussion, the Conclusion and the Data
   availability statement — are quoted for this primary set, and every nine-indicator number that
   survives is explicitly labelled as such. Nine-indicator ESI: 0.258 (2005) → 0.709 (2010) →
   0.486 (2023). Eight-indicator ESI: 0.289 → 0.676 → 0.478, with an identical 19-year grade
   sequence.
2. **Weight renormalisation is stated, not hidden.** Entropy weights are not recomputed: deleting
   the column rescales all eight surviving weights by the common factor 1/(1−w^E_X9) = 1.062653
   (a closed form that reproduces a numerical recomputation to 3×10⁻⁸). The AHP weights cannot be
   rescaled that way (the five live criteria sum to 0.749769 and would leave the indicator layer
   summing to 0.750), so rule A renormalises the surviving criteria to one (factor 1.333744); rule
   D re-solves the 4×4 surviving judgement matrix as a sensitivity check (λmax = 4.004,
   CR = 0.0015, largest difference from rule A 0.0122). The overlap group State + Impact carries
   0.656 under the primary set, against 0.693 for State + Impact + Response under nine indicators;
   the earlier "69.29 %" figure belongs to the nine-indicator overlap group and is no longer
   quoted for the primary set. Layer totals: Driving 0.154, Pressure 0.190, State 0.421, Impact
   0.235, summing to 1.000000.
3. **The 2010 peak is stated as specification-dependent.** It is kept, with 0.676 (eight) and
   0.709 (nine) given together; the peak year (2010) and all 19 grades are identical under both
   specifications and no year changes grade.
4. **The trend claim was downgraded to "suggestive".** Under the primary set, Mann–Kendall gives
   p = 0.184 (2005–2023) and p = 0.189 (2010–2023), Hamed–Rao 0.193 / 0.185, and both Sen slopes
   have confidence intervals spanning zero (−0.0031, CI [−0.0078, +0.0017]; −0.0035, CI
   [−0.0117, +0.0013]). Trend-free pre-whitening returns a significant full-period value
   (p = 0.012) and a non-significant segment (p = 0.200), so the conventions disagree and the
   decline is reported as suggestive. The significant post-2010 decline of the nine-indicator set
   is retained only as a labelled contrast.
5. **2028 is reported as three models plus their equal-weight mixture.** GM(1,1) 0.448, NGBM
   0.380, ARIMA(0,1,1) 0.485, mixture 0.438; the 2028 grade is model-dependent (mild warning for
   GM, ARIMA and the mixture; medium warning for the NGBM) and every margin to the 0.400 boundary
   (+0.048, −0.020, +0.085, +0.038) is of the same order as the rounding unit of the reported
   value, so no 2028 grade is treated as decision-relevant. The NGBM exponent window is reported
   honestly: the training-only optimum is 0.15, the full-series optimum is 0.05 **at the lower
   bound of the search grid**, and the holdout error is also minimised at 0.05, so the crossing is
   exponent-conditional. The ARIMA interval reaches 1.113, above the [0, 1] support of the index,
   and that is stated wherever the interval is quoted.
6. **Obstacle diagnosis.** The formula O_ij = (1 − x′_ij) w_j, the within-year normalisation
   O*_ij = O_ij / Σ_j O_ij and the phase-mean definition are now written out; the archived
   nine-indicator table's missing generating script is disclosed as archived; and the phase means
   are declared **weight-conditional** rather than weight-free (with entropy, equal and AHP weights
   the plateau-phase leader changes, and the recovery-phase leader becomes the forest proportion
   under AHP weights alone).
7. **Journal-of-Mountain-Science reference style.** In-text citations lose the comma before the
   year (`(Liu et al. 2023)`) through `\setcitestyle{aysep={ }}`, and the reference list is
   rendered in Springer name-year style — `Author A, Author B (2022) Title. J Mt Sci 17(11):
   2591–2610. https://doi.org/...`, no terminal period, more than three authors abbreviated to
   `et al.`. No installed `.bst` provides this format (`spbasic.bst`/`spphys.bst`/`spmpsci.bst` are
   absent from this TeX distribution), so `manuscript.bbl` is generated from the single source of
   truth `manuscript.bib` by **`make_bbl_jms.py`**. Build order:
   `pdflatex → bibtex manuscript → python make_bbl_jms.py → pdflatex → pdflatex`
   (bibtex overwrites the `.bbl`, so the generator must run after it). Four never-cited entries
   (`dl_conservation_bio_2023`, `du2024dpsir`, `earlywarning_grassland2024`,
   `qilian_desertification_gee`) were deleted from the `.bib`; `CO2` in the NGBM title became
   `CO$_2$`; the Lyu et al. (2026) entry gained its issue number; and the CLCD entry records
   version 1.0.3 while naming the 1.0.2 tile record used for 2020.
8. **Figure regeneration and cross-reference fixes.** Fig. 2 now carries the eight-indicator
   weights and an unweighted policy-background row; Fig. 4 is drawn from the primary series with
   the legend reading "NGBM bootstrap interval (95 %)"; Fig. 5 shows the eight-indicator weights;
   the framework label "NGBM · 95 % intervals" and the stale "95 % interval" legend are gone. The
   Figure 8 and Figure 9 captions were rewritten to match the panels actually drawn (single panel;
   three bars with the lighter bar marking the weaker single-factor q), Fig. 6 is now cited in the
   α subsection, Table 10 is cited where it is first discussed, the "Sec. 3" pointers use
   `\ref{}` labels (`sec:dpsir`, `sec:warning`), the six interaction rows read
   "bivariate-enhancing", the archived 0.005 permutation p of Table D.17 was moved into a footnote
   marker so it can no longer be misread as a collapsed column, apostrophes were corrected,
   `\usepackage{xurl}` was added for the long repository URL, and the 26 literal degree signs were
   unified to `$^{\circ}$`.
9. **Chinese manuscript synced (R30).** The R29 changes were carried into the Chinese Word
   manuscript by literal, run-splitting-tolerant replacement inside `word/document.xml` only:
   abstract/conclusion values (0.676 / 0.478 primary; 0.709 / 0.486 as the labelled nine-indicator
   contrast), the Response layer as an unweighted policy-background layer, the two weight
   reallocation rules (entropy factor 1.062653, AHP rule A 1.333744, rule D as sensitivity), the
   four 2028 口径 (NGBM 0.380, GM(1,1) 0.448, ARIMA 0.485, equal-weight mixture 0.438) with the
   margin caveat, the 2028 intervals and grade probabilities, the `suggestive` trend wording, the
   specification-dependent 2010 peak, the above-support ARIMA bound 1.113, the obstacle formula
   with weight-conditional phase means, and the terminological change from driving factors to
   spatial associations. The CLCD (Yang & Huang, 2024) entry missing from the Chinese reference
   list was inserted, so the paragraph invariant moves from 439 to 440 **by design**; tables 11,
   drawings 10, oMath 12, non-black `w:color` 0, `testzip()` None and "only `word/document.xml`
   differs" all still hold. The scripts are `cn_r30_sync.py`, `cn_r30_ref_add.py` and
   `cn_r30_sweep.py` (they operate on an extracted `word/document.xml` baseline, which is not
   distributed here).
10. **Still open after R30 (stated, not hidden).** Figs. 3 and 6 are still nine-indicator figures
   (captioned as such); the five out-of-sample validation schemes were **not** recomputed for the
   eight-indicator set, so Table 7 remains nine-indicator evidence with an explicit note; the
   Figure 8/9 panels were not redrawn (captions were corrected instead); 32 of the 37 pages were
   machine-audited rather than read page by page by a human; and the 300 dpi TIFF figure set for
   the submission system was not regenerated.
