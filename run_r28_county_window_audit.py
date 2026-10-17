# -*- coding: utf-8 -*-
"""R28 · T8 前置诊断：县域土地覆被 CSV 与 CLCD 2020 质心窗口的逐县对账

目的：run_county_esi.py 的 6 项指标中，barren_neg 由
      `100 - forest - grass - water - crop`（run_county_esi.py:48）以**残差**方式构造。
      若 qilian_county_landcover.csv 的 5 类占比本身不闭合到 100（CLCD 还有灌木/冰雪/
      不透水面/湿地 4 类未计入），则残差式会把"未计入类别"整体计入 barren_neg，
      从而把真实裸地占比结构性放大。

方法：按 run_county_geodetector.py:40-52 的同一窗口口径（质心 ±0.1°，非零像元占比）
      逐县重算 9 类占比，与已入库 CSV 对账。**只读，不覆盖任何已跟踪文件。**

输出：data/r28_county_window_audit.csv
"""
import os
import sys

import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
sys.path.insert(0, BASE)
import io_utils  # noqa: E402

import rasterio  # noqa: E402
from rasterio.windows import from_bounds  # noqa: E402
from pyproj import Transformer  # noqa: E402

QILIAN_COUNTIES = {
    "天祝": (37.20, 102.86), "肃南": (38.84, 99.62), "肃北": (39.51, 97.85),
    "阿克塞": (39.34, 94.34), "民乐": (38.43, 100.81), "山丹": (38.78, 101.09),
    "门源": (37.38, 101.62), "祁连": (38.18, 100.24), "刚察": (37.33, 100.14),
    "德令哈": (37.37, 97.36), "天峻": (37.30, 99.02),
}
CLS_NAME = {1: "cropland", 2: "forest", 3: "shrub", 4: "grass", 5: "water",
            6: "snow_ice", 7: "barren", 8: "impervious", 9: "wetland"}
HALVES = {"+0.05": 0.05, "+0.10": 0.10, "+0.20": 0.20, "+0.30": 0.30}


def window_pcts(src, lat, lon, half):
    tf = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
    x0, y0 = tf.transform(lon - half, lat - half)
    x1, y1 = tf.transform(lon + half, lat + half)
    win = from_bounds(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1), src.transform)
    arr = src.read(1, window=win)
    vals, counts = np.unique(arr[arr != 0], return_counts=True)
    d = {int(v): int(c) for v, c in zip(vals, counts)}
    tot = sum(d.values())
    return {CLS_NAME.get(k, str(k)): (d.get(k, 0) * 100.0 / tot if tot else 0.0) for k in CLS_NAME}, tot, arr.size


def main():
    lcdir = io_utils.resolve_lc_dir()
    tif = os.path.join(lcdir, "CLCD_v01_2020_albert.tif")
    print("CLCD 2020 =", tif)
    src = rasterio.open(tif)
    arch = pd.read_csv(os.path.join(DATA, "qilian_county_landcover.csv")).set_index("unit")

    rows = []
    for unit, (lat, lon) in QILIAN_COUNTIES.items():
        for hlabel, half in HALVES.items():
            pcts, tot, size = window_pcts(src, lat, lon, half)
            five = ["cropland", "forest", "grass", "water", "barren"]
            five_sum = sum(pcts[k] for k in five)
            omitted = sum(pcts[k] for k in ["shrub", "snow_ice", "impervious", "wetland"])
            rec = {"unit": unit, "half_deg": hlabel, "half": half, "n_pixels": tot}
            for k in CLS_NAME.values():
                rec[k + "_window_pct"] = round(pcts[k], 6)
            rec["five_class_sum_window"] = round(five_sum, 6)
            rec["omitted_four_class_sum_window"] = round(omitted, 6)
            if hlabel == "+0.10":
                a = arch.loc[unit]
                rec["forest_csv"] = float(a["forest_pct"])
                rec["grass_csv"] = float(a["grass_pct"])
                rec["water_csv"] = float(a["water_pct"])
                rec["barren_csv"] = float(a["barren_pct"])
                rec["crop_csv"] = float(a["crop_pct"])
                rec["five_class_sum_csv"] = float(a[["forest_pct", "grass_pct", "water_pct",
                                                     "barren_pct", "crop_pct"]].sum())
                rec["barren_csv_minus_window"] = round(float(a["barren_pct"]) - pcts["barren"], 6)
                rec["barren_residual_100_minus4"] = round(100.0 - float(a["forest_pct"]) - float(a["grass_pct"])
                                                          - float(a["water_pct"]) - float(a["crop_pct"]), 6)
                rec["barren_csv_equals_residual"] = bool(
                    abs(float(a["barren_pct"]) - rec["barren_residual_100_minus4"]) < 1e-9)
                rec["five_sum_csv_plus_omitted_window"] = round(float(a[["forest_pct", "grass_pct", "water_pct",
                                                                         "crop_pct"]].sum()) + omitted, 6)
            rows.append(rec)

    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(DATA, "r28_county_window_audit.csv"), index=False, encoding="utf-8-sig")

    print("\n=== ±0.10° 窗口：CSV 五类之和 vs 100，以及 CSV barren 与真实裸地占比之差 ===")
    sub = out[out.half_deg == "+0.10"][
        ["unit", "five_class_sum_csv", "barren_csv", "barren_window_pct",
         "barren_csv_minus_window", "omitted_four_class_sum_window", "barren_csv_equals_residual"]]
    print(sub.to_string(index=False))
    print("\n=== 五类占比之和（窗口重算，9 类闭合应=100；CSV 口径只含 5 类）===")
    print(out[out.half_deg == "+0.10"][["unit", "five_class_sum_window", "omitted_four_class_sum_window"]].to_string(index=False))
    print("\n已写出 data/r28_county_window_audit.csv（%d 行）" % len(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())