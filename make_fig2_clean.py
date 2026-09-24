# -*- coding: utf-8 -*-
"""图2/图3（方法总图）升级重绘：三列研究框架总图
左：DPSIR 五层指标（9 指标标 +/-）｜中：方法与模型选择逻辑（含五级预警阈值带、
单调性判断→GM(1,1)/NGBM 选择、ARIMA 基准、GeoDetector）｜右：输出与应用。
Arial、白底细线框、CVD-safe（viridis 阈值带）、矢量 PDF + 600dpi PNG。"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

# 路径自解析：仓库克隆/解压到任意目录均可运行
BASE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(BASE, "figures")

EDGE = "#4d4d4d"
TXT = "#1a1a1a"
HDR = "#e9e9e9"
ARROW = "#666666"
HL = "#0e7a5f"  # NGBM 高亮（深绿，可辨识）

plt.rcParams.update({"font.family": "Arial", "font.size": 9,
                     "mathtext.fontset": "custom", "mathtext.rm": "Arial",
                     "mathtext.it": "Arial:italic", "mathtext.bf": "Arial:bold",
                     "savefig.dpi": 600, "figure.dpi": 100})

fig, ax = plt.subplots(figsize=(11.0, 8.1))
ax.set_xlim(0, 12)
ax.set_ylim(0, 8.4)
ax.axis("off")


def box(x, y, w, h, title, body=None, fc="white", fs=8.2, ec=EDGE, bold=True, tc=TXT):
    ax.add_patch(Rectangle((x, y), w, h, fc=fc, ec=ec, lw=0.8, zorder=2))
    if body:
        ax.text(x + w / 2, y + h * 0.70, title, ha="center", va="center",
                fontsize=fs, color=tc, fontweight="bold" if bold else "normal", zorder=3)
        ax.text(x + w / 2, y + h * 0.28, body, ha="center", va="center",
                fontsize=fs - 0.6, color=TXT, zorder=3)
    else:
        ax.text(x + w / 2, y + h / 2, title, ha="center", va="center",
                fontsize=fs, color=tc, fontweight="bold" if bold else "normal", zorder=3)


def varrow(x, y1, y2, ec=ARROW, lw=0.9):
    ax.annotate("", xy=(x, y2), xytext=(x, y1),
                arrowprops=dict(arrowstyle="-|>", color=ec, lw=lw, shrinkA=0, shrinkB=0),
                zorder=1)


def harrow(x1, x2, y):
    ax.annotate("", xy=(x2, y), xytext=(x1, y),
                arrowprops=dict(arrowstyle="-|>", color=ARROW, lw=1.1, shrinkA=0, shrinkB=0),
                zorder=1)


# ---------------- 栏头 ----------------
LX, LW = 0.30, 2.70
MX, MW = 3.60, 4.30
RX, RW = 8.30, 3.50
box(LX, 7.98, LW, 0.40, "Data / indicators", fc=HDR, fs=8.6)
box(MX, 7.98, MW, 0.40, "Methods and model selection", fc=HDR, fs=8.6)
box(RX, 7.98, RW, 0.40, "Outputs and application", fc=HDR, fs=8.6)

# ---------------- 左列：DPSIR ----------------
left = [
    ("Driving (D)", "Precipitation (+)\nTemperature (+)"),
    ("Pressure (P)", "Barren/degraded (-)\nCropland (-)"),
    ("State (S)", "Grassland (+)\nForest (+)  Water (+)"),
    ("Impact (I)", "Grassland change\nrate (+)"),
    ("Response (R)", "Ecological land (+)"),
]
Y0, BH, GAP = 6.95, 1.28, 0.10
for i, (t, b) in enumerate(left):
    box(LX, Y0 - i * (BH + GAP), LW, BH, t, b, fs=8.2)
    if i < len(left) - 1:
        varrow(LX + LW / 2, Y0 - i * (BH + GAP), Y0 - (i + 1) * (BH + GAP) + BH)

# ---------------- 中列：方法/模型选择 ----------------
my, bh, gap = 6.95, 1.00, 0.116
box(MX, my, MW, bh, "Min\u2013max normalization", "all indicators \u2192 [0,1]", fs=8.2)
box(MX, 5.834, MW, bh, "Combined weighting", "AHP \u00d7 entropy, \u03b1 = 0.4 (sensitivity 0\u20131)", fs=8.2)
# 阈值带（画在 ESI 框内）
yx, yh = 4.718, 1.20
ax.add_patch(Rectangle((MX, yx), MW, yh, fc="white", ec=EDGE, lw=0.8, zorder=2))
ax.text(MX + MW / 2, yx + yh - 0.28, "ESI 2005\u20132023", ha="center", va="center",
        fontsize=8.2, fontweight="bold", color=TXT, zorder=3)
seg = [("Severe", 0.0, 0.2), ("Medium", 0.2, 0.4), ("Mild", 0.4, 0.6),
       ("Rel. safe", 0.6, 0.8), ("Safe", 0.8, 1.0)]
import matplotlib.cm as cm
cmap = plt.get_cmap("viridis")
sw = MW * 0.82
sx0 = MX + (MW - sw) / 2
for name, a, b in seg:
    w = sw * (b - a)
    c = cmap((a + b) / 2)
    ax.add_patch(Rectangle((sx0 + sw * a, yx + 0.42), w, 0.34, fc=c, ec="none", zorder=3))
    ax.text(sx0 + sw * (a + b) / 2, yx + 0.315, name, ha="center", va="center",
            fontsize=5.4, color="white", fontweight="bold", zorder=4)
for xv, lab in [(0.0, "0"), (0.2, "0.2"), (0.4, "0.4"), (0.6, "0.6"), (0.8, "0.8"), (1.0, "1")]:
    ax.text(sx0 + sw * xv, yx + 0.10, lab, ha="center", va="center", fontsize=5.4, color=TXT, zorder=3)
box(MX, 3.462, MW, 1.14, "Forecast model selection",
    "Monotonic \u2192 GM(1,1)\nNon-monotonic \u2192 NGBM (selected)  ARIMA (benchmark)",
    fs=8.2)
box(MX, 2.206, MW, 1.0, "Spatial attribution", "GeoDetector: single / interaction q, 999 perms", fs=8.2)
box(MX, 1.05, MW, 0.9, "Rolling-origin backtest", "NGBM RMSE 0.034 vs. GM(1,1) 0.065", fs=8.2)

arrows = [6.95, 5.834, 4.718 + 1.20, 3.462 + 1.14, 2.206 + 1.0]
for i in range(len(arrows) - 1):
    varrow(MX + MW / 2, arrows[i], arrows[i + 1])

# NGBM 高亮说明见正文 Fig 注（此处模型选择框内已加粗标注）

# ---------------- 右列：输出与应用 ----------------
right = [
    ("ESI series + warning bands", "observed 2005\u20132023,\nforecast 2024\u20132028"),
    ("Warning grades", "five levels, mild since 2011\n(ESI 2023 = 0.486)"),
    ("Forecast (NGBM)", "2024\u20132028: 0.446 \u2192 0.394,\n95% CI 0.358\u20130.533 (2024)"),
    ("Drivers", "barren q = 0.80,\ngrassland q = 0.71"),
    ("Zonal management", "grassland restoration in\nmild-warning zones"),
]
for i, (t, b) in enumerate(right):
    box(RX, Y0 - i * (BH + GAP), RW, BH, t, b, fs=8.2)
    if i < len(right) - 1:
        varrow(RX + RW / 2, Y0 - i * (BH + GAP), Y0 - (i + 1) * (BH + GAP) + BH)
# 中→右 三条输出箭头
harrow(MX + MW, RX, 6.45)
harrow(MX + MW, RX, 4.90)
harrow(MX + MW, RX, 3.50)

# ---------------- 底注 ----------------
ax.text(6.0, 0.60, "Data sources: CRU TS 4.10 \u00b7 CLCD v1.0   |   All indicators min\u2013max normalized; "
                   "thresholds: 0.8 / 0.6 / 0.4 / 0.2",
        ha="center", va="center", fontsize=6.8, style="italic", color="#555555")

plt.savefig(os.path.join(FIG, "fig2_workflow.pdf"), bbox_inches="tight")
plt.savefig(os.path.join(FIG, "fig2_workflow.png"), bbox_inches="tight")
plt.close()
print("saved fig2_workflow.pdf + .png (upgraded framework figure, Arial, viridis threshold band)")