# -*- coding: utf-8 -*-
"""图4 候选版式：时空结合图（预览，输出到 out\\ 不覆盖正式文件）
上：2020 点尺度 ESI 空间分布（五级预警配色 + 公园数字化轮廓红线 + 县城标注）
下：ESI 时序（五级色带 + NGBM 95% 区间 + 三模型预测）
底：五级图例条（级名 + 区间）。所有数据与正文同源。"""
import json
import os

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import matplotlib.colors as mcolors

BASE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(BASE, "figures")

BLUE, ORANGE, PURPLE, RED = "#2166ac", "#e07b39", "#6c5b9c", "#b2182b"
# (下界, 上界, 主色, 填充斜纹, 级名, 图例条文字色)
WARN5 = [
    (0.0, 0.2, "#b2182b", "////", "Severe warning", "white"),
    (0.2, 0.4, "#e07b39", "xxxx", "Medium warning", "white"),
    (0.4, 0.6, "#f4d03f", "....", "Mild warning", "#333333"),
    (0.6, 0.8, "#7dcea0", "\\\\\\\\", "Relatively safe", "#333333"),
    (0.8, 1.0, "#1b7837", "", "Safe", "white"),
]

import jms_style
plt.rcParams.update({"axes.labelsize": 8.5, "xtick.labelsize": 8, "ytick.labelsize": 8,
                     "axes.edgecolor": "#444444", "axes.linewidth": 0.8,
                     "savefig.dpi": 600, "figure.dpi": 100, "hatch.linewidth": 0.6})

esi_df = pd.read_csv(os.path.join(BASE, "data", "results_esi_regional.csv"))
fc_df = pd.read_csv(os.path.join(BASE, "data", "results_forecast_comparison.csv"))
ci_df = pd.read_csv(os.path.join(BASE, "data", "results_forecast_ci.csv"))
pts = pd.read_csv(os.path.join(BASE, "data", "spatial_esi_points.csv"))

QILIAN = {"Tianzhu": (37.20, 102.86), "Sunan": (38.84, 99.62), "Subei": (39.51, 97.85),
          "Aksai": (39.34, 94.34), "Minle": (38.43, 100.81), "Shandan": (38.78, 101.09),
          "Menyuan": (37.38, 101.62), "Qilian": (38.18, 100.24), "Gangcha": (37.33, 100.14),
          "Delingha": (37.37, 97.36), "Tianjun": (37.30, 99.02)}
OFF = {"Sunan": (5, 6), "Shandan": (6, -6), "Minle": (6, 4), "Qilian": (-6, 5),
       "Gangcha": (5, 4), "Menyuan": (6, -5), "Tianjun": (6, -6), "Delingha": (-6, 5),
       "Tianzhu": (-6, 6), "Subei": (4, 4), "Aksai": (4, 4)}


def grade_entry(v):
    for lo, hi, c, h, lab, tc in WARN5:
        if lo <= v < hi:
            return c, lab
    return WARN5[-1][2], WARN5[-1][4]


def park_rings():
    p = os.path.join(BASE, "data", "qmn_park_digitized.geojson")
    gj = json.load(open(p, encoding="utf-8"))
    rings = []
    for f in gj["features"]:
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        for poly in polys:
            rings.append(np.array(poly[0]))
    return rings


fig = plt.figure(figsize=(8.8, 6.2))
gs = fig.add_gridspec(2, 1, height_ratios=[0.92, 0.78], hspace=0.30)
axS = fig.add_subplot(gs[0])
axT = fig.add_subplot(gs[1])

# ================= 上：空间分布（五级配色） =================
cols = [grade_entry(v)[0] for v in pts["esi"]]
axS.scatter(pts["lon"], pts["lat"], c=cols, s=11, edgecolors="none", zorder=3)
for ring in park_rings():
    axS.plot(ring[:, 0], ring[:, 1], color="#c0392b", lw=0.8, ls=(0, (4, 2)), zorder=4)
for n, (la, lo) in QILIAN.items():
    axS.plot(lo, la, "k.", ms=5, zorder=5)
    dx, dy = OFF.get(n, (4, 4))
    axS.annotate(n, (lo, la), fontsize=7.5, xytext=(dx, dy), textcoords="offset points",
                 zorder=6, path_effects=[pe.withStroke(linewidth=2.0, foreground="white")])
axS.set_xlim(93.5, 103.5); axS.set_ylim(36.0, 40.5)
axS.set_xlabel("Longitude (°E)"); axS.set_ylabel("Latitude (°N)")
axS.grid(alpha=0.12, lw=0.35); axS.set_aspect(1.15)
axS.text(0.01, 0.985, "(a)  Point ESI (2020)", transform=axS.transAxes,
         ha="left", va="top", fontsize=8.5, color="#333333",
         path_effects=[pe.withStroke(linewidth=2.0, foreground="white")])

