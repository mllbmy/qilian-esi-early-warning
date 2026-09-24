# -*- coding: utf-8 -*-
"""图4-5: 统一学术配色 + Arial 字体 + CVD 安全色图（R5-M2）
注意：图3（ESI 时序）已由 make_fig3_clean.py 生成，本脚本不再产出图3，
避免重跑时用旧版（图例压在预警带上）覆盖已审定的新图。"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import patheffects

# 路径自解析：仓库克隆/解压到任意目录均可运行
BASE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(BASE, "figures")
os.makedirs(FIG, exist_ok=True)

BLUE = "#2166ac"
GREEN = "#1b7837"
ORANGE = "#e07b39"
RED = "#b2182b"
GOLD = "#f0a30a"
PURPLE = "#6c5b9c"
# 统一预警5级: Severe / Medium / Mild / Rel. safe / Safe
WARN5 = [(0.0, 0.2, RED, "Severe"), (0.2, 0.4, ORANGE, "Medium"),
         (0.4, 0.6, "#f4d03f", "Mild"), (0.6, 0.8, "#7dcea0", "Rel. safe"),
         (0.8, 1.0, GREEN, "Safe")]

import jms_style  # JMS 指南§6：图内文字 Times New Roman 8–9 pt（R10 MEDIUM-2）
plt.rcParams.update({"axes.labelsize": 9, "xtick.labelsize": 8, "ytick.labelsize": 8,
                     "axes.edgecolor": "#444444", "axes.linewidth": 0.8,
                     "savefig.dpi": 600, "figure.dpi": 100})

esi_df = pd.read_csv(os.path.join(BASE, "data", "results_esi_regional.csv"))
alpha_df = pd.read_csv(os.path.join(BASE, "data", "results_alpha_sensitivity.csv"))
fc_df = pd.read_csv(os.path.join(BASE, "data", "results_forecast_comparison.csv"))
pts = pd.read_csv(os.path.join(BASE, "data", "spatial_esi_points.csv"))
QILIAN = {"Tianzhu": (37.20, 102.86), "Sunan": (38.84, 99.62), "Subei": (39.51, 97.85),
          "Aksai": (39.34, 94.34), "Minle": (38.43, 100.81), "Shandan": (38.78, 101.09),
          "Menyuan": (37.38, 101.62), "Qilian": (38.18, 100.24), "Gangcha": (37.33, 100.14),
          "Delingha": (37.37, 97.36), "Tianjun": (37.30, 99.02)}

# ---------- Fig 4: α 敏感性 ----------
fig, ax = plt.subplots(figsize=(7.0, 4.2))
a = alpha_df["alpha"].values; v = alpha_df["esi_2023"].values
ax.fill_between(a, 0.4, 0.6, color="#f4d03f", alpha=0.4, label="Mild-warning zone")
ax.plot(a, v, "-o", color=BLUE, lw=2, ms=5.5, zorder=3)
ax.axhline(0.4, color=RED, ls="--", lw=1.1, label="Medium-warning threshold (0.4)")
ax.axhline(0.6, color=GREEN, ls="--", lw=1.1, label="Relatively-safe threshold (0.6)")
ax.text(0.5, 0.55, f"ESI 2023: {v.min():.3f}-{v.max():.3f}\nGrade: mild warning (all α)",
        ha="center", fontsize=8.5, bbox=dict(boxstyle="round,pad=0.35", fc="white", ec=BLUE, alpha=0.9))
ax.set_xlabel(r"Weighting ratio $\alpha$ (0 = entropy only, 1 = AHP only)")
ax.set_ylabel("ESI 2023"); ax.set_xlim(0, 1); ax.set_ylim(0.35, 0.62)
ax.legend(fontsize=8, loc="lower right"); ax.grid(alpha=0.25, lw=0.4)
plt.tight_layout()
plt.savefig(os.path.join(FIG, "fig4_alpha_sensitivity.pdf"))
plt.savefig(os.path.join(FIG, "fig4_alpha_sensitivity.png"))
plt.close()

# ---------- Fig 5: 空间 ESI（R5-M2 CVD 安全色图 viridis + R5-M3 可读性重构） ----------
# R5-M3 根因：vmin=0/vmax=0.8 硬编码，点值集中于 0.1-0.5，viridis 只用了暗端。
# 处置：vmin/vmax 数据驱动(0.05-0.60)让色图全程发色、点径 s=24、县名白描边+错位、网格淡化。
fig, ax = plt.subplots(figsize=(7.4, 5.8))
sc = ax.scatter(pts["lon"], pts["lat"], c=pts["esi"], cmap="viridis", s=24,
                vmin=0.05, vmax=0.60, edgecolors="none", zorder=3)
cb = plt.colorbar(sc, ax=ax, shrink=0.82, pad=0.02, label="Point ESI (2020)")
cb.ax.tick_params(labelsize=8.5)
# 县名：白色描边防压点；对密集簇(Sunan/Shandan/Minle)差异化偏移防标签间重叠
OFF = {"Sunan": (5, 6), "Shandan": (6, -6), "Minle": (6, 4), "Qilian": (-6, 5),
       "Gangcha": (5, 4), "Menyuan": (6, -5), "Tianjun": (6, -6), "Delingha": (-6, 5),
       "Tianzhu": (-6, 6), "Subei": (4, 4), "Aksai": (4, 4)}
for n, (la, lo) in QILIAN.items():
    ax.plot(lo, la, "k.", ms=6, zorder=4)
    dx, dy = OFF.get(n, (4, 4))
    ax.annotate(n, (lo, la), fontsize=9.0, xytext=(dx, dy), textcoords="offset points",
                zorder=5, path_effects=[patheffects.withStroke(linewidth=2.2, foreground="white")])
ax.set_xlabel("Longitude (°E)"); ax.set_ylabel("Latitude (°N)")
ax.grid(alpha=0.12, lw=0.35); ax.set_aspect(1.15)
plt.tight_layout(); plt.savefig(os.path.join(FIG, "fig5_spatial_esi.png")); plt.close()

print("saved fig4/fig5 (fig3 见 make_fig3_clean.py)")