# -*- coding: utf-8 -*-
"""图3 重绘（R4-m2）：图例移出绘图区（无边框）、去悬浮数值标注、
预警带改为右侧等级刻度；数据与旧图完全一致。"""
import os

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# 路径自解析：仓库克隆/解压到任意目录均可运行
BASE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(BASE, "figures")

BLUE, ORANGE, PURPLE, RED = "#2166ac", "#e07b39", "#6c5b9c", "#b2182b"
WARN5 = [(0.0, 0.2, RED, "Severe"), (0.2, 0.4, ORANGE, "Medium"),
         (0.4, 0.6, "#f4d03f", "Mild"), (0.6, 0.8, "#7dcea0", "Rel. safe"),
         (0.8, 1.0, "#1b7837", "Safe")]

import jms_style  # JMS 指南§6：图内文字 Times New Roman 8–9 pt（R10 MEDIUM-2）
plt.rcParams.update({"axes.labelsize": 9, "xtick.labelsize": 8, "ytick.labelsize": 8,
                     "axes.edgecolor": "#444444", "axes.linewidth": 0.8,
                     "savefig.dpi": 600, "figure.dpi": 100})

esi_df = pd.read_csv(os.path.join(BASE, "data", "results_esi_regional.csv"))
fc_df = pd.read_csv(os.path.join(BASE, "data", "results_forecast_comparison.csv"))

fig, ax = plt.subplots(figsize=(8.8, 4.6))
years = esi_df["year"].values

for lo, hi, c, lab in WARN5:
    ax.axhspan(lo, hi, color=c, alpha=0.10, zorder=0)

ax.plot(years, esi_df["esi"], "-o", color=BLUE, lw=2.0, ms=4.5, zorder=3,
        label="Observed ESI")
fcy = np.arange(2024, 2029)
ax.plot(fcy, fc_df["gm11"], "--s", color=BLUE, lw=1.4, ms=3.8, zorder=3,
        label="GM(1,1)")
ax.plot(fcy, fc_df["ngbm"], "--^", color=ORANGE, lw=1.4, ms=3.8, zorder=3,
        label="NGBM")
ax.plot(fcy, fc_df["arima"], "--v", color=PURPLE, lw=1.4, ms=3.8, zorder=3,
        label="ARIMA")
ax.axvspan(2023.5, 2028.5, color="#cccccc", alpha=0.20, zorder=1)
ax.text(2026.0, 0.775, "Forecast", fontsize=8.5, ha="center", color="#555555")

# 预警带等级刻度：置于绘图区右侧外，避免压带
for lo, hi, c, lab in WARN5:
    mid = (lo + hi) / 2
    if mid > 0.80:
        continue
    ax.text(2029.1, mid, lab, fontsize=8.0, color="#555555",
            va="center", ha="left", clip_on=False)

ax.set_xlabel("Year")
ax.set_ylabel("Ecological security index (ESI)")
ax.set_xlim(2004.5, 2028.5)
ax.set_ylim(0, 0.82)
# 图例移出绘图区（下方横排、无边框）——修掉“图例压预警带”
ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=4,
          frameon=False, fontsize=8.5)
ax.grid(alpha=0.25, lw=0.4)

plt.tight_layout()
plt.savefig(os.path.join(FIG, "fig3_esi_timeseries.pdf"), bbox_inches="tight")
plt.savefig(os.path.join(FIG, "fig3_esi_timeseries.png"), bbox_inches="tight")
plt.close()
print("saved fig3_esi_timeseries.pdf + .png (legend outside, Arial)")