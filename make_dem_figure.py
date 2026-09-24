# -*- coding: utf-8 -*-
"""祁连山地形图 v5（R10 方案③：删除左上角中国位置示意图 inset，作者决定）：
分层设色 + 省界 + 黄河。数据:Copernicus DEM 90m(高程) + Natural Earth(省界50m/黄河10m)。
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

# JMS 指南§6（R10 MEDIUM-2）：图内文字 Times New Roman 8–9 pt
import jms_style

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

hyps = LinearSegmentedColormap.from_list("hyps", [
    "#2f5d3f", "#6d9460", "#9fb56f", "#c9bd7f", "#b08a56",
    "#8a5f45", "#75604f", "#8d8780", "#e8e3da"])

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
fig, ax = plt.subplots(figsize=(10.6, 6.4))
ax.imshow(shade, cmap="Greys", extent=[lon_min, lon_max, lat_min, lat_max],
          vmin=0, vmax=1, aspect="auto", interpolation="bilinear", zorder=1)
im = ax.imshow(elev, cmap=hyps, extent=[lon_min, lon_max, lat_min, lat_max],
               alpha=0.62, vmin=800, vmax=5800, aspect="auto", interpolation="bilinear", zorder=2)
cb = fig.colorbar(im, ax=ax, shrink=0.78, pad=0.02)
cb.set_label("Elevation (m a.s.l.)", fontsize=9)
cb.ax.tick_params(labelsize=8)

ax.contour(X, Y, elev, levels=[2000, 3000, 4000, 5000], colors="#3b2f2f",
           linewidths=0.4, alpha=0.45, zorder=3)

# 省界(重点省加深, 其余淡灰)
BOLD = {"Gansu", "Qinghai"}
for nm, geoms in prov_geom.items():
    c = "#4a4a4a" if nm in BOLD else "#9a9a9a"
    lw = 1.0 if nm in BOLD else 0.6
    for gp in geoms:
        for pt in gp:
            xs = [a[0] for a in pt]; ys = [a[1] for a in pt]
            ax.plot(xs, ys, "-", color=c, lw=lw, alpha=0.8, zorder=4)

# 水系(OSM): 主要河流加粗, 支流细淡
MAIN = ["黑河", "疏勒河", "大通河", "湟水", "石羊河", "党河"]
for r in osm_rivers:
    xs = [p[0] for p in r["pts"]]; ys = [p[1] for p in r["pts"]]
    if len(xs) < 2:
        continue
    main = any(k in r["name"] for k in MAIN)
    ax.plot(xs, ys, "-", color="#2b6cb0", lw=1.0 if main else 0.55,
            alpha=0.85 if main else 0.5, zorder=4, solid_joinstyle="round")

# 省名
ax.text(98.0, 39.05, "Gansu", fontsize=8, color="#333333", ha="center", style="italic", zorder=6)
ax.text(95.9, 37.75, "Qinghai", fontsize=8, color="#333333", ha="center", style="italic", zorder=6)
ax.text(101.9, 36.55, "Huang He", fontsize=8, color="#2b6cb0", rotation=8, style="italic", zorder=6)
for txt, x, y, rot in [
    ("Heihe", 100.15, 39.25, -50), ("Shule", 97.5, 40.05, 0),
    ("Datong", 101.15, 37.6, 35), ("Huangshui", 101.75, 36.6, 15),
    ("Shiyang", 102.6, 38.25, 60), ("Danghe", 95.9, 39.4, 20),
]:
    ax.text(x, y, txt, fontsize=8, color="#1a5276", rotation=rot, style="italic",
            ha="center", zorder=6, alpha=0.92)

# 县域点
for n, (la, lo) in QILIAN.items():
    ax.plot(lo, la, "o", ms=4.5, mfc="#d73027", mec="white", mew=0.5, zorder=6)
    ax.annotate(n, (lo, la), fontsize=8, xytext=(4.0, 3.5), textcoords="offset points",
                zorder=7, color="#1a1a1a",
                bbox=dict(boxstyle="round,pad=0.1", fc="white", alpha=0.75, ec="none"))

ax.text(99.9, 38.95, "Qilian Mountains", fontsize=9, color="#2b2b2b",
        rotation=-14, ha="center", zorder=7, style="italic",
        bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.7, ec="none"))
# 公园标注（R4-m1）：移至右下空白区，去掉实心白底块与边框，仅留淡底保证可读
ax.text(102.30, 36.34, "Qilian Mountain National Park", fontsize=8, color="#1a5276",
        ha="center", va="center", zorder=7,
        bbox=dict(boxstyle="round,pad=0.18", fc="white", alpha=0.45, ec="none"))

# 比例尺
km = 111.32 * math.cos(math.radians(38.0))
bl = 100.0 / km
bx, by = 93.25, 36.22
ax.plot([bx, bx + bl], [by, by], "-", color="black", lw=2, zorder=8)
for b in (bx, bx + bl):
    ax.plot([b, b], [by - 0.08, by + 0.08], "-", color="black", lw=1.3, zorder=8)
ax.text(bx + bl / 2, by + 0.14, "100 km", ha="center", fontsize=8, zorder=8)

# 指北针
nx0, ny0 = 103.35, 40.7
ax.annotate("", xy=(nx0, ny0 + 0.26), xytext=(nx0, ny0 - 0.26),
            arrowprops=dict(arrowstyle="-|>", color="black", lw=1.5), zorder=8)
ax.text(nx0, ny0 + 0.4, "N", ha="center", fontsize=9, fontweight="bold", zorder=8)

# 经纬网
ax.set_xticks(np.arange(93, 105, 2)); ax.set_yticks(np.arange(36, 42, 2))
ax.set_xticklabels([f"{v}°E" for v in np.arange(93, 105, 2)], fontsize=8.5)
ax.set_yticklabels([f"{v}°N" for v in np.arange(36, 42, 2)], fontsize=8.5)
ax.set_xlim(lon_min, lon_max); ax.set_ylim(lat_min, lat_max)
ax.set_xlabel("Longitude", fontsize=9); ax.set_ylabel("Latitude", fontsize=9)
ax.grid(alpha=0.18, lw=0.4, color="white", linestyle="--")
for s in ("top", "right"):
    ax.spines[s].set_visible(False)

plt.savefig(os.path.join(FIG, "fig1_study_area.png"), dpi=600, bbox_inches="tight")
plt.close()
print("saved fig1_study_area.png")
print("高程 %.0f-%.0f m; 省份 %d 个; 水系 %d 段" % (
    np.nanmin(elev), np.nanmax(elev), len(prov_geom), len(osm_rivers)))