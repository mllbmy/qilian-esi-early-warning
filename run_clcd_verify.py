# -*- coding: utf-8 -*-
"""任务① CLCD 2020 栅格校验 + 采样管线复活验证

目的
────
CLCD_v01_2020_albert.tif 此前是下载残件（不可读），现已恢复并声明通过官方 md5。
本脚本验证：
  1) 文件完整性（md5 + 字节数，与 Zenodo 8176941 / DOI 10.5281/zenodo.8176941 声明一致）
  2) 栅格可正常读取、CRS/尺寸/分辨率/类别值正常、无错位
  3) 全国类别像元数与面积（分块窗口读取，绝不整幅载入内存）
  4) 用与 run_county_geodetector.py **逐字相同**的口径重建 1,914 个采样点的主导覆被类别：
       · 同一 open_clcd(year) 路径
       · 同一 pyproj Transformer(EPSG:4326 -> src.crs)
       · 同一点位经纬度 ±0.02° 转 Albers 米制后 from_bounds 开窗
       · 同一 arr[arr != 0] + np.bincount(...).argmax() 众数
  5) 逐点比对重建类别与归档 data/spatial_samples.csv 的 class 字段；比对类别分布
  6) 顺带复核县域 ±0.1° 窗口覆被占比能否复现 data/qilian_county_landcover.csv

判定
────
一致率 >= 99%  ->  "管线复活，归档数据可再生成"
一致率 <  99%  ->  脚本以非零退出码结束，并打印差异规模与逐点差异清单，不掩盖

内存策略
────────
栅格 161,378 x 135,079 (21.8e9 像元)；全部读取均通过 rasterio window（行条带 / 点窗口），
峰值内存 < 200 MB。

输出（全部新增，不覆盖任何既有文件）
────────────────────────────────────
  data/results_clcd2020_verify_summary.csv     —— 校验摘要（含 md5/一致率/结论）
  data/results_clcd2020_verify_points.csv      —— 1,914 点逐点比对
  data/results_clcd2020_class_area.csv         —— 全国类别像元数与面积
  data/results_clcd2020_verify_county_lc.csv   —— 县域 ±0.1° 窗口覆被占比 vs 归档

运行：python run_clcd_verify.py
"""
import hashlib
import os
import sys
import time

import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer
from rasterio.windows import Window, from_bounds

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
sys.path.insert(0, BASE)
import io_utils  # noqa: E402  # R22：共享 I/O 层（目录回退）
LC_DIR = io_utils.resolve_lc_dir()  # QILIAN_LC_DATA -> _raw/lc_data -> 递归兜底
TIF = os.path.join(LC_DIR, "CLCD_v01_2020_albert.tif")

EXPECTED_MD5 = "1274285BB18F9B1D443A3CC906B1310C"
EXPECTED_BYTES = 810739687

# 冻结口径（照抄 run_county_geodetector.py）
POINT_HALF = 0.02          # 点窗口半宽（度）
COUNTY_HALF = 0.1          # 县域质心窗口半宽（度）
LAT0, LAT1, LON0, LON1 = 36.0, 40.5, 93.5, 103.5
STEP = 0.15
QILIAN_COUNTIES = {
    "天祝": (37.20, 102.86), "肃南": (38.84, 99.62), "肃北": (39.51, 97.85),
    "阿克塞": (39.34, 94.34), "民乐": (38.43, 100.81), "山丹": (38.78, 101.09),
    "门源": (37.38, 101.62), "祁连": (38.18, 100.24), "刚察": (37.33, 100.14),
    "德令哈": (37.37, 97.36), "天峻": (37.30, 99.02),
}

# CLCD v01 类别码（Yang & Huang 2021, ESSD）
CLASS_NAMES = {
    1: "耕地 cropland", 2: "林地 forest", 3: "灌木 shrub", 4: "草地 grassland",
    5: "水域 water", 6: "冰雪 snow/ice", 7: "裸地 barren", 8: "不透水面 impervious",
    9: "湿地 wetland", 0: "nodata",
}
PIXEL_AREA_M2 = 30.0 * 30.0   # Albers 等积投影，像元面积恒为 900 m^2


# ---------------------------------------------------------------------------
# 与 run_county_geodetector.py 完全一致的两个开窗函数
# ---------------------------------------------------------------------------
def open_clcd(year):
    """逐字照抄 run_county_geodetector.py L29-32。"""
    p = os.path.join(LC_DIR, f"CLCD_v01_{year}_albert.tif")
    src = rasterio.open(p)
    return src


