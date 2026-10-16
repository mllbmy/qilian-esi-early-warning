# -*- coding: utf-8 -*-
"""补充材料分析：县域 ESI 对"空间支撑口径"的稳健性（Supplementary Table S1 / Figure S1）

三种口径下同一套赋权方案（alpha = 0.4，11 个县级单元间 min-max 标准化，6 指标）：
  A  已发表口径：质心 +/-0.1 度窗口内 CLCD 2020 土地覆被 + 县级气候        -> 表 6（data/results_county_esi.csv）
  B  县域多边形口径：GADM 4.1 县级行政边界内 CLCD 2020 土地覆被 + 县级气候 -> data/_supp_poly_lc.csv
  C  点位口径：1914 个样本点 ESI 在各县多边形内的均值（点位标准化，标度不同 -> 仅比较秩）

自检：用 A 口径重跑必须逐位复现已发表表 6（最大偏差 < 1e-3），否则脚本报错退出。

输出：
  data/results_county_support_sensitivity.csv   -> 三口径数值、秩、秩差
  data/results_county_window_truncation.csv     -> 窗口口径对县面积的截断比例（披露用）

运行：python run_county_support_sensitivity.py
"""
import json
import os
import sys

import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "eco_security"))
from eco_security import minmax_normalize, entropy_weights, combined_weights, esi_series  # noqa: E402

ALPHA = 0.4
REGION_UNIT = "区域(祁连山盒)"
INDICATORS = ["forest_pct", "grass_pct", "water_pct"]

# 11 个县级单元：中文名 -> GADM 可能出现的拼音名（NAME_3 / NL_NAME_3 双字段匹配）
COUNTIES = {
    "肃南": ["Sunan"], "天祝": ["Tianzhu"], "祁连": ["Qilian"], "德令哈": ["Delingha"],
    "门源": ["Menyuan"], "肃北": ["Subei"], "刚察": ["Gangcha"], "山丹": ["Shandan"],
    "天峻": ["Tianjun"], "民乐": ["Minle"], "阿克塞": ["Aksai"],
}
# 外部 GADM 县级边界（约 10 MB，未入库）：优先读 QILIAN_GADM 环境变量，缺省回退到仓库内相对路径
GADM = os.environ.get("QILIAN_GADM", os.path.join(BASE, "data", "gadm41_CHN_3.json"))


def county_climate():
    cli = pd.read_csv(os.path.join(BASE, "data", "qilian_climate.csv"))
    cli = cli[cli.unit != REGION_UNIT]
    return cli.groupby("unit")[["precip_mm", "temp_c"]].mean()


def esi_from_landcover(lc, cli, land_cols):
    """同一套赋权方案：6 指标（降水+/气温+/林地+/草地+/水域+/裸地-）"""
    m = lc.set_index("unit")[land_cols].join(cli).dropna()
    X = np.column_stack([
        m["precip_mm"].values, m["temp_c"].values,
        m["forest_pct"].values, m["grass_pct"].values, m["water_pct"].values,
        (100.0 - m["forest_pct"] - m["grass_pct"] - m["water_pct"] - m["crop_pct"]).values,
    ])
    directions = [+1, +1, +1, +1, +1, -1]
    Xn = minmax_normalize(X, directions)
    w = combined_weights(np.ones(X.shape[1]) / X.shape[1], entropy_weights(Xn), ALPHA)
    return pd.Series(esi_series(Xn, w), index=m.index)


def load_polygons():
    """GADM 县级多边形（中文名 -> shapely 几何）"""
    from shapely.geometry import shape
    from shapely.ops import unary_union
    gj = json.load(open(GADM, encoding="utf-8"))
    geoms, area = {}, {}
    for ft in gj["features"]:
        pr = ft["properties"]
        nm = str(pr.get("NAME_3", ""))
        nl = str(pr.get("NL_NAME_3", ""))
        for cn, pys in COUNTIES.items():
            cands = [cn] + pys
            if any(nm.startswith(c) or nl.startswith(c) or nm == c or nl == c for c in cands):
                g = shape(ft["geometry"])
                geoms[cn] = g if cn not in geoms else unary_union([geoms[cn], g])
    for cn, g in geoms.items():
        area[cn] = g.area  # 以度^2 计的粗略权重（仅用于截断比例）
    return geoms, area


def point_support(geoms):
    """各多边形内的点位 ESI 均值与点数"""
    from shapely import contains_xy
    pts = pd.read_csv(os.path.join(BASE, "data", "spatial_esi_points.csv"))
    lon, lat, esi = pts["lon"].values, pts["lat"].values, pts["esi"].values
    rows = []
    for cn, g in geoms.items():
        inside = contains_xy(g, lon, lat)
        rows.append({"unit": cn, "n_points_polygon": int(inside.sum()),
                     "esi_points_mean": float(esi[inside].mean()) if inside.any() else np.nan})
    return pd.DataFrame(rows).set_index("unit")


