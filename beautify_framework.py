# -*- coding: utf-8 -*-
"""分析框架图（投稿版）生成器 — 内容基线 = figures/fig_dpsir_framework.dot（dsh Graphviz 版）
自 v18 起本脚本产出论文实际使用的 figures/fig_dpsir_framework.pdf/.png；.dot 保留为
"内容与语义基线"（节点文字/层级/箭头/反馈环含义以 .dot 为准，逐字一致由 verify 断言）。
版式要点：
  1) 层标题条：浅色底+彩边+彩色粗体标题+细分隔线；
  2) 盒宽按文字实测尺寸自动适配（renderer 量测），杜绝溢出/贴边；
  3) DPSIR→归一化 五箭头扇形汇聚；
  4) 管理反馈环：左缘正交虚线，标注沿线竖排；
  5) Arial，PDF Type 42 嵌入，600dpi PNG；
  6) 导出不依赖 bbox_inches="tight"（axis("off") 后 axes 矩形仍会使 tight=整幅，
     留下死白）：直接令 xlim/ylim=内容跨度、figsize=内容尺寸，四周 0.04in 对称出血。
输出: figures/fig_dpsir_framework.pdf + .png（本脚本同目录下的 figures/）
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

plt.rcParams.update({"font.family": "Arial", "pdf.fonttype": 42,
                     "axes.unicode_minus": False})

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures")
os.makedirs(OUT, exist_ok=True)

# 与 dsh 版一致的层配色(D蓝/P红/S绿/I赭/R紫)
C_D, C_P, C_S, C_I, C_R = "#2a6f97", "#b23a48", "#2d6a4f", "#b06c1f", "#5a4a8a"
EDGE, ARROW = "#5b6b7c", "#5b6b7c"
BOX_BG, WARN_BG = "#f2f6fa", "#f6f4ef"

FIGW = 7.2          # 图宽(in); 稿中 1.0\\linewidth≈6.3in 插入, 缩比0.875, 设计字号8~9.6pt→有效7~8.4pt
CANVAS_W = 140.0    # 画布数据坐标宽(留出盒间空隙)
fig, ax = plt.subplots(figsize=(FIGW, 8.1))
ax.set_xlim(-10, CANVAS_W + 10)
ax.set_ylim(0, 106)
ax.axis("off")
fig.subplots_adjust(left=0.0, right=1.0, top=1.0, bottom=0.0)
_renderer = fig.canvas.get_renderer()


def text_w(s, fs, bold=False):
    """测量文本在数据坐标下的宽度"""
    t = ax.text(0, 0, s, fontsize=fs, fontweight="bold" if bold else "normal")
    bb = t.get_window_extent(renderer=_renderer)
    t.remove()
    inv = ax.transData.inverted()
    x0, _ = inv.transform((0, 0))
    x1, _ = inv.transform((bb.width, 0))
    return abs(x1 - x0)


def tint(hex_c, a=0.12):
    h = hex_c.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return (r, g, b, a)


def layer_box(x, y, w, h, color, title, items):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.3,rounding_size=1.2",
                                fc=tint(color), ec=color, lw=1.1, zorder=2))
    ax.text(x + w / 2, y + h - 2.4, title, ha="center", va="top",
            fontsize=9.0, fontweight="bold", color=color, zorder=3)
    ax.plot([x + 2.0, x + w - 2.0], [y + h - 5.8] * 2, color=color, lw=0.7,
            alpha=0.55, zorder=3)
    for i, it in enumerate(items):
        ax.text(x + 2.2, y + h - 8.8 - i * 3.5, it, ha="left", va="top",
                fontsize=8.0, color="#14181c", zorder=3)


def proc_box(cx, y, w, h, lines, fc=BOX_BG, ec=EDGE, fs=8.8, title_fs=9.6):
    ax.add_patch(FancyBboxPatch((cx - w / 2, y), w, h,
                                boxstyle="round,pad=0.3,rounding_size=1.2",
                                fc=fc, ec=ec, lw=1.0, zorder=2))
    n = len(lines)
    total = (n - 1) * 3.8
    cy = y + h / 2 + total / 2
    for i, ln in enumerate(lines):
        ax.text(cx, cy - i * 3.8, ln, ha="center", va="center",
                fontsize=title_fs if i == 0 else fs,
                fontweight="bold" if i == 0 else "normal",
                color="#14181c", zorder=3)


def arrow(x1, y1, x2, y2, color=ARROW, lw=1.1, ls="-", ms=12):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                                 mutation_scale=ms, lw=lw, color=color,
                                 linestyle=ls, zorder=1))


# ---------- 顶带: DPSIR 五层因果链(盒宽实测自适应) ----------
Y0, H = 86, 18
layers = [
    ("Driving (D)", ["Precipitation (+)", "Temperature (+)"], C_D),
    ("Pressure (P)", ["Barren/degraded (\u2212)", "Cropland (\u2212)"], C_P),
    ("State (S)", ["Grassland (+)", "Forest (+)", "Water (+)"], C_S),
    ("Impact (I)", ["Grassland change (+)"], C_I),
    ("Response (R)", ["Ecological land (+)"], C_R),
]
PAD_L, PAD_R = 2.2, 2.2  # 条目左对齐起点2.2, 右侧同留2.2, 杜绝贴边
widths = []
for title, items, c in layers:
    w_need = max([text_w(title, 9.0, bold=True)] +
                 [text_w(it, 8.0) for it in items]) + PAD_L + PAD_R
    widths.append(w_need)
GAP = (CANVAS_W - sum(widths)) / 6  # 五盒六等间隔(含两端)
print(f"[layout] layer widths={[round(w,1) for w in widths]} GAP={GAP:.2f}")
xs, _x = [], 0.0
for w in widths:
    _x += GAP
    xs.append(_x)
    _x += w
for (title, items, c), x, w in zip(layers, xs, widths):
    layer_box(x, Y0, w, H, c, title, items)
# 盒间缝隙画衔接三角(▸): 缝隙窄, 三角叠在缝上, 示意 D→P→S→I→R 流向
from matplotlib.patches import Polygon
for i in range(4):
    sx = xs[i] + widths[i] + GAP / 2
    ym = Y0 + H / 2
    ax.add_patch(Polygon([(sx - 1.3, ym - 2.2), (sx - 1.3, ym + 2.2), (sx + 1.5, ym)],
                         closed=True, fc=ARROW, ec="white", lw=0.5, zorder=4))

# ---------- 中带: 归一化 → 组合赋权 → ESI → 预警 ----------
CX = CANVAS_W / 2
chain = [
    (69, 8, ["Nine indicators \u2192 min\u2013max normalization to [0, 1]"], BOX_BG, 9.0, 9.8),
    (53, 12, ["Combined weighting", "AHP (\u03b1 = 0.4) + entropy (1 \u2212 \u03b1)",
              "\u03b1 sensitivity over 0\u20131"], BOX_BG, 9.0, 9.8),
    (39.5, 9.5, ["Ecological security index (ESI)", "2005\u20132023, annual"], BOX_BG, 9.0, 9.8),
    (23.5, 12, ["Five-grade early warning",
                "safe \u00b7 relatively safe \u00b7 mild \u00b7 medium \u00b7 severe"], WARN_BG, 9.0, 9.8),
]
CW = max(max(text_w(ln, 9.8, bold=True) if i == 0 else text_w(ln, 9.0)
             for i, ln in enumerate(lines))
         for _, _, lines, _, _, _ in chain) + 7.0
for y, h, lines, fc, fs, tfs in chain:
    proc_box(CX, y, CW, h, lines, fc=fc, fs=fs, title_fs=tfs)

# DPSIR → norm: 扇形汇聚
fan = [CX - CW / 2 + f * CW / 4 for f in range(5)]
for x, w, xt in zip(xs, widths, fan):
    arrow(x + w / 2, Y0 - 0.6, xt, 77.4, lw=0.9)
arrow(CX, 68.6, CX, 65.4)   # norm → weighting
arrow(CX, 52.6, CX, 49.4)   # weighting → ESI
arrow(CX, 39.1, CX, 35.9)   # ESI → warning

# ---------- 底带: 三个输出(盒宽实测自适应) ----------
OY, OH = 6, 12.5
outs = [
    ["Zonal management", "recommendations"],
    ["Forecast 2024\u20132028", "GM(1,1) \u00b7 NGBM (selected) \u00b7 ARIMA"],
    ["Spatial attribution", "GeoDetector q (999 permutations)"],
]
ow = [max(text_w(lines[0], 9.0, bold=True), text_w(lines[1], 8.0)) + 6.0
      for lines in outs]
ogap = (CANVAS_W - sum(ow)) / 4
print(f"[layout] out widths={[round(w,1) for w in ow]} ogap={ogap:.2f}")
ox, _x = [], 0.0
for w in ow:
    _x += ogap
    ox.append(_x)
    _x += w
for lines, x, w in zip(outs, ox, ow):
    proc_box(x + w / 2, OY, w, OH, lines, fs=8.0, title_fs=9.0)
arrow(CX - CW / 2 + 8, 23.1, ox[0] + ow[0] / 2, OY + OH + 0.5, lw=0.9)
arrow(CX, 23.1, ox[1] + ow[1] / 2, OY + OH + 0.5, lw=0.9)
arrow(CX + CW / 2 - 8, 23.1, ox[2] + ow[2] / 2, OY + OH + 0.5, lw=0.9)

# ---------- 管理反馈环: zonal management → Driving (左缘正交虚线) ----------
FX = -3.5
ax.plot([ox[0] - 0.5, FX], [OY + OH / 2] * 2, ls=(0, (5, 3)), color="#8a97a5", lw=1.0, zorder=1)
ax.plot([FX, FX], [OY + OH / 2, Y0 + H / 2], ls=(0, (5, 3)), color="#8a97a5", lw=1.0, zorder=1)
arrow(FX, Y0 + H / 2, xs[0] - 0.5, Y0 + H / 2, color="#8a97a5", lw=1.0, ms=11)
ax.text(FX - 3.2, (OY + OH / 2 + Y0 + H / 2) / 2, "management feedback",
        rotation=90, ha="center", va="center", fontsize=8.4, style="italic", color="#7a8794")

# ---------- 导出: 画布收紧到内容实际跨度, 消除死白(dsh 复核项) ----------
# axis("off") 后 axes 白底 patch 仍使 tight=整幅, 故不依赖 tight: 直接令
# xlim/ylim=内容跨度, figsize=内容尺寸; SX/SY 与测量期一致 → 版式(英寸)零位移
SX = (CANVAS_W + 20) / FIGW   # 横向 数据单位/英寸
SY = 106 / 8.1                # 纵向 数据单位/英寸
X0c, X1c = -8.05, xs[-1] + widths[-1] + 0.5
YBc, YTc = OY - 0.5, Y0 + H + 0.5
MX, MY = 0.9, 0.55            # 对称出血≈0.04in, 防外框线半笔宽被页边裁切
ax.set_xlim(X0c - MX, X1c + MX)
ax.set_ylim(YBc - MY, YTc + MY)
fig.set_size_inches((X1c - X0c + 2 * MX) / SX, (YTc - YBc + 2 * MY) / SY)
print(f"[layout] page = {fig.get_figwidth():.2f} x {fig.get_figheight():.2f} in "
      f"(content {X1c - X0c:.1f} x {YTc - YBc:.1f} units)")

fig.savefig(os.path.join(OUT, "fig_dpsir_framework.pdf"))
fig.savefig(os.path.join(OUT, "fig_dpsir_framework.png"), dpi=600)
print("saved fig_dpsir_framework.pdf/.png ->", OUT)
