# Ecological security early warning in the Qilian Mountain region, China

Reproduction materials for the manuscript *Ecological security early warning in the
Qilian Mountain region, China: temporal dynamics, forecasts, and spatial
associations*.

The study builds an eight-indicator Driving-Pressure-State-Impact (DPSI) system for the
Qilian Mountain region (2005-2023), weights it with a combined AHP-entropy scheme
(alpha = 0.4), builds the ecological security index (ESI), forecasts it with GM(1,1),
NGBM and ARIMA(0,1,1) responses and an inverse-RMSE mixture, and attributes the spatial
pattern with a GeoDetector on a separate six-indicator index.

## Contents

| path | content |
|---|---|
| `manuscript.tex`, `manuscript.bib`, `manuscript.bbl` | manuscript source (LaTeX, JMS house style) and bibliography |
| `data/` | processed inputs, weights, model outputs, validation and sensitivity tables; the tables used in the manuscript are `data/r47_*` |
| `figures/` | vector figure masters (PDF) plus the journal figure audit |
| `run_r47_revision.py` | end-to-end analysis: normalization, combined weighting, ESI series, grey and ARIMA responses with rolling-origin validation, mixture weights, conditional bootstrap, obstacle diagnosis, spatial attribution |
| `forecast_models.py` | grey (GM(1,1), NGBM) and ARIMA response implementations |
| `make_r47_figures.py`, `make_equations.py`, `make_bbl_jms.py` | figure masters, equation table and bibliography builder |
| `run_county_esi.py`, `README_county_esi.md` | static county-level relative index (Table 6) |
| `eco_security/` | shared utilities |

## Reproducing the reported results

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

## Implementation notes

Choices that matter for reproducing the reported numbers:

- Weighting: AHP weights (Table 3) are combined with entropy weights from the
  maximum-entropy formula; the combination parameter is alpha = 0.4.
- Grey responses: accumulated response time starts at zero, so the first forecast
  follows the last fitted increment without a gap; the NGBM exponent 1 is singular and
  excluded from the search.
- Validation: one 2018 five-year holdout, ten one-year origins and six five-year
  origins; only the rolling five-year errors enter the mixture weights.
- Evaluation targets: every validation target is the full-period reconstruction, so the
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
NDVI. All are openly available from their providers.

## License

MIT; see `LICENSE`.
