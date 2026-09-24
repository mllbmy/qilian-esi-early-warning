# -*- coding: utf-8 -*-
"""步骤2：县域 ESI + 空间点采样 GeoDetector 因子探测
1) 县域尺度：11 县域质心窗口 CLCD 土地覆被 + 县域气候 → 县域 ESI (11x19)
2) 空间 GeoDetector：祁连山区域 ~200 格网点（2020）→ 因子探测 q 统计量
"""
import os
import sys, os
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import from_bounds
from pyproj import Transformer
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "eco_security"))
from eco_security import minmax_normalize, entropy_weights, combined_weights, esi_series, geodetector_q

# 路径自解析：仓库克隆/解压到任意目录均可运行
BASE = os.path.dirname(os.path.abspath(__file__))
LC_DIR = os.environ.get("QILIAN_LC_DATA", os.path.join(os.path.dirname(os.path.abspath(__file__)), "_raw", "lc_data"))
CRU_DIR = os.environ.get("QILIAN_CRU_DATA", os.path.join(os.path.dirname(os.path.abspath(__file__)), "_raw", "cru_data"))
LAT0, LAT1, LON0, LON1 = 36.0, 40.5, 93.5, 103.5

QILIAN_COUNTIES = {
    "天祝": (37.20, 102.86), "肃南": (38.84, 99.62), "肃北": (39.51, 97.85),
    "阿克塞": (39.34, 94.34), "民乐": (38.43, 100.81), "山丹": (38.78, 101.09),
    "门源": (37.38, 101.62), "祁连": (38.18, 100.24), "刚察": (37.33, 100.14),
    "德令哈": (37.37, 97.36), "天峻": (37.30, 99.02),
}

def open_clcd(year):
    p = os.path.join(LC_DIR, f"CLCD_v01_{year}_albert.tif")
    src = rasterio.open(p)
    return src

def class_pct_around(src, lat, lon, half=0.1):
    """质心 ±0.1° 窗口内的类别占比（近似县域土地覆被）"""
    tf = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
    x0, y0 = tf.transform(lon - half, lat - half)
    x1, y1 = tf.transform(lon + half, lat + half)
    win = from_bounds(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1), src.transform)
    arr = src.read(1, window=win)
    vals, counts = np.unique(arr[arr != 0], return_counts=True)
    d = {int(v): int(c) for v, c in zip(vals, counts)}
    tot = sum(d.values())
    def pct(c):
        return d.get(c, 0) * 100 / tot if tot else 0.0
    return pct(2), pct(4), pct(5), pct(7), pct(1)  # forest, grass, water, barren, crop

cli = pd.read_csv(os.path.join(BASE, "data", "qilian_climate.csv"))
YEARS = list(range(2005, 2024))

# ---------- 1) 县域 ESI（11 县域 × 19 年）----------
src2020 = open_clcd(2020)
county_rows = []
for name, (lat, lon) in QILIAN_COUNTIES.items():
    f, g, w, b, c = class_pct_around(src2020, lat, lon)
    county_rows.append({"unit": name, "forest_pct": f, "grass_pct": g, "water_pct": w, "barren_pct": b, "crop_pct": c})
cdf = pd.DataFrame(county_rows)
cdf.to_csv(os.path.join(BASE, "data", "qilian_county_landcover.csv"), index=False, encoding="utf-8-sig")
print("县域土地覆被(2020 质心窗口):")
print(cdf.round(2).to_string(index=False))

# 县域 ESI（用 2020 土地覆被 + 县域多年平均气候构造静态空间 ESI 对比）
cnt_cli = cli[cli.unit != "区域(祁连山盒)"].groupby("unit")[["precip_mm", "temp_c"]].mean()
m = cdf.set_index("unit").join(cnt_cli).dropna()
X = m[["precip_mm", "temp_c", "forest_pct", "grass_pct", "water_pct"]].values
dirs = [+1, +1, +1, +1, +1]
barren_neg = (100 - m["forest_pct"] - m["grass_pct"] - m["water_pct"] - m["crop_pct"]).values
X2 = np.column_stack([X, barren_neg])
dirs2 = dirs + [-1]
Xn = minmax_normalize(X2, dirs2)
w_ent = entropy_weights(Xn)
w_ahp = np.ones(X2.shape[1]) / X2.shape[1]
w = combined_weights(w_ahp, w_ent, 0.4)
esi_c = esi_series(Xn, w)
county_esi = pd.DataFrame({"unit": m.index, "esi_2020": esi_c.round(4)}).sort_values("esi_2020", ascending=False)
county_esi.to_csv(os.path.join(BASE, "data", "results_county_esi.csv"), index=False, encoding="utf-8-sig")
print("\n县域 ESI(2020 静态):")
print(county_esi.to_string(index=False))

