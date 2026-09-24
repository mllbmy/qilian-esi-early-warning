# -*- coding: utf-8 -*-
"""图8(交互q矩阵)— Arial 字体 + 统一学术配色（R5-M2）
注意：旧版图2（粉彩三栏流程）已废弃。图2 由 make_fig2_clean.py 生成单色版，
本脚本不再产出图2，以免重跑时用旧版覆盖已审定的图件。
统一 palette(全论文图共用):
  蓝 #2166ac / 绿 #1b7837 / 橙 #e07b39 / 红 #b2182b / 金 #f0a30a / 灰 #7f8c8d
"""
import os
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

# 路径自解析：仓库克隆/解压到任意目录均可运行
BASE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(BASE, "figures")
os.makedirs(FIG, exist_ok=True)

# 统一学术配色
BLUE, BLUE2, BLUE_L = "#2166ac", "#4393c3", "#d1e5f0"
GREEN, GREEN2, GREEN_L = "#1b7837", "#35978f", "#d9f0e3"
ORANGE, ORANGE_L = "#e07b39", "#fde8d0"
RED, RED_L = "#b2182b", "#f9dcd7"
GOLD, GRAY = "#f0a30a", "#7f8c8d"

plt.rcParams.update({"font.family": "Arial", "font.size": 9,
                     "mathtext.fontset": "custom", "mathtext.rm": "Arial",
                     "mathtext.it": "Arial:italic", "mathtext.bf": "Arial:bold",
                     "savefig.dpi": 600, "figure.dpi": 100})

# ================= 图8: 交互 q 矩阵 =================
sys.path.insert(0, os.path.join(BASE, "eco_security"))
from eco_security import geodetector_q

pts = pd.read_csv(os.path.join(BASE, "data", "spatial_samples.csv"))
esi = pd.read_csv(os.path.join(BASE, "data", "spatial_esi_points.csv"))
df = esi.merge(pts[["lat", "lon", "temp", "precip", "grass", "forest", "barren"]], on=["lat", "lon"])
y = df["esi"].values

def disc(x, k=4):
    qs = np.quantile(x, np.linspace(0, 1, k + 1)[1:-1])
    return np.digitize(x, qs)

single = {f: geodetector_q(y, disc(df[f].values)) for f in ["temp", "precip", "grass", "barren"]}
inter = {}
for f1, f2 in [("grass", "barren"), ("precip", "barren"), ("precip", "grass"),
               ("temp", "barren"), ("temp", "precip"), ("temp", "grass")]:
    combo = disc(df[f1].values, 4) * 10 + disc(df[f2].values, 4)
    inter[(f1, f2)] = geodetector_q(y, combo)

factors = ["temp", "precip", "grass", "barren"]
labels = ["Temperature", "Precipitation", "Grassland", "Barren"]
n = len(factors)
M = np.full((n, n), np.nan)
for k, f in enumerate(factors):
    M[k, k] = single[f]
for (f1, f2), q in inter.items():
    i, j = factors.index(f1), factors.index(f2)
    M[max(i, j), min(i, j)] = q
mask = np.triu(np.ones((n, n), dtype=bool), k=1)
Mdisp = np.ma.masked_where(mask, M)

fig, ax = plt.subplots(figsize=(5.8, 5.0))
cmap = plt.colormaps["YlGnBu"].copy()
cmap.set_bad("#ffffff")
im = ax.imshow(Mdisp, cmap=cmap, vmin=0.15, vmax=0.88)
ax.set_xticks(range(n)); ax.set_yticks(range(n))
ax.set_xticklabels(labels, fontsize=9.5)
ax.set_yticklabels(labels, fontsize=9.5)
ax.set_xticks(np.arange(-0.5, n, 1), minor=True)
ax.set_yticks(np.arange(-0.5, n, 1), minor=True)
ax.grid(which="minor", color="white", lw=1.6)
ax.tick_params(which="minor", length=0)
for i in range(n):
    for j in range(n):
        if mask[i, j]:
            continue
        v = M[i, j]
        if np.isnan(v):
            continue
        if i == j:
            ax.add_patch(Rectangle((j - 0.5, i - 0.5), 1, 1, fill=False, ec="#ffffff", lw=2.0))
        ax.text(j, i, f"{v:.3f}", ha="center", va="center", fontsize=9,
                color="white" if v > 0.52 else "#1a1a1a")
cb = plt.colorbar(im, ax=ax, shrink=0.9, pad=0.03)
cb.set_label("q value", fontsize=9.5)
cb.ax.tick_params(labelsize=8.5)
ax.set_title("GeoDetector interaction q (2020)", fontsize=11)
ax.text(0.5, -0.16, "Diagonal: single-factor q   ·   lower triangle: interaction q (all enhance)",
        transform=ax.transAxes, ha="center", va="top", fontsize=7.8, color="#555555")
plt.tight_layout()
plt.savefig(os.path.join(FIG, "fig8_interaction.png"), bbox_inches="tight")
plt.close()
print("saved fig8_interaction.png")