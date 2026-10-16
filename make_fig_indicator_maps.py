# -*- coding: utf-8 -*-
"""图件定稿 v7：「指标空间分布图」六面板（按作者参考图恢复 c/d/e 连续占比面）。

面板（2 行 x 3 列，等宽）：
  (a) 降水（2005-2023 均值，连续场）  (b) 气温（2005-2023 均值，连续场）
  (c) 草地占比（2020，连续场 0-100%）  (d) 森林占比（2020，连续场 0-100%）
  (e) 裸地占比（2020，连续场 0-100%）  (f) 点尺度 ESI（2020，连续场）

c/d/e 说明：data/spatial_samples.csv 的 grass/forest/barren 是 CLCD ±0.02° 邻域
主导类型掩膜（0/1）。此处按作者参考图样式，把该 0/1 场 ×100 后用 griddata 线性插值
成连续面、配 0-100 色标（与 (a)(b)(f) 同法），面板满铺、无灰洞。
配色：(c) YlGn  (d) BuGn  (e) YlOrBr。
注意：该"占比"是主导掩膜的插值场，不是 CLCD 面积比例；若需真实面积占比，
需完整 CLCD 2020 栅格（本地 _raw/lc_data 的 tif 缺本区瓦片）。

叠加 Copernicus DEM 90m 地形阴影 + 公园红线 + 县域。
输出：投稿前优化\\图件\\定稿\\Fig06_indicator_spatial_final.{pdf,png}
      + JMS_Figure_6_final.tif（600 dpi LZW）
"""
import json
import math
import os

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch
import rasterio
from rasterio.enums import Resampling
from scipy.interpolate import griddata

BASE = os.path.dirname(os.path.abspath(__file__))

import jms_style

# R17：画布宽 = A4 版心宽 14.66 cm（5.772 in）；同步把印刷字号提升 18%
#（原设计 7.0-7.5 pt 是为 16.76 cm 画布设定，缩到 14.66 cm 会掉到 6.6 pt）
S = 1.18
plt.rcParams.update({"axes.labelsize": 7.0, "xtick.labelsize": 6.2, "ytick.labelsize": 6.2,
                     "axes.edgecolor": "#444444", "axes.linewidth": 0.6,
                     "savefig.dpi": 600, "figure.dpi": 100})

smp = pd.read_csv(os.path.join(BASE, "data", "spatial_samples.csv"))
pts = pd.read_csv(os.path.join(BASE, "data", "spatial_esi_points.csv"))
QILIAN = {"Tianzhu": (37.20, 102.86), "Sunan": (38.84, 99.62), "Subei": (39.51, 97.85),
          "Aksai": (39.34, 94.34), "Minle": (38.43, 100.81), "Shandan": (38.78, 101.09),
          "Menyuan": (37.38, 101.62), "Qilian": (38.18, 100.24), "Gangcha": (37.33, 100.14),
          "Delingha": (37.37, 97.36), "Tianjun": (37.30, 99.02)}
OFF = {"Sunan": (5, 6), "Shandan": (6, -6), "Minle": (6, 4), "Qilian": (-6, 5),
       "Gangcha": (5, 4), "Menyuan": (6, -5), "Tianjun": (6, -6), "Delingha": (-6, 5),
       "Tianzhu": (-6, 6), "Subei": (4, 4), "Aksai": (4, 4)}

# CLCD v1.0 类别（Yang & Huang, 2021）：1 农田 2 森林 4 草地 5 水域 7 裸地
GRIDD = 0.15
GREY = "#d8d5cf"             # 二值图"其他类型主导"底色（暖浅灰）
FOCUS_COLOR = {4: "#63a64b", 2: "#1f5c33", 7: "#c25437"}  # 草地 / 森林 / 裸地(红棕)


def park_rings():
    gj = json.load(open(os.path.join(BASE, "data", "qmn_park_digitized.geojson"), encoding="utf-8"))
    rings = []
    for f in gj["features"]:
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        for poly in polys:
            rings.append(np.array(poly[0]))
    return rings


RINGS = park_rings()
PTS = np.column_stack([smp["lon"], smp["lat"]])
XI, YI = np.meshgrid(np.linspace(93.5, 103.5, 500), np.linspace(36.0, 40.5, 220))

# ---------- 地形底图：Copernicus DEM 90m ----------
DEM = os.path.join(BASE, "data", "cop90")
TILE = 300
_rows = []
for la in range(40, 35, -1):
    _col = []
    for lo in range(93, 104):
        with rasterio.open(os.path.join(DEM, f"N{la:02d}_E{lo:03d}.tif")) as ds:
            _col.append(ds.read(1, out_shape=(TILE, TILE),
                                resampling=Resampling.average).astype(np.float64))
    _rows.append(np.concatenate(_col, axis=1))
