# -*- coding: utf-8 -*-
"""县域静态 ESI（2020）——可复现脚本（manuscript Table 6 / 表 6 的唯一数据来源）

口径（冻结）:
  1) 土地覆被：质心 ±0.1° 窗口内 CLCD (2020) 各类别占比
     -> data/qilian_county_landcover.csv（由 run_county_geodetector.py 生成并已提交）
  2) 气候：该县 2005-2023 年 CRU TS 4.10 年均降水与年均气温的多年平均
     -> data/qilian_climate.csv
  3) 指标（6 个）：年降水(+)、年均气温(+)、林地占比(+)、草地占比(+)、水域占比(+)、
     裸地/退化占比(-)，其中 裸地占比 = 100 - 林地 - 草地 - 水域 - 耕地
  4) 标准化：在 11 个县级单元之间做 min-max 标准化（正向 +1 / 负向 -1）
  5) 权重：w = (1 - alpha) * w_entropy + alpha * w_AHP，alpha = 0.4，w_AHP 取等权
     （与区域分析使用同一套 AHP-熵权组合赋权方案）
  6) ESI = sum_j w_j * x'_ij

输出:
  data/results_county_esi.csv          -> 论文表 6 的数值（unit, esi_2020）
  data/results_county_esi_details.csv  -> 中间量（标准化指标、熵权、组合权重），供审稿复核

运行: python run_county_esi.py
"""
import os
import sys

import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "eco_security"))
from eco_security import minmax_normalize, entropy_weights, combined_weights, esi_series  # noqa: E402

ALPHA = 0.4  # AHP 权重占比（与区域分析一致）
REGION_UNIT = "区域(祁连山盒)"  # 区域盒单元不参与县级排序


def load_inputs():
    lc = pd.read_csv(os.path.join(BASE, "data", "qilian_county_landcover.csv"))
    cli = pd.read_csv(os.path.join(BASE, "data", "qilian_climate.csv"))
    cli = cli[cli.unit != REGION_UNIT]
    cnt_cli = cli.groupby("unit")[["precip_mm", "temp_c"]].mean()
    return lc.set_index("unit").join(cnt_cli).dropna()


def county_esi():
    m = load_inputs()
    indicators = ["precip_mm", "temp_c", "forest_pct", "grass_pct", "water_pct"]
    X = m[indicators].values
    barren_neg = (100.0 - m["forest_pct"] - m["grass_pct"] - m["water_pct"] - m["crop_pct"]).values
    X2 = np.column_stack([X, barren_neg])
    names = ["precip_mm", "temp_c", "forest_pct", "grass_pct", "water_pct", "barren_neg_pct"]
    directions = [+1, +1, +1, +1, +1, -1]

    Xn = minmax_normalize(X2, directions)
    w_ent = entropy_weights(Xn)
    w_ahp = np.ones(X2.shape[1]) / X2.shape[1]
    w = combined_weights(w_ahp, w_ent, ALPHA)
    esi = esi_series(Xn, w)

    detail = pd.DataFrame(Xn, columns=[n + "_norm" for n in names], index=m.index)
    detail.insert(0, "unit", m.index)
    for n, we, wa, wc, d in zip(names, w_ent, w_ahp, w, directions):
        detail["w_entropy_" + n] = we
        detail["w_ahp_" + n] = wa
        detail["w_combined_" + n] = wc
        detail["direction_" + n] = d
    out = pd.DataFrame({"unit": m.index, "esi_2020": np.round(esi, 4)})
    out = out.sort_values("esi_2020", ascending=False).reset_index(drop=True)
    return out, detail


def main():
    out, detail = county_esi()
    out.to_csv(os.path.join(BASE, "data", "results_county_esi.csv"), index=False, encoding="utf-8-sig")
    detail.to_csv(os.path.join(BASE, "data", "results_county_esi_details.csv"), index=False, encoding="utf-8-sig")
    print("静态县域 ESI (2020)，alpha = %.1f，11 个县级单元间 min-max 标准化 + AHP-熵权组合赋权" % ALPHA)
    print(out.to_string(index=False))
    print("\n已写入: data/results_county_esi.csv, data/results_county_esi_details.csv")
    return out


if __name__ == "__main__":
    main()