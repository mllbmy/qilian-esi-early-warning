# -*- coding: utf-8 -*-
"""Fig. 7 指标/ESI 空间分布图 —— 本轮（R37）新增的**可复现生成脚本**。

背景（仓库缺陷）：manuscript.tex 引用的 figures/fig_spatial_maps.pdf 原先在仓库内
**没有任何生成脚本**（README §9.1 item C），只能靠外部一次性步骤产出，且画布 17.29 cm、
图内字号 5.25–7.50 pt，不满足 JMS 指南（16 cm / 8–9 pt / Times New Roman）。
本脚本把该图纳入可复跑主线，并把版式改为 3 行 × 2 列（每幅地图 6.5 cm 宽），
使 8 pt 的经纬度刻度、色标刻度、县名与面板标题可以并存而不压字。

数据与算法（与仓库既有指标空间图一致，未改任何数值）：
  spatial_samples.csv -> precip / temp / class(CLCD 主导类型)
  spatial_esi_points.csv -> esi
  连续场：scipy.griddata(linear) 插值到 500×220 网格（10–103.5°E 等），
          边界外空洞用 nearest 回填（与 make_fig_indicator_maps.py 同法）；
  底图：Copernicus DEM 90 m 山体阴影（315°/45°）+ 数字化国家公园红线 + 11 县点位；
  色标：与改前图逐色标一致——(a) 100–400 mm yr⁻¹ (b) −5–5 °C (c)(d)(e) 0–100 %
        (f) 0.2–0.6（点尺度 ESI）。

版式取舍（记录在 figures/JMS_figure_audit.tsv 的 notes 列）：
  * 6 幅地图由 2×3 改为 3×2：宽度不变（16 cm），每幅地图从 4.3 cm 增到 6.5 cm，
    字号从 6.2–7.5 pt 提到 8 pt 后仍不压字；
  * 经纬度轴标题只在最左列/最下行出现一次（原为 6 幅各标一次），刻度数字全保留；
  * 县名保留全部 11 个，换行/偏移重排以避免互相覆盖。
"""
import json
import math
import os
import sys

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.text import Text as _MplText
from scipy.interpolate import griddata
import rasterio
from rasterio.enums import Resampling

import jms_style  # JMS 指南 §6：画布 16.00 cm + Times New Roman 8–9 pt

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(BASE, "figures")

smp = pd.read_csv(os.path.join(BASE, "data", "spatial_samples.csv"))
pts = pd.read_csv(os.path.join(BASE, "data", "spatial_esi_points.csv"))

QILIAN = {"Tianzhu": (37.20, 102.86), "Sunan": (38.84, 99.62), "Subei": (39.51, 97.85),
          "Aksai": (39.34, 94.34), "Minle": (38.43, 100.81), "Shandan": (38.78, 101.09),
          "Menyuan": (37.38, 101.62), "Qilian": (38.18, 100.24), "Gangcha": (37.33, 100.14),
          "Delingha": (37.37, 97.36), "Tianjun": (37.30, 99.02)}
# 注记偏移（points）：东段 Qilian/Minle/Shandan/Gangcha/Menyuan/Tianzhu 互挤，四向散开
OFF = {"Aksai": (5, 6), "Subei": (4, 6), "Sunan": (-6, 5), "Qilian": (-7, 5),
       "Minle": (-1, 12), "Shandan": (7, -3), "Gangcha": (-7, 6), "Menyuan": (-6, -6),
       "Tianzhu": (-7, 8), "Delingha": (-5, -8), "Tianjun": (2, -13)}
ALIGN = {"Aksai": "left", "Subei": "left", "Sunan": "right", "Qilian": "right",
         "Minle": "center", "Shandan": "left", "Gangcha": "right", "Menyuan": "right",
         "Tianzhu": "right", "Delingha": "right", "Tianjun": "left"}

# ---------- 地形底图（Copernicus DEM 90 m，与 make_dem_figure.py 同源同法）----------
DEM = os.path.join(BASE, "data", "cop90")
TILE = 300
_rows = []
for la in range(40, 35, -1):
    _col = []
    for lo in range(93, 104):
        with rasterio.open(os.path.join(DEM, "N%02d_E%03d.tif" % (la, lo))) as ds:
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
BASE_EXT = [93, 104, 36, 41]

