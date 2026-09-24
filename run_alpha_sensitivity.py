# -*- coding: utf-8 -*-
"""T3 权重敏感性分析：α∈[0,1] 下 ESI 与预警等级稳定性（方法贡献之一）"""
import os
import sys, os
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "eco_security"))
from eco_security import minmax_normalize, entropy_weights, combined_weights, esi_series, classify_warning

# 路径自解析：仓库克隆/解压到任意目录均可运行
BASE = os.path.dirname(os.path.abspath(__file__))
cli = pd.read_csv(os.path.join(BASE, "data", "qilian_climate.csv"))
lc = pd.read_csv(os.path.join(BASE, "data", "qilian_landcover.csv"))
YEARS = list(range(2005, 2024))
reg_cli = cli[cli.unit == "区域(祁连山盒)"].set_index("year")
lc = lc.set_index("year").reindex(YEARS)
for c in lc.columns:
    lc[c] = lc[c].interpolate(method="linear").bfill().ffill()

indicators = {
    "X1_降水mm": (reg_cli["precip_mm"], +1), "X2_气温C": (reg_cli["temp_c"], +1),
    "X3_草地占比%": (lc["grass_pct"], +1), "X4_森林占比%": (lc["forest_pct"], +1),
    "X5_水域占比%": (lc["water_pct"], +1),
    "X6_裸地荒漠%": (100 - lc["grass_pct"] - lc["forest_pct"] - lc["water_pct"] - lc["crop_pct"], -1),
    "X7_农田占比%": (lc["crop_pct"], -1),
    "X8_草地变化率": (lc["grass_pct"].pct_change().fillna(0) * 100, +1),
    "X9_生态用地%": (lc["grass_pct"] + lc["forest_pct"] + lc["water_pct"], +1),
}
names = list(indicators.keys())
X = np.column_stack([indicators[n][0].values for n in names])
directions = [indicators[n][1] for n in names]
Xn = minmax_normalize(X, directions)
w_ent = entropy_weights(Xn)
w_ahp = np.ones(len(names)) / len(names)

print("α   2023ESI 2023等级  近5年均值  等级分布(2005-2023)")
rows = []
for alpha in np.arange(0, 1.01, 0.1):
    w = combined_weights(w_ahp, w_ent, alpha)
    esi = esi_series(Xn, w)
    lv = classify_warning(esi)
    from collections import Counter
    cnt = Counter(lv)
    rows.append({"alpha": round(alpha, 1), "esi_2023": round(esi[-1], 4),
                 "level_2023": lv[-1], "mean_last5": round(esi[-5:].mean(), 4),
                 "level_dist": dict(cnt)})
    print(f"{alpha:.1f}  {esi[-1]:.4f}  {lv[-1]:<4}  {esi[-5:].mean():.4f}  {dict(cnt)}")

df = pd.DataFrame(rows)
df.to_csv(os.path.join(BASE, "data", "results_alpha_sensitivity.csv"), index=False, encoding="utf-8-sig")
print("\n敏感性分析已保存: results_alpha_sensitivity.csv")
