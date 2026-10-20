# Current analysis: manuscript version 2.2

The paper studies ecological security in the Qilian Mountain region using a
retrospectively reconstructed regional index and a separate spatial index.
The current results are `data/r47_*.csv`. Earlier round tables are retained as
archived analyses and sensitivity inputs; their forecast scores and intervals
must not be substituted for the current tables.

## Recompute the corrected analyses

Python 3.13 with numpy, pandas, scipy, statsmodels and matplotlib is required.
The exact producing environment is recorded in `data/r47_environment.json`.
From this directory:

```powershell
python run_r47_revision.py --stage all --bootstrap 2000
python make_r47_figures.py
python make_figure_audit.py
python make_bbl_jms.py
python verify_refs_jms.py
```

`forecast_models.py` is the canonical response implementation. Accumulated grey
response time starts at zero and the first forecast follows the last fitted
increment without a gap. NGBM excludes the singular exponent 1. Validation uses
one 2018 five-year holdout, ten one-year origins and six five-year origins.
Only rolling-five-year errors determine mixture weights. No deleted-year
score is used. All evaluation targets retain the full-period reconstruction;
the exercise does not establish real-time forecasting performance.

The bootstrap refits the same estimator, including exponent selection, on
logit-scale block-resampled histories, then accumulates future logit disturbances.
Its central envelopes and grade shares are conditional simulation summaries.
Spatial reference fractions enumerate all 1,913 nonidentity periodic translations
of the 29 by 66 lattice. They describe alignment under periodic boundaries.
The correlation effective-sample-size approximation is used for Pearson r only.
Obstacles use the primary eight-indicator normalized matrix and weights directly.

`QILIAN_WORK` controls logs, cache and diagnostic output; the default is
`../ChatGPT/revision_2.2_2026-10-20`. Font rendering uses Times New Roman.
The source figure PDFs are the files in `figures/`; current figure generators
update Figures 2, 4, 7, 8 and 10. Other figures retain their existing generators.

## Manuscript and submission build

`manuscript.tex` and `manuscript.bib` are the sources. **Never run bibtex**:
`make_bbl_jms.py` generates the JMS-style `manuscript.bbl` directly.
Compile with pdflatex until references settle. When compiling in a separate work
directory, put that directory first in `TEXINPUTS` to avoid stale source-directory
auxiliary files. `build_release.py` copies figure masters programmatically,
packages processed-data reproduction sources, and creates checksum manifests.

The Word builder is `tools/docx_build/build_docx.py`. Its main document has no
author identity. `build_front_matter.py` reads the private, excluded
`author_local.py` for the Title Page and Cover Letter. `QILIAN_VERSION` defaults
to 2.2. The system with PyMuPDF can be selected with `QILIAN_PDF_PYTHON` when the
Word interpreter lacks that package. Word on Windows can export the review PDF
with `tools/docx_build/export_review_pdf.ps1`.

The anonymous mirror currently requires the author's real URL. Set it with
`python set_anon_repo.py <https://anonymous.4open.science/r/actual-id>` and rebuild.
Local packaging does not upload data, change Zenodo access or publish a mirror.

## Superseded analyses kept in `data/`

These files are retained as evidence of earlier rounds. Read them only through the
labels below, never as current results.

| File | Status |
|---|---|
| `results_effective_n.csv` | Superseded for q. The F statistics, corrected degrees of freedom and CR p values in the q rows are withdrawn (no valid reference distribution; see the spatial section of the paper). Only the Pearson r row is used, and only for its correlation-variance approximation and effective sample size. |
| `results_blockperm_q.csv` | Superseded. The 100-shift permutation calibration is replaced by the exhaustive nonidentity translation set in `r47_shift_reference.csv`. |
| `results_alpha_sensitivity.csv`, `results_alpha_sensitivity_equalweight.csv` | Nine-indicator alpha sensitivity. The eight-indicator values quoted for Figure 6 come from `r28_alpha_grade_matrix.csv`. |
| `r29_*`, `r28_forecast*`, `results_forecast*` | Earlier reweighted or pre-fix forecast tables. Point projections, envelopes and grade shares in the manuscript come only from `r47_*.csv`. |

If a reviewer asks about the withdrawn q calibration, the answer is that the
manuscript reports single-factor q values with the periodic-shift alignment
reference and does not attach a significance test to them.

## Data and reproduction boundary

`data/*.csv` contains the processed inputs and outputs. The regional series uses
CRU TS 4.10 climate and CLCD regional proportions from 2005, 2010, 2015, 2020 and
2023, with intervening years reconstructed. The processed spatial inputs cover
1,914 points; independent NDVI has 1,785 valid points. County values are centroid
window estimates. `r28_core.py` reconstructs the regional specifications from
the processed inputs without modifying historical ESI values.

Raw rasters are not included in the submission reproduction ZIP. CRU grids are
available from https://crudata.uea.ac.uk/cru/data/hrg/ . CLCD's annual collection
is https://doi.org/10.5281/zenodo.12779975 ; the 2020 tile used locally is record
8176941, file `CLCD_v01_2020_albert.tif`, 810739687 bytes, MD5
`1274285BB18F9B1D443A3CC906B1310C`. Other four epochs are supplied as processed
regional values; rebuilding them from raw data requires the corresponding tiles.
Copernicus DEM GLO-90, NOAA CDR NDVI and Natural Earth support terrain, vegetation
and background-map analyses. Historical raw-data readers additionally require
their geospatial dependencies and the source datasets in their documented paths.

The reproduction package omits author metadata, Git history, credentials,
delivery documents and internal review logs. It includes archived round scripts
for provenance; `run_r47_revision.py` is the current numerical entry point.