# ---------- 国家公园红线（数字化，示意）----------
_gj = json.load(open(os.path.join(BASE, "data", "qmn_park_digitized.geojson"),
                     encoding="utf-8"))
RINGS = []
for _f in _gj["features"]:
    _g = _f["geometry"]
    _polys = _g["coordinates"] if _g["type"] == "MultiPolygon" else [_g["coordinates"]]
    for _poly in _polys:
        RINGS.append(np.array(_poly[0]))

PTS = np.column_stack([smp["lon"], smp["lat"]])
XI, YI = np.meshgrid(np.linspace(93.5, 103.5, 500), np.linspace(36.0, 40.5, 220))
XMIN, XMAX, YMIN, YMAX = 93.5, 103.5, 36.0, 40.5


def interp(v):
    zi = griddata(PTS, v, (XI, YI), method="linear")
    zn = griddata(PTS, v, (XI, YI), method="nearest")
    return np.where(np.isnan(zi), zn, zi)


def draw_base(ax):
    for ring in RINGS:
        ax.plot(ring[:, 0], ring[:, 1], color="#c0392b", lw=0.55, ls=(0, (3, 1.6)),
                zorder=5)
    for n, (la, lo) in QILIAN.items():
        ax.plot(lo, la, "k.", ms=2.4, zorder=6)
        ax.annotate(n, (lo, la), fontsize=8, xytext=OFF.get(n, (4, 4)),
                    textcoords="offset points", ha=ALIGN.get(n, "left"),
                    va="center", zorder=7,
                    bbox=dict(boxstyle="round,pad=0.10", fc="white", ec="none",
                              alpha=0.62),
                    arrowprops=dict(arrowstyle="-", color="#444444", lw=0.4,
                                    shrinkA=1.5, shrinkB=2.0, zorder=6))
    ax.set_xlim(XMIN, XMAX)
    ax.set_ylim(YMIN, YMAX)
    ax.set_box_aspect(0.55)


def _shade_on_panel_grid(ny, nx):
    """把地形晕渲重采样到面板网格（供与插值场**预合成**为一张不透明 RGB 底图）。

    原来分两层 imshow（晕渲 + alpha=0.8 的场）会让 PDF 存两份 RGBA 图 + SMask；
    预合成后仍是一张 300 dpi JPEG，肉眼效果与 alpha 叠加一致，但体积降到几分之一。
    """
    from PIL import Image as _Im
    _h, _w = SHADE.shape
    c0 = int(round((XMIN - BASE_EXT[0]) / (BASE_EXT[1] - BASE_EXT[0]) * _w))
    c1 = int(round((XMAX - BASE_EXT[0]) / (BASE_EXT[1] - BASE_EXT[0]) * _w))
    r0 = int(round((BASE_EXT[3] - YMAX) / (BASE_EXT[3] - BASE_EXT[2]) * _h))
    r1 = int(round((BASE_EXT[3] - YMIN) / (BASE_EXT[3] - BASE_EXT[2]) * _h))
    _crop = np.clip(SHADE[r0:r1, c0:c1], 0, 1)
    _u8 = (_crop * 255).astype(np.uint8)
    _res = np.asarray(_Im.fromarray(_u8).resize((nx, ny), _Im.BILINEAR))
    return _res.astype(np.float64) / 255.0


def field(ax, v, cmap, title, vmin, vmax, ticks):
    """连续场面板：晕渲底 + 插值场（预合成为不透明 RGB）+ 公园红线 + 县点/县名 + 色标。"""
    from matplotlib.cm import ScalarMappable
    from matplotlib.colors import Normalize
    zi = interp(v)
    _norm = Normalize(vmin, vmax)
    _cmap = plt.get_cmap(cmap)
    _fg = _cmap(_norm(np.clip(zi, vmin, vmax)))[..., :3]
    _bg = plt.get_cmap("Greys")(_shade_on_panel_grid(*zi.shape))[..., :3]
    _rgb = 0.80 * _fg + 0.20 * _bg
    ax.imshow(_rgb, extent=[XMIN, XMAX, YMIN, YMAX], origin="lower",
              interpolation="bilinear", aspect="auto", zorder=1)
    draw_base(ax)
    _sm = ScalarMappable(norm=_norm, cmap=_cmap)
    _sm.set_array([])
    cb = fig.colorbar(_sm, ax=ax, fraction=0.046, pad=0.020, aspect=13, ticks=ticks)
    cb.ax.tick_params(labelsize=8, length=1.8, pad=1.5)
    cb.outline.set_linewidth(0.4)
    ax.set_title(title, fontsize=8.5, pad=3.0)


