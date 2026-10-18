# -*- coding: utf-8 -*-
"""图4（ESI 时序）R21 重构版：浅色五级预警带 + 阈值虚线（兼作横向网格）+
底部双行图例（上行：观测/三模型/95% 区间；下行：五级预警色块）。

设计要点（相对 R20 全改）：
  1. 删除右侧外挂色条与底部色带条 → 五级预警改为极低透明度的背景色带（alpha 0.10），
     0.2/0.4/0.6/0.8 阈值虚线兼作横向网格（期刊安全画法）。
  2. 预警等级以色块图例放在底部第二行，不再占用图面左右空间。
  3. 三条预测曲线锚定 2023 年观测值（数据不变，仅消除观测/预测视觉断点）。
  4. figsize 宽 5.67 in = 正文插图宽 14.4 cm → 字体 1:1 等效印刷字号。
  5. 数据零改动：results_esi_regional.csv / results_forecast_comparison.csv /
     results_forecast_ci.csv；五级色值与图 2 预警色带一致。
"""
import os

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import AutoMinorLocator

# 路径自解析：仓库克隆/解压到任意目录均可运行
BASE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(BASE, "figures")

BLUE, ORANGE, PURPLE = "#2166ac", "#e07b39", "#6c5b9c"
GRAY = "#666666"
# 五级预警（与正文及图 2 色带完全一致，0.2 等距）：(下界, 上界, 色值, 级名)
WARN5 = [
    (0.0, 0.2, "#b2182b", "Severe"),
    (0.2, 0.4, "#e07b39", "Medium"),
    (0.4, 0.6, "#f4d03f", "Mild"),
    (0.6, 0.8, "#7dcea0", "Relatively safe"),
    (0.8, 1.0, "#1b7837", "Safe"),
]

import jms_style  # JMS 指南§6：图内文字 Times New Roman 8–9 pt
plt.rcParams.update({"axes.labelsize": 9, "xtick.labelsize": 8, "ytick.labelsize": 8,
                     "axes.edgecolor": "#444444", "axes.linewidth": 0.8,
                     "savefig.dpi": 600, "figure.dpi": 100})

# Primary specification (R29): the eight-indicator DPSI set is the manuscript's
# primary series, so the figure is drawn from the primary-specification archives
# rather than from the nine-indicator results_* files. Set R29_PRIMARY=0 to
# reproduce the earlier nine-indicator version.
import os as _os
if _os.environ.get("R29_PRIMARY", "1") == "1":
    _ser = pd.read_csv(_os.path.join(BASE, "data", "r28_deredundancy_series.csv"))
    esi_df = pd.DataFrame({"year": _ser["year"], "esi": _ser["esi_drop_X9"]})
    _fc = pd.read_csv(_os.path.join(BASE, "data", "r29_forecast_8ind.csv"))
    fc_df = pd.DataFrame({"gm11": _fc["gm11_8ind"], "ngbm": _fc["ngbm_8ind_gamma_train"],
                          "arima": _fc["arima_011_8ind"]})
    _iv = pd.read_csv(_os.path.join(BASE, "data", "r29_forecast_8ind_intervals.csv"))
    _iv = _iv[(_iv["model"] == "NGBM") & (_iv["method"] == "total_block")
              & (_iv["gamma_mode"] == "reselect_each_replicate") & (_iv["year"] >= 2024)]
    ci_df = pd.DataFrame({"year": _iv["year"], "ci_lo": _iv["boot_p2.5"], "ci_hi": _iv["boot_p97.5"]})
else:
    esi_df = pd.read_csv(os.path.join(BASE, "data", "results_esi_regional.csv"))
    fc_df = pd.read_csv(os.path.join(BASE, "data", "results_forecast_comparison.csv"))
    ci_df = pd.read_csv(os.path.join(BASE, "data", "results_forecast_ci.csv"))

years = esi_df["year"].values
e2023 = float(esi_df["esi"].iloc[-1])          # 2023 观测值：预测曲线锚点
fcy = np.arange(2023, 2029)                    # 2023(锚) + 2024-2028
fcy24 = np.arange(2024, 2029)

