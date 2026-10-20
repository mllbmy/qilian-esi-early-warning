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
from matplotlib.ticker import AutoMinorLocator, MaxNLocator
from matplotlib import rcParams

import jms_style  # JMS 指南§6：TNR 8–9 pt
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

# 9 面板 9 色（用户指定各不相同）：保留 DPSIR 层色系，层内拉开明度
INK, GRID, MUTED = "#14181c", "#dce2e8", "#8a97a5"

# 9 指标（原始值；方向与表 2 一致）——顺序：D、D、S、S、S、P、P、I、R
ind = [
    ("Driving (D)", "Precipitation (mm)", reg_cli["precip_mm"], "#1f6f9f", True),
    ("Driving (D)", "Temperature (°C)", reg_cli["temp_c"], "#5aa9cf", True),
    ("State (S)", "Grassland (%)", lc["grass_pct"], "#14532d", True),
    ("State (S)", "Forest (%)", lc["forest_pct"], "#2e8b57", True),
    ("State (S)", "Water (%)", lc["water_pct"], "#52b788", True),
    ("Pressure (P)", "Barren/degraded (%)",
     100 - lc["grass_pct"] - lc["forest_pct"] - lc["water_pct"] - lc["crop_pct"], "#a52633", True),
    ("Pressure (P)", "Cropland (%)", lc["crop_pct"], "#d1495b", True),
    ("Impact (I)", "Grassland change rate (%/yr)",
     lc["grass_pct"].pct_change().fillna(0) * 100, "#b06c1f", True),
    ("Response (R)", "Ecological land (%)",
     lc["grass_pct"] + lc["forest_pct"] + lc["water_pct"], "#5a4a8a", True),
]

# R31: the primary specification is the eight-indicator set. Its Response layer is carried as an
# unweighted policy-background layer, so the duplicated ecological-land panel is not plotted;
# setting R31_EIGHT=1 draws the eight weighted indicators in the same 3x3 grid.
if os.environ.get("R31_EIGHT"):
    ind = [x for x in ind if x[0] != "Response (R)"]

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
LAYER_LETTER = {"Driving (D)": "D", "Pressure (P)": "P", "State (S)": "S",
                "Impact (I)": "I", "Response (R)": "R"}
# JMS §5.7：画布宽 = 印刷插入宽 16.00 cm；3×3 面板，刻度 8 pt、轴标题 9 pt
fig, axes = jms_style.subplots(height_cm=12.8, nrows=3, ncols=3, sharex="col",
                               layout="constrained")
for i, (ax, (layer, name, series, color, pos)) in enumerate(zip(axes.ravel(), ind)):
    ax.grid(axis="both", color=GRID, lw=0.5, ls=(0, (4, 2)), zorder=0)  # 横+竖虚线网格
    ax.plot(YEARS, series, color=color, lw=1.4, zorder=3)
    ax.plot(EPOCHS, series.loc[EPOCHS].values, "o", ms=3.4, color=color,
            mec="white", mew=0.6, zorder=4)
    # 顶刊风：黑色 y 轴标签取代彩色标题；长名折行
    ylabel = name.replace("Grassland change rate (%/yr)",
                          "Grassland change rate\n(%/yr)")
    ax.set_ylabel(ylabel, fontsize=8.0, color=INK, linespacing=1.25)
    ax.text(-0.16, 1.10, "(%s)" % chr(ord("a") + i), transform=ax.transAxes,
            fontsize=9.0, fontweight="bold", color=INK, ha="left", va="center")
    # 层归属：面板外右上角小号灰字母（与 (x) 标签左右对称，避免压数据线）
    ax.text(1.0, 1.03, LAYER_LETTER[layer], transform=ax.transAxes,
            fontsize=8.0, fontweight="bold", color="#6a6a6a",
            ha="right", va="center")
    ax.set_xticks([2005, 2010, 2015, 2020, 2023])     # 末尾补 2023（正文最常引用）

    ax.yaxis.set_major_locator(MaxNLocator(nbins=6))  # 加密 y 刻度，轴末端有数字
    ax.xaxis.set_minor_locator(AutoMinorLocator(2))   # 主刻度间 1 个次级刻度
    ax.yaxis.set_minor_locator(AutoMinorLocator(2))
    ax.tick_params(labelsize=8.0, colors=INK, length=2.0, pad=1.5,
                   labelbottom=True)                  # 每个面板都显示年份标签
    ax.tick_params(which="minor", length=1.2, colors="#9aa7b2")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#9aa7b2")
        ax.spines[s].set_linewidth(0.6)
    ax.margins(x=0.04)

for _ax in axes.ravel():                      # R31: hide panels unused by the eight-item set
    if not _ax.has_data():
        _ax.set_visible(False)

handles = [Line2D([], [], color=MUTED, lw=1.3, label="Annual value"),
           Line2D([], [], color=MUTED, marker="o", ms=3.2, lw=0,
                  mec="white", mew=0.6, label="CLCD observation epoch (5 dates)")]
fig.legend(handles=handles, loc="outside lower center", ncol=2, fontsize=8.0,
           frameon=False, handlelength=1.9, columnspacing=1.4,
           handletextpad=0.5, borderaxespad=0.0)

FIGD = os.path.join(BASE, "figures")
# 2020 与 2023 相隔 3 年，8 pt 标签在 3.2 cm 宽面板内会连成 "20202023"：
# 末位标签改为左对齐贴刻度（向右伸出轴框），五个年份标签全部保留、字号不缩到 8 pt 以下。
fig.canvas.draw()
for _ax in axes.ravel():
    _labs = _ax.get_xticklabels()
    if len(_labs) >= 2:
        _labs[-1].set_horizontalalignment("left")

jms_style.save(fig, "fig_indicator_trends", outdir=FIGD)
print("saved: fig_indicator_trends.pdf/.png ; results_indicators.csv rows=%d" % len(YEARS))