fig = jms_style.figure(12.4, layout="constrained")
gs = fig.add_gridspec(3, 2, wspace=0.10, hspace=0.22)
axes = [fig.add_subplot(gs[r, c]) for r in range(3) for c in range(2)]

field(axes[0], smp["precip"], "Blues",
      "(a)  Precipitation (mm yr\u207b\u00b9, 2005-23)", 100, 400, [100, 200, 300, 400])
field(axes[1], smp["temp"], "RdYlBu_r",
      "(b)  Temperature (\u00b0C, 2005-23)", -5, 5, [-5, 0, 5])
field(axes[2], (smp["class"] == 4).astype(float) * 100.0, "YlGn",
      "(c)  Grassland proportion (2020, %)", 0, 100, [0, 20, 40, 60, 80, 100])
field(axes[3], (smp["class"] == 2).astype(float) * 100.0, "BuGn",
      "(d)  Forest proportion (2020, %)", 0, 100, [0, 20, 40, 60, 80, 100])
field(axes[4], (smp["class"] == 7).astype(float) * 100.0, "YlOrBr",
      "(e)  Barren proportion (2020, %)", 0, 100, [0, 20, 40, 60, 80, 100])
field(axes[5], pts["esi"], "viridis",
      "(f)  Point ESI (2020)", 0.2, 0.6, [0.2, 0.4, 0.6])

for i, ax in enumerate(axes):
    ax.set_xticks([94, 96, 98, 100, 102])
    ax.set_yticks([36, 37, 38, 39, 40])
    ax.tick_params(labelsize=8, length=2.0, pad=1.5)
    ax.set_xticklabels(["94", "96", "98", "100", "102"] if i >= 4 else [""] * 5)
    ax.set_yticklabels(["36", "37", "38", "39", "40"] if i % 2 == 0 else [""] * 5)
    if i >= 4:
        ax.set_xlabel("Longitude (\u00b0E)", fontsize=9, labelpad=2)
    if i % 2 == 0:
        ax.set_ylabel("Latitude (\u00b0N)", fontsize=9, labelpad=2)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#8a97a5")
        ax.spines[s].set_linewidth(0.5)

# ---------------- 落盘前自检：县名之间、县名与边框不得重叠 ----------------
fig.canvas.draw()
_r = fig.canvas.get_renderer()
_bad = []
for ax in axes:
    _ab = ax.get_window_extent(renderer=_r)
    _boxes = []
    for _t in ax.texts:
        # Annotation.get_window_extent 会把引导线算进去 -> 只量文字本身
        _b = _MplText.get_window_extent(_t, renderer=_r)
        _boxes.append((_t.get_text(), _b))
        if _b.x0 < _ab.x0 - 1 or _b.x1 > _ab.x1 + 1:
            _bad.append("%s 越出面板左右界" % _t.get_text())
    for _i in range(len(_boxes)):
        for _j in range(_i + 1, len(_boxes)):
            _a, _b2 = _boxes[_i][1], _boxes[_j][1]
            if (_a.x0 < _b2.x1 and _b2.x0 < _a.x1
                    and _a.y0 < _b2.y1 and _b2.y0 < _a.y1):
                _bad.append("%s vs %s 重叠" % (_boxes[_i][0], _boxes[_j][0]))
if _bad:
    for _b in sorted(set(_bad)):
        print("[LABEL]", _b, file=sys.stderr)
    raise SystemExit("Fig.7 自检失败：县名重叠/出界 %d 处" % len(set(_bad)))

jms_style.save(fig, "fig_spatial_maps", outdir=FIG, png_dpi=300,
               pdf_dpi=300, raster_dpi=300, raster_quality=90)
plt.close(fig)
print("[OK] figures/fig_spatial_maps.pdf/.png (16.00 cm, 3\u00d72 \u9762\u677f, 8\u20139 pt TNR)")