def window_support(geoms, area):
    """窗口（质心 +/-0.1 度）在多边形内的近似截断比例：窗口 ∩ 多边形 面积 / 多边形面积"""
    from shapely.geometry import box
    rows = []
    for cn, g in geoms.items():
        c = g.centroid
        win = box(c.x - 0.1, c.y - 0.1, c.x + 0.1, c.y + 0.1)
        inter = g.intersection(win).area
        rows.append({"unit": cn, "window_over_county_area": float(inter / g.area) if g.area else np.nan,
                     "county_area_deg2": float(g.area)})
    return pd.DataFrame(rows).set_index("unit")


def spearman(a, b):
    return float(pd.Series(a).corr(pd.Series(b), method="spearman"))


def main():
    cli = county_climate()
    lc_cols = ["forest_pct", "grass_pct", "water_pct", "barren_pct", "crop_pct"]

    # --- A: 已发表口径（自检必须复现） ---
    lcA = pd.read_csv(os.path.join(BASE, "data", "qilian_county_landcover.csv"))
    esiA = esi_from_landcover(lcA, cli, lc_cols)
    pub = pd.read_csv(os.path.join(BASE, "data", "results_county_esi.csv")).set_index("unit")["esi_2020"]
    dev = (esiA - pub.reindex(esiA.index)).abs().max()
    print("自检: A 口径 vs 已发表表 6 最大偏差 = %.6f" % dev)
    assert dev < 1e-3, "A 口径未能复现已发表表 6，脚本中止"

    # --- B: 县域多边形土地覆被 ---
    lcB = pd.read_csv(os.path.join(BASE, "data", "_supp_poly_lc.csv"))
    esiB = esi_from_landcover(lcB, cli, lc_cols)

    # --- C: 点位 ESI ---
    geoms, area = load_polygons()
    print("GADM 匹配到县级单元: %d 个 %s" % (len(geoms), sorted(geoms.keys())))
    miss = [c for c in COUNTIES if c not in geoms]
    if miss:
        print("  ⚠️ 未匹配:", miss)
    pt = point_support(geoms)
    win = window_support(geoms, area)

    df = pd.DataFrame({"esi_published_A": esiA, "esi_polygon_B": esiB})
    df = df.join(pt).join(win)
    df["rank_A"] = df["esi_published_A"].rank(ascending=False).astype(int)
    df["rank_B"] = df["esi_polygon_B"].rank(ascending=False).astype(int)
    df["rank_C"] = df["esi_points_mean"].rank(ascending=False).astype(int)
    df["rank_shift_B"] = df["rank_B"] - df["rank_A"]
    df["rank_shift_C"] = df["rank_C"] - df["rank_A"]
    df = df.sort_values("rank_A")
    df.index.name = "unit"
    df.round(4).to_csv(os.path.join(BASE, "data", "results_county_support_sensitivity.csv"), encoding="utf-8-sig")
    win.round(4).to_csv(os.path.join(BASE, "data", "results_county_window_truncation.csv"), encoding="utf-8-sig")

    print("\n=== 三口径对比（按已发表口径排序）===")
    print(df[["esi_published_A", "esi_polygon_B", "esi_points_mean", "rank_A", "rank_B", "rank_C",
              "rank_shift_B", "rank_shift_C", "window_over_county_area"]].round(4).to_string())

    ok = df[df["esi_polygon_B"].notna() & df["esi_points_mean"].notna()]
    rho_AB = spearman(ok["esi_published_A"], ok["esi_polygon_B"])
    rho_AC = spearman(ok["esi_published_A"], ok["esi_points_mean"])
    print("\n秩相关: A-B Spearman rho = %.3f | A-C Spearman rho = %.3f" % (rho_AB, rho_AC))
    print("最大秩变化: B 口径 %d 位 | C 口径 %d 位" % (df["rank_shift_B"].abs().max(), df["rank_shift_C"].abs().max()))
    print("前 3 名（A/B/C）: %s / %s / %s"
          % (list(df.index[:3]), list(df.sort_values("rank_B").index[:3]), list(df.sort_values("rank_C").index[:3])))
    print("末位（A/B/C）: %s / %s / %s" % (df.index[-1], df.sort_values("rank_B").index[-1], df.sort_values("rank_C").index[-1]))
    print("窗口占县面积比例: 最小 %.2f 中位 %.2f 最大 %.2f"
          % (df["window_over_county_area"].min(), df["window_over_county_area"].median(), df["window_over_county_area"].max()))
    print("\n已写入: data/results_county_support_sensitivity.csv, data/results_county_window_truncation.csv")
    return df


if __name__ == "__main__":
    main()