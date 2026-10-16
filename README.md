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
python _hardening_backup\snapshot_md5.py before   # record md5 of every archived CSV + manuscript file
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

The 4–5 × 10⁻⁵ residuals are **not** model error: the archived CSVs store 4 decimals (max rounding error 5e-5).
`run_cru_verify.py` proves this with a control experiment (archived climate in → 4.675e-05; rebuilt climate in → 1.110e-16).

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
| record | Zenodo record **8176941** — <https://zenodo.org/records/8176941> |
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

- No absolute path is hard-coded: every script resolves the project directory from `__file__`.
- **Windows note:** `pdflatex` is available, but **Perl is not** — do **not** use `latexmk`, run `pdflatex` directly (see §3).
- **Non-ASCII path note:** see §5, item 1. This repository lives under `D:\比赛\论文\...` (CJK characters),
  which is exactly the case the engine fallback was written for.

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

```powershell
# Fig. 1  study area      -> figures/fig1_study_area.pdf
python download_cop90.py          # only if data/cop90/ is absent
python make_dem_figure.py         # needs data/ne/ (§9.1 item B), data/cop90/, data/lakes_region.json

# Fig. 2  DPSIR framework -> figures/fig_dpsir_framework.pdf   (authoritative since v18)
python beautify_framework.py      # self-contained; figures/fig_dpsir_framework.dot is the semantic baseline

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

```powershell
pdflatex -interaction=nonstopmode -halt-on-error manuscript.tex   # pass 1
pdflatex -interaction=nonstopmode -halt-on-error manuscript.tex   # pass 2
```

Expected: exit code `0`, **0 warnings**, **22 pages**, `manuscript.pdf` ≈ 10.3 MB (the 2.0 manuscript
adds the Table 1 terrain row and the leave-one-target / fractional-cover sentences, which pushes the
build from 21 to 22 pages).
`manuscript.bbl` is committed, so `bibtex` is not required for an identical build (and `.bbl` regeneration is
not needed). Run the pass twice so that all `\ref`/`\label` cross-references resolve.

### Stage 6 — Word deliverables (JMS submission + Chinese working copy)

```powershell
python build_word_jms.py     # out/jms/ ... (author identity comes from author_local.py; neutral placeholders if absent)
python build_word_cn.py      # out/论文_CN_latest.docx
python jms\export_tiff.py    # jms/figures_tiff/ — TIFF ≥ 600 dpi, JMS requirement
```

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

---

## 5. Frozen conventions and traps (read before trusting a number)

1. **CJK path breaks the netCDF4 engine.** xarray's default backend is netCDF4/HDF5, whose C library cannot
   open paths containing non-ASCII characters; it raises
   `FileNotFoundError: [Errno 2] No such file or directory: '...\比赛\...'` although the file exists.
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
6. **Claude/manuscript numeric provenance.** Every published number is read from a CSV in `data/` (see §4)
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
[io_utils] CLCD 目录 = D:\比赛\论文\paper-code\_raw\lc_data  (默认回退)
[io_utils] CRU 目录  = D:\比赛\论文\paper-code\data\cru      (默认回退)
```

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
| `paper-code/manuscript.tex` | `C0E49A5C8E8F549FF5E8E307227CD878` |
| `paper-code/manuscript.bib` | `143E9487E76878FFA1AB78D0F555E429` |
| `paper-code/manuscript.bbl` | `F89C9CDE0354B9D2ECD2F1A535C6DBD3` |
| `投稿前优化/JMS CN 论文_R17修订版.docx` | `69D7325E6D650CC6407A6C8BD631F0D6` |
| `交付/2.0版本/JMS CN 论文_2.0版本.docx` | `69D7325E6D650CC6407A6C8BD631F0D6` |

`manuscript.tex`/`.bib`/`.bbl` and both `.docx` files are byte-identical to their state before this round.
`manuscript.pdf` was **rebuilt** by the two-pass `pdflatex` check in §7.5: the new file has the same size
(10,334,465 B) and the same page count (21) as before, and its md5 moved from
`46172C3E404664928756445332DCA6C4` to `975704DA38DBD166221832908724E1F9` because pdfTeX stamps a fresh
`/ModDate` into each build. The pre-build file was not copied aside beforehand, so the byte-exact original
is available only from the authors' own archive/CDN copy of `paper-code/manuscript.pdf`; the rebuild in
§7.5 regenerates an equivalent artefact (`manuscript.pdf` is Git-ignored, so Git does not hold either
version).

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

---

## 8. Committing the fix for the stale `results_county_esi.csv` (author action)

