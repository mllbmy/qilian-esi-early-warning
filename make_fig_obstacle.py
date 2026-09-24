# -*- coding: utf-8 -*-
"""图 10 障碍因子：2005-2023 逐年障碍度堆叠面积图（每年各行和为 1）

数值全部读自 data/results_obstacle.csv（比值口径与正文 0.233/0.221/0.151、
0.364/0.206 期段均值一致；2010 虚线区分恢复期/平台期）。
样式对齐 make_fig_trends（jms_style：TNR 8-9 pt；DPSIR 五色）。
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import jms_style  # JMS 指南 §6：TNR 8-9 pt（R10 MEDIUM-2）
from matplotlib import patheffects

BASE = os.path.dirname(os.path.abspath(__file__))
df = pd.read_csv(os.path.join(BASE, "data", "results_obstacle.csv"), index_col=0)
years = df.index.astype(int).values

ORDER = ["降水", "气温", "草地", "森林", "水域", "裸地/荒漠", "农田", "草地变化率", "生态用地"]
EN = {
    "降水": "Precipitation", "气温": "Temperature", "草地": "Grassland",
    "森林": "Forest", "水域": "Water", "裸地/荒漠": "Barren/degraded",
    "农田": "Cropland", "草地变化率": "Grassland change rate",
    "生态用地": "Ecological land",
}
assert df.columns.tolist() == ORDER, "results_obstacle.csv 列序不一致"
COL = {
    "降水": "#74a9cf", "气温": "#c9dff0",
    "草地": "#b9d7a8", "森林": "#7fae87", "水域": "#2d6a4f",
    "裸地/荒漠": "#e08a8a", "农田": "#b23a48",
    "草地变化率": "#b06c1f",
    "生态用地": "#5a4a8a",
}
stack = [df[c].values for c in ORDER]
colors = [COL[c] for c in ORDER]
labs = [EN[c] for c in ORDER]

fig, ax = plt.subplots(figsize=(8.8, 3.3), layout="constrained")
ax.stackplot(years, stack, labels=labs, colors=colors, alpha=0.92)
ax.axvline(2010.5, color="#14181c", lw=0.8, ls=(0, (3, 2)), zorder=4)
# Qoder 定向修复：两标签左右错开避免互叠；白字+深描边兼顾深紫/棕底色
ax.text(2010.3, 0.985, "Recovery phase", fontsize=7.6, color="white", ha="right", va="top",
        path_effects=[patheffects.withStroke(linewidth=1.6, foreground="#333333")])
ax.text(2010.8, 0.985, "Plateau phase", fontsize=7.6, color="white", ha="left", va="top",
        path_effects=[patheffects.withStroke(linewidth=1.6, foreground="#333333")])
ax.set_xlim(2005, 2023)
ax.set_xticks([2005, 2008, 2011, 2014, 2017, 2020, 2023])
ax.set_ylim(0, 1.0)
ax.set_yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
ax.set_ylabel("Annual obstacle degree", fontsize=9)
ax.grid(axis="y", color="#ffffff", lw=0.6, zorder=3)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
for s in ("left", "bottom"):
    ax.spines[s].set_color("#9aa7b2")
    ax.spines[s].set_linewidth(0.6)
ax.legend(loc="center left", bbox_to_anchor=(1.005, 0.5), fontsize=7.4,
          frameon=False, ncol=1, handlelength=1.4, handletextpad=0.5,
          columnspacing=0.8)

FIG = os.path.join(BASE, "figures")
fig.savefig(os.path.join(FIG, "fig_obstacle.pdf"))
fig.savefig(os.path.join(FIG, "fig_obstacle.png"), dpi=600)
print("saved fig_obstacle.pdf/.png（堆叠面积，19 年；行和校验均值=%.4f）"
      % df.sum(axis=1).mean())