# ================= 下：ESI 时序 + 五级带 =================
for lo, hi, c, h, lab, _tc in WARN5:
    axT.axhspan(lo, hi, color=c, alpha=0.22, hatch=h, lw=0.0, zorder=0)
years = esi_df["year"].values
axT.plot(years, esi_df["esi"], "-o", color=BLUE, lw=2.0, ms=4.2, zorder=4)
fcy = np.arange(2024, 2029)
axT.plot(fcy, fc_df["gm11"], "--s", color=BLUE, lw=1.2, ms=3.4, zorder=4)
axT.plot(fcy, fc_df["ngbm"], "--^", color=ORANGE, lw=1.5, ms=3.8, zorder=5)
axT.plot(fcy, fc_df["arima"], "--v", color=PURPLE, lw=1.2, ms=3.4, zorder=4)
axT.fill_between(fcy, ci_df["ci_lo"], ci_df["ci_hi"], color=ORANGE, alpha=0.14,
                 lw=0.0, zorder=2)
axT.axvspan(2023.5, 2028.5, color="#cccccc", alpha=0.22, zorder=1)
axT.axvline(2023.5, color="#666666", lw=0.9, ls="--", zorder=3)
axT.text(2026.0, 0.925, "Forecast", fontsize=8.0, ha="center", color="#333333", zorder=6,
         path_effects=[pe.withStroke(linewidth=2.0, foreground="white")])
axT.set_ylabel("Ecological security index (ESI)")
axT.set_xlim(2004.5, 2028.5); axT.set_ylim(0.0, 1.0)
axT.set_yticks([0.0, 0.2, 0.4, 0.6, 0.8, 1.0])
axT.tick_params(labelbottom=False)
axT.text(0.01, 0.985, "(b)  Observed ESI (2005\u20132023) and forecasts (2024\u20132028)",
         transform=axT.transAxes, ha="left", va="top", fontsize=8.5, color="#333333",
         path_effects=[pe.withStroke(linewidth=2.0, foreground="white")])

# ================= 底：五级图例条（挂在时序面板下，对齐年份） =================
from mpl_toolkits.axes_grid1.inset_locator import inset_axes
axl = inset_axes(axT, width="100%", height="100%", loc="lower center",
                 bbox_to_anchor=(0.0, -0.42, 1.0, 0.10), bbox_transform=axT.transAxes,
                 borderpad=0)
strip_rgb = np.array([[mcolors.to_rgb(c) for (_lo, _hi, c, _h, _lab, _tc) in WARN5]])
axl.imshow(strip_rgb, extent=[2004.5, 2028.5, 0, 1], aspect="auto")
axl.set_yticks([])
axl.set_xlim(2004.5, 2028.5)
for lo, hi, c, h, lab, tc in WARN5:
    xc = 2004.5 + (lo + hi) / 2 * 24.0
    txt = "%s\n[%.1f,%.1f)" % (lab, lo, hi) if hi < 1.0 else "%s\n[%.1f,%.1f]" % (lab, lo, hi)
    axl.text(xc, 0.5, txt, ha="center", va="center", fontsize=6.6, color=tc, zorder=5)
axl.set_xlabel("Year", fontsize=8.5)

# ================= 系列图例 =================
fig.legend(loc="lower center", bbox_to_anchor=(0.5, 0.005), ncol=5, frameon=False,
           fontsize=8.0, columnspacing=1.0,
           labels=["Observed ESI", "GM(1,1)", "NGBM (adopted)", "ARIMA", "NGBM 95% interval"],
           handles=[plt.Line2D([], [], color=BLUE, lw=1.8, marker="o", ms=4),
                    plt.Line2D([], [], color=BLUE, ls="--", marker="s", ms=4),
                    plt.Line2D([], [], color=ORANGE, ls="--", marker="^", ms=4),
                    plt.Line2D([], [], color=PURPLE, ls="--", marker="v", ms=4),
                    plt.Rectangle((0, 0), 1, 1, color=ORANGE, alpha=0.3)])

out = os.path.join(BASE, "out")
os.makedirs(out, exist_ok=True)
plt.savefig(os.path.join(out, "_fig4_时空结合预览.pdf"), bbox_inches="tight")
plt.savefig(os.path.join(out, "_fig4_时空结合预览.png"), bbox_inches="tight")
plt.close()
print("saved out\\_fig4_时空结合预览.pdf/.png (时空结合：上空间分布 + 下时序 + 五级条)")