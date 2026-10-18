# -*- coding: utf-8 -*-
"""Fig.2 框架图 R36 —— 恢复缎带横幅版（按用户提供的 R30 截图 1:1 重建）。

R36 说明：
- 用户指定回退到 R30 视觉风格（截图为准）：彩色 chevron 缎带横幅（绿/蓝/紫/红）
  + 分区淡彩底与同色系虚线边框 + DPSIR 彩底白字字母徽章
  + 浅蓝灰标题条模块 + 深灰块状箭头 + 左缘管理反馈虚线
- R35（白底 inset 版）已存档：投稿前优化/图件/版本存档/Fig02_R35_white_insets.{py,png,pdf,tif}
- 版式几何按截图像素实测换算（1080x914 px -> 100x86 坐标）
- ESI 公式沿用 R31 修复方案（STIX mathtext，避免 Unicode 下标回退黑体）

科学内容零改动（与 R24–R35 一致）：
- 九指标真实组合权重（data/results_weights.csv）；五级预警色/顺序/阈值与 fig3 一致
- 结构 = v5 正文 §3 + Fig.2 图注：数据 → DPSIR → ①–④管线 → ⑤预测/⑥归因 → 输出 → 虚线反馈
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Rectangle

import jms_style  # Times New Roman，与全部图件统一
plt.rcParams.update({"savefig.dpi": 600, "figure.dpi": 110})

BASE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(BASE, "figures")
os.makedirs(FIG, exist_ok=True)

# ---- 色板：缎带横幅版 ----
INK = "#1a1a1a"
GRAY = "#3a3a3a"
EDGE = "#6e6e6e"          # 模块边框灰
HDR_BG = "#d2dbe9"        # 模块标题条浅蓝灰
AFILL, AEDGE = "#8f8f8f", "#6e6e6e"   # 块状箭头
FB = "#777777"            # 管理反馈虚线

GREEN = dict(banner="#2e8b47", fill="#edf5ec", edge="#3f9159")
BLUE = dict(banner="#3d6ba8", fill="#ebf1f8", edge="#3d6ba8")
PURP = dict(banner="#77689e", fill="#f0eef6", edge="#77689e")
RED = dict(banner="#bd3a2e", fill="#faeeec", edge="#bd3a2e")
BADGE = {"D": "#2f6db3", "P": "#e07b39", "S": "#3a9e4f",
         "I": "#77689e", "R": "#bd3a2e"}

FS_BAN, FS_T, FS_B = 13.5, 12.5, 11.0   # 横幅 / 模块标题 / 正文
W, H = 100.0, 86.0
fig = plt.figure(figsize=(9.0, 7.74))   # 1 单位 = 0.09 in
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, W); ax.set_ylim(0, H); ax.axis("off")

HDR, LH = 3.2, 3.2        # 标题条高 / 内容行高


def rect(x, y, w, h, fc, ec=EDGE, lw=1.0, z=2, ls="solid"):
    ax.add_patch(Rectangle((x, y), w, h, fc=fc, ec=ec, lw=lw, zorder=z, linestyle=ls))


def txt(x, y, s, fs=FS_B, color=INK, weight="normal", ha="center", va="center",
        style="normal", rot=0, z=6):
    ax.text(x, y, s, fontsize=fs, color=color, fontweight=weight, ha=ha, va=va,
            style=style, rotation=rot, zorder=z)


def ribbon(cx, y, w, h, label, c):
    """chevron 缎带横幅：左端燕尾缺口、右端尖角，白粗体字。"""
    n = h * 0.55
    pts = [(cx - w / 2, y), (cx + w / 2 - n, y), (cx + w / 2, y + h / 2),
           (cx + w / 2 - n, y + h), (cx - w / 2, y + h), (cx - w / 2 + n, y + h / 2)]
    ax.add_patch(Polygon(pts, closed=True, fc=c, ec="none", zorder=3))
    txt(cx, y + h / 2, label, fs=FS_BAN, color="white", weight="bold", z=4)


def zone(x, y, w, h, zc):
    """分区：淡彩底 + 同色系虚线边框。"""
    rect(x, y, w, h, zc["fill"], zc["edge"], lw=1.3, z=1, ls=(0, (5, 3)))


def barrow_v(cx, y_top, y_bot, sw=1.6, hw=3.2):
    """向下块状箭头（深灰）。"""
    L = y_top - y_bot
    hh = min(1.3, L * 0.6)
    ys = y_bot + hh
    pts = [(cx - sw / 2, y_top), (cx + sw / 2, y_top), (cx + sw / 2, ys),
           (cx + hw / 2, ys), (cx, y_bot), (cx - hw / 2, ys), (cx - sw / 2, ys)]
    ax.add_patch(Polygon(pts, closed=True, fc=AFILL, ec=AEDGE, lw=0.6, zorder=3))


def barrow_h(x_l, x_r, cy, sw=1.6, hw=3.2):
    """向右块状箭头（深灰）。"""
    L = x_r - x_l
    hh = min(1.3, L * 0.6)
    xs = x_r - hh
    pts = [(x_l, cy - sw / 2), (xs, cy - sw / 2), (xs, cy - hw / 2), (x_r, cy),
           (xs, cy + hw / 2), (xs, cy + sw / 2), (x_l, cy + sw / 2)]
    ax.add_patch(Polygon(pts, closed=True, fc=AFILL, ec=AEDGE, lw=0.6, zorder=3))


def module_h(n):
    return HDR + LH * n


def pmodule(x, w, ytop, title, lines, lh=LH):
    """管线/输入模块：浅蓝灰标题条（居中粗体）+ 白底居中内容。"""
    h = HDR + lh * len(lines)
    y0 = ytop - h
    rect(x, y0, w, h, "white", EDGE, lw=1.0, z=2)
    rect(x + 0.06, ytop - HDR + 0.04, w - 0.12, HDR - 0.10, HDR_BG, "none", z=3)
    txt(x + w / 2, ytop - HDR / 2, title, fs=FS_T, weight="bold", z=4)
    for j, s in enumerate(lines):
        txt(x + w / 2, ytop - HDR - (j + 0.5) * lh, s, fs=FS_B, z=4)
    return y0


def dmodule(x, w, ytop, letter, title, lines):
    """DPSIR 模块：浅蓝灰标题条 + 彩底白字徽章 + 左标签右权重。"""
    h = module_h(len(lines))
    y0 = ytop - h
    rect(x, y0, w, h, "white", EDGE, lw=1.0, z=2)
    rect(x + 0.06, ytop - HDR + 0.04, w - 0.12, HDR - 0.10, HDR_BG, "none", z=3)
    bs = 2.3                                  # 徽章边长
    rect(x + 0.75, ytop - HDR / 2 - bs / 2, bs, bs, BADGE[letter], "none", z=4)
    txt(x + 0.75 + bs / 2, ytop - HDR / 2, letter, fs=FS_T, color="white",
        weight="bold", z=5)
    txt(x + 3.8, ytop - HDR / 2, title, fs=FS_T, weight="bold", ha="left", z=4)
    for j, (nm, meta) in enumerate(lines):
        yy = ytop - HDR - (j + 0.5) * LH
        txt(x + 1.1, yy, nm, fs=FS_B, ha="left", z=4)
        txt(x + w - 1.1, yy, meta, fs=FS_B, ha="right", color=GRAY, z=4)
    return y0


# ================= 分区 1：Open data inputs（绿） =================
zone(2.2, 72.8, 95.6, 13.0, GREEN)
ribbon(50.0, 82.3, 36.0, 3.0, "Open data inputs", GREEN["banner"])
IN_W = 40.5
cru_b = pmodule(6.3, IN_W, 80.5, "CRU TS 4.10 climate",
                ["monthly precipitation \u00b7 temperature, 2005\u20132023"])
clcd_b = pmodule(53.2, IN_W, 80.5, "CLCD 30 m land cover",
                 ["five epochs: 2005 / 2010 / 2015 / 2020 / 2023"])
barrow_v(43.5, cru_b - 0.15, 71.3, sw=2.0, hw=4.2)      # 数据 → 中下区域（按截图）

# ================= 分区 2/3：DPSIR（蓝）+ 预警管线（紫） =================
zone(2.4, 12.4, 33.6, 58.7, BLUE)
ribbon(19.2, 66.6, 31.5, 3.4, "DPSIR indicator system", BLUE["banner"])
zone(39.4, 12.4, 58.4, 58.7, PURP)
ribbon(68.6, 66.6, 56.0, 3.4, "ESI early-warning pipeline", PURP["banner"])

LX, LW_ = 3.4, 30.0
RX, RW_ = 41.6, 54.0

# ---- 左栏：DPSIR 五框（真实组合权重） ----
DPSIR = [
    ("D", "Driving force (D)",
     [("Precipitation", "(+)  w = 0.092"), ("Temperature", "(+)  w = 0.062")]),
    ("P", "Pressure (P)",
     [("Barren/degraded land", "(\u2212)  w = 0.059"), ("Cropland", "(\u2212)  w = 0.131")]),
    ("S", "State (S)",
     [("Grassland", "(+)  w = 0.125"), ("Forest", "(+)  w = 0.144"),
      ("Water", "(+)  w = 0.151")]),
    ("I", "Impact (I)",
     [("Grassland change rate", "(+)  w = 0.235")]),
    ("R", "Policy background (R)",
     [("Policy background", "unweighted (qualitative)")]),
]
heights = [module_h(len(ls)) for _, _, ls in DPSIR]
GAP = (65.6 - 16.4 - sum(heights)) / 4
y_cur = 65.6
boxes = []
for (letter, name, lines), bh in zip(DPSIR, heights):
    y0 = dmodule(LX, LW_, y_cur, letter, name, lines)
    boxes.append((y0, y_cur))
    y_cur = y0 - GAP
for k in range(4):
    barrow_v(LX + LW_ / 2, boxes[k][0] - 0.05, boxes[k + 1][1] + 0.05, sw=1.3, hw=2.6)

# ---- 右栏：预警管线 ①–⑥ ----
W4_H = 11.6
r_heights = [module_h(1), module_h(1), module_h(2), W4_H, 11.5]
r_gap = (65.6 - 15.2 - sum(r_heights)) / 4

y_cur = 65.6
y0_1 = pmodule(RX, RW_, y_cur, "1  Indicator integration",
               ["eight weighted indicators \u00b7 min\u2013max normalization to [0, 1]"])
barrow_v(RX + RW_ / 2, y0_1 - 0.05, y0_1 - r_gap + 0.05, sw=1.3, hw=2.6)
y0_2 = pmodule(RX, RW_, y0_1 - r_gap, "2  Combined weighting",
               ["AHP (\u03b1 = 0.4) + entropy weight (1 \u2212 \u03b1)"])
barrow_v(RX + RW_ / 2, y0_2 - 0.05, y0_2 - r_gap + 0.05, sw=1.3, hw=2.6)
y0_3 = pmodule(RX, RW_, y0_2 - r_gap, "3  Ecological security index (ESI)",
               [r"$\mathrm{ESI} = \sum_i w_i x_i$",
                "annual, 2005\u20132023 \u00b7 regional + 11 counties"])
barrow_v(RX + RW_ / 2, y0_3 - 0.05, y0_3 - r_gap + 0.05, sw=1.3, hw=2.6)

# ④ 五级预警（标题条 + 彩色色带，与 fig3 完全一致）
W4T = y0_3 - r_gap
w4b = W4T - W4_H
rect(RX, w4b, RW_, W4_H, "white", EDGE, lw=1.0, z=2)
rect(RX + 0.06, W4T - HDR + 0.04, RW_ - 0.12, HDR - 0.10, HDR_BG, "none", z=3)
txt(RX + RW_ / 2, W4T - HDR / 2, "4  Five-grade early warning", fs=FS_T,
    weight="bold", z=4)
WARN5 = [("Severe", "#b2182b", "[0.0, 0.2)", "white"),
         ("Medium", "#e07b39", "[0.2, 0.4)", "white"),
         ("Mild", "#f4d03f", "[0.4, 0.6)", INK),
         ("Relatively safe", "#7dcea0", "[0.6, 0.8)", INK),
         ("Safe", "#1b7837", "[0.8, 1.0]", "white")]
gw, gg = 9.6, 0.5
gx0 = RX + (RW_ - (5 * gw + 4 * gg)) / 2
gy = w4b + 4.1
for k, (name, c, rng, tc) in enumerate(WARN5):
    gx = gx0 + k * (gw + gg)
    rect(gx, gy, gw, 3.0, c, "none", z=3)
    txt(gx + gw / 2, gy + 1.5, rng, fs=10.5, color=tc, weight="bold", z=4)
    txt(gx + gw / 2, w4b + 2.2, name, fs=FS_B, z=4)

# ⑤⑥ 并联
bt = w4b - r_gap
hw_, hg = 25.6, 2.8
barrow_v(RX + hw_ / 2, w4b - 0.05, bt + 0.05, sw=1.3, hw=2.6)
barrow_v(RX + hw_ + hg + hw_ / 2, w4b - 0.05, bt + 0.05, sw=1.3, hw=2.6)
y0_5 = pmodule(RX, hw_, bt, "5  Forecasting",
               ["NGBM vs GM(1,1) vs ARIMA", "rolling-origin backtest",
                "2024\u20132028 projection"], lh=(11.5 - HDR) / 3)
y0_6 = pmodule(RX + hw_ + hg, hw_, bt, "6  Spatial attribution",
               ["County ESI (2020)", "Moran's I clustering",
                "GeoDetector q-statistic"], lh=(11.5 - HDR) / 3)

# ---- 左栏 → 右栏：横向块状大箭头 ----
barrow_h(36.2, 39.2, 42.5, sw=2.2, hw=4.4)

# ================= 分区 4：Early-warning outputs（红） =================
zone(2.2, 0.4, 95.6, 10.7, RED)
ribbon(50.0, 7.0, 41.0, 3.0, "Early-warning outputs", RED["banner"])
outs = [("Warning dynamics", "2005\u20132023 \u00b7 grade series", 2.8),
        ("Forecast 2024\u20132028", "NGBM \u00b7 bootstrap intervals", 36.2),
        ("Zonal management", "recommendations", 69.0)]
for t, s, ox in outs:
    rect(ox, 1.3, 28.6, 4.5, "white", EDGE, lw=1.0, z=2)
    txt(ox + 14.3, 4.35, t, fs=FS_T, weight="bold", z=4)
    txt(ox + 14.3, 2.45, s, fs=FS_B, color=GRAY, z=4)
for cx in (RX + hw_ / 2, RX + hw_ + hg + hw_ / 2):
    barrow_v(cx, y0_5 - 0.05, 11.25, sw=1.6, hw=3.2)

# ================= 管理反馈虚线环（左缘回 Driving force） =================
fb_x = 1.15
d_hdr = boxes[0][1] - HDR / 2     # Driving 框标题条高度
ax.plot([2.2, fb_x], [7.9, 7.9], color=FB, lw=1.0, ls=(0, (4, 2.6)), zorder=2)
ax.plot([fb_x, fb_x], [7.9, d_hdr], color=FB, lw=1.0, ls=(0, (4, 2.6)), zorder=2)
ax.add_patch(Polygon([(fb_x, d_hdr - 0.55), (fb_x, d_hdr + 0.55),
                      (LX - 0.1, d_hdr)], closed=True, fc=FB, ec="none", zorder=3))
txt(0.5, (7.9 + d_hdr) / 2, "management feedback", fs=FS_B, color=FB,
    style="italic", rot=90)

out_png = os.path.join(FIG, "fig_dpsir_framework.png")
out_pdf = os.path.join(FIG, "fig_dpsir_framework.pdf")
fig.savefig(out_png, dpi=600)
fig.savefig(out_pdf)
print("[OK]", out_png)
print("[OK]", out_pdf)
