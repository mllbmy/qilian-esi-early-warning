# -*- coding: utf-8 -*-
"""图 8 单因子探测 q 值（4 因子，横向条形 + 数值标注）

数值全部读自 data/results_geodetector_pvalues.csv 中无 '+' 的单因子行；
标注 %.2f 与正文口径完全一致（barren 0.80 / grass 0.71 / precip 0.51 / temp 0.17）。
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
raw = pd.read_csv(os.path.join(BASE, "data", "results_geodetector_pvalues.csv"))
single = raw[~raw["factor"].str.contains("+", regex=False, na=False)].copy()  # 只留单因子行
LAB = {"temp": "Temperature", "precip": "Precipitation",
       "grass": "Grassland", "barren": "Barren/degraded"}
order = ["barren", "grass", "precip", "temp"]            # 图内从高到低
single = single.set_index("factor").loc[order].reset_index()
labs = [LAB[f] for f in single["factor"]]
qs = single["q"].astype(float).values

fig, ax = plt.subplots(figsize=(6.6, 2.2), layout="constrained")
yy = np.arange(len(single))[::-1]
ax.barh(yy, qs, height=0.58, color="#2a6f97")
for x, yv in zip(qs, yy):
    ax.text(x + 0.012, yv, "%.2f" % x, va="center", ha="left", fontsize=8, color="#14181c")
ax.set_yticks(yy)
ax.set_yticklabels(labs, fontsize=8)
ax.set_xlim(0, 0.95)
ax.set_xticks([0, 0.2, 0.4, 0.6, 0.8])
ax.set_xlabel("q statistic", fontsize=9)
ax.grid(axis="x", color="#dce2e8", lw=0.5, zorder=0)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
for s in ("left", "bottom"):
    ax.spines[s].set_color("#9aa7b2")
    ax.spines[s].set_linewidth(0.6)

FIG = os.path.join(BASE, "figures")
fig.savefig(os.path.join(FIG, "fig_geodetector_q.pdf"))
fig.savefig(os.path.join(FIG, "fig_geodetector_q.png"), dpi=600)
print("saved fig_geodetector_q.pdf/.png（4 单因子，q=%.2f..%.2f）" % (qs.min(), qs.max()))