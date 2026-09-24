# -*- coding: utf-8 -*-
"""DPSIR 概念分析框架图（新图，方法节开篇；矢量 PDF + 600dpi PNG）
展示：D→P→S→I→R 因果链（9 指标归层标 +/-）→ 归一化+组合权重 → ESI → 预警分级
→ 分区管理 / 预测 / 归因；R 层虚线反馈环。Arial、viridis 派生态色系、CVD-safe。"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import rcParams
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

rcParams["font.family"] = "Arial"
rcParams["pdf.fonttype"] = 42
rcParams["axes.unicode_minus"] = False

# 路径自解析：仓库克隆/解压到任意目录均可运行
BASE = os.path.dirname(os.path.abspath(__file__))
fig, ax = plt.subplots(figsize=(12.2, 7.4))
ax.set_xlim(0, 100); ax.set_ylim(0, 72); ax.axis("off")

cmap = plt.get_cmap("viridis")
layer_colors = [cmap(x) for x in (0.18, 0.36, 0.52, 0.66, 0.80)]


def tint(c, a=0.16):
    return (c[0], c[1], c[2], a)


def box(x, y, w, h, fc, ec, lines, fs=8.2, title_fs=9.2, lw=1.1, lc="k"):
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.35",
                       fc=fc, ec=ec, lw=lw, zorder=2)
    ax.add_patch(p)
    ax.text(x + w / 2, y + h - 2.6, lines[0], ha="center", va="top",
            fontsize=title_fs, fontweight="bold", color=lc, zorder=3)
    for i, ln in enumerate(lines[1:]):
        ax.text(x + w / 2, y + h - 7.6 - i * 3.6, ln, ha="center", va="top",
                fontsize=fs, color=lc, zorder=3)


def arrow(x1, y1, x2, y2, color="0.25", lw=1.4, style="-|>", ls="-", rad=0.0):
    a = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=16,
                        lw=lw, color=color, linestyle=ls, connectionstyle=f"arc3,rad={rad}",
                        zorder=1)
    ax.add_patch(a)


# ---------- 顶带：DPSIR 五层因果链 ----------
Y0, H = 38, 30
layer = [
    ("Driving (D)", ["Precipitation  (+)", "Temperature  (+)"], 2),
    ("Pressure (P)", ["Barren/degraded (-)", "Cropland  (-)"], 21),
    ("State (S)", ["Grassland (+)", "Forest (+)", "Water (+)"], 40),
    ("Impact (I)", ["Grassland change", "rate (+)"], 59),
    ("Response (R)", ["Ecological land (+)"], 78),
]
W = 17
for name, inds, x in layer:
    box(x, Y0, W, H, fc=tint(cmap(0.18)), ec=layer_colors[layer.index((name, inds, x))],
        lines=[name] + inds, fs=8.0, title_fs=9.4, lc="0.12")
for x in (19, 38, 57, 76):
    arrow(x, Y0 + H / 2, x + 2, Y0 + H / 2)

# R→D 反馈环（虚线）
arrow(86.5, Y0 + H + 1, 10.5, Y0 + H + 1, color="0.45", lw=1.1, ls="--", style="-|>", rad=0)
ax.text(48.5, Y0 + H + 3.4, "management feedback (R)", ha="center", fontsize=7.6,
        style="italic", color="0.35")

# ---------- 中带：指标 → 权重 → ESI ----------
box(3, 28, 22, 7.2, fc="#eef2ff", ec="#4c72b0", lines=["Nine DPSIR indicators", "min-max normalized to [0,1]"],
    fs=7.8, title_fs=8.2)
box(28, 28, 25, 7.2, fc="#eef6f2", ec="#2e8b57", lines=["Combined weighting", "AHP (0.4) + entropy (0.6)"], fs=7.8, title_fs=8.2)
box(56, 28, 20, 7.2, fc="#fff7e6", ec="#b8860b", lines=["ESI series", "2005-2023"], fs=7.8, title_fs=8.2)
box(79, 28, 18, 7.2, fc="#fdecea", ec="#c0392b", lines=["Warning grades", "five levels"], fs=7.8, title_fs=8.2)
arrow(25, 31.6, 28, 31.6); arrow(53, 31.6, 56, 31.6); arrow(76, 31.6, 79, 31.6)
arrow(79 + 9, 24.6, 79 + 9, 21)  # 预警级向下

# ---------- 底带：管理/预测/归因 ----------
box(2, 8, 27, 10, fc="#f0f7ff", ec="#3b7dd8", lines=["Zonal management", "mild-warning zones: grassland restoration", "regulating cropland expansion"], fs=7.6, title_fs=8.4)
box(36, 8, 27, 10, fc="#f0f7ff", ec="#3b7dd8", lines=["Forecast 2024-2028", "GM(1,1) - NGBM - ARIMA", "NGBM selected (qualified)"], fs=7.6, title_fs=8.4)
box(69, 8, 29, 10, fc="#f0f7ff", ec="#3b7dd8", lines=["Spatial attribution", "GeoDetector q (999 perms)", "barren q=0.80, grassland q=0.71"], fs=7.6, title_fs=8.4)
arrow(15.5, 18, 15.5, 21)
arrow(49.5, 18, 49.5, 21)
arrow(83.5, 18, 83.5, 21)

fig.savefig(os.path.join(BASE, "figures", "fig_dpsir_framework.pdf"), bbox_inches="tight")
fig.savefig(os.path.join(BASE, "figures", "fig_dpsir_framework.png"), dpi=600, bbox_inches="tight")
print("saved: fig_dpsir_framework.pdf/.png")