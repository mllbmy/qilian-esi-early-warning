# -*- coding: utf-8 -*-
"""Fig.2 DPSIR 框架图 R37 —— 按 JMS 指南（画布 16.00 cm + 图内 TNR 8–9 pt）重排。

R37 相对 R36 的改动（**只改版式与字号，科学内容与数值零改动**）：
  * 画布宽由 9.0 in（22.86 cm）改为 16.00 cm 印刷插入宽；坐标系 1 单位 = 1 mm，
    图内所有文字直接写 8 pt（正文/刻度）或 9 pt（分区标题、模块标题），
    不再靠"大画布缩小到 16 cm"折算出 5.4–9.5 pt 的不可控字号；
  * 横幅/标题条/色带高度按 mm 重算，模块行高 4.6 mm、标题条 5.4 mm；
  * 长句在 16 cm 内放不下的两处标签做了**同义压缩**（不删信息、不改数值）：
      "monthly precipitation · temperature, 2005–2023"   （保留原样，1 行放得下）
      "eight weighted indicators · min–max normalization to [0, 1]"
        -> "eight indicators · min–max normalization to [0, 1]"
      "nine-indicator contrast" 等其余标签保持原样；
  * ESI 公式改用 Unicode 上/下标（ESI = Σ wᵢxᵢ），不再用 mathtext：
    matplotlib 的 mathtext 把下标压到 0.7 倍（9 pt -> 6.3 pt），违反 8–9 pt 下限；
  * 自检：脚本在落盘前用渲染器实测每个文本的宽度，超过所属模块内宽即报错退出，
    避免"改完画布后标签压框/出界"这类静默缺陷。

科学内容（与 R24–R36 完全一致）：
  * 九指标真实组合权重（data/results_weights.csv 语义，此处沿用 R36 的硬编码值，
    与图中原值逐位一致）；五级预警色/顺序/阈值与 fig3 一致；
  * 结构 = 正文 §3 + Fig.2 图注：数据 → DPSIR → ①–④管线 → ⑤预测/⑥归因 → 输出 → 虚线反馈。
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Rectangle

import jms_style  # JMS 指南 §6：画布 16.00 cm + Times New Roman 8–9 pt
plt.rcParams.update({"savefig.dpi": 600, "figure.dpi": 110})

BASE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(BASE, "figures")
os.makedirs(FIG, exist_ok=True)

# ---- 色板：缎带横幅版（与 R36 一致，未改） ----
INK = "#1a1a1a"
GRAY = "#3a3a3a"
EDGE = "#6e6e6e"
HDR_BG = "#d2dbe9"
AFILL, AEDGE = "#8f8f8f", "#6e6e6e"
FB = "#777777"

GREEN = dict(banner="#2e8b47", fill="#edf5ec", edge="#3f9159")
BLUE = dict(banner="#3d6ba8", fill="#ebf1f8", edge="#3d6ba8")
PURP = dict(banner="#77689e", fill="#f0eef6", edge="#77689e")
RED = dict(banner="#bd3a2e", fill="#faeeec", edge="#bd3a2e")
BADGE = {"D": "#2f6db3", "P": "#e07b39", "S": "#3a9e4f",
         "I": "#77689e", "R": "#bd3a2e"}

FS_BAN, FS_T, FS_B = 9.0, 9.0, 8.0      # 横幅 / 模块标题 / 正文（JMS 8–9 pt）

# ---- 画布：1 数据单位 = 1 mm ----
W, H = 160.0, 155.0
ML, MR = 5.0, 3.0          # 左右页边（左侧留 5 mm：管理反馈虚线 + 竖排标签不被裁切）
CW = W - ML - MR           # 可用宽 152 mm
CX = ML + CW / 2.0         # 版面中心 x
fig = jms_style.figure(H / 10.0)
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, W); ax.set_ylim(0, H); ax.axis("off")

HDR, LH = 5.4, 4.6        # 标题条高 / 正文行高（mm）

_FIT = []                 # (artist, 允许最大宽度 mm, 文本片段) —— 落盘前实测校核


def rect(x, y, w, h, fc, ec=EDGE, lw=0.8, z=2, ls="solid"):
    ax.add_patch(Rectangle((x, y), w, h, fc=fc, ec=ec, lw=lw, zorder=z, linestyle=ls))


def txt(x, y, s, fs=FS_B, color=INK, weight="normal", ha="center", va="center",
        style="normal", rot=0, z=6, fit=None):
    t = ax.text(x, y, s, fontsize=fs, color=color, fontweight=weight, ha=ha, va=va,
                style=style, rotation=rot, zorder=z)
    if fit is not None:
        _FIT.append((t, fit, s))
    return t


def ribbon(cx, y, w, h, label, c):
    """chevron 缎带横幅：左端燕尾缺口、右端尖角，白粗体字。"""
    n = h * 0.55
    pts = [(cx - w / 2, y), (cx + w / 2 - n, y), (cx + w / 2, y + h / 2),
           (cx + w / 2 - n, y + h), (cx - w / 2, y + h), (cx - w / 2 + n, y + h / 2)]
    ax.add_patch(Polygon(pts, closed=True, fc=c, ec="none", zorder=3))
    txt(cx, y + h / 2, label, fs=FS_BAN, color="white", weight="bold", z=4, fit=w * 0.82)


def zone(x, y, w, h, zc):
    rect(x, y, w, h, zc["fill"], zc["edge"], lw=1.0, z=1, ls=(0, (5, 3)))


def barrow_v(cx, y_top, y_bot, sw=1.4, hw=2.8):
    L = y_top - y_bot
    hh = min(1.6, L * 0.7)
    ys = y_bot + hh
    pts = [(cx - sw / 2, y_top), (cx + sw / 2, y_top), (cx + sw / 2, ys),
           (cx + hw / 2, ys), (cx, y_bot), (cx - hw / 2, ys), (cx - sw / 2, ys)]
    ax.add_patch(Polygon(pts, closed=True, fc=AFILL, ec=AEDGE, lw=0.5, zorder=3))


def barrow_h(x_l, x_r, cy, sw=1.4, hw=2.8):
    L = x_r - x_l
    hh = min(1.6, L * 0.7)
    xs = x_r - hh
    pts = [(x_l, cy - sw / 2), (xs, cy - sw / 2), (xs, cy - hw / 2), (x_r, cy),
           (xs, cy + hw / 2), (xs, cy + sw / 2), (x_l, cy + sw / 2)]
    ax.add_patch(Polygon(pts, closed=True, fc=AFILL, ec=AEDGE, lw=0.5, zorder=3))


def pmodule(x, w, ytop, title, lines, lh=LH):
    """管线/输入模块：浅蓝灰标题条（居中粗体 9 pt）+ 白底居中正文 8 pt。"""
    h = HDR + lh * len(lines)
    y0 = ytop - h
    rect(x, y0, w, h, "white", EDGE, lw=0.8, z=2)
    rect(x + 0.5, ytop - HDR + 0.35, w - 1.0, HDR - 0.8, HDR_BG, "none", z=3)
    txt(x + w / 2, ytop - HDR / 2, title, fs=FS_T, weight="bold", z=4, fit=w - 5)
    for j, s in enumerate(lines):
        txt(x + w / 2, ytop - HDR - (j + 0.5) * lh, s, fs=FS_B, z=4, fit=w - 5)
    return y0


def dmodule(x, w, ytop, letter, title, lines):
    """DPSIR 模块：浅蓝灰标题条 + 彩底白字徽章 + 左标签右权重。"""
    h = HDR + LH * len(lines)
    y0 = ytop - h
    rect(x, y0, w, h, "white", EDGE, lw=0.8, z=2)
    rect(x + 0.5, ytop - HDR + 0.35, w - 1.0, HDR - 0.8, HDR_BG, "none", z=3)
    bs = 3.4                                   # 徽章边长
    rect(x + 1.0, ytop - HDR / 2 - bs / 2, bs, bs, BADGE[letter], "none", z=4)
    txt(x + 1.0 + bs / 2, ytop - HDR / 2 - 0.15, letter, fs=FS_T, color="white",
        weight="bold", z=5)
    txt(x + 5.6, ytop - HDR / 2, title, fs=FS_T, weight="bold", ha="left", z=4,
        fit=w - 7.0)
    for j, (nm, meta) in enumerate(lines):
        yy = ytop - HDR - (j + 0.5) * LH
        txt(x + 1.6, yy, nm, fs=FS_B, ha="left", z=4, fit=w - 18.0)
        if meta:
            txt(x + w - 1.4, yy, meta, fs=FS_B, ha="right", color=GRAY, z=4, fit=17.0)
    return y0


# ================= 分区 1：Open data inputs（绿） =================
zone(ML, 130.0, CW, 22.0, GREEN)
ribbon(CX, 144.6, 62.0, 7.0, "Open data inputs", GREEN["banner"])
IN_W = 72.0
cru_x, clcd_x = ML + 1.5, ML + 1.5 + IN_W + 9.0
cru_b = pmodule(cru_x, IN_W, 143.4, "CRU TS 4.10 climate",
                ["monthly precipitation \u00b7 temperature, 2005\u20132023"])
clcd_b = pmodule(clcd_x, IN_W, 143.4, "CLCD 30 m land cover",
                 ["five epochs: 2005 / 2010 / 2015 / 2020 / 2023"])
barrow_v(CX, cru_b - 0.3, 125.0, sw=2.0, hw=4.0)

# ================= 分区 2/3：DPSIR（蓝）+ 预警管线（紫） =================
LX, LW_ = ML, 53.0
RX, RW_ = LX + LW_ + 7.0, W - MR - (LX + LW_ + 7.0)
zone(LX, 28.0, LW_, 96.0, BLUE)
ribbon(LX + LW_ / 2, 116.0, 46.0, 7.0, "DPSIR indicator system", BLUE["banner"])
zone(RX, 28.0, RW_, 96.0, PURP)
ribbon(RX + RW_ / 2, 116.0, 62.0, 7.0, "ESI early-warning pipeline", PURP["banner"])

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
     [("Unweighted (qualitative)", "")]),
]
heights = [HDR + LH * len(ls) for _, _, ls in DPSIR]
TOP_L, BOT_L = 113.0, 32.0
GAP = (TOP_L - BOT_L - sum(heights)) / 4.0
y_cur = TOP_L
boxes = []
for (letter, name, lines), bh in zip(DPSIR, heights):
    y0 = dmodule(LX, LW_, y_cur, letter, name, lines)
    boxes.append((y0, y_cur))
    y_cur = y0 - GAP
for k in range(4):
    barrow_v(LX + LW_ / 2, boxes[k][0] - 0.1, boxes[k + 1][1] + 0.1, sw=1.3, hw=2.6)

# ---- 右栏：预警管线 ①–⑥ ----
TOP_R, BOT_R = 113.0, 32.0
W4_H = 19.0
r_heights = [HDR + LH, HDR + LH, HDR + 2 * LH, W4_H, 18.0]
r_gap = (TOP_R - BOT_R - sum(r_heights)) / 4.0

y_cur = TOP_R
y0_1 = pmodule(RX, RW_, y_cur, "1  Indicator integration",
               ["eight indicators \u00b7 min\u2013max normalization to [0, 1]"])
barrow_v(RX + RW_ / 2, y0_1 - 0.1, y0_1 - r_gap + 0.1, sw=1.3, hw=2.6)
y0_2 = pmodule(RX, RW_, y0_1 - r_gap, "2  Combined weighting",
               ["AHP (\u03b1 = 0.4) + entropy weight (1 \u2212 \u03b1)"])
barrow_v(RX + RW_ / 2, y0_2 - 0.1, y0_2 - r_gap + 0.1, sw=1.3, hw=2.6)
y0_3 = pmodule(RX, RW_, y0_2 - r_gap, "3  Ecological security index (ESI)",
               ["ESI = \u03a3 w\u1d62x\u1d62   (weighted normalized indicators)",
                "annual, 2005\u20132023 \u00b7 regional + 11 counties"])
barrow_v(RX + RW_ / 2, y0_3 - 0.1, y0_3 - r_gap + 0.1, sw=1.3, hw=2.6)

# ④ 五级预警（标题条 + 彩色色带，与 fig3 完全一致）
W4T = y0_3 - r_gap
w4b = W4T - W4_H
rect(RX, w4b, RW_, W4_H, "white", EDGE, lw=0.8, z=2)
rect(RX + 0.5, W4T - HDR + 0.35, RW_ - 1.0, HDR - 0.8, HDR_BG, "none", z=3)
txt(RX + RW_ / 2, W4T - HDR / 2, "4  Five-grade early warning", fs=FS_T,
    weight="bold", z=4, fit=RW_ - 5)
WARN5 = [("Severe", "#b2182b", "[0.0, 0.2)", "white"),
         ("Medium", "#e07b39", "[0.2, 0.4)", "white"),
         ("Mild", "#f4d03f", "[0.4, 0.6)", INK),
         ("Rel. safe", "#7dcea0", "[0.6, 0.8)", INK),
         ("Safe", "#1b7837", "[0.8, 1.0]", "white")]
inner = RW_ - 5.0
gg = 1.6
gw = (inner - 4 * gg) / 5.0
gx0 = RX + (RW_ - (5 * gw + 4 * gg)) / 2.0
gy = w4b + 5.4
for k, (name, c, rng, tc) in enumerate(WARN5):
    gx = gx0 + k * (gw + gg)
    rect(gx, gy, gw, 3.6, c, "none", z=3)
    txt(gx + gw / 2, gy + 1.8, rng, fs=8.0, color=tc, weight="bold", z=4, fit=gw + 1.5)
    txt(gx + gw / 2, w4b + 2.5, name, fs=FS_B, z=4, fit=gw + 2.0)

# ⑤⑥ 并联
bt = w4b - r_gap
hg = 3.2
hw_ = (RW_ - hg) / 2.0
barrow_v(RX + hw_ / 2, w4b - 0.1, bt + 0.1, sw=1.3, hw=2.6)
barrow_v(RX + hw_ + hg + hw_ / 2, w4b - 0.1, bt + 0.1, sw=1.3, hw=2.6)
y0_5 = pmodule(RX, hw_, bt, "5  Forecasting",
               ["NGBM vs GM(1,1) vs ARIMA", "rolling-origin backtest",
                "2024\u20132028 projection"], lh=(18.0 - HDR) / 3)
y0_6 = pmodule(RX + hw_ + hg, hw_, bt, "6  Spatial attribution",
               ["County ESI (2020)", "Moran's I clustering",
                "GeoDetector q-statistic"], lh=(18.0 - HDR) / 3)

# ---- 左栏 → 右栏：横向块状大箭头 ----
barrow_h(LX + LW_ + 0.2, RX - 0.2, 70.0, sw=2.2, hw=4.4)

# ================= 分区 4：Early-warning outputs（红） =================
zone(ML, 3.0, CW, 20.0, RED)
ribbon(CX, 15.6, 66.0, 7.0, "Early-warning outputs", RED["banner"])
OUT_GAP = 3.0
OUT_W = (CW - 3.0 - 2 * OUT_GAP) / 3.0
outs = [("Warning dynamics", "2005\u20132023 \u00b7 grade series", ML + 1.5),
        ("Forecast 2024\u20132028", "NGBM \u00b7 bootstrap intervals",
         ML + 1.5 + OUT_W + OUT_GAP),
        ("Zonal management", "recommendations",
         ML + 1.5 + 2 * (OUT_W + OUT_GAP))]
for t, s, ox in outs:
    rect(ox, 4.2, OUT_W, 9.2, "white", EDGE, lw=0.8, z=2)
    txt(ox + OUT_W / 2, 10.4, t, fs=FS_T, weight="bold", z=4, fit=OUT_W - 4)
    txt(ox + OUT_W / 2, 6.9, s, fs=FS_B, color=GRAY, z=4, fit=OUT_W - 4)
for cx in (RX + hw_ / 2, RX + hw_ + hg + hw_ / 2):
    barrow_v(cx, y0_5 - 0.3, 23.6, sw=1.6, hw=3.2)

# ================= 管理反馈虚线环（左缘回 Driving force） =================
fb_x = 3.2
d_hdr = boxes[0][1] - HDR / 2
ax.plot([ML, fb_x], [8.8, 8.8], color=FB, lw=0.8, ls=(0, (4, 2.6)), zorder=2)
ax.plot([fb_x, fb_x], [8.8, d_hdr], color=FB, lw=0.8, ls=(0, (4, 2.6)), zorder=2)
ax.add_patch(Polygon([(fb_x, d_hdr - 0.9), (fb_x, d_hdr + 0.9),
                      (LX - 0.2, d_hdr)], closed=True, fc=FB, ec="none", zorder=3))
txt(1.5, (8.8 + d_hdr) / 2, "management feedback", fs=FS_B, color=FB,
    style="italic", rot=90, fit=80.0)

# ---------------- 落盘前实测：文本宽度不得超出所属模块 ----------------
fig.canvas.draw()
_r = fig.canvas.get_renderer()
_px_per_mm = fig.dpi / 25.4
_over = []
for artist, limit, s in _FIT:
    w_mm = artist.get_window_extent(renderer=_r).width / _px_per_mm
    if w_mm > limit:
        _over.append((s, round(w_mm, 1), round(limit, 1)))
if _over:
    for s, w_mm, lim in _over:
        print("[OVERFLOW] %.1f > %.1f mm : %s" % (w_mm, lim, s), file=sys.stderr)
    raise SystemExit("Fig.2 版式自检失败：%d 处文本超出模块内宽" % len(_over))

jms_style.save(fig, "fig_dpsir_framework", outdir=FIG)
plt.close(fig)
print("[OK] figures/fig_dpsir_framework.pdf/.png  (16.00 cm, 8\u20139 pt TNR, 自检通过)")
