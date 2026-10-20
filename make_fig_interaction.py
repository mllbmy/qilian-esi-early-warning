# -*- coding: utf-8 -*-
"""图 9 交互探测：6 对因子的 q1/q2/联合 q 分组柱状图（联合值标注三位，与表 7 一致）

数值全部读自 data/results_interaction_detector.csv（q_interaction 三位标注
0.818/0.833/0.808/0.849/0.723/0.529，与表 7 逐位一致）。

JMS 合规（本轮 R37 重排）：
  * 画布宽 = 印刷插入宽 16.00 cm（jms_style），图内文字全部 TNR 8–9 pt；
  * 原先把 6 个因子对标签旋转 18° 排在一行（8.6 in 画布缩到 16 cm 后掉到 7.6 pt），
    现改为**两行标签 + 16 cm 画布**：标签不旋转、不缩号，仍全部保留 6 对因子，
    未删除任何数据系列、未改动任何数值；
  * 图例中的 q1/q2/q_int 用 Unicode 下标（q₁ / q₂ / qᵢₙₜ）而非 mathtext——
    mathtext 下标会被压到 0.7 倍（8 pt -> 5.6 pt），违反 8–9 pt 下限。
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import jms_style  # JMS 指南 §6：画布 16.00 cm + TNR 8–9 pt

BASE = os.path.dirname(os.path.abspath(__file__))
df = pd.read_csv(os.path.join(BASE, "data", "results_interaction_detector.csv"))
# 显示标签：两行排版（避免旋转压字/缩号），因子对与表 7 行序一一对应
PAIR_LABEL = {
    "grass+barren": "Grassland\n\u00d7 Barren",
    "precip+barren": "Precipitation\n\u00d7 Barren",
    "precip+grass": "Precipitation\n\u00d7 Grassland",
    "temp+barren": "Temperature\n\u00d7 Barren",
    "temp+grass": "Temperature\n\u00d7 Grassland",
    "temp+precip": "Temperature\n\u00d7 Precipitation",
}
assert set(df["pair"]) == set(PAIR_LABEL), "交互对与表 7 映射不一致"
df = df.set_index("pair").loc[list(PAIR_LABEL)].reset_index()   # 保持表 7 行序
labs = [PAIR_LABEL[p] for p in df["pair"]]
q1 = df["q1"].astype(float).values
q2 = df["q2"].astype(float).values
qj = df["q_interaction"].astype(float).values

fig, ax = jms_style.subplots(height_cm=8.0, layout="constrained")
x = np.arange(len(df))
w = 0.27
ax.bar(x - w, q1, width=w, color="#c3d3e0", label="Individual q\u2081")
ax.bar(x,     q2, width=w, color="#b9cfb8", label="Individual q\u2082")
ax.bar(x + w, qj, width=w, color="#2a6f97", label="Joint q\u1d62\u2099\u209c")
for xx, v in zip(x + w, qj):
    ax.text(xx, v + 0.012, "%.3f" % v, ha="center", va="bottom", fontsize=8.0,
            color="#14181c")
ax.set_xticks(x)
ax.set_xticklabels(labs, fontsize=8.0, linespacing=1.05)
ax.set_ylim(0, 1.0)
ax.set_ylabel("q", fontsize=9)
ax.grid(axis="y", color="#dce2e8", lw=0.5, zorder=0)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
for s in ("left", "bottom"):
    ax.spines[s].set_color("#9aa7b2")
    ax.spines[s].set_linewidth(0.6)
ax.tick_params(labelsize=8.0, length=2.0, pad=1.5)
ax.legend(loc="upper left", fontsize=8, frameon=False, ncol=3,
          bbox_to_anchor=(0.0, 1.02), handlelength=1.6, columnspacing=1.2)

FIG = os.path.join(BASE, "figures")
jms_style.save(fig, "fig_interaction", outdir=FIG)
plt.close()
print("saved fig_interaction.pdf/.png（6 对交互，q_int 三位与表 7 一致）")
