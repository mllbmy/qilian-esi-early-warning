# -*- coding: utf-8 -*-
"""AHP 准则层判断矩阵 → 权重 + 一致性指标（λmax / CI / CR）

为论文 §3.2 提供**可溯源**的 AHP 结果。此前判断矩阵只存在于一次性脚本中，
λmax 与 CI 从未落盘，导致审稿人无法验证 AHP 是否真实执行（审稿意见 R1-M1）。

设计：准则层（D/P/S/I/R）用 Saaty 1–9 标度构造 5×5 判断矩阵；
层内指标权重按该层指标数均分。

输出：
  data/results_ahp_criteria.csv    准则层权重
  data/results_ahp_consistency.csv λmax / CI / RI / CR
  data/ahp_weights.csv             9 个指标的 AHP 权重（供管线读取）
"""
import os
from collections import Counter

import numpy as np
import pandas as pd

# 路径自解析：仓库克隆/解压到任意目录均可运行
BASE = os.path.dirname(os.path.abspath(__file__))

# 准则层顺序：D(驱动力), P(压力), S(状态), I(影响), R(响应)
CRIT = ["Driving", "Pressure", "State", "Impact", "Response"]

# 判断矩阵：S 对生态安全的指示性最强，R 次之，I 居中，D/P 为背景（标度依据写入论文 §3.2）
CMP = np.array([
    [1, 1, 1 / 5, 1 / 2, 1 / 3],   # D
    [1, 1, 1 / 5, 1 / 2, 1 / 3],   # P
    [5, 5, 1, 3, 2],               # S
    [2, 2, 1 / 3, 1, 1 / 2],       # I
    [3, 3, 1 / 2, 2, 1],           # R
])

n = CMP.shape[0]
eigvals, eigvecs = np.linalg.eig(CMP)
k = int(np.argmax(eigvals.real))
lam = float(eigvals.real[k])
w_crit = np.abs(eigvecs[:, k].real)
w_crit = w_crit / w_crit.sum()

CI = (lam - n) / (n - 1)
RI_TABLE = {1: 0.0, 2: 0.0, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45}
RI = RI_TABLE[n]
CR = CI / RI

print("=== AHP 准则层 ===")
for nm, w in zip(CRIT, w_crit):
    print(f"  {nm:<10} {w:.4f}")
print(f"  lambda_max = {lam:.4f}   CI = {CI:.4f}   RI = {RI:.2f}   CR = {CR:.4f}"
      f"   ({'通过' if CR < 0.1 else '不通过'} CR<0.1)")

crit_of_ind = {
    "X1_降水mm": "Driving", "X2_气温C": "Driving",
    "X3_草地占比%": "State", "X4_森林占比%": "State", "X5_水域占比%": "State",
    "X6_裸地荒漠%": "Pressure", "X7_农田占比%": "Pressure",
    "X8_草地变化率": "Impact", "X9_生态用地%": "Response",
}
ind_names = list(crit_of_ind.keys())
cnt = Counter(crit_of_ind.values())
w_ahp = np.array([w_crit[CRIT.index(crit_of_ind[i])] / cnt[crit_of_ind[i]] for i in ind_names])

print("\n=== 指标层 AHP 权重（层内均分）===")
for nm, w in zip(ind_names, w_ahp):
    print(f"  {nm:<14} {w:.6f}")
print(f"  合计 = {w_ahp.sum():.6f}")

pd.DataFrame({"criterion": CRIT, "weight": w_crit.round(6)}).to_csv(
    os.path.join(BASE, "data", "results_ahp_criteria.csv"), index=False, encoding="utf-8-sig")
pd.DataFrame([{"n": n, "lambda_max": round(lam, 6), "CI": round(CI, 6), "RI": RI,
               "CR": round(CR, 6), "threshold": 0.1, "pass": bool(CR < 0.1)}]).to_csv(
    os.path.join(BASE, "data", "results_ahp_consistency.csv"), index=False, encoding="utf-8-sig")
with open(os.path.join(BASE, "data", "ahp_weights.csv"), "w", encoding="utf-8-sig") as f:
    f.write("indicator,ahp_weight\n")
    for nm, w in zip(ind_names, w_ahp):
        f.write(f"{nm},{w:.6f}\n")

print("\n已保存: results_ahp_criteria.csv / results_ahp_consistency.csv / ahp_weights.csv")