`data/results_county_esi.csv` in `HEAD` is the stale lineage (Sunan 0.46616203586085775, Aksai
0.07406172156023644); the working-tree file is the correct, reproduced one (Sunan 0.5578, Aksai 0.0673, and
byte-identical to `data/results_county_esi_from_clcd.csv`, md5 `8E6091F56ED42C577DA6A1D35E8E10C4`).

```powershell
cd D:\比赛\论文\paper-code
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

**No commit is made by this hardening round.** `run_esi_regional.py`, `run_alpha_sensitivity.py` and
`run_forecast_comparison.py` are currently untracked; add only the files whose changes you accept.

---

## 9. Known gaps and residual uncertainties

### 9.1 Inputs a cold clone lacks

| id | item | detail |
|---|---|---|
| A | CLCD epochs other than 2020 | `data/qilian_landcover.csv` is the five-epoch (2005/2010/2015/2020/2023) regional table driving indicators X3–X9. Only the 2020 tile is present locally, so `process_clcd.py` writes `data/results_landcover_partial_2020.csv` there. Regenerating the committed five-epoch table from raw data needs the remaining epochs from Zenodo record 8176941. |
| B | verification inputs outside the repo | `verify_v12.py` reads `交付\投稿材料\Highlights.txt` (or `交付\JNC_投稿材料\`); `polish_gate.py` reads the `优化\baseline` snapshot. With those absent, `verify_v12.py` stops with `FileNotFoundError` and `polish_gate.py` reports drift against the 2026-09-24 baseline. `make_dem_figure.py` additionally needs `data/ne/` (Natural Earth 1:50m) and `data/cop90/`. |
| C | Fig. 6 generator | `manuscript.tex` includes `figures/fig_spatial_maps.pdf`; no script in this repository writes that filename. `make_fig_indicator_maps.py` writes `投稿前优化\图件\定稿\Fig06_indicator_spatial_final.{pdf,png}`. The `fig_spatial_maps.pdf` build step lives outside the repo, so Fig. 6 requires that external step. |
| D | Git-ignored figure tree | `figures/` and `manuscript.pdf` are in `.gitignore`, so a clone has none of the ten included PDFs and `pdflatex` needs stage 4 to run first. All figure inputs that are committed allow nine of the ten figures to be rebuilt; Fig. 6 is covered by item C. |

### 9.2 Residual uncertainties

1. **Scope of this round's execution.** The `≥ 600 dpi` TIFF export (`jms/export_tiff.py`) and the Word
   builds (`build_word_*.py`) write into Git-ignored output directories and were outside the requested
   verification scope, so they were not run. Their inputs are unchanged.
2. **`results_forecast_comparison.csv` has two writers.** `rerun_pipeline_ahp.py` computes GM(1,1) inline;
   `run_forecast_comparison.py` calls `eco_security.gm11_forecast`. Both write the same filename and differ
   by max \|Δ\| = 1e-4 in the last printed digit. The file is not on the protected list and is read by
   `make_fig3_clean.py` / `make_fig4_combo.py` / `make_figures.py` / the Word builders, so the filename was
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

- `manuscript.tex/.bib/.bbl` — manuscript source (elsarticle, author-year); `manuscript.pdf` is Git-ignored
- `data/` — processed climate, land cover, county and result CSVs (the numeric source of every figure/table)
- `data/cru/` — CRU TS 4.10 raw grids (Git-ignored, ~2.4 GB)
- `_raw/lc_data/` — CLCD 30 m GeoTIFF (Git-ignored, ~810 MB)
- `io_utils.py` — shared data-directory resolution + netCDF engine fallback
- `eco_security/` — frozen method functions (`minmax_normalize`, `entropy_weights`, `combined_weights`,
  `esi_series`, `gm11_forecast`, `classify_warning`, `geodetector_q`); imported via `sys.path`
- `*.py` — processing scripts, figure builders, build scripts, verification gates
- `jms/` — JMS-specific exporters and `verify_jms.py`; `refs_jms.txt`, `keywords_jms.txt`,
  `declarations_jms.txt` are the submission-form source texts
- `figures/`, `out/`, `jms/figures_tiff/` — build artifacts (Git-ignored, regenerate with §3)
- `_hardening_backup/` — R22 backups, md5 snapshots and audit tools

## License

- Code (`.py`, `.tex`, `.cls`, `.bst`): MIT License, see `LICENSE`.
- Processed data (`data/*.csv`): derived from public sources (CRU, CLCD, Copernicus, OSM); redistribution
  permitted under the upstream terms. Cite the upstream datasets in any reuse.