# -*- coding: utf-8 -*-
"""图 7 权重对比：熵权 / AHP / 组合（α=0.4）九指标哑铃图（矢量 PDF + 600 dpi PNG）

R2 重构：27 根分组横条 → 每指标一条灰线连接熵权与 AHP 权（直观呈现两法分歧），
组合权重为深蓝实心点落于连线上（=0.6·entropy+0.4·AHP，必居两者之间）。
行按组合权重降序排列；指标前缀 DPSIR 层字母（与 fig_indicator_trends 一致）。
数值全部读自 data/results_weights.csv；图内不标注数值（口径与表 4 一致，避免舍入歧义）。
样式对齐 make_fig_trends（jms_style：TNR 8-9 pt；成品宽度出图 1:1 字号）。
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.ticker import AutoMinorLocator

import jms_style  # JMS 指南 §6：TNR 8-9 pt

BASE = os.path.dirname(os.path.abspath(__file__))
df = pd.read_csv(os.path.join(BASE, "data", "results_weights.csv"))
df = df.set_index("indicator")

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
LAYER = {  # DPSIR 分层（与 fig_indicator_trends 一致）
    "X1_降水mm": "D", "X2_气温C": "D",
    "X3_草地占比%": "S", "X4_森林占比%": "S", "X5_水域占比%": "S",
    "X6_裸地荒漠%": "P", "X7_农田占比%": "P",
    "X8_草地变化率": "I", "X9_生态用地%": "R",
}
assert set(df.index) == set(EN), "results_weights.csv 指标与表 4 不一致"

# 按组合权重降序：最重要的指标置顶
order = sorted(EN, key=lambda k: -df.loc[k, "combined_w"])
labels = [EN[k] for k in order]

C_ENT = "#4a7ba6"   # 熵权：钢蓝空心圆
C_AHP = "#6b9e5f"   # AHP：灰绿空心菱
C_COM = "#1f4e79"   # 组合：深蓝实心圆
LNK_E = "#b4c7d8"   # 分歧连线：熵权占优 → 钢蓝浅调
LNK_A = "#bcd2b2"   # 分歧连线：AHP 占优 → 灰绿浅调
# DPSIR 层字母配色（与 fig_indicator_trends 层色系同族）
LAYER_C = {"D": "#1f6f9f", "S": "#2e8b57", "P": "#d1495b",
           "I": "#b06c1f", "R": "#5a4a8a"}

# figsize 宽 = 正文插图宽 13.5 cm（5.31 in）→ 字体 1:1 等效印刷字号
fig, ax = plt.subplots(figsize=(5.31, 3.05), layout="constrained")
y = np.arange(len(order))[::-1]          # 组合权重最大者显示在图顶部

for i, (yi, k) in enumerate(zip(y, order)):
    e, a, c = (df.loc[k, "entropy_w"], df.loc[k, "ahp_w"], df.loc[k, "combined_w"])
    if i % 2 == 1:                       # 隔行浅底纹，引导视线横读
        ax.axhspan(yi - 0.5, yi + 0.5, facecolor="#f4f6f9", lw=0, zorder=0)
    ax.plot([e, a], [yi, yi], color=LNK_E if e > a else LNK_A, lw=2.2,
            zorder=1, solid_capstyle="round")
    ax.plot([e], [yi], marker="o", ms=5.5, mfc="white", mec=C_ENT, mew=1.2,
            ls="", zorder=2)
    ax.plot([a], [yi], marker="D", ms=4.6, mfc="white", mec=C_AHP, mew=1.2,
            ls="", zorder=2)
    ax.plot([c], [yi], marker="o", ms=7.5, mfc=C_COM, mec="white", mew=0.9,
            ls="", zorder=3)
    # 层字母置图内左缘（最小权重 0.0407，x<0.035 区域恒为空）
    ax.text(0.007, yi, LAYER[k], fontsize=8.5, fontweight="bold",
            color=LAYER_C[LAYER[k]], ha="center", va="center", zorder=4)

ax.set_yticks(y)
ax.set_yticklabels(labels, fontsize=8)
ax.set_ylim(-0.6, len(order) - 0.4)
ax.set_xlim(0, 0.28)
ax.set_xticks([0, 0.05, 0.10, 0.15, 0.20, 0.25])
ax.xaxis.set_minor_locator(AutoMinorLocator(2))   # 主刻度间 1 个次级刻度
ax.set_xlabel("Weight", fontsize=9)
ax.tick_params(labelsize=8, length=2.0, pad=1.5)
ax.tick_params(which="minor", length=1.2, colors="#9aa7b2")
ax.grid(axis="x", color="#dce2e8", lw=0.5, ls=(0, (4, 2)), zorder=0)  # 竖向虚线网格
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
for s in ("left", "bottom"):
    ax.spines[s].set_color("#9aa7b2")
    ax.spines[s].set_linewidth(0.6)

handles = [
    Line2D([], [], marker="o", ms=5.5, mfc="white", mec=C_ENT, mew=1.2, ls="",
           label="Entropy weight"),
    Line2D([], [], marker="D", ms=4.6, mfc="white", mec=C_AHP, mew=1.2, ls="",
           label="AHP weight"),
    Line2D([], [], marker="o", ms=6.5, mfc=C_COM, mec="white", mew=0.9, ls="",
           label="Combined weight ($\\alpha$ = 0.4)"),
]
# 图例外置底部居中、无边框（与 fig_indicator_trends 一致）
ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.155),
          ncol=3, fontsize=8, frameon=False, handletextpad=0.4,
          columnspacing=1.2)

FIG = os.path.join(BASE, "figures")
fig.savefig(os.path.join(FIG, "fig_weights.pdf"))
fig.savefig(os.path.join(FIG, "fig_weights.png"), dpi=600)
print("saved fig_weights.pdf/.png（9 指标哑铃图：熵权-AHP 分歧连线 + 组合权重）")