fig, ax = plt.subplots(figsize=(5.67, 3.6), layout="constrained")

# ---------- 五级预警背景带（极浅）+ 阈值虚线（兼横向网格）----------
for lo, hi, c, _lab in WARN5:
    ax.axhspan(lo, hi, color=c, alpha=0.10, lw=0.0, zorder=0)
for t in (0.2, 0.4, 0.6, 0.8):
    ax.axhline(t, color="#9aa7b2", lw=0.7, ls=(0, (4, 2)), zorder=1)

# ---------- NGBM 95% 预测区间 ----------
ax.fill_between(fcy24, ci_df["ci_lo"], ci_df["ci_hi"], color=ORANGE, alpha=0.15,
                lw=0.0, zorder=2, label="NGBM bootstrap interval (95%)")

# ---------- 观测与三模型预测（锚定 2023）----------
ax.plot(years, esi_df["esi"], "-o", color=BLUE, lw=1.8, ms=4.0, zorder=5,
        label="Observed ESI")
ax.plot(fcy, [e2023] + fc_df["gm11"].tolist(), "--s", color=BLUE, lw=1.3, ms=3.6,
        mfc="white", zorder=4, label="GM(1,1)")
ax.plot(fcy, [e2023] + fc_df["ngbm"].tolist(), "--^", color=ORANGE, lw=1.5, ms=4.2,
        zorder=5, label="NGBM (adopted)")
ax.plot(fcy, [e2023] + fc_df["arima"].tolist(), "--v", color=PURPLE, lw=1.3, ms=3.6,
        mfc="white", zorder=4, label="ARIMA")

# ---------- 观测/预测分界 ----------
ax.axvline(2023.5, color=GRAY, lw=0.9, ls="--", zorder=3)
ax.text(2026.0, 0.945, "Forecast", fontsize=8.5, ha="center", style="italic",
        color=GRAY, zorder=6)

# ---------- 轴与刻度 ----------
ax.set_ylabel("Ecological security index (ESI)")
ax.set_xlabel("Year")
ax.set_xlim(2004.5, 2028.5)
ax.set_ylim(0.0, 1.0)
ax.set_yticks([0.0, 0.2, 0.4, 0.6, 0.8, 1.0])
ax.set_xticks([2005, 2010, 2015, 2020, 2025, 2028])   # 末端补 2028（同图3"末尾有数字"）
ax.xaxis.set_minor_locator(AutoMinorLocator(2))
ax.yaxis.set_minor_locator(AutoMinorLocator(2))
ax.tick_params(length=2.0, pad=1.5)
ax.tick_params(which="minor", length=1.2, colors="#9aa7b2")
for s in ("top", "right"):
    ax.spines[s].set_visible(False)

# ---------- 底部双行图例：上行系列，下行五级预警色块 ----------
handles, labels_ = ax.get_legend_handles_labels()
# fill_between 排在最前，重排：Observed / GM / NGBM / ARIMA / CI
order = [1, 2, 3, 4, 0]
handles = [handles[k] for k in order]
labels_ = [labels_[k] for k in order]
chips, chip_labels = [], []
for lo, hi, c, lab in WARN5:
    chips.append(Line2D([], [], marker="s", ls="", ms=7.0, mfc=c, mec="none"))
    chip_labels.append(lab)
# matplotlib ncol 按列填充 → 交错排列使上行=系列、下行=预警级
handles = [h for pair in zip(handles, chips) for h in pair]
labels_ = [l for pair in zip(labels_, chip_labels) for l in pair]
fig.legend(handles, labels_, loc="outside lower center", ncol=5, fontsize=8,
           frameon=False, handlelength=1.8, columnspacing=1.0, handletextpad=0.5)

fig.savefig(os.path.join(FIG, "fig3_esi_timeseries.pdf"))
fig.savefig(os.path.join(FIG, "fig3_esi_timeseries.png"))
plt.close()
print("saved fig3_esi_timeseries.pdf + .png (R21 重构：浅色预警带+阈值虚线+双行图例)")
