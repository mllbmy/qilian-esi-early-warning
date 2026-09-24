# -*- coding: utf-8 -*-
"""GeoDetector 交互探测器：因子两两交互 q 值（高区论文标配补充）"""
import os
import sys, os
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "eco_security"))
from eco_security import geodetector_q

# 路径自解析：仓库克隆/解压到任意目录均可运行
BASE = os.path.dirname(os.path.abspath(__file__))
pts = pd.read_csv(os.path.join(BASE, "data", "spatial_samples.csv"))
esi = pd.read_csv(os.path.join(BASE, "data", "spatial_esi_points.csv"))
df = esi.merge(pts[["lat", "lon", "temp", "precip", "grass", "forest", "barren"]], on=["lat", "lon"])
y = df["esi"].values

def disc(x, k=4):
    qs = np.quantile(x, np.linspace(0, 1, k + 1)[1:-1])
    return np.digitize(x, qs)

single = {f: geodetector_q(y, disc(df[f].values)) for f in ["temp", "precip", "grass", "barren"]}
print("单因子 q:", {k: round(v, 4) for k, v in single.items()})
print()
print("=== 交互探测器 ===")
print(f"{'Factor pair':<18}{'q1':<8}{'q2':<8}{'q_int':<8}{'Relation'}")
rows = []
for f1, f2 in [("grass", "barren"), ("precip", "barren"), ("precip", "grass"), ("temp", "barren"), ("temp", "precip"), ("temp", "grass")]:
    q1, q2 = single[f1], single[f2]
    combo = disc(df[f1].values, 4) * 10 + disc(df[f2].values, 4)
    qi = geodetector_q(y, combo)
    rel = "enhance" if qi > max(q1, q2) else ("weaken" if qi < min(q1, q2) else "nonlinear")
    print(f"{f1}+{f2:<12}{q1:.4f}  {q2:.4f}  {qi:.4f}  {rel}")
    rows.append({"pair": f1 + "+" + f2, "q1": q1, "q2": q2, "q_interaction": qi, "relation": rel})
pd.DataFrame(rows).to_csv(os.path.join(BASE, "data", "results_interaction_detector.csv"), index=False, encoding="utf-8-sig")
print("\n已保存: results_interaction_detector.csv")
