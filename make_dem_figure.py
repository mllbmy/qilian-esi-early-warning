# -*- coding: utf-8 -*-
"""祁连山地形图 v5（R10：删除中国位置示意图 inset；R12：作者决定不画公园边界，
图幅范围即分析窗口 93.5-103.5°E / 36.0-40.5°N，公园轮廓代码保留于 SHOW_PARK 开关）：
分层设色 + 省界 + 黄河。数据:Copernicus DEM 90m(高程) + Natural Earth(省界50m/湖泊10m) + OSM(河流/哈拉湖等)。
R24：湖面高程恒定→山体阴影全平、分层设色同色，青海湖/哈拉湖等呈"单色平斑"疑似渲染错误
——以水体多边形（NE 10m + OSM way，data/lakes_region.json）统一着水体蓝并标注两大湖名。
"""
import os
import math
import numpy as np
import shapefile
import rasterio
from rasterio.enums import Resampling
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Rectangle, Polygon as MplPolygon
import json as _json

# JMS 指南§6：图内文字 Times New Roman 8–9 pt
import jms_style

# R37（JMS 合规）：图内文字（含县名、经纬网、图例、比例尺）一律 Times New Roman，
# 原先的 Arial 覆盖已删除——Arial 违反 JMS 指南 §5.7「Words in figures must be in
# Times New Roman」，是本轮图件审计唯一字体不达标的图。
jms_style.check_fonts()

# 路径自解析：仓库克隆/解压到任意目录均可运行
BASE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(BASE, "figures")
DEM = os.path.join(BASE, "data", "cop90")
NE = os.path.join(BASE, "data", "ne")

QILIAN = {
    "Tianzhu": (37.20, 102.86), "Sunan": (38.84, 99.62), "Subei": (39.51, 97.85),
    "Aksai": (39.34, 94.34), "Minle": (38.43, 100.81), "Shandan": (38.78, 101.09),
    "Menyuan": (37.38, 101.62), "Qilian": (38.18, 100.24), "Gangcha": (37.33, 100.14),
    "Delingha": (37.37, 97.36), "Tianjun": (37.30, 99.02),
}
# 主图范围
lon_min, lon_max, lat_min, lat_max = 93.0, 104.0, 36.0, 41.0
TILE = 600
SHOW_PARK = True           # R14（作者决定）：画出数字化公园轮廓；图内不再重复写公园名（图例已给出）

# ---------- 1. 读 Copernicus DEM, 拼接 ----------
rows = []
for la in range(40, 35, -1):
    col = []
    for lo in range(93, 104):
        p = os.path.join(DEM, f"N{la:02d}_E{lo:03d}.tif")
        with rasterio.open(p) as ds:
            col.append(ds.read(1, out_shape=(TILE, TILE), resampling=Resampling.average).astype(np.float64))
    rows.append(np.concatenate(col, axis=1))
elev = np.concatenate(rows, axis=0)
elev = np.where(elev < -1000, np.nan, elev)
ny, nx = elev.shape
lon = np.linspace(lon_min, lon_max, nx)
lat = np.linspace(lat_max, lat_min, ny)
X, Y = np.meshgrid(lon, lat)

# hillshade
dy, dx = np.gradient(elev)
slope = np.pi / 2 - np.arctan(np.sqrt(dx * dx + dy * dy))
aspect = np.arctan2(-dx, dy)
az, alt = math.radians(315), math.radians(45)
shade = np.clip(np.sin(alt) * np.sin(slope) + np.cos(alt) * np.cos(slope) * np.cos(az - aspect), 0, 1)

# R15：学术风低饱和大地色分层设色（参考 JMS 已发表研究区图的灰调 earth-tone）
hyps = LinearSegmentedColormap.from_list("hyps", [
    "#4f7757", "#7d9c6d", "#aab87e", "#cfc493", "#d3b47e",
    "#b98f5e", "#966f4f", "#7c6757", "#96908a", "#ddd9d2"])

# ---------- 2. 读省界(50m admin_1, 中国) ----------
def parts_of(shape):
    pts = shape.points
    pr = list(shape.parts) + [len(pts)]
    return [pts[pr[i]:pr[i + 1]] for i in range(len(pr) - 1)]

prov = shapefile.Reader(os.path.join(NE, "ne_50m_admin_1_states_provinces.shp"))
pnames = [f[0] for f in prov.fields[1:]]
prov_geom = {}
for sh, rec in zip(prov.shapes(), prov.records()):
    if rec[pnames.index("adm0_a3")] != "CHN":
        continue
    nm = rec[pnames.index("name")]
    prov_geom.setdefault(nm, []).append(parts_of(sh))