def class_pct_around(src, lat, lon, half=COUNTY_HALF):
    """逐字照抄 run_county_geodetector.py L34-46。"""
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


def dominant_class_point(src, tf, lat, lon, half=POINT_HALF):
    """逐字照抄 run_county_geodetector.py L110-117，并额外回传窗口像元数。"""
    x0, y0 = tf.transform(lon - half, lat - half)
    x1, y1 = tf.transform(lon + half, lat + half)
    win = from_bounds(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1), src.transform)
    arr = src.read(1, window=win)
    vals = arr[arr != 0]
    if vals.size == 0:
        return None, arr.shape, 0, 0
    cls = int(np.bincount(vals.flatten().astype(int)).argmax())
    return cls, arr.shape, int(vals.size), int(arr.size - vals.size)


# ---------------------------------------------------------------------------
# 完整性校验
# ---------------------------------------------------------------------------
def md5_of(path, chunk=64 * 1024 * 1024):
    h = hashlib.md5()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest().upper()


def full_class_histogram(src, strip_rows=512):
    """分块（行条带）统计全国类别像元数——内存安全，绝不整幅载入。"""
    hist = np.zeros(256, dtype=np.int64)
    n_strips = 0
    t0 = time.time()
    for r0 in range(0, src.height, strip_rows):
        h = min(strip_rows, src.height - r0)
        arr = src.read(1, window=Window(0, r0, src.width, h))
        hist += np.bincount(arr.ravel(), minlength=256)
        n_strips += 1
    return hist, n_strips, time.time() - t0


def box_histogram(src, lat_min, lat_max, lon_min, lon_max, strip_rows=512):
    """经纬度盒（取变换后四角的 Albers 外接矩形，是盒的超集）的类别统计。"""
    tf = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
    xs, ys = [], []
    for la in (lat_min, lat_max):
        for lo in (lon_min, lon_max):
            x, y = tf.transform(lo, la)
            xs.append(x); ys.append(y)
    win = from_bounds(min(xs), min(ys), max(xs), max(ys), src.transform)
    win = win.round_offsets().round_lengths()
    hist = np.zeros(256, dtype=np.int64)
    n_strips = 0
    for r0 in range(0, int(win.height), strip_rows):
        h = min(strip_rows, int(win.height) - r0)
        arr = src.read(1, window=Window(int(win.col_off), int(win.row_off) + r0, int(win.width), h))
        hist += np.bincount(arr.ravel(), minlength=256)
        n_strips += 1
    return hist, win, n_strips