# ---------- 2) 空间点采样 GeoDetector（2020）----------
import xarray as xr
pre_ds = xr.open_dataset(os.path.join(CRU_DIR, "cru_ts4.10.2001.2010.pre.dat.nc")).sel(time=slice("2005-01","2023-12"))
tmp_ds = xr.open_dataset(os.path.join(CRU_DIR, "cru_ts4.10.2001.2010.tmp.dat.nc")).sel(time=slice("2005-01","2023-12"))
# 合并 2011-2020, 2021-2023 段
for seg in ["2011.2020", "2021.2025"]:
    p2 = xr.open_dataset(os.path.join(CRU_DIR, f"cru_ts4.10.{seg}.pre.dat.nc")).sel(time=slice("2005-01","2023-12"))
    t2 = xr.open_dataset(os.path.join(CRU_DIR, f"cru_ts4.10.{seg}.tmp.dat.nc")).sel(time=slice("2005-01","2023-12"))
    pre_ds = xr.concat([pre_ds, p2], dim="time")
    tmp_ds = xr.concat([tmp_ds, t2], dim="time")
pre_ann = pre_ds["pre"].groupby("time.year").sum("time").mean("year")
tmp_ann = tmp_ds["tmp"].groupby("time.year").mean("time").mean("year")
src = open_clcd(2020)
tf = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
lats = np.arange(LAT0 + 0.2, LAT1, 0.15)
lons = np.arange(LON0 + 0.2, LON1, 0.15)
pts = []
for lat in lats:
    for lon in lons:
        pts.append((lat, lon))
print(f"\n采样点数: {len(pts)}")
rows = []
for lat, lon in pts:
    # CRU 点值
    try:
        p = float(pre_ann.sel(lat=lat, lon=lon, method="nearest").values)
        t = float(tmp_ann.sel(lat=lat, lon=lon, method="nearest").values)
    except Exception:
        continue
    # CLCD 点值（3x3 邻域众数）—— 用经纬度 ±0.02° 转 Albers 米制
    x0, y0 = tf.transform(lon - 0.02, lat - 0.02)
    x1, y1 = tf.transform(lon + 0.02, lat + 0.02)
    win = from_bounds(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1), src.transform)
    arr = src.read(1, window=win)
    vals = arr[arr != 0]
    if vals.size == 0: continue
    cls = np.bincount(vals.flatten().astype(int)).argmax()
    grass = 1 if cls == 4 else 0
    forest = 1 if cls == 2 else 0
    barren = 1 if cls == 7 else 0
    water = 1 if cls == 5 else 0
    rows.append({"lat": lat, "lon": lon, "temp": t, "precip": p, "grass": grass, "forest": forest, "barren": barren, "water": water, "class": cls})
sdf = pd.DataFrame(rows)
sdf.to_csv(os.path.join(BASE, "data", "spatial_samples.csv"), index=False, encoding="utf-8-sig")
print("有效样本:", len(sdf))
# 点 ESI（简化指标：降水、气温、草地、森林、水域、裸地）
Xp = sdf[["precip", "temp", "grass", "forest", "water"]].values.astype(float)
bar_p = (1 - sdf["grass"] - sdf["forest"] - sdf["water"]).clip(lower=0).values
Xp2 = np.column_stack([Xp, bar_p])
dp = [1, 1, 1, 1, 1, -1]
Xnp = minmax_normalize(Xp2, dp)
wp = entropy_weights(Xnp)
wpa = np.ones(6) / 6
wpf = combined_weights(wpa, wp, 0.4)
esip = esi_series(Xnp, wpf)
sdf["esi"] = esip
# GeoDetector：因子离散化（分位数 3-4 层）
def disc(x, k=4):
    qs = np.quantile(x, np.linspace(0, 1, k+1)[1:-1])
    return np.digitize(x, qs)
print("\n=== GeoDetector 因子探测（2020, n=%d）===" % len(sdf))
for f in ["temp", "precip", "grass", "forest", "barren"]:
    q = geodetector_q(sdf["esi"].values, disc(sdf[f].values))
    print(f"  {f:<8} q = {q:.4f}")
sdf[["lat","lon","esi"]].to_csv(os.path.join(BASE, "data", "spatial_esi_points.csv"), index=False, encoding="utf-8-sig")
print("空间结果已保存: spatial_esi_points.csv, results_county_esi.csv")
