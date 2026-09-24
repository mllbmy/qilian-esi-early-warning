# -*- coding: utf-8 -*-
"""贡献矩阵图(替换对比表 Tab.7/中文表8): 本研究 vs 代表性保护区生态安全研究
行=方法特性, 列=研究; ✓=有, 部分=文字, –=无, 新增=红标
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

# 路径自解析：仓库克隆/解压到任意目录均可运行
BASE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(BASE, "figures")

BLUE = "#2166ac"
BLUE_L = "#d1e5f0"
GREEN = "#1b7837"
GREEN_L = "#d9f0e3"
RED = "#b2182b"
GRAY_T = "#555555"

plt.rcParams.update({"font.family": "DejaVu Sans", "savefig.dpi": 600})

fig, ax = plt.subplots(figsize=(9.4, 5.9))
ax.set_xlim(0, 12.6); ax.set_ylim(0, 6.6); ax.axis("off")

features = [
    "DPSIR / PSR framework",
    "Combined weighting",
    "GM(1,1) forecasting",
    "GeoDetector attribution",
    "County-level spatial analysis",
    "Weighting robustness test",
    "Open data & reproducible code",
]
studies = ["Liu et al. (2023)", "Changbai\nDPSIRM", "DPSIR–DEA", "This study"]
# ptype: full / partial / ext / none
data = [
    [("✓", "full"), ("✓", "full"), ("✓", "full"), ("✓", "full")],
    [("✓", "full"), ("AHP only", "partial"), ("Entropy–DEA", "partial"), ("✓  + α sensitivity", "ext")],
    [("✓", "full"), ("–", "none"), ("–", "none"), ("✓  vs NGBM, ARIMA", "ext")],
    [("✓", "full"), ("–", "none"), ("–", "none"), ("✓  + interaction", "ext")],
    [("–", "none"), ("✓", "full"), ("✓", "full"), ("✓", "full")],
    [("–", "none"), ("–", "none"), ("–", "none"), ("✓  NEW", "new")],
    [("–", "none"), ("–", "none"), ("–", "none"), ("✓  NEW", "new")],
]

ROW_H = 0.74
COL_W = 2.15
X0 = 3.6
Y0 = 5.6

# 列标题
for j, s in enumerate(studies):
    cx = X0 + (j + 0.5) * COL_W
    c = BLUE if j == 3 else "#333333"
    ax.text(cx, Y0 + ROW_H * 0.35, s, ha="center", va="center", fontsize=9,
            color=c, fontweight="bold" if j == 3 else "normal")
# 分隔线
ax.plot([X0, X0 + 4 * COL_W], [Y0, Y0], color="#888888", lw=0.9)

# 行标签
for i, f in enumerate(features):
    ry = Y0 - (i + 0.5) * ROW_H
    ax.text(X0 - 0.2, ry, f, ha="right", va="center", fontsize=8.4, color="#222222",
            fontweight="bold" if i in (5, 6) else "normal")

# 单元格
for i in range(7):
    for j in range(4):
        cx = X0 + j * COL_W
        cy = Y0 - (i + 1) * ROW_H
        text, ptype = data[i][j]
        is_new_row = (i in (5, 6))
        fc, tc, fs, bold = "#ffffff", GRAY_T, 8.2, False
        if ptype == "full":
            fc = BLUE_L if j == 3 else GREEN_L
            tc = BLUE if j == 3 else GREEN
            bold = True
        elif ptype == "ext":
            fc = BLUE_L
            tc = BLUE
        elif ptype == "partial":
            fc = "#f3efe4"
            tc = "#6b5b28"
        elif ptype == "new":
            fc = "#f9dcd7"
            tc = RED
            bold = True
        elif ptype == "none":
            fc = "#ffffff"; tc = "#bbbbbb"
        ax.add_patch(Rectangle((cx, cy), COL_W, ROW_H, fc=fc, ec="#cccccc", lw=0.7))
        ax.text(cx + COL_W / 2, cy + ROW_H / 2, text, ha="center", va="center",
                fontsize=fs, color=tc, fontweight="bold" if bold else "normal")

# This study 列高亮边框
ax.add_patch(Rectangle((X0 + 3 * COL_W, Y0 - 7 * ROW_H), COL_W, 7 * ROW_H,
                       fill=False, ec=BLUE, lw=2.2))

plt.savefig(os.path.join(FIG, "fig_compare.png"), bbox_inches="tight")
plt.close()
print("saved fig_compare.png")