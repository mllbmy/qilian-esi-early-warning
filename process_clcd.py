# -*- coding: utf-8 -*-
"""CLCD 土地覆被处理：祁连山 11 县域指标提取
输入：_raw/lc_data/CLCD_v01_YYYY_albert.tif（ASCII路径，rasterio 兼容）
输出：data/qilian_landcover.csv（县域×年份 覆盖率指标）
CLCD 分类（v1.0 albert.tif 的像元值含义需从随附 legend 确认；常见约定）：
  1 农田 2 森林 3 灌木 4 草地 5 水域 6 冰雪 7 裸地 8 湿地 9 苔原 10 不透水面(建设用地)
  —— 脚本先输出每个年份的唯一像元值集合，便于核对 legend。
"""
import os, sys
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import from_bounds
try:
    from pyproj import Transformer
except ImportError:
    print("缺少 pyproj，先安装: python -m pip install pyproj")
    sys.exit(1)

# 祁连山区域（bbox: 与气候脚本一致，稍外扩）
LAT0, LAT1, LON0, LON1 = 36.0, 40.5, 93.5, 103.5
LC_DIR = os.environ.get("QILIAN_LC_DATA", os.path.join(os.path.dirname(os.path.abspath(__file__)), "_raw", "lc_data"))
# 路径自解析：仓库克隆/解压到任意目录均可运行
BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "data", "qilian_landcover.csv")

def load_and_clip(path):
    """打开 tif，用 Albers 投影窗口裁剪祁连山 bbox，返回像元数组（内存友好）。"""
    with rasterio.open(path) as src:
        src_crs = src.crs
        if src_crs is None or src_crs.to_epsg() == 4326:
            # 经纬度直接裁剪
            win = from_bounds(LON0, LAT0, LON1, LAT1, src.transform)
        else:
            # 投影转换：lat/lon -> 源CRS（Albers 米制）
            transformer = Transformer.from_crs("EPSG:4326", src_crs, always_xy=True)
            x0, y0 = transformer.transform(LON0, LAT0)
            x1, y1 = transformer.transform(LON1, LAT1)
            lo, hi = min(x0, x1), max(x0, x1)
            lo2, hi2 = min(y0, y1), max(y0, y1)
            win = from_bounds(lo, lo2, hi, hi2, src.transform)
        arr = src.read(1, window=win)
        return arr, src_crs

def class_stats(arr):
    """统计各类别面积占比（像元数占比近似）。"""
    total = arr.size
    vals, counts = np.unique(arr[arr != 0], return_counts=True)
    d = {int(v): int(c) for v, c in zip(vals, counts)}
    return d, total

def main():
    years = []
    for f in sorted(os.listdir(LC_DIR)):
        if f.startswith("CLCD_v01_") and f.endswith("_albert.tif"):
            y = int(f.split("_")[2])
            years.append((y, os.path.join(LC_DIR, f)))
    if not years:
        print("未找到 CLCD tif 于", LC_DIR); sys.exit(1)
    years.sort()
    print("找到年份:", [y for y, _ in years])
    rows = []
    for y, path in years:
        arr, crs = load_and_clip(path)
        d, total = class_stats(arr)
        print(f"{y}: CRS={crs} 像元数={total} 类别={{k:v 万像元}}".replace("{", "").replace("}", ""))
        # 打印类别分布供核对 legend
        dist = " ".join(f"C{c}={cnt*100/max(total,1):.2f}%" for c, cnt in sorted(d.items()))
        print(f"  {y} 类别占比: {dist}")
        rows.append({"year": y, "crs": str(crs), "classes": d})
    # 生成指标（假设 legend：2森林 3灌木 4草地 5水域 10不透水面；1农田）
    def pct(d, cls):
        tot = sum(d.values())
        return d.get(cls, 0) * 100 / tot if tot else 0.0
    out_rows = []
    for r in rows:
        d = r["classes"]
        out_rows.append({
            "year": r["year"],
            "forest_pct": pct(d, 2), "shrub_pct": pct(d, 3),
            "grass_pct": pct(d, 4), "water_pct": pct(d, 5),
            "built_pct": pct(d, 10), "crop_pct": pct(d, 1),
        })
    df = pd.DataFrame(out_rows)
    df.to_csv(OUT, index=False, encoding="utf-8-sig")
    print("已保存:", OUT)
    print(df.to_string(index=False))

if __name__ == "__main__":
    main()
