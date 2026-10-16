# County-level ecological security index (manuscript Table 6)

`run_county_esi.py` is the **sole producer** of `data/results_county_esi.csv`, the file behind Table 6
and the county ranking discussed in Section 4.

## Inputs (both committed)

| File | Content |
|---|---|
| `data/qilian_county_landcover.csv` | CLCD 2020 land-cover proportions within the ±0.1° centroid window of each of the 11 counties (produced by `run_county_geodetector.py`) |
| `data/qilian_climate.csv` | Annual climate per county; averaged over 2005–2023 here |

## Method (frozen)

Six indicators — annual precipitation (+), annual mean temperature (+), forest proportion (+),
grassland proportion (+), water proportion (+), barren/degraded proportion (−) — are min–max
normalised **across the 11 county units** and aggregated with the same AHP–entropy combined-weighting
scheme used for the regional analysis:

    w = 0.6 · w_entropy + 0.4 · w_AHP        (w_AHP equal weights)
    ESI_county = Σ_j w_j · x'_ij

## Reproduce

    python run_county_esi.py

Outputs:

- `data/results_county_esi.csv` — the published values (unit, esi_2020)
- `data/results_county_esi_details.csv` — normalised indicators, entropy/AHP/combined weights,
  and indicator directions, so every step can be audited

## Run order

    run_county_geodetector.py   →  qilian_county_landcover.csv, qilian_climate.csv
    run_county_esi.py           →  results_county_esi.csv   (Table 6)

`run_county_geodetector.py` writes its own CLCD-direct county table to
`data/results_county_esi_from_clcd.csv` and **no longer overwrites** `results_county_esi.csv`.

## Scope note

The county index is normalised within the 11 county units, so its numerical scale is not
identical to the regional ESI time series. County values are used for **ranking and spatial
prioritisation only**, not for warning-grade assignment.

---

## 中文说明（自用）

**这是什么**：论文表 6 那 11 个县域 ESI 数值的唯一来源脚本与数据。

**口径**：土地覆被取各县质心 ±0.1° 窗口内 CLCD 2020 各类占比；气候取 2005–2023 年均值；
6 个指标（降水+、气温+、林地+、草地+、水域+、裸地−）在 **11 个县级单元之间**做 min-max 标准化，
再按 `w = 0.6·熵权 + 0.4·AHP（等权）` 组合赋权求和。

**怎么复跑**：`python run_county_esi.py` → 直接生成表 6 数值，并额外输出
`results_county_esi_details.csv`（标准化后的指标 + 三套权重 + 方向），审稿人可逐步核对。

**顺序**：先 `run_county_geodetector.py`（产出土地覆被与气候输入），再 `run_county_esi.py`（产出表 6）。
前者的 CLCD 直读结果现在写到 `results_county_esi_from_clcd.csv`，不会覆盖表 6 的数据来源。

**边界说明**：县域指数是在 11 个县之间标准化的，与区域 ESI 时间序列不同刻度，
因此只用于**排序与空间优先级**，不用于预警等级判定。