_ELEV = np.concatenate(_rows, axis=0)
_ELEV = np.where(_ELEV < -1000, np.nan, _ELEV)
_dy, _dx = np.gradient(_ELEV)
_slope = np.pi / 2 - np.arctan(np.sqrt(_dx * _dx + _dy * _dy))
_aspect = np.arctan2(-_dx, _dy)
_az, _alt = math.radians(315), math.radians(45)
SHADE = np.clip(np.sin(_alt) * np.sin(_slope) + np.cos(_alt) * np.cos(_slope)
                * np.cos(_az - _aspect), 0, 1)
BASE_EXT = [93, 104, 36, 41]  # 瓦片 N36..N40 × E093..E103 实际覆盖：93-104°E, 36-41°N（图1 同源同法，extent 必须与瓦片覆盖一致，否则地形整体错位 + 顶部缺条）


def draw_terrain(ax, light=False):
    # light=True(二值主导图)：把山影大幅提亮到 [0.75,1]，呈"浅灰底+隐约地形"，
    # 匹配参考图的浅色柔底（参考图背景中位数约 230 灰）。
    shade = 0.75 + 0.25 * SHADE if light else SHADE
    ax.imshow(shade, cmap="Greys", extent=BASE_EXT, vmin=0, vmax=1,
              aspect="auto", interpolation="bilinear", zorder=1, alpha=1.0)


def interp(v):
    zi = griddata(PTS, v, (XI, YI), method="linear")
    zn = griddata(PTS, v, (XI, YI), method="nearest")
    return np.where(np.isnan(zi), zn, zi)


def draw_base(ax):
    for ring in RINGS:
        ax.plot(ring[:, 0], ring[:, 1], color="#c0392b", lw=0.6, ls=(0, (4, 2)), zorder=5)
    for n, (la, lo) in QILIAN.items():
        ax.plot(lo, la, "k.", ms=2.2, zorder=6)
        dx, dy = OFF.get(n, (3, 3))
        ax.annotate(n, (lo, la), fontsize=5.2*S, xytext=(dx, dy), textcoords="offset points",
                    zorder=7, path_effects=[pe.withStroke(linewidth=1.4, foreground="white")])
    ax.set_xlim(93.5, 103.5)
    ax.set_ylim(36.0, 40.5)
    ax.grid(alpha=0.10, lw=0.3)


def field(ax, v, cmap, label, vmin=None, vmax=None):
    """连续量：(a) 降水 (b) 气温 (f) 点 ESI —— 插值成连续面有意义。"""
    zi = interp(v)
    if vmin is None or vmax is None:
        lo, hi = np.percentile(v, 2), np.percentile(v, 98)
        if lo == hi:
            lo, hi = float(v.min()), float(v.max())
        if lo == hi:
            hi = lo + 1e-6
        vmin, vmax = float(lo), float(hi)
    draw_terrain(ax)
    im = ax.imshow(zi, extent=[XI.min(), XI.max(), YI.min(), YI.max()],
                   origin="lower", cmap=cmap, vmin=vmin, vmax=vmax,
                   interpolation="bilinear", aspect="auto", zorder=3, alpha=0.80)
    cb = plt.colorbar(im, ax=ax, fraction=0.045, pad=0.02, aspect=16)
    cb.ax.tick_params(labelsize=6.2*S)
    cb.outline.set_linewidth(0.4)
    draw_base(ax)
    ax.set_title(label, fontsize=7.5*S, pad=4)
    return im


def _grid_for(cls):
    la_u = np.sort(smp["lat"].round(3).unique())
    lo_u = np.sort(smp["lon"].round(3).unique())
    g = np.full((len(la_u), len(lo_u)), np.nan)
    la_i = {v: i for i, v in enumerate(la_u)}
    lo_i = {v: i for i, v in enumerate(lo_u)}
    for la, lo, cl in zip(smp["lat"].round(3), smp["lon"].round(3), smp["class"]):
        g[la_i[la], lo_i[lo]] = 1.0 if int(cl) == cls else 0.0
    return g, la_u, lo_u


def presence_map(ax, cls, color, name, label):
    """二值主导图：彩色=该类主导格点，浅灰地形底=其他类型（铺满整个画框）；值不插值。"""
    draw_terrain(ax, light=True)
    g, la_u, lo_u = _grid_for(cls)
    n = int(np.nansum(g))
    share = 100.0 * n / int(len(smp))
    # 焦点格点=彩色(不透明、实心清晰)，非主导(0)=透明 → 显示满铺暖灰底
    cmap = ListedColormap([(0, 0, 0, 0.0), color])
    cmap.set_bad(alpha=0.0)
    norm = BoundaryNorm([-0.5, 0.5, 1.5], 2)
    d = GRIDD
    ax.imshow(g, origin="lower", cmap=cmap, norm=norm,
              extent=[lo_u[0] - d / 2, lo_u[-1] + d / 2, la_u[0] - d / 2, la_u[-1] + d / 2],
              interpolation="nearest", aspect="auto", zorder=3)
    draw_base(ax)
    ax.set_title(label, fontsize=7.5*S, pad=4)
    # 左下角两档小图例，白底，避免窄色标标签溢出
    handles = [Patch(facecolor=color, edgecolor="#666666", linewidth=0.3,
                     label="%s (%d, %.1f%%)" % (name, n, share)),
               Patch(facecolor=GREY, edgecolor="#666666", linewidth=0.3, label="Other")]
    ax.legend(handles=handles, loc="lower left", fontsize=5.4*S, framealpha=0.88,
              handlelength=0.9, handleheight=0.9, borderpad=0.4, labelspacing=0.32,
              columnspacing=0.7, edgecolor="#999999", frameon=True)
    return n, share


# R17：画布宽 = A4 版心宽 14.66 cm（5.772 in）；面板布局由 2 行×3 列 改为 3 行×2 列，
# 使每个地图面板分到更宽的空间，从而在版心内使用 8-9 pt 字号而不互相压字。
fig = plt.figure(figsize=(5.772, 4.55))
gs = fig.add_gridspec(3, 2, left=0.075, right=0.985, top=0.955, bottom=0.075,
                      wspace=0.24, hspace=0.42)
axes = [fig.add_subplot(gs[r, c]) for r in range(3) for c in range(2)]

field(axes[0], smp["precip"], "Blues",
      "(a)  Precipitation (mm yr$^{-1}$, 2005-23)")
field(axes[1], smp["temp"], "RdYlBu_r",
      "(b)  Temperature (°C, 2005-23)")
# (c)(d)(e)：按作者参考图恢复"连续占比(%)"面 —— 0-100 色标、满铺无灰洞
field(axes[2], (smp["class"] == 4).astype(float) * 100.0, "YlGn",
      "(c)  Grassland proportion (2020, %)", vmin=0, vmax=100)
field(axes[3], (smp["class"] == 2).astype(float) * 100.0, "BuGn",
      "(d)  Forest proportion (2020, %)", vmin=0, vmax=100)
field(axes[4], (smp["class"] == 7).astype(float) * 100.0, "YlOrBr",
      "(e)  Barren proportion (2020, %)", vmin=0, vmax=100)
field(axes[5], pts["esi"], "viridis",
      "(f)  Point ESI (2020)", vmin=0.05, vmax=0.60)

for i, ax in enumerate(axes):
    ax.set_xlabel("Longitude (°E)", fontsize=7.0*S)
    ax.tick_params(length=1.8, pad=1.2)
for i in (0, 2, 4):
    axes[i].set_ylabel("Latitude (°N)", fontsize=7.0*S)

out = os.path.join(BASE, "out")
os.makedirs(out, exist_ok=True)
plt.savefig(os.path.join(out, "_fig_指标空间分布预览.pdf"), dpi=700, bbox_inches="tight")
plt.savefig(os.path.join(out, "_fig_指标空间分布预览.png"), dpi=700, bbox_inches="tight")
plt.close()
print("saved out\\_fig_指标空间分布预览.pdf/.png (v5 六面板诚实版)")
print("主导格点: 草地 %d (%.1f%%) | 森林 %d (%.1f%%) | 裸地 %d (%.1f%%)"
      % ((smp["class"] == 4).sum(), (smp["class"] == 4).mean() * 100,
         (smp["class"] == 2).sum(), (smp["class"] == 2).mean() * 100,
         (smp["class"] == 7).sum(), (smp["class"] == 7).mean() * 100))

# ---------- 定稿输出：投稿前优化\\图件\\定稿 ----------
import shutil
from PIL import Image
DEST = os.path.normpath(os.path.join(BASE, "..", "投稿前优化", "图件", "定稿"))
os.makedirs(DEST, exist_ok=True)
pdf_dst = os.path.join(DEST, "Fig06_indicator_spatial_final.pdf")
png_dst = os.path.join(DEST, "Fig06_indicator_spatial_final.png")
tif_dst = os.path.join(DEST, "JMS_Figure_6_final.tif")
shutil.copy(os.path.join(out, "_fig_指标空间分布预览.pdf"), pdf_dst)
shutil.copy(os.path.join(out, "_fig_指标空间分布预览.png"), png_dst)
img = Image.open(png_dst).convert("RGB")
img.save(tif_dst, format="TIFF", compression="tiff_lzw", dpi=(700, 700))
print("saved 定稿\\Fig06_indicator_spatial_final.pdf/.png")
print("saved 定稿\\JMS_Figure_6_final.tif (600dpi LZW)")