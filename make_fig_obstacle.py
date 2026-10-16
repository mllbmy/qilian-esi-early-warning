# -*- coding: utf-8 -*-
"""图 10 障碍因子：2005-2023 九项指标逐年障碍度单图多线 + 线端直接标注

R6：堆叠面积 / 堆叠柱 / 热图 / 3×3 分面（撞图 3 形式）均被否 →
单面板多线图（FT/NYT 编辑式强调）：
- 正文点名的 5 个主导因子用 DPSIR 层色粗线 + 右端直接标注（末端值间隙
  均 ≥0.03，无需错位）；其余 4 项（降水/气温/草地/裸地）浅灰细线退居背景，
  底部一条灰线图例说明——故事线（恢复期 S/R 约束 → 平台期 I/P 约束）直接可读；
- 全部 9 条线均在图中，数据零改动（行和校验=1）。
- 2010/2011 虚线分期，期段名置顶侧上方；x 轴延伸至 2030 为线端标注留白。
数值全部读自 data/results_obstacle.csv（与正文 0.233/0.221/0.151、
0.364/0.206 期段均值一致）。figsize 宽 = Word 插入宽 14.6 cm（5.75 in）1:1 字号。
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
df = pd.read_csv(os.path.join(BASE, "data", "results_obstacle.csv"), index_col=0)
years = df.index.astype(int).values

EN = {
    "降水": "Precipitation", "气温": "Temperature", "草地": "Grassland",
    "森林": "Forest", "水域": "Water", "裸地/荒漠": "Barren/degraded",
    "农田": "Cropland", "草地变化率": "Grassland change rate",
    "生态用地": "Ecological land",
}
assert set(EN) == set(df.columns), "results_obstacle.csv 列不一致"
# 正文点名的主导因子：恢复期 = 水域/森林/生态用地；平台期 = 草地变化率/农田
KEY = ["水域", "森林", "生态用地", "草地变化率", "农田"]
GREY = ["降水", "气温", "草地", "裸地/荒漠"]
# DPSIR 层色（与 fig_indicator_trends / fig_weights 同族）
COL = {
    "水域": "#52b788", "森林": "#2e8b57", "生态用地": "#5a4a8a",
    "草地变化率": "#b06c1f", "农田": "#d1495b",
}
C_GREY = "#c3c9cf"
INK, GRID = "#14181c", "#dce2e8"

# figsize 宽 = Word 插入宽 14.6 cm（5.75 in）→ 字体 1:1 等效印刷字号
fig, ax = plt.subplots(figsize=(5.75, 3.05), layout="constrained")

for c in GREY:                                   # 背景：其余 4 项浅灰细线
    ax.plot(years, df[c].values, color=C_GREY, lw=0.9, zorder=1)
for c in KEY:                                    # 前景：5 个主导因子层色粗线
    v = df[c].values
    ax.plot(years, v, color=COL[c], lw=1.5, zorder=3)
    ax.plot([years[-1]], [v[-1]], "o", ms=3.2, color=COL[c], zorder=4)
    lab = EN[c].replace("Grassland change rate", "Grassland\nchange rate")  # 长名折行缩留白
    ax.text(2023.5, v[-1], lab, fontsize=7.4, color=COL[c], linespacing=1.1,
            ha="left", va="center", zorder=4)

ax.axvline(2010.5, color=INK, lw=0.8, ls=(0, (3, 2)), zorder=2)
ax.text(2007.75, 1.035, "Recovery phase", transform=ax.get_xaxis_transform(),
        ha="center", va="bottom", fontsize=8, color="#4a5560")
ax.text(2016.75, 1.035, "Plateau phase", transform=ax.get_xaxis_transform(),
        ha="center", va="bottom", fontsize=8, color="#4a5560")

ax.set_xlim(2004.6, 2027.4)                      # 右延约 4 年为线端标注留白
ax.set_xticks([2005, 2008, 2011, 2014, 2017, 2020, 2023])
ax.xaxis.set_minor_locator(AutoMinorLocator(2))
ax.set_ylim(0, 0.5)
ax.set_yticks([0, 0.1, 0.2, 0.3, 0.4, 0.5])
ax.yaxis.set_minor_locator(AutoMinorLocator(2))
ax.set_ylabel("Annual obstacle degree", fontsize=9)
ax.tick_params(labelsize=8, length=2.0, pad=1.5)
ax.tick_params(which="minor", length=1.2, colors="#9aa7b2")
ax.grid(axis="both", color=GRID, lw=0.5, ls=(0, (4, 2)), zorder=0)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
for s in ("left", "bottom"):
    ax.spines[s].set_color("#9aa7b2")
    ax.spines[s].set_linewidth(0.6)

grey_lab = "Other indicators: " + ", ".join(EN[c] for c in GREY)
fig.legend(handles=[Line2D([], [], color=C_GREY, lw=0.9, label=grey_lab)],
           loc="outside lower center", ncol=1, fontsize=7.6, frameon=False,
           handlelength=1.6, handletextpad=0.5, borderaxespad=0.0)

FIG = os.path.join(BASE, "figures")
fig.savefig(os.path.join(FIG, "fig_obstacle.pdf"))
fig.savefig(os.path.join(FIG, "fig_obstacle.png"), dpi=600)
print("saved fig_obstacle.pdf/.png（多线强调版，9 线；行和=%.4f）"
      % df.sum(axis=1).mean())
