# -*- coding: utf-8 -*-
"""图 7 权重对比：熵权 / AHP / 组合（α=0.4）九指标分组横向条形图（矢量 PDF + 600 dpi PNG）

数值全部读自 data/results_weights.csv；图内不标注数值（口径与表 4 一致，避免舍入歧义）。
样式对齐 make_fig_trends（jms_style：TNR 8-9 pt；DPSIR 五色；成品宽度出图）。
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import jms_style  # JMS 指南 §6：TNR 8-9 pt（R10 MEDIUM-2）

BASE = os.path.dirname(os.path.abspath(__file__))
df = pd.read_csv(os.path.join(BASE, "data", "results_weights.csv"))

EN = {
    "X1_降水mm": "Precipitation (mm)",
    "X2_气温C": "Temperature (°C)",
    "X3_草地占比%": "Grassland (%)",
    "X4_森林占比%": "Forest (%)",
    "X5_水域占比%": "Water (%)",
    "X6_裸地荒漠%": "Barren/degraded (%)",
    "X7_农田占比%": "Cropland (%)",
    "X8_草地变化率": "Grassland change rate",
    "X9_生态用地%": "Ecological land (%)",
}
order = list(EN.keys())
assert df["indicator"].tolist() == order, "results_weights.csv 指标顺序与表 4 不一致"
labels = [EN[k] for k in order]

fig, ax = plt.subplots(figsize=(7.4, 3.3), layout="constrained")
y = np.arange(len(order))[::-1]          # 表中第 1 行显示在图顶部
h = 0.26
ax.barh(y + h, df["entropy_w"], height=h, color="#a9c4de", label="Entropy weight")
ax.barh(y,     df["ahp_w"],     height=h, color="#b8cfae", label="AHP weight")
ax.barh(y - h, df["combined_w"], height=h, color="#2a6f97",
        label="Combined weight ($\\alpha$ = 0.4)")
ax.set_yticks(y)
ax.set_yticklabels(labels, fontsize=8)
ax.set_xlim(0, 0.28)
ax.set_xticks([0, 0.05, 0.10, 0.15, 0.20, 0.25])
ax.set_xlabel("Weight", fontsize=9)
ax.grid(axis="x", color="#dce2e8", lw=0.5, zorder=0)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
for s in ("left", "bottom"):
    ax.spines[s].set_color("#9aa7b2")
    ax.spines[s].set_linewidth(0.6)
ax.legend(loc="lower left", bbox_to_anchor=(1.02, 0.02), fontsize=8, frameon=True,
          edgecolor="#9aa7b2", framealpha=1.0)

FIG = os.path.join(BASE, "figures")
fig.savefig(os.path.join(FIG, "fig_weights.pdf"))
fig.savefig(os.path.join(FIG, "fig_weights.png"), dpi=600)
print("saved fig_weights.pdf/.png（9 指标 × 3 权重系列）")