# -*- coding: utf-8 -*-
"""图 8 单因子探测 q 值（v2：双面板，回应"空间归因内生性"质疑）

(a) Compositional factors —— 与 ESI 构成项重叠的 4 个因子（现有结果，数值零改动）
    数值读自 data/results_geodetector_pvalues.csv 的单因子行。
(b) Exogenous factors —— 仅含外生因子的对照探测（降水、气温、高程、坡度）
    数值为本轮实测：同一 1,914 个格点、同一 ESI、同一四分位离散化、999 次置换；
    地形由本地 Copernicus DEM 90 m 采样（data/_aux_terrain_points.csv）。
    降水 0.5060 / 气温 0.1697 与原图完全一致，验证了复算管线。

R17：画布宽 = Word 插入宽 12.0 cm（4.72 in），字号 1:1（TNR 8-9 pt），dpi=600 → 2832 px。
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import AutoMinorLocator

import jms_style  # noqa: F401  (JMS 指南 §6：TNR 8-9 pt)

BASE = os.path.dirname(os.path.abspath(__file__))
raw = pd.read_csv(os.path.join(BASE, "data", "results_geodetector_pvalues.csv"))
single = raw[~raw["factor"].str.contains("+", regex=False, na=False)].copy()
single = single.set_index("factor")

INK = "#14181c"
C_A = "#1f6f9f"      # 面板 a 主色（与 jms 层色 D 同族）
C_B = "#b5651d"      # 面板 b 主色（外生/地形，暖色区分）

# ---- 面板数据 ----
PANEL_A = [("Barren/degraded", float(single.loc["barren", "q"]), "P"),
           ("Grassland",       float(single.loc["grass",  "q"]), "S"),
           ("Precipitation",   float(single.loc["precip", "q"]), "D"),
           ("Temperature",     float(single.loc["temp",   "q"]), "D")]
# 外生对照：读自 data/results_geodetector_exogenous.csv（由 run_exogenous_geodetector.py 生成）
# 该管线复现出 elev 0.0904 与 slope 0.0647。
# 两者四舍五入均为 0.09 / 0.06，与正文 §4.5 的标注一致。
exo = pd.read_csv(os.path.join(BASE, "data", "results_geodetector_exogenous.csv")).set_index("factor")
PANEL_B = [("Precipitation", float(exo.loc["precip", "q"]), "C"),
           ("Temperature",   float(exo.loc["temp",   "q"]), "C"),
           ("Elevation",     float(exo.loc["elev",   "q"]), "T"),
           ("Slope",         float(exo.loc["slope",  "q"]), "T")]
LAYER_C = {"D": "#1f6f9f", "S": "#2e8b57", "P": "#d1495b", "C": C_B, "T": "#7a7f87"}

# JMS §5.7：画布宽 = 印刷插入宽 16.00 cm
fig, axes = jms_style.subplots(height_cm=10.8, nrows=2, ncols=1, layout="constrained")

for ax, data, tag, ttl in [
        (axes[0], PANEL_A, "(a)", "(a)  Compositional factors (overlap ESI inputs)"),
        (axes[1], PANEL_B, "(b)", "(b)  Exogenous factors only")]:
    labs = [d[0] for d in data]
    qs = np.array([d[1] for d in data])
    yy = np.arange(len(data))[::-1]
    for i, (x, yv, (_, _, lk)) in enumerate(zip(qs, yy, data)):
        if i % 2 == 1:
            ax.axhspan(yv - 0.5, yv + 0.5, facecolor="#f4f6f9", lw=0, zorder=0)
        c = LAYER_C[lk]
        ax.plot([0, x], [yv, yv], color=c, alpha=0.35, lw=2.4,
                solid_capstyle="round", zorder=1)
        ax.plot([x], [yv], marker="o", ms=7.0, mfc=c, mec="white", mew=1.0,
                ls="", zorder=3)
        ax.text(x + 0.022, yv, "%.2f" % x, va="center", ha="left",
                fontsize=8, color=INK, zorder=4)
    ax.set_yticks(yy)
    ax.set_yticklabels(labs, fontsize=8)
    ax.set_ylim(-0.6, len(data) - 0.4)
    ax.set_xlim(0, 0.95)
    ax.set_xticks([0, 0.2, 0.4, 0.6, 0.8])
    ax.xaxis.set_minor_locator(AutoMinorLocator(2))
    ax.set_xlabel("q statistic", fontsize=9)
    ax.set_title(ttl, fontsize=8.5, loc="left", pad=3, color=INK)
    ax.tick_params(labelsize=8, length=2.0, pad=1.5)
    ax.tick_params(which="minor", length=1.2, colors="#9aa7b2")
    ax.grid(axis="x", color="#dce2e8", lw=0.5, ls=(0, (4, 2)), zorder=0)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#9aa7b2")
        ax.spines[s].set_linewidth(0.6)

FIG = os.path.join(BASE, "figures")
jms_style.save(fig, "fig_geodetector_q", outdir=FIG)

DEST = os.path.normpath(os.path.join(BASE, "..", "投稿前优化", "图件", "定稿"))
os.makedirs(DEST, exist_ok=True)
fig.savefig(os.path.join(DEST, "Fig08_geodetector_q_final.png"), dpi=610)
print("saved fig_geodetector_q.pdf/.png + 定稿\\Fig08_geodetector_q_final.png")
print("  (a) 内生: " + ", ".join("%s %.4f" % (d[0], d[1]) for d in PANEL_A))
print("  (b) 外生: " + ", ".join("%s %.4f" % (d[0], d[1]) for d in PANEL_B))