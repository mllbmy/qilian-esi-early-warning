# -*- coding: utf-8 -*-
"""图 8 单因子探测 q 值（4 因子，棒棒糖图 + 数值标注）

R2 重构：单色横条 → 棒棒糖（细茎 + DPSIR 层色圆点 + 层字母），与 fig_weights
哑铃图同一视觉体系；figsize 宽 = Word 插入宽 10.5 cm（4.13 in），字体 1:1 等效
印刷字号（旧版 6.6 in 插入 10.5 cm，字号被缩至 0.63 倍）。
数值全部读自 data/results_geodetector_pvalues.csv 中无 '+' 的单因子行；
标注 %.2f 与正文口径完全一致（barren 0.80 / grass 0.71 / precip 0.51 / temp 0.17）。
样式对齐 make_fig_trends / make_fig_weights（jms_style：TNR 8-9 pt）。
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import AutoMinorLocator

import jms_style  # JMS 指南 §6：TNR 8-9 pt

BASE = os.path.dirname(os.path.abspath(__file__))
raw = pd.read_csv(os.path.join(BASE, "data", "results_geodetector_pvalues.csv"))
single = raw[~raw["factor"].str.contains("+", regex=False, na=False)].copy()  # 只留单因子行
LAB = {"temp": "Temperature", "precip": "Precipitation",
       "grass": "Grassland", "barren": "Barren/degraded"}
LAYER = {"temp": "D", "precip": "D", "grass": "S", "barren": "P"}
# DPSIR 层色（与 fig_indicator_trends / fig_weights 层色系同族）
LAYER_C = {"D": "#1f6f9f", "S": "#2e8b57", "P": "#d1495b"}
LAYER_T = {"D": "#bcd4e2", "S": "#bcd9c6", "P": "#ecc3ca"}  # 茎用层色浅调
order = ["barren", "grass", "precip", "temp"]            # 图内从高到低
single = single.set_index("factor").loc[order].reset_index()
labs = [LAB[f] for f in single["factor"]]
qs = single["q"].astype(float).values

INK = "#14181c"
# figsize 宽 = Word 插入宽 10.5 cm（4.13 in）→ 字体 1:1 等效印刷字号
fig, ax = plt.subplots(figsize=(4.13, 1.75), layout="constrained")
yy = np.arange(len(single))[::-1]

for i, (x, yv, f) in enumerate(zip(qs, yy, single["factor"])):
    if i % 2 == 1:                       # 隔行浅底纹（与 fig_weights 一致）
        ax.axhspan(yv - 0.5, yv + 0.5, facecolor="#f4f6f9", lw=0, zorder=0)
    c = LAYER_C[LAYER[f]]
    ax.plot([0, x], [yv, yv], color=LAYER_T[LAYER[f]], lw=2.4,
            solid_capstyle="round", zorder=1)
    ax.plot([x], [yv], marker="o", ms=8.0, mfc=c, mec="white", mew=1.0,
            ls="", zorder=3)
    ax.text(x + 0.022, yv, "%.2f" % x, va="center", ha="left",
            fontsize=8, color=INK, zorder=4)
    # 层字母置图内左缘（最小 q=0.17，x<0.1 区域恒为空）
    ax.text(0.028, yv, LAYER[f], fontsize=8.5, fontweight="bold", color=c,
            ha="center", va="center", zorder=4)

ax.set_yticks(yy)
ax.set_yticklabels(labs, fontsize=8)
ax.set_ylim(-0.6, len(single) - 0.4)
ax.set_xlim(0, 0.95)
ax.set_xticks([0, 0.2, 0.4, 0.6, 0.8])
ax.xaxis.set_minor_locator(AutoMinorLocator(2))   # 主刻度间 1 个次级刻度
ax.set_xlabel("q statistic", fontsize=9)
ax.tick_params(labelsize=8, length=2.0, pad=1.5)
ax.tick_params(which="minor", length=1.2, colors="#9aa7b2")
ax.grid(axis="x", color="#dce2e8", lw=0.5, ls=(0, (4, 2)), zorder=0)  # 竖向虚线网格
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
for s in ("left", "bottom"):
    ax.spines[s].set_color("#9aa7b2")
    ax.spines[s].set_linewidth(0.6)

FIG = os.path.join(BASE, "figures")
fig.savefig(os.path.join(FIG, "fig_geodetector_q.pdf"))
fig.savefig(os.path.join(FIG, "fig_geodetector_q.png"), dpi=600)
print("saved fig_geodetector_q.pdf/.png（4 单因子棒棒糖，q=%.2f..%.2f）" % (qs.min(), qs.max()))