# ---------- 3. 读祁连山水系(OSM Overpass) ----------
import json as _json
osm_rivers = _json.load(open(os.path.join(BASE, "data", "_osm_key_rivers.json"), encoding="utf-8"))

# ---------- 5. 绘图 ----------
# JMS §5.7：画布宽 = 印刷插入宽 16.00 cm（原 6.6 in = 16.76 cm 与投稿宽度不符）
fig, ax = jms_style.subplots(height_cm=10.06)

# R37 体积：底图改为**一张不透明 RGB 总图**（晕渲 + 分层设色按原 alpha=0.62 预合成）。
# 原来两层 RGBA imshow 会在 PDF 里各存一份带 SMask 的图像（600 dpi 下 8.6 MB）；
# 预合成后矢量文字/线划不变，底图可整体压成 300 dpi JPEG（见 jms_style.shrink_pdf）。
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize

_ENORM = Normalize(800, 5800)


def _box(a, k=4):
    """k×k 均值降采样（底图 0.002° 精度对 300 dpi 印刷过剩 3–4 倍）。"""
    ny, nx = a.shape[0] // k * k, a.shape[1] // k * k
    return a[:ny, :nx].reshape(ny // k, k, nx // k, k).mean(axis=(1, 3))


_elev_s = _box(elev)
_shade_s = _box(shade)
_rgbe = hyps(_ENORM(np.nan_to_num(_elev_s, nan=800.0)))[..., :3]
_grey = plt.get_cmap("Greys")(np.clip(_shade_s, 0, 1))[..., :3]
_BASE = 0.62 * _rgbe + 0.38 * _grey
_BASE[~np.isfinite(_elev_s)] = _grey[~np.isfinite(_elev_s)]      # 越界瓦片只留晕渲
ax.imshow(_BASE, extent=[lon_min, lon_max, lat_min, lat_max],
          aspect="auto", interpolation="bilinear", zorder=2)
_SM = ScalarMappable(norm=_ENORM, cmap=hyps)
_SM.set_array([])
cb = fig.colorbar(_SM, ax=ax, shrink=0.78, pad=0.02)
cb.set_label("Elevation (m a.s.l.)", fontsize=9)
cb.ax.tick_params(labelsize=8)

# 等高线在降采样网格上画（300 dpi 印刷下与全分辨率无可见差别，矢量节点数降 16 倍）
_xs = np.linspace(lon_min, lon_max, _elev_s.shape[1])
_ys = np.linspace(lat_max, lat_min, _elev_s.shape[0])
ax.contour(*np.meshgrid(_xs, _ys), np.nan_to_num(_elev_s, nan=800.0),
           levels=[2000, 3000, 4000, 5000], colors="#3b2f2f",
           linewidths=0.4, alpha=0.45, zorder=3)

# 省界(重点省加深, 其余淡灰)
# R37 体积：只把**落在图幅内**的折线节点写进 PDF（否则全国 31 省界面的全部节点都进文件）
_PAD = 0.4


def _clip_runs(xs, ys):
    """按图幅窗口裁折线：返回窗口内的连续段（含 _PAD 度余量）。"""
    runs, cur = [], []
    for x, y in zip(xs, ys):
        inside = (lon_min - _PAD <= x <= lon_max + _PAD
                  and lat_min - _PAD <= y <= lat_max + _PAD)
        if inside:
            cur.append((x, y))
        else:
            if len(cur) > 1:
                runs.append(cur)
            cur = []
    if len(cur) > 1:
        runs.append(cur)
    return runs


BOLD = {"Gansu", "Qinghai"}
for nm, geoms in prov_geom.items():
    c = "#4a4a4a" if nm in BOLD else "#9a9a9a"
    lw = 1.0 if nm in BOLD else 0.6
    for gp in geoms:
        for pt in gp:
            for run in _clip_runs([a[0] for a in pt], [a[1] for a in pt]):
                ax.plot([p[0] for p in run], [p[1] for p in run], "-",
                        color=c, lw=lw, alpha=0.8, zorder=4)

# 水系(OSM): 主要河流加粗, 支流细淡
MAIN = ["黑河", "疏勒河", "大通河", "湟水", "石羊河", "党河"]
for r in osm_rivers:
    xs = [p[0] for p in r["pts"]]; ys = [p[1] for p in r["pts"]]
    if len(xs) < 2:
        continue
    main = any(k in r["name"] for k in MAIN)
    for run in _clip_runs(xs, ys):     # 同上：只写图幅内的河段
        ax.plot([p[0] for p in run], [p[1] for p in run], "-",
                color="#33679e", lw=1.0 if main else 0.55,
                alpha=0.85 if main else 0.5, zorder=4, solid_joinstyle="round")

# 湖泊(R24): NE 10m 面多边形(青海湖/小柴旦湖) + OSM way(哈拉湖/苏干湖/尕海/更尕海)
# 湖面 DEM 高程恒定→hillshade 与分层设色全平, 不覆盖会呈单色平斑
C_LAKE = "#6f9fc6"                                   # 水体蓝(与河流 #33679e 同族、略浅)
lakes = _json.load(open(os.path.join(BASE, "data", "lakes_region.json"), encoding="utf-8"))["lakes"]
for L in lakes:
    xs = [p[0] for p in L["pts"]]; ys = [p[1] for p in L["pts"]]
    ax.fill(xs, ys, color=C_LAKE, alpha=0.88, ec="#2a5a8a", lw=0.6, zorder=4)

# 省名/河名（R21：全部提到 zorder 12 与地标同层——红虚线 zorder 6 且绘制在后，同级会被压）
# R25（作者决定）：全部注记去除白色底框；R26（作者决定）：注记改白色（黑字在深色地形上看不清）
ax.text(97.40, 39.08, "Gansu", fontsize=8, color="white", ha="center", zorder=12)  # R22：左移，与 Sunan 县名错开
ax.text(95.9, 37.75, "Qinghai", fontsize=8, color="white", ha="center", zorder=12)
ax.text(102.35, 36.55, "Huang He", fontsize=8, color="white", rotation=8, zorder=12,
        ha="center")
for txt, x, y, rot in [
    ("Heihe", 100.60, 39.52, -50), ("Shule", 96.85, 39.82, 0), ("Danghe", 95.55, 39.32, 20),
    ("Qinghai Lake", 100.20, 36.89, 0), ("Hala Lake", 97.60, 38.03, 0),   # R24：两大湖名（Hala 标注置于湖下方，不压湖面）
]:
    ax.text(x, y, txt, fontsize=8, color="white", rotation=rot,
            ha="center", zorder=12)

# 县域点（R13：画布缩到印刷尺寸后逐个微调注记偏移，避免相互压字/出框）
SPECIAL = {"Sunan": (-40.0, 2.0), "Tianzhu": (-34.0, -9.0), "Aksai": (-10.0, -11.0),
           "Qilian": (-38.0, -3.0), "Minle": (5.0, 5.0), "Shandan": (5.0, 5.5)}  # R22：县名两两错开，Minle/Shandan 上移、Qilian 放左侧
for n, (la, lo) in QILIAN.items():
    ax.plot(lo, la, "o", ms=4.5, mfc="#d73027", mec="white", mew=0.5, zorder=12)  # R19：地标点置顶，不被虚线/注记压住
    _dx, _dy = SPECIAL.get(n, (4.0, 3.5))
    ax.annotate(n, (lo, la), fontsize=8, xytext=(_dx, _dy), textcoords="offset points",
                zorder=12, color="white",   # R26：县名改白色
                arrowprops=dict(arrowstyle="-", color="white", lw=0.9,  # R26：引线同步白色
                                shrinkA=1, shrinkB=3))                     # R25：去白底框

ax.text(100.12, 39.06, "Qilian Mountains", fontsize=9, color="white",  # R19：上移，避开 Sunan 点；R26：改白色
        rotation=-14, ha="center", zorder=12)  # R20：山名同地标层；R25：去白底框
# 公园标注（R11）：颜色与公园轮廓统一为蓝绿；半透明底加强，避开 Huang He 注记
if not SHOW_PARK:   # R14：画出轮廓时名称由图例给出，避免与图例挤在一行
    ax.text(100.85, 36.17, "Qilian Mountain National Park", fontsize=8, color="#1a5276",
            ha="center", va="center", zorder=8)


# ---------- 4b. 分析窗口（R12：图幅＝分析窗口，因此不画虚线框，也不需要图例）----------
if SHOW_PARK:
    _pk = _json.load(open(os.path.join(BASE, "data", "qmn_park_digitized.geojson"), encoding="utf-8"))
    _exts = []
    for _f in _pk["features"]:
        _g = _f["geometry"]
        _polys = [_g["coordinates"]] if _g["type"] == "Polygon" else _g["coordinates"]
        for _poly in _polys:
            _e = _poly[0]
            _a = sum(_e[i][0] * _e[i + 1][1] - _e[i + 1][0] * _e[i][1] for i in range(len(_e) - 1)) / 2.0
            if abs(_a) >= 0.003:                 # 去掉 <0.003 deg² 的碎屑
                _exts.append(_e)
    print("公园轮廓部件 %d 个" % len(_exts))
    for _e in _exts:
        _xs = [q[0] for q in _e]; _ys = [q[1] for q in _e]
        ax.plot(_xs, _ys, color="#c0392b", lw=0.75, ls=(0, (4, 2)), zorder=6)  # R16：砖红虚线；R17：细一档
    ax.plot([], [], color="#c0392b", lw=0.95, ls=(0, (4, 2)),         # 图例只加一条（避免每块多边形各占一行）
            label="National park boundary (digitised, schematic)")    # R15：图内不写公园全名，全名留题注
    ax.legend(loc="lower left", fontsize=8, framealpha=0.88, borderpad=0.5)

# 研究区标注（图幅即范围，用一行文字点明；R18：下移，避免贴/出上边框；R25：去白底框；R26：改白色）
# Unicode 度数符号（不用 mathtext 上标：$^\circ$ 会被压到 0.7×8 = 5.6 pt）
ax.text(99.30, 40.25, "Study area 36.0-40.5\u00b0N, 93.5-103.5\u00b0E", fontsize=8,
        color="white", ha="center", zorder=8)

# 比例尺（R16：黑白相间分段式，学术风标准画法；标注 0 / 100 km 在条下方，参考 JMS 已发表图）
import matplotlib.patheffects as _pe
km = 111.32 * math.cos(math.radians(38.0))
bl = 100.0 / km
bx, by = 94.05, 40.10
_h = 0.045                                        # 条高（°）
for _i in range(2):                               # 两段：黑 | 白
    _x0 = bx + _i * bl / 2
    ax.add_patch(MplPolygon([(_x0, by), (_x0 + bl / 2, by), (_x0 + bl / 2, by + _h), (_x0, by + _h)],
                            closed=True, fc=("black" if _i == 0 else "white"),
                            ec="black", lw=0.9, zorder=8))
for _x, _t, _ha in ((bx, "0", "left"), (bx + bl, "100 km", "right")):
    ax.text(_x, by - 0.045, _t, ha=_ha, va="top", fontsize=8, zorder=8,
            path_effects=[_pe.withStroke(linewidth=1.8, foreground="white", alpha=0.85)])

# R16b：先锁图幅再设经纬比例——罗盘用轴分数坐标，draw 取轴框时数据范围必须是最终窗口
# （否则河流/省界 autoscale 的大范围会算错轴框，圆环变椭圆）
VX0, VX1, VY0, VY1 = 93.5, 103.5, 36.0, 40.5
ax.set_xlim(VX0, VX1); ax.set_ylim(VY0, VY1)
ax.set_aspect(1.0 / math.cos(math.radians(38.0)))   # 按 38°N 真实经纬比例，消除纵向拉伸

# 指北针（R16b：按 JMS 已发表图（s11629-013-2558-z Fig.1）样式——圆环 + 内置四角星，
# 黑白相间刻面 + 中心饰点；轴分数坐标绘制，先 draw 使 aspect 生效再换算横纵比，不变形不出框）
fig.canvas.draw()
_pos = ax.get_position()
_kx = _pos.height * fig.get_figheight() / (_pos.width * fig.get_figwidth())  # y 分数→x 分数视觉等长换算
_cx, _cy = 0.925, 0.820          # 罗盘中心（轴分数坐标，框内右上）
_r = 0.075                       # 圆环半径（y 分数）
_hn, _hs = 0.058, 0.046          # N 针 / S 针半高（y 分数，收进圆环内）
_ex = 0.046 * _kx                # E/W 针半长（x 分数，视觉与 S 等长）
_w = 0.0105                      # 针腰半宽（x 分数）
from matplotlib.patches import Ellipse as _Ellipse
ax.add_patch(_Ellipse((_cx, _cy), 2 * _r * _kx, 2 * _r, transform=ax.transAxes,   # 圆环底（x 向按 _kx 补偿，视觉为正圆）
                      fc="white", alpha=0.72, ec="black", lw=1.0, zorder=9))
def _tri(p1, p2, p3, fc):
    ax.add_patch(MplPolygon([p1, p2, p3], closed=True, transform=ax.transAxes,
                            fc=fc, ec="black", lw=0.6, zorder=10))
_tri((_cx, _cy + _hn), (_cx - _w, _cy), (_cx, _cy), "black")           # N 左黑
_tri((_cx, _cy + _hn), (_cx + _w, _cy), (_cx, _cy), "white")           # N 右白
_tri((_cx, _cy - _hs), (_cx - _w * 0.8, _cy), (_cx, _cy), "white")     # S 左白
_tri((_cx, _cy - _hs), (_cx + _w * 0.8, _cy), (_cx, _cy), "black")     # S 右黑
_tri((_cx - _ex, _cy), (_cx, _cy + _w), (_cx, _cy - _w), "black")      # W 上黑
_tri((_cx - _ex, _cy), (_cx, _cy - _w), (_cx, _cy + _w), "white")      # W 下白
_tri((_cx + _ex, _cy), (_cx, _cy + _w), (_cx, _cy - _w), "white")      # E 上白
_tri((_cx + _ex, _cy), (_cx, _cy - _w), (_cx, _cy + _w), "black")      # E 下黑
ax.add_patch(_Ellipse((_cx, _cy), 0.012 * _kx, 0.012, transform=ax.transAxes,     # 中心饰点（正圆）
                      fc="black", ec="white", lw=0.5, zorder=11))
ax.text(_cx, _cy + _r + 0.013, "N", transform=ax.transAxes, ha="center", va="bottom",
        fontsize=9, fontweight="bold", zorder=11,
        path_effects=[_pe.withStroke(linewidth=1.8, foreground="white", alpha=0.85)])

# 经纬网（R12；R15：加密至 0.5° 一级，整度线粗、半度线细；窗口范围已在上方锁定）
for _v in np.arange(VY0 + 0.5, VY1, 0.5):
    _int = abs(_v - round(_v)) < 1e-9
    ax.axhline(_v, color="white", ls="--", lw=0.9 if _int else 0.25,
               alpha=0.32 if _int else 0.11, zorder=3)   # R16：整度粗、半度细；R17：整体再变浅一档
for _v in np.arange(VX0 + 0.5, VX1, 0.5):
    _int = abs(_v - round(_v)) < 1e-9
    ax.axvline(_v, color="white", ls="--", lw=0.9 if _int else 0.25,
               alpha=0.32 if _int else 0.11, zorder=3)
ax.set_xticks(np.arange(94, 104, 1))
ax.set_xticklabels([f"{v}°E" for v in np.arange(94, 104, 1)], fontsize=8)
_lat_t = np.arange(36.5, 40.01, 0.5)     # 36.5–40.0 每 0.5° 一条标注
ax.set_yticks(_lat_t)
ax.set_yticklabels([f"{v:g}°N" for v in _lat_t], fontsize=8)
ax.tick_params(which="both", direction="out", length=3, width=0.6,
               top=True, right=True, labeltop=False, labelright=False)
ax.set_xlim(VX0, VX1); ax.set_ylim(VY0, VY1)
ax.set_xlabel("Longitude", fontsize=9); ax.set_ylabel("Latitude", fontsize=9)
for s in ("top", "right", "left", "bottom"):   # R12：四边全显，边框即研究区边界
    ax.spines[s].set_visible(True); ax.spines[s].set_linewidth(1.5); ax.spines[s].set_color("#1a1a1a")

# R37：PDF 严格保持 16.00 cm 画布（不传 bbox_inches），PNG 600 dpi 预览
# PDF：底图 300 dpi（16 cm 宽印刷足够），再用 shrink_pdf 转 JPEG 近无损压缩；
# 文字/线划仍是矢量（校验见 figures/JMS_figure_audit.tsv）
jms_style.save(fig, "fig1_study_area", outdir=FIG, png_dpi=300,
               pdf_dpi=300, raster_dpi=300, raster_quality=90)
_PREVIEW_OUT = os.path.join(BASE, "out", "fig1_preview.png")   # 仓库内相对落点（out/ 已 Git-ignore）
os.makedirs(os.path.dirname(_PREVIEW_OUT), exist_ok=True)
plt.savefig(_PREVIEW_OUT, dpi=140, bbox_inches="tight")
plt.close()
print("saved fig1_study_area.png")
print("高程 %.0f-%.0f m; 省份 %d 个; 水系 %d 段" % (
    np.nanmin(elev), np.nanmax(elev), len(prov_geom), len(osm_rivers)))