# ---------------------------------------------------------------------------
def main():
    print("=" * 84)
    print("任务① CLCD 2020 栅格校验 + 采样管线复活验证")
    print("=" * 84)
    summary = []

    # ---------- 1) 完整性 ----------
    print("\n[1] 文件完整性")
    if not os.path.exists(TIF):
        print("!! 栅格不存在: %s" % TIF); return 2
    size = os.path.getsize(TIF)
    t0 = time.time()
    md5 = md5_of(TIF)
    print("    路径        : %s" % TIF)
    print("    字节数      : %d  (期望 %d)  %s"
          % (size, EXPECTED_BYTES, "MATCH" if size == EXPECTED_BYTES else "MISMATCH"))
    print("    md5         : %s  (期望 %s)  %s"
          % (md5, EXPECTED_MD5, "MATCH" if md5 == EXPECTED_MD5 else "MISMATCH"))
    print("    校验耗时    : %.1f s" % (time.time() - t0))
    md5_ok = (md5 == EXPECTED_MD5) and (size == EXPECTED_BYTES)
    summary.append(("md5", md5, EXPECTED_MD5, "MATCH" if md5 == EXPECTED_MD5 else "MISMATCH"))
    summary.append(("bytes", size, EXPECTED_BYTES, "MATCH" if size == EXPECTED_BYTES else "MISMATCH"))
    if not md5_ok:
        print("\n!! 栅格完整性校验失败，立即停止（不进行任何后续分析）。")
        pd.DataFrame(summary, columns=["item", "observed", "expected", "status"]).to_csv(
            os.path.join(DATA, "results_clcd2020_verify_summary.csv"),
            index=False, encoding="utf-8-sig")
        return 3

    # ---------- 2) 元数据 ----------
    print("\n[2] 栅格元数据")
    src = open_clcd(2020)
    print("    driver/dtype : %s / %s" % (src.driver, src.dtypes))
    print("    CRS          : %s" % src.crs.to_string())
    print("    size         : %d cols x %d rows" % (src.width, src.height))
    print("    res          : %s (m)" % (src.res,))
    print("    transform    : %s" % (tuple(src.transform)[:6],))
    print("    bounds       : %s" % (src.bounds,))
    print("    nodata       : %s ; compress=%s ; tiled blocks=%s ; overviews=%s"
          % (src.nodata, src.profile.get("compress"), src.block_shapes, src.overviews(1)))
    print("    总像元       : %.3e" % (src.width * src.height))

    # ---------- 3) 全国类别像元数/面积（分块读取） ----------
    print("\n[3] 全国类别像元数与面积（行条带 %d 行分块读取）" % 512)
    hist, n_strips, dt = full_class_histogram(src)
    hist = hist[:10]
    total_valid = int(hist[1:].sum())
    print("    条带数 %d，读取耗时 %.1f s" % (n_strips, dt))
    rows = []
    print("    %-6s %-22s %16s %14s" % ("code", "class", "pixels", "area (km2)"))
    for c in range(0, 10):
        n = int(hist[c])
        if n == 0 and c not in (0,):
            continue
        area = n * PIXEL_AREA_M2 / 1e6
        rows.append({"code": c, "class": CLASS_NAMES.get(c, "?"), "pixels": n,
                     "area_km2": round(area, 3),
                     "pct_of_valid": round(n * 100.0 / total_valid, 4) if c != 0 and total_valid else np.nan})
        print("    %-6d %-22s %16d %14.1f" % (c, CLASS_NAMES.get(c, "?"), n, area))
    ca = pd.DataFrame(rows)
    ca.to_csv(os.path.join(DATA, "results_clcd2020_class_area.csv"), index=False, encoding="utf-8-sig")
    print("    有效像元合计 = %d ；全国国土面积 = %.1f 万 km2"
          % (total_valid, total_valid * PIXEL_AREA_M2 / 1e6 / 1e4))
    summary.append(("raster_readable", "yes", "yes", "OK"))
    summary.append(("crs", src.crs.to_string()[:60], "Albers Conic Equal Area", "OK"))
    summary.append(("size", "%dx%d" % (src.width, src.height), "161378x135079",
                    "MATCH" if (src.width, src.height) == (161378, 135079) else "MISMATCH"))
    summary.append(("res_m", "%.1f" % src.res[0], "30.0", "MATCH" if abs(src.res[0] - 30) < 1e-9 else "MISMATCH"))
    summary.append(("valid_pixels", total_valid, "n/a", "-"))
    summary.append(("valid_area_km2", round(total_valid * PIXEL_AREA_M2 / 1e6, 1), "n/a", "-"))

    # 研究区盒（超集）参考统计
    bh, bwin, bstrips = box_histogram(src, LAT0, LAT1, LON0, LON1)
    btot = int(bh[1:].sum())
    print("\n    研究区盒 %s (Albers 外接矩形, %d x %d px, 超集)：" % (
        (LAT0, LAT1, LON0, LON1), int(bwin.width), int(bwin.height)))
    for c in range(1, 10):
        if bh[c] > 0:
            print("      %-4d %-22s %12d  %6.2f%%" % (c, CLASS_NAMES[c], bh[c], bh[c] * 100.0 / btot))

    # ---------- 4) 重建 1,914 点主导覆被 ----------
    print("\n[4] 重建 1,914 个采样点的主导覆被类别（口径与 run_county_geodetector.py 逐字一致）")
    lats = np.arange(LAT0 + 0.2, LAT1, STEP)
    lons = np.arange(LON0 + 0.2, LON1, STEP)
    print("    网格: %d lat x %d lon = %d 点 (lat %.2f..%.2f step %.2f; lon %.2f..%.2f step %.2f)"
          % (len(lats), len(lons), len(lats) * len(lons), lats[0], lats[-1], STEP,
             lons[0], lons[-1], STEP))
    tf = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
    rec = []
    t0 = time.time()
    for lat in lats:
        for lon in lons:
            cls, shape, n_valid, n_nodata = dominant_class_point(src, tf, float(lat), float(lon))
            rec.append({"lat": float(lat), "lon": float(lon), "class_rebuilt": cls,
                        "win_rows": shape[0], "win_cols": shape[1],
                        "win_pixels": shape[0] * shape[1],
                        "win_valid_pixels": n_valid, "win_nodata_pixels": n_nodata})
    rb = pd.DataFrame(rec)
    print("    采样完成，耗时 %.1f s ；窗口尺寸 %d x %d px （注：并非字面 3x3）"
          % (time.time() - t0, rb.win_rows.iloc[0], rb.win_cols.iloc[0]))
    print("    窗口有效像元: min %d / median %d / max %d ；含 nodata 的点位数 %d"
          % (rb.win_valid_pixels.min(), int(rb.win_valid_pixels.median()),
             rb.win_valid_pixels.max(), int((rb.win_nodata_pixels > 0).sum())))
    print("    未取到有效像元的点位: %d" % int(rb.class_rebuilt.isna().sum()))

    # ---------- 5) 与归档比对 ----------
    print("\n[5] 与归档 data/spatial_samples.csv 逐点比对")
    arch = pd.read_csv(os.path.join(DATA, "spatial_samples.csv"))
    print("    归档点数 %d ；重建点数 %d" % (len(arch), len(rb)))
    if len(arch) != len(rb):
        print("    !! 点数不一致，无法逐点比对。")
        return 4
    # 坐标一致性（numpy arange 末位 ULP 差异，需确认是同一网格）
    dlat = np.abs(arch["lat"].values - rb["lat"].values)
    dlon = np.abs(arch["lon"].values - rb["lon"].values)
    print("    坐标逐行偏差: max|dlat| = %.3e, max|dlon| = %.3e (同一 arange 网格的浮点末位差)" % (dlat.max(), dlon.max()))
    coord_ok = bool(dlat.max() < 1e-9 and dlon.max() < 1e-9)
    print("    坐标同一网格判定（容差 1e-9）: %s" % ("OK" if coord_ok else "FAIL"))
    # 排序后的集合匹配（不依赖行序）
    grid_set = {(round(a, 6), round(b, 6)) for a, b in zip(rb["lat"], rb["lon"])}
    arch_set = {(round(a, 6), round(b, 6)) for a, b in zip(arch["lat"], arch["lon"])}
    set_ok = grid_set == arch_set
    print("    网格集合一致（坐标四舍五入到 1e-6 后比较）: %s" % ("OK" if set_ok else "FAIL"))
    summary.append(("point_grid_same", "yes" if (coord_ok and set_ok) else "no", "yes",
                    "OK" if (coord_ok and set_ok) else "FAIL"))

    cmp = pd.DataFrame({
        "lat": arch["lat"].values, "lon": arch["lon"].values,
        "class_archived": arch["class"].values,
        "class_rebuilt": rb["class_rebuilt"].values,
        "win_valid_pixels": rb["win_valid_pixels"].values,
    })
    cmp["match"] = cmp["class_archived"] == cmp["class_rebuilt"]
    for c, nm in [(4, "grass"), (2, "forest"), (7, "barren"), (5, "water")]:
        cmp["arch_" + nm] = cmp["class_archived"].eq(c).astype(int)
        cmp["reb_" + nm] = cmp["class_rebuilt"].eq(c).astype(int)
        cmp[nm + "_match"] = cmp["arch_" + nm].eq(cmp["reb_" + nm])
    n_match = int(cmp["match"].sum())
    rate = n_match / len(cmp)
    print("    ---- 逐点一致 ----")
    print("    一致点位: %d / %d = %.4f (%.2f%%)" % (n_match, len(cmp), rate, rate * 100))
    for nm in ["grass", "forest", "barren", "water"]:
        m = int(cmp[nm + "_match"].sum())
        print("      %-7s one-hot 一致 %d/%d = %.4f" % (nm, m, len(cmp), m / len(cmp)))
    print("    ---- 类别分布 ----")
    da = cmp["class_archived"].value_counts().sort_index()
    dr = cmp["class_rebuilt"].value_counts().sort_index()
    dist = pd.DataFrame({"class": sorted(set(da.index) | set(dr.index))})
    dist["name"] = dist["class"].map(lambda c: CLASS_NAMES.get(int(c), "?"))
    dist["archived"] = dist["class"].map(lambda c: int(da.get(c, 0)))
    dist["rebuilt"] = dist["class"].map(lambda c: int(dr.get(c, 0)))
    dist["diff"] = dist["rebuilt"] - dist["archived"]
    print(dist.to_string(index=False))

    mism = cmp[~cmp["match"]]
    if len(mism):
        print("    ---- 不一致点位（前 30 条）----")
        print(mism.head(30).to_string(index=False))
        print("    不一致点的类别迁移矩阵 (archived -> rebuilt):")
        mig = mism.groupby(["class_archived", "class_rebuilt"]).size().reset_index(name="n")
        print(mig.to_string(index=False))
        cmp.to_csv(os.path.join(DATA, "results_clcd2020_verify_points.csv"),
                   index=False, encoding="utf-8-sig")
    else:
        print("    ---- 无不一致点位 ----")
        cmp.to_csv(os.path.join(DATA, "results_clcd2020_verify_points.csv"),
                   index=False, encoding="utf-8-sig")
    dist.to_csv(os.path.join(DATA, "results_clcd2020_verify_class_dist.csv"),
                index=False, encoding="utf-8-sig")

    # ---------- 6) 县域 ±0.1° 窗口覆被占比复核 ----------
    print("\n[6] 县域质心 ±0.1° 窗口覆被占比 vs 归档 data/qilian_county_landcover.csv")
    crow = []
    for name, (lat, lon) in QILIAN_COUNTIES.items():
        f, g, w, b, c = class_pct_around(src, lat, lon, COUNTY_HALF)
        crow.append({"unit": name, "forest_pct": f, "grass_pct": g,
                     "water_pct": w, "barren_pct": b, "crop_pct": c})
    cdf = pd.DataFrame(crow)
    arc_lc = pd.read_csv(os.path.join(DATA, "qilian_county_landcover.csv"))
    mg = arc_lc.merge(cdf, on="unit", suffixes=("_arch", "_reb"))
    devs = []
    for col in ["forest_pct", "grass_pct", "water_pct", "barren_pct", "crop_pct"]:
        d = (mg[col + "_arch"] - mg[col + "_reb"]).abs().max()
        devs.append(d)
        print("    %-14s max|Δ| = %.6f (pp)" % (col, d))
    max_dev = float(np.max(devs))
    print("    县域覆被占比最大绝对偏差 = %.6f 个百分点 -> %s"
          % (max_dev, "复现" if max_dev < 0.01 else "不一致"))
    out_lc = mg[["unit"] + [c + "_arch" for c in ["forest_pct", "grass_pct", "water_pct", "barren_pct", "crop_pct"]]
                + [c + "_reb" for c in ["forest_pct", "grass_pct", "water_pct", "barren_pct", "crop_pct"]]]
    out_lc.round(6).to_csv(os.path.join(DATA, "results_clcd2020_verify_county_lc.csv"),
                           index=False, encoding="utf-8-sig")

    # ---------- 7) 结论 ----------
    print("\n" + "=" * 84)
    if rate >= 0.99 and set_ok:
        verdict = "PASS：管线复活，归档数据可再生成（一致率 %.2f%% >= 99%%）" % (rate * 100)
    else:
        verdict = ("FAIL：一致率 %.2f%% < 99%%，或网格集合不一致 —— 立即停止后续任务" % (rate * 100))
    print("判定: %s" % verdict)
    print("=" * 84)
    summary.append(("point_match_n", n_match, len(cmp), "-"))
    summary.append(("point_match_rate", round(rate, 6), ">=0.99", "PASS" if rate >= 0.99 else "FAIL"))
    summary.append(("county_lc_max_dev_pp", round(max_dev, 6), "<0.01", "OK" if max_dev < 0.01 else "FAIL"))
    summary.append(("verdict", verdict.split("：")[0], "PASS", "PASS" if rate >= 0.99 else "FAIL"))
    pd.DataFrame(summary, columns=["item", "observed", "expected", "status"]).to_csv(
        os.path.join(DATA, "results_clcd2020_verify_summary.csv"), index=False, encoding="utf-8-sig")
    print("已写入: results_clcd2020_verify_summary.csv / _points.csv / _class_dist.csv / "
          "_class_area.csv / _verify_county_lc.csv")
    src.close()
    return 0 if (rate >= 0.99 and set_ok) else 5


if __name__ == "__main__":
    sys.exit(main())