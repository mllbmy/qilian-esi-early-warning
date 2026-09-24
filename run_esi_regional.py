# -*- coding: utf-8 -*-
"""构建全真实 DPSIR 指标矩阵并运行 ESI 预警管线（方向 A+T3 实证主体）
数据源：
  - 气候: paper-code/data/qilian_climate.csv (CRU 真实, 2005-2023, 区域+11县域)
  - 土地覆被: paper-code/data/qilian_landcover.csv (CLCD 真实, 2005/2010/2015/2020/2023, 区域)
输出: ESI 时序、预警等级、GM(1,1) 预测、精度检验 —— 写 Results 素材文件
"""
import os
import sys, os
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "eco_security"))
from eco_security import minmax_normalize, entropy_weights, combined_weights, esi_series, gm11_forecast, classify_warning

# 路径自解析：仓库克隆/解压到任意目录均可运行
BASE = os.path.dirname(os.path.abspath(__file__))
cli = pd.read_csv(os.path.join(BASE, "data", "qilian_climate.csv"))
lc = pd.read_csv(os.path.join(BASE, "data", "qilian_landcover.csv"))

YEARS = list(range(2005, 2024))

# ---------- 区域尺度指标矩阵 ----------
reg_cli = cli[cli.unit == "区域(祁连山盒)"].set_index("year")
# 土地覆被插值到年度（线性）
lc = lc.set_index("year").reindex(YEARS)
for c in lc.columns:
    lc[c] = lc[c].interpolate(method="linear").bfill().ffill()

# DPSIR 指标（方向：+ 正向生态 / - 负向）
indicators = {
    "X1_降水mm":      (reg_cli["precip_mm"], +1),
    "X2_气温C":       (reg_cli["temp_c"],    +1),
    "X3_草地占比%":    (lc["grass_pct"],      +1),
    "X4_森林占比%":    (lc["forest_pct"],     +1),
    "X5_水域占比%":    (lc["water_pct"],      +1),
    "X6_裸地荒漠%":    (100 - lc["grass_pct"] - lc["forest_pct"] - lc["water_pct"] - lc["crop_pct"], -1),
    "X7_农田占比%":    (lc["crop_pct"],       -1),
    "X8_草地变化率":   (lc["grass_pct"].pct_change().fillna(0) * 100, +1),
    "X9_生态用地%":    (lc["grass_pct"] + lc["forest_pct"] + lc["water_pct"], +1),
}
names = list(indicators.keys())
X = np.column_stack([indicators[n][0].values for n in names])
directions = [indicators[n][1] for n in names]

# 熵权
Xn = minmax_normalize(X, directions)
w_ent = entropy_weights(Xn)
# AHP：简化等权（正式版由专家判断矩阵给出；此处用熵权作为主权重演示组合方法）
w_ahp = np.ones(len(names)) / len(names)
w = combined_weights(w_ahp, w_ent, alpha=0.4)

esi = esi_series(Xn, w)
fut, fit, C, P = gm11_forecast(esi, n_pred=5)
levels = classify_warning(esi)
fut_levels = classify_warning(fut)

# ---------- 输出 Results 素材 ----------
print("=" * 70)
print("指标权重（熵权）:")
for n, ww in zip(names, w_ent):
    print(f"  {n:<14} {ww:.4f}")
print("组合权重(α=0.4):")
for n, ww in zip(names, w):
    print(f"  {n:<14} {ww:.4f}")
print()
print("ESI 时序与预警等级:")
for y, e, lv in zip(YEARS, esi, levels):
    print(f"  {y}  ESI={e:.4f}  {lv}")
print()
print(f"GM(1,1) 预测 2024-2028: {[round(v,4) for v in fut]}")
print(f"预测预警等级: {fut_levels}")
print(f"精度检验: C={C:.4f}  P={P:.4f}")
grade = "优" if (C < 0.35 and P > 0.95) else ("合格" if (C < 0.50 and P > 0.80) else ("勉强" if (C < 0.65 and P > 0.70) else "不合格"))
print(f"精度等级: {grade}")
print("=" * 70)

# 保存 Results 素材
res = pd.DataFrame({
    "year": YEARS, "esi": esi.round(4), "warning": levels,
    "forecast": list(fut.round(4)) + [np.nan]*14,
    "fc_warning": fut_levels + [""]*14,
})
res.to_csv(os.path.join(BASE, "data", "results_esi_regional.csv"), index=False, encoding="utf-8-sig")
wdf = pd.DataFrame({"indicator": names, "entropy_w": w_ent.round(4), "combined_w": w.round(4), "direction": directions})
wdf.to_csv(os.path.join(BASE, "data", "results_weights.csv"), index=False, encoding="utf-8-sig")
print("Results 素材已保存: results_esi_regional.csv, results_weights.csv")
