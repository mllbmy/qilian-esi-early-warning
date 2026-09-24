# -*- coding: utf-8 -*-
"""图 9 交互探测：6 对因子的 q1/q2/联合 q 分组柱状图（联合值标注三位，与表 7 一致）

数值全部读自 data/results_interaction_detector.csv（q_interaction 三位标注
0.818/0.833/0.808/0.849/0.723/0.529，与表 7 逐位一致）。
样式对齐 make_fig_trends（jms_style：TNR 8-9 pt；成品宽度出图）。
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import jms_style  # JMS 指南 §6：TNR 8-9 pt（R10 MEDIUM-2）

BASE = os.path.dirname(os.path.abspath(__file__))
df = pd.read_csv(os.path.join(BASE, "data", "results_interaction_detector.csv"))
PAIR_LABEL = {
    "grass+barren": "Grassland × Barren",
    "precip+barren": "Precipitation × Barren",
    "precip+grass": "Precipitation × Grassland",
    "temp+barren": "Temperature × Barren",
    "temp+grass": "Temperature × Grassland",
    "temp+precip": "Temperature × Precipitation",
}
assert set(df["pair"]) == set(PAIR_LABEL), "交互对与表 7 映射不一致"
df = df.set_index("pair").loc[list(PAIR_LABEL)].reset_index()   # 保持表 7 行序
labs = [PAIR_LABEL[p] for p in df["pair"]]
q1 = df["q1"].astype(float).values
q2 = df["q2"].astype(float).values
qj = df["q_interaction"].astype(float).values

fig, ax = plt.subplots(figsize=(8.6, 2.9), layout="constrained")
x = np.arange(len(df))
w = 0.27
ax.bar(x - w, q1, width=w, color="#c3d3e0", label="Individual $q_1$")
ax.bar(x,     q2, width=w, color="#b9cfb8", label="Individual $q_2$")
ax.bar(x + w, qj, width=w, color="#2a6f97", label="Joint $q_{\\mathrm{int}}$")
for xx, v in zip(x + w, qj):
    ax.text(xx, v + 0.012, "%.3f" % v, ha="center", va="bottom", fontsize=7.2, color="#14181c")
ax.set_xticks(x)
ax.set_xticklabels(labs, fontsize=7.6, rotation=18, ha="right")
ax.set_ylim(0, 1.0)
ax.set_ylabel("q", fontsize=9)
ax.grid(axis="y", color="#dce2e8", lw=0.5, zorder=0)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
for s in ("left", "bottom"):
    ax.spines[s].set_color("#9aa7b2")
    ax.spines[s].set_linewidth(0.6)
ax.legend(loc="upper left", fontsize=8, frameon=False, ncol=3,
          bbox_to_anchor=(0.0, 1.02))

FIG = os.path.join(BASE, "figures")
fig.savefig(os.path.join(FIG, "fig_interaction.pdf"))
fig.savefig(os.path.join(FIG, "fig_interaction.png"), dpi=600)
print("saved fig_interaction.pdf/.png（6 对交互，q_int 三位与表 7 一致）")