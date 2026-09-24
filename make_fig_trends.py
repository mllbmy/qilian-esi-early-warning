# -*- coding: utf-8 -*-
"""九项 DPSIR 指标变化趋势图（3×3 面板；矢量 PDF + 600 dpi PNG）

v16 重绘要点（针对"看不清/发虚"）：
  1. **按成品印刷尺寸出图**：figsize = 5.9 in 宽（论文中插图宽 0.95\\linewidth ≈ 6.2 in，
     缩放比 ≈ 1.05，故 7–7.5 pt 字号在成品中仍是 7–7.5 pt）；旧版按 10.4 in 设计、
     缩到 0.6 倍后 8.6 pt 标题只剩 ~5 pt，是"丑"的主因。
  2. 配色改为 **按 DPSIR 层的 5 色克制配色**（与概念框架图同族），取代九色 viridis 渐变。
  3. 面板标题两行 = 层名（本层色）+ 指标（单位）；2010 虚线、观测时点、插值线只在图例中
     解释一次（置于图外底部），不再横铺一行说明文字压住面板。

指标计算与 run_esi_regional.py / rerun_pipeline_ahp.py 完全同构（防数值漂移）；
另存 data/results_indicators.csv（逐年年值，供数据核对与正文引用）。
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib import rcParams

import jms_style  # JMS 指南§6：TNR 8–9 pt（R10 MEDIUM-2）
rcParams["pdf.fonttype"] = 42
rcParams["axes.unicode_minus"] = False

BASE = os.path.dirname(os.path.abspath(__file__))
cli = pd.read_csv(os.path.join(BASE, "data", "qilian_climate.csv"))
lc = pd.read_csv(os.path.join(BASE, "data", "qilian_landcover.csv"))
YEARS = list(range(2005, 2024))
reg_cli = cli[cli.unit == "区域(祁连山盒)"].set_index("year")
lc = lc.set_index("year").reindex(YEARS)
for c in lc.columns:
    lc[c] = lc[c].interpolate(method="linear").bfill().ffill()

BLUE, RED, GREEN, OCHRE, PURPLE = "#2a6f97", "#b23a48", "#2d6a4f", "#b06c1f", "#5a4a8a"
INK, GRID, MUTED = "#14181c", "#dce2e8", "#8a97a5"

# 9 指标（原始值；方向与表 2 一致）——顺序：D、D、S、S、S、P、P、I、R
ind = [
    ("Driving (D)", "Precipitation (mm)", reg_cli["precip_mm"], BLUE, True),
    ("Driving (D)", "Temperature (°C)", reg_cli["temp_c"], BLUE, True),
    ("State (S)", "Grassland (%)", lc["grass_pct"], GREEN, True),
    ("State (S)", "Forest (%)", lc["forest_pct"], GREEN, True),
    ("State (S)", "Water (%)", lc["water_pct"], GREEN, True),
    ("Pressure (P)", "Barren/degraded (%)",
     100 - lc["grass_pct"] - lc["forest_pct"] - lc["water_pct"] - lc["crop_pct"], RED, True),
    ("Pressure (P)", "Cropland (%)", lc["crop_pct"], RED, True),
    ("Impact (I)", "Grassland change rate (%/yr)",
     lc["grass_pct"].pct_change().fillna(0) * 100, OCHRE, True),
    ("Response (R)", "Ecological land (%)",
     lc["grass_pct"] + lc["forest_pct"] + lc["water_pct"], PURPLE, True),
]

# 同构原始值落盘（表 2 命名）——正文 §4 指标动态段的数字来源
pd.DataFrame({
    "year": YEARS,
    "precip_mm": reg_cli["precip_mm"].values,
    "temp_c": reg_cli["temp_c"].values,
    "grass_pct": lc["grass_pct"].values,
    "forest_pct": lc["forest_pct"].values,
    "water_pct": lc["water_pct"].values,
    "barren_pct": (100 - lc["grass_pct"] - lc["forest_pct"] - lc["water_pct"] - lc["crop_pct"]).values,
    "crop_pct": lc["crop_pct"].values,
    "grass_chg_rate": (lc["grass_pct"].pct_change().fillna(0) * 100).values,
    "ecoland_pct": (lc["grass_pct"] + lc["forest_pct"] + lc["water_pct"]).values,
}).round(3).to_csv(os.path.join(BASE, "data", "results_indicators.csv"),
                   index=False, encoding="utf-8-sig")

EPOCHS = [2005, 2010, 2015, 2020, 2023]
fig, axes = plt.subplots(3, 3, figsize=(5.9, 4.55), sharex="col",
                         layout="constrained")
for ax, (layer, name, series, color, pos) in zip(axes.ravel(), ind):
    ax.axvline(2010, color=MUTED, lw=0.7, ls=(0, (3, 2)), zorder=1)
    ax.plot(YEARS, series, color=color, lw=1.3, zorder=3)
    ax.plot(EPOCHS, series.loc[EPOCHS].values, "o", ms=3.2, color=color,
            mec="white", mew=0.6, zorder=4)
    ax.set_title("%s  %s" % (layer, "▲" if pos else "▼") + "\n" + name,
                 fontsize=8.0, color=color, linespacing=1.3, pad=3.0)
    ax.grid(axis="y", color=GRID, lw=0.5, zorder=0)
    ax.set_xticks([2005, 2010, 2015, 2020])
    ax.tick_params(labelsize=6.2, colors=INK, length=2.0, pad=1.5)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#9aa7b2")
        ax.spines[s].set_linewidth(0.6)
    ax.margins(x=0.04)

handles = [Line2D([], [], color=MUTED, lw=1.3, label="Interpolated annual value"),
           Line2D([], [], color=MUTED, marker="o", ms=3.2, lw=0,
                  mec="white", mew=0.6, label="CLCD observation epoch (5 dates)"),
           Line2D([], [], color=MUTED, lw=0.7, ls=(0, (3, 2)),
                  label="2010: ESI peak")]
fig.legend(handles=handles, loc="outside lower center", ncol=3, fontsize=8.0,
           frameon=False, handlelength=1.9, columnspacing=1.4,
           handletextpad=0.5, borderaxespad=0.0)

FIGD = os.path.join(BASE, "figures")
fig.savefig(os.path.join(FIGD, "fig_indicator_trends.pdf"))
fig.savefig(os.path.join(FIGD, "fig_indicator_trends.png"), dpi=600)
print("saved: fig_indicator_trends.pdf/.png ; results_indicators.csv rows=%d" % len(YEARS))