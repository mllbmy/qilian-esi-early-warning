# -*- coding: utf-8 -*-
"""任务③ 县域质心窗口多尺度检验（±0.05° / ±0.1°(原口径) / ±0.2° / ±0.3°）

回答的问题
────────────
"县域 ESI 用质心 ±0.1° 窗口近似县域土地覆被，对面积大、质心落在无覆被差异处的县
（尤其阿克塞 ESI = 0.067）代表性有限，该低值是否只是窗口伪影？"

方法（口径严格照抄 run_county_geodetector.py 县域部分 + run_county_esi.py 权重方案）
──────────────────────────────────────────────────────────────────────────
· 土地覆被：质心 ±half° 窗口内 CLCD 2020 各类别像元占比（class_pct_around 逐字照抄）
· 气候：qilian_climate.csv 该县 2005-2023 年均降水/气温的多年平均（run_county_esi.load_inputs）
· 指标 6 项：[年降水(+), 年均气温(+), 林地占比(+), 草地占比(+), 水域占比(+),
              裸地/退化占比(-)]，其中 裸地占比 = 100 - 林地 - 草地 - 水域 - 耕地
· 标准化：每次窗口设置下，在 11 个县级单元之间做 min-max（+1/-1）
· 权重：w = (1-α)·w_entropy + α·w_AHP，α = 0.4，w_AHP 等权
· ESI = Σ w_j x'_ij
自检：±0.1° 档必须逐位复现 data/results_county_esi.csv（偏差 < 1e-3），否则报错退出。

输出（全部新增）
  data/results_county_window_multiscale.csv     —— 11 县 x 4 档窗口 ESI + 排名
  data/results_county_window_landcover.csv      —— 11 县 x 4 档窗口的覆被占比明细
  data/results_county_window_stability.csv      —— 秩相关矩阵 + 阿克塞专项
运行：python run_county_window_sensitivity.py
"""
import os
import sys

import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer
from rasterio.windows import from_bounds

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
sys.path.insert(0, BASE)
import io_utils  # noqa: E402  # R22：共享 I/O 层（目录回退）
LC_DIR = io_utils.resolve_lc_dir()  # QILIAN_LC_DATA -> _raw/lc_data -> 递归兜底
TIF = os.path.join(LC_DIR, "CLCD_v01_2020_albert.tif")
sys.path.insert(0, os.path.join(BASE, "eco_security"))
from eco_security import (  # noqa: E402
    minmax_normalize, entropy_weights, combined_weights, esi_series,
)

ALPHA = 0.4
REGION_UNIT = "区域(祁连山盒)"
HALVES = [0.05, 0.10, 0.20, 0.30]          # 四档质心窗口半宽（度）
HALF_LABEL = {0.05: "±0.05°", 0.10: "±0.10°", 0.20: "±0.20°", 0.30: "±0.30°"}
PUBLISHED_HALF = 0.10                       # 原口径 / 已发表口径

QILIAN_COUNTIES = {
    "天祝": (37.20, 102.86), "肃南": (38.84, 99.62), "肃北": (39.51, 97.85),
    "阿克塞": (39.34, 94.34), "民乐": (38.43, 100.81), "山丹": (38.78, 101.09),
    "门源": (37.38, 101.62), "祁连": (38.18, 100.24), "刚察": (37.33, 100.14),
    "德令哈": (37.37, 97.36), "天峻": (37.30, 99.02),
}


def class_pct_around(src, lat, lon, half):
    """逐字照抄 run_county_geodetector.py class_pct_around，half 参数化。

    返回 (forest, grass, water, barren, crop) 百分比 + 窗口审计信息。
    """
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

    audit = {"win_pixels": int(arr.size), "valid_pixels": int(tot),
             "nodata_pixels": int(arr.size - tot)}
    return pct(2), pct(4), pct(5), pct(7), pct(1), audit


def load_climate():
    cli = pd.read_csv(os.path.join(DATA, "qilian_climate.csv"))
    cli = cli[cli.unit != REGION_UNIT]
    return cli.groupby("unit")[["precip_mm", "temp_c"]].mean()


def esi_of_setting(lc, cli):
    """口径沿用 run_county_esi.county_esi()（6 指标，alpha=0.4，AHP 等权）。"""
    m = lc.set_index("unit").join(cli).dropna()
    X = m[["precip_mm", "temp_c", "forest_pct", "grass_pct", "water_pct"]].values
    barren_neg = (100.0 - m["forest_pct"] - m["grass_pct"] - m["water_pct"] - m["crop_pct"]).values
    X2 = np.column_stack([X, barren_neg])
    Xn = minmax_normalize(X2, [+1, +1, +1, +1, +1, -1])
    w_ent = entropy_weights(Xn)
    w_ahp = np.ones(X2.shape[1]) / X2.shape[1]
    w = combined_weights(w_ahp, w_ent, ALPHA)
    return pd.Series(esi_series(Xn, w), index=m.index), w_ent, w


def spearman(a, b):
    return float(pd.Series(a).corr(pd.Series(b), method="spearman"))


def main():
    print("=" * 92)
    print("任务③ 县域质心窗口多尺度检验：%s" % " / ".join(HALF_LABEL[h] for h in HALVES))
    print("=" * 92)
    cli = load_climate()
    src = rasterio.open(TIF)
    print("栅格: %s ; CRS=%s ; res=%s m" % (os.path.basename(TIF), src.crs.to_string()[:48], src.res))

    # ---------- 1) 各档窗口覆被占比 ----------
    lc_rows, audit_rows = [], []
    for half in HALVES:
        for name, (lat, lon) in QILIAN_COUNTIES.items():
            f, g, w, b, c, aud = class_pct_around(src, lat, lon, half)
            lc_rows.append({"unit": name, "half_deg": half, "label": HALF_LABEL[half],
                            "forest_pct": f, "grass_pct": g, "water_pct": w,
                            "barren_pct": b, "crop_pct": c})
            audit_rows.append({"unit": name, "half_deg": half, "label": HALF_LABEL[half], **aud})
    lc_all = pd.DataFrame(lc_rows)
    aud = pd.DataFrame(audit_rows)
    lc_all.round(4).to_csv(os.path.join(DATA, "results_county_window_landcover.csv"),
                           index=False, encoding="utf-8-sig")
    print("\n[1] 窗口覆被占比已算（11 县 x %d 档）" % len(HALVES))
    print("    各档窗口像元数（11 县合计）:")
    for half in HALVES:
        s = aud[aud.half_deg == half]
        print("      %-8s 窗口 %d x %d px，有效像元 min %d / median %d / max %d，含 nodata 县数 %d"
              % (HALF_LABEL[half],
                 int(np.sqrt(s.win_pixels.max())), int(np.sqrt(s.win_pixels.max())),
                 s.valid_pixels.min(), int(s.valid_pixels.median()), s.valid_pixels.max(),
                 int((s.nodata_pixels > 0).sum())))
    wl = aud[aud.nodata_pixels > 0]
    if len(wl):
        print("    窗口含 nodata 的记录（已按非 nodata 像元为分母）:")
        print(wl.to_string(index=False))

    # ---------- 2) 各档 ESI ----------
    print("\n[2] 各档窗口的县域 ESI（11 单元间 min-max；alpha=%.1f；AHP 等权）" % ALPHA)
    esi_by_half, w_by_half = {}, {}
    for half in HALVES:
        sub = lc_all[lc_all.half_deg == half]
        e, w_ent, w = esi_of_setting(sub, cli)
        esi_by_half[half] = e
        w_by_half[half] = pd.DataFrame({"indicator": ["precip_mm", "temp_c", "forest_pct",
                                                     "grass_pct", "water_pct", "barren_neg_pct"],
                                        "w_entropy": w_ent, "w_ahl_equal": np.ones(6) / 6,
                                        "w_combined": w})
        w_by_half[half].insert(0, "label", HALF_LABEL[half])
        print("\n    %s 组合权重: %s" % (HALF_LABEL[half], np.round(w, 5)))

    # 自检：±0.1° 必须复现已发表表 6
    pub = pd.read_csv(os.path.join(DATA, "results_county_esi.csv")).set_index("unit")["esi_2020"]
    e_pub = esi_by_half[PUBLISHED_HALF]
    dev = float((e_pub - pub.reindex(e_pub.index)).abs().max())
    print("\n[3] 自检: ±0.10° 档 vs 已发表 results_county_esi.csv 最大偏差 = %.8f" % dev)
    assert dev < 1e-3, "±0.1° 档未能复现已发表表 6，脚本中止（口径不一致）"
    print("    自检通过（口径一致）。")

    # ---------- 3) 汇总表 + 排名 ----------
    mat = pd.DataFrame({HALF_LABEL[h]: esi_by_half[h] for h in HALVES})
    mat.index.name = "unit"
    rank = mat.rank(ascending=False, method="min").astype(int)
    rank.columns = [c + "_rank" for c in rank.columns]
    out = mat.round(4).join(rank)
    out["rank_min"] = rank.min(axis=1)
    out["rank_max"] = rank.max(axis=1)
    out["rank_span"] = out["rank_max"] - out["rank_min"]
    out["esi_range"] = (mat.max(axis=1) - mat.min(axis=1)).round(4)
    out = out.sort_values(HALF_LABEL[PUBLISHED_HALF], ascending=False)
    print("\n[4] 11 县 x 4 档窗口 ESI 与排名（按 ±0.10° 降序）")
    print(out.to_string())
    out.to_csv(os.path.join(DATA, "results_county_window_multiscale.csv"),
               encoding="utf-8-sig")

    # ---------- 4) 排序稳定性 ----------
    print("\n[5] 排序稳定性（Spearman 秩相关，11 县）")
    labs = [HALF_LABEL[h] for h in HALVES]
    smat = pd.DataFrame(index=labs, columns=labs, dtype=float)
    for a in labs:
        for b in labs:
            smat.loc[a, b] = round(spearman(mat[a], mat[b]), 4)
    print(smat.to_string())
    base_lab = HALF_LABEL[PUBLISHED_HALF]
    print("    各档 vs ±0.10°(原口径) 的 Spearman: " +
          " ; ".join("%s rho=%.3f" % (l, smat.loc[l, base_lab]) for l in labs if l != base_lab))
    kendall = {l: round(float(pd.Series(mat[l]).corr(pd.Series(mat[base_lab]), method="kendall")), 4)
               for l in labs}
    print("    Kendall tau vs 原口径: %s" % kendall)

    # ---------- 5) 阿克塞专项 ----------
    print("\n[6] 阿克塞专项")
    ak = "阿克塞"
    ak_row = out.loc[ak]
    for h in HALVES:
        print("    %-8s ESI = %.4f  排名 %d/11   (覆被: 草地 %.2f%% 裸地 %.2f%% 耕地 %.2f%% 林地 %.2f%% 水域 %.2f%%)"
              % (HALF_LABEL[h], mat.loc[ak, HALF_LABEL[h]], rank.loc[ak, HALF_LABEL[h] + "_rank"],
                 lc_all[(lc_all.unit == ak) & (lc_all.half_deg == h)].grass_pct.iloc[0],
                 lc_all[(lc_all.unit == ak) & (lc_all.half_deg == h)].barren_pct.iloc[0],
                 lc_all[(lc_all.unit == ak) & (lc_all.half_deg == h)].crop_pct.iloc[0],
                 lc_all[(lc_all.unit == ak) & (lc_all.half_deg == h)].forest_pct.iloc[0],
                 lc_all[(lc_all.unit == ak) & (lc_all.half_deg == h)].water_pct.iloc[0]))
    ak_min = mat.loc[ak].min()
    always_last = bool((rank.loc[ak] == 11).all())
    print("    阿克塞 4 档最小 ESI = %.4f ；是否 4 档均为末位: %s" % (ak_min, "是" if always_last else "否"))
    print("    ESI 极差（4 档内） = %.4f" % (mat.loc[ak].max() - mat.loc[ak].min()))
    # 阿克塞排名与"含裸地/退化"的对照：裸地占比本身在 4 档下是否稳定最高
    ak_barren = [lc_all[(lc_all.unit == ak) & (lc_all.half_deg == h)].barren_pct.iloc[0] for h in HALVES]
    barrel_rank = []
    for h in HALVES:
        sub = lc_all[lc_all.half_deg == h].set_index("unit")["barren_pct"]
        barrel_rank.append(int(sub.rank(ascending=False)[ak]))
    print("    阿克塞 4 档裸地占比 = %s ；裸地占比排名 = %s"
          % ([round(v, 2) for v in ak_barren], barrel_rank))

    # ---------- 6) 分区结论支撑度 ----------
    print("\n[7] 排序是否支撑管理分区结论")
    print("    4 档下排名跨度最大的县: %s"
          % out.sort_values("rank_span", ascending=False).head(3)[["rank_span"]].to_dict()["rank_span"])
    print("    4 档下排名完全不变的县数: %d / 11" % int((out["rank_span"] == 0).sum()))
    n_swing3 = int((out["rank_span"] >= 3).sum())
    print("    排名跨度 >= 3 位的县数: %d / 11" % n_swing3)
    print("    四档 ESI 均值排序前 3: %s"
          % list(mat.mean(axis=1).sort_values(ascending=False).head(3).index))
    print("    四档 ESI 均值排序末 3: %s"
          % list(mat.mean(axis=1).sort_values().head(3).index))

    stab = pd.DataFrame({
        "label": labs,
        "spearman_vs_published_window": [smat.loc[l, base_lab] for l in labs],
        "kendall_vs_published_window": [kendall[l] for l in labs],
        "akxai_esi": [mat.loc[ak, l] for l in labs],
        "akxai_rank": [rank.loc[ak, l + "_rank"] for l in labs],
        "akxai_barren_pct": ak_barren,
        "akxai_barren_rank": barrel_rank,
        "n_counties_rank_span0": int((out["rank_span"] == 0).sum()),
        "n_counties_rank_span_ge3": n_swing3,
    })
    stab.to_csv(os.path.join(DATA, "results_county_window_stability.csv"),
                index=False, encoding="utf-8-sig")
    ww = pd.concat(w_by_half.values(), ignore_index=True)
    ww.round(6).to_csv(os.path.join(DATA, "results_county_window_weights.csv"),
                       index=False, encoding="utf-8-sig")
    print("\n已写入: results_county_window_multiscale.csv / _landcover.csv / _stability.csv / _weights.csv")
    print("（未改动任何既有文件；results_county_esi.csv 等仅只读引用）")
    src.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())