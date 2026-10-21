# Observation frequency and forecast reliability of ecological security indices in the Qilian Mountain region, China

This anonymous reproduction package contains the historical five-epoch analysis and the complete annual CLCD v1.0.5 extension. It also includes MODIS Terra NPP summaries, training-window forecasts, processed inputs, figure masters and source manifests.

## Contents

| path | content |
|---|---|
| `manuscript.tex`, `manuscript.bib`, `manuscript.bbl` | manuscript source (LaTeX, JMS house style) and bibliography |
| `data/` | processed inputs, weights, model outputs, validation and sensitivity tables; the tables used in the manuscript are `data/r47_*`, `data/r56_*` and `data/r67_*` |
| `figures/` | vector figure masters (PDF) plus the journal figure audit |
| `run_r47_revision.py` | end-to-end analysis: normalization, combined weighting, ESI series, grey and ARIMA responses with rolling-origin validation, mixture weights, conditional bootstrap, obstacle diagnosis, spatial attribution |
| `forecast_models.py` | grey (GM(1,1), NGBM) and ARIMA response implementations |
| `make_r47_figures.py`, `make_equations.py`, `make_bbl_jms.py` | figure masters, equation table and bibliography builder |
| `run_county_esi.py`, `README_county_esi.md` | static county-level relative index (county comparison) |
| `eco_security/` | shared utilities |

## Reproducing the historical reconstruction

Python 3.13 with numpy, pandas, scipy, statsmodels and matplotlib; the exact producing
environment is recorded in `data/r47_environment.json`.

```powershell
python run_r47_revision.py --stage all --bootstrap 2000
python make_r47_figures.py
python make_equations.py
python make_bbl_jms.py
```

`run_r47_revision.py` writes the `data/r47_*.csv` tables; `make_r47_figures.py` writes
the figure masters in `figures/`. Logs and cached intermediates go to the directory
named by the optional `QILIAN_WORK` environment variable.

## Annual observation analysis

Run `python run_r67_annual_extraction.py --work ./work/annual` to extract the annual CLCD support and record provider checksums, selected-pixel hashes and class counts. The public source rasters are read from Zenodo record 18180184; raw crops and metadata are written under the chosen work directory.

Run `python run_r67_annual_validation.py --work ./work/annual` to create annual index series, the same-release five-epoch interpolation control, a fixed-historical-scale sensitivity, rolling-origin forecasts, NDVI comparisons and summary tables. The annual release is retrospective; this procedure does not recreate historical data availability at the forecast origins.

Run `python run_r67_NPP_validation.py --work ./work/npp` to download MODIS Terra MOD17A3HGF Collection 6.1 assets and reproduce the annual productivity and quality summaries. Run `python make_annual_validation_figure.py` to regenerate the vector figure master from the processed tables.

The forecast evaluation uses 12 one-year origins and eight five-year origins. Records for five-year forecasts overlap and are not independent temporal replications. A fixed historical-scale sensitivity changes seven warning grades and places the annual peak in 2009 rather than 2010, while independently estimated normalization and weights shift it to 2017. NPP is a model-derived productivity estimate, not field data or an ecological-event label. The package reports level, detrended and first-difference associations and identifies the 2014 quality-layer increase.

Historical analysis sources and inputs remain in their original directories. The same-release comparison separates the observation sequence from the product-version update; the fixed-scale sensitivity shows that peak timing also depends on whether bounds and weights are re-estimated. Neither analysis calibrates relative warning grades against independently observed ecological events.

## Observed-input check for 2024-2025

`run_r56_observation_validation.py` compares the unchanged 2023-origin forecasts
with later observed inputs. It retains historical normalization bounds and weights,
reports historical-anchor continuation and a same-release 2023 bridge, and evaluates
input-wise clipping as a sensitivity. Two years do not calibrate warning performance
against ecological events.

```powershell
python run_r56_observation_validation.py --from-processed --work ./work/observed
```

This reproduces `data/r56_*` from the supplied raster class counts and climate
summaries. The observation script requires rasterio and pyproj; raw climate extraction also
requires xarray. Full extraction uses:

```powershell
python run_r56_observation_validation.py --lc-dir /path/to/v105 --old-lc-dir /path/to/v103 --baseline-lc-dir /path/to/2020 --cru-dir /path/to/cru --work ./work/observed
```

CLCD version 1.0.5 (2023-2025) is Zenodo record 18180184; the original 2023
control is version 1.0.3, record 12779975. Use the original provider filenames.
`data/r56_source_manifest.json` records checksums, pixel counts, extraction windows
and software versions. Historical data and forecast tables remain unchanged.

## Implementation notes

Choices that matter for reproducing the reported numbers:

- Weighting: AHP weights (Table 3) are combined with entropy weights from the
  maximum-entropy formula; the combination parameter is alpha = 0.4.
- Grey responses: accumulated response time starts at zero, so the first forecast
  follows the last fitted increment without a gap; the NGBM exponent 1 is singular and
  excluded from the search.
- Historical validation: one 2018 five-year holdout, ten one-year origins and six five-year
  origins; only the rolling five-year errors enter the mixture weights.
- Evaluation targets: historical rolling-validation targets use the full-period reconstruction, so the
  exercise is a retrospective evaluation of the fitted process rather than a real-time
  forecasting experiment.
- Bootstrap: the full estimator, including exponent selection, is refitted on
  logit-scale block-resampled histories and future logit disturbances are accumulated;
  the reported envelopes and grade shares are conditional simulation summaries.
- Spatial analysis: statistics use a separate six-indicator index evaluated at 1,914
  lattice points (29 x 66, 0.15 degrees); the shift fractions enumerate all 1,913
  non-identity periodic translations of that lattice and describe alignment under
  periodic boundaries.
- Effective sample size: the correlation-variance approximation is applied to the
  Pearson correlation only, not to the spatially weighted statistics.
- Obstacle diagnosis uses the primary eight-indicator normalized matrix and weights.

## Data sources

Climate: CRU TS 4.10. Land cover: China Land Cover Dataset (CLCD) v1.0, annual
collection (DOI 10.5281/zenodo.12779975; the 2020 tile used here is record 8176941).
Terrain: Copernicus DEM GLO-90. Independent vegetation product: NOAA CDR AVHRR/VIIRS
NDVI. The complete annual extension uses CLCD v1.0.5 (record 18180184); the additional productivity comparison uses MODIS Terra MOD17A3HGF Collection 6.1 (DOI 10.5067/MODIS/MOD17A3HGF.061). All are openly available from their providers.

## License

MIT; see `LICENSE`.
