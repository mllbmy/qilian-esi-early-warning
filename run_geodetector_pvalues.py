# -*- coding: utf-8 -*-
"""GeoDetector 因子/交互 q 值的置换检验（999 次）

输出 data/results_geodetector_pvalues.csv —— 为论文 §3.5 / §4.5 的 q 与 p 值
提供**单一可溯源**数据源（此前的 p 值文件无生成脚本，不可复现）。

因子：4 个单因子（temp, precip, grass, barren）+ 6 对交互（C(4,2) 全枚举，与
run_interaction_detector.py 一致，避免选择性报告）。
"""
import sys
import os
import numpy as np
import pandas as pd

# 路径自解析：仓库克隆/解压到任意目录均可运行
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "eco_security"))
from eco_security import geodetector_q

NPERM = 999
rng = np.random.default_rng(42)

pts = pd.read_csv(os.path.join(BASE, "data", "spatial_samples.csv"))
esi = pd.read_csv(os.path.join(BASE, "data", "spatial_esi_points.csv"))
df = esi.merge(pts[["lat", "lon", "temp", "precip", "grass", "forest", "barren"]],
               on=["lat", "lon"])
y = df["esi"].values
print(f"样本数 n = {len(y)}")


def disc(x, k=4):
    """四分位分层（与单因子分析一致）"""
    qs = np.quantile(x, np.linspace(0, 1, k + 1)[1:-1])
    return np.digitize(x, qs)


def q_of(strata):
    return geodetector_q(y, strata)


def pval_perm(strata, q_obs):
    """置换检验：打乱分层标签，统计 q_perm >= q_obs 的比例"""
    cnt = 0
    for _ in range(NPERM):
        if q_of(rng.permutation(strata)) >= q_obs:
            cnt += 1
    return (cnt + 1) / (NPERM + 1)


factors = ["temp", "precip", "grass", "barren"]
strata = {f: disc(df[f].values, 4) for f in factors}

pairs = [("grass", "barren"), ("precip", "barren"), ("precip", "grass"),
         ("temp", "barren"), ("temp", "precip"), ("temp", "grass")]
for f1, f2 in pairs:
    strata[f1 + "+" + f2] = strata[f1] * 10 + strata[f2]

rows = []
print(f"\n=== 置换检验（{NPERM} 次）===")
for name, s in strata.items():
    q = q_of(s)
    p = pval_perm(s, q)
    rows.append({"factor": name, "q": q, "p": p})
    print(f"{name:<16} q={q:.4f}  p={p:.4f}")

pd.DataFrame(rows).round(6).to_csv(
    os.path.join(BASE, "data", "results_geodetector_pvalues.csv"),
    index=False, encoding="utf-8-sig")
print(f"\n已保存: results_geodetector_pvalues.csv（{len(rows)} 项 = 4 单因子 + 6 交互对）")