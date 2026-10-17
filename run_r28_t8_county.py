# -*- coding: utf-8 -*-
"""R28 · T8 —— 县级指数可比性与不确定性（审稿意见第 5 条）

核心问题（三件事必须说清）
  (A) 县级 ESI 是**相对县际指数**：2020 单截面、11 县之间 min-max、质心窗口、
      县级截面重算权重、AHP 对 6 指标等权 ⇒ **不可与区域五级阈值直接比较**。
  (B) 窗口尺度 / 权重方案 / 指标选择三类不确定性对县排名的影响（Spearman + 排名位移）。
  (C) 现有脚本用「残差式」构造县级裸地指标：barren_neg = 100 − 林地 − 草地 − 水域 − 耕地
      （run_county_esi.py:48）。但 qilian_county_landcover.csv 的五类占比之和
      只有 97.99–100.00（CLCD 还有灌丛/冰雪/不透水面/湿地四类未计入），
      故残差式把未计入类别一并算成裸地，偏差最大 2.0126 个百分点（见
      data/r28_county_window_audit.csv）。本脚本给出**修正口径**（直接用 CLCD class-7 占比）
      及其对排名的影响。

另补：面积加权口径 vs 质心窗口口径的对比（复用已入库的分数覆被/支撑敏感性产物，
      不重新下载任何数据），以及**多年份县级 ESI 的数据限制说明**。

输出
  data/r28_county_uncertainty.csv

运行：python run_r28_t8_county.py
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
sys.path.insert(0, os.path.join(BASE, "eco_security"))
from eco_security import (  # noqa: E402
    combined_weights, entropy_weights, esi_series, minmax_normalize,
)
import io_utils  # noqa: E402
import r28_core as C  # noqa: E402

import rasterio  # noqa: E402
from rasterio.windows import from_bounds  # noqa: E402
from pyproj import Transformer  # noqa: E402

OUT = os.path.join(DATA, "r28_county_uncertainty.csv")
ALPHA = 0.4
QILIAN_COUNTIES = {
    "天祝": (37.20, 102.86), "肃南": (38.84, 99.62), "肃北": (39.51, 97.85),
    "阿克塞": (39.34, 94.34), "民乐": (38.43, 100.81), "山丹": (38.78, 101.09),
    "门源": (37.38, 101.62), "祁连": (38.18, 100.24), "刚察": (37.33, 100.14),
    "德令哈": (37.37, 97.36), "天峻": (37.30, 99.02),
}
HALVES = [0.05, 0.10, 0.20, 0.30]


def window_pcts(src, lat, lon, half):
    tf = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
    x0, y0 = tf.transform(lon - half, lat - half)
    x1, y1 = tf.transform(lon + half, lat + half)
    win = from_bounds(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1), src.transform)
    arr = src.read(1, window=win)
    vals, counts = np.unique(arr[arr != 0], return_counts=True)
    d = {int(v): int(c) for v, c in zip(vals, counts)}
    tot = sum(d.values())
    p = lambda c: (d.get(c, 0) * 100.0 / tot if tot else 0.0)  # noqa: E731
    return dict(cropland=p(1), forest=p(2), shrub=p(3), grass=p(4), water=p(5),
                snow_ice=p(6), barren=p(7), impervious=p(8), wetland=p(9))


def build(landcover_df, climate_df, indicator_mode, weight_mode):
    """按指标口径与权重方案算县 ESI。"""
    m = landcover_df.join(climate_df, how="inner")
    cols = ["precip_mm", "temp_c", "forest_pct", "grass_pct", "water_pct"]
    if indicator_mode == "residual_barren":          # 论文现用口径（残差式）
        barren = 100.0 - m["forest_pct"] - m["grass_pct"] - m["water_pct"] - m["crop_pct"]
        names = cols + ["barren_residual_pct"]
        dirs = [+1, +1, +1, +1, +1, -1]
    elif indicator_mode == "clcd_barren":            # 修正口径（CLCD class-7 真值）
        barren = m["barren_pct"]
        names = cols + ["barren_clcd_pct"]
        dirs = [+1, +1, +1, +1, +1, -1]
    elif indicator_mode == "no_barren":              # 敏感性：完全去掉裸地指标
        barren = None
        names = cols
        dirs = [+1, +1, +1, +1, +1]
    elif indicator_mode == "composition_full":       # 敏感性：五类覆被全上（含耕地）
        barren = m["barren_pct"]
        X0 = np.column_stack([m[cols].values, m["barren_pct"].values, m["crop_pct"].values])
        names = cols + ["barren_clcd_pct", "crop_pct"]
        dirs = [+1, +1, +1, +1, +1, -1, -1]
    else:
        raise ValueError(indicator_mode)
    if indicator_mode != "composition_full":
        X0 = np.column_stack([m[cols].values] + ([barren.values] if barren is not None else []))
    Xn = minmax_normalize(X0.astype(float), dirs)
    we = entropy_weights(Xn)
    wa = np.ones(len(names)) / len(names)
    if weight_mode == "entropy":
        w = we
    elif weight_mode == "ahp_equal":
        w = wa
    elif weight_mode == "combined":
        w = combined_weights(wa, we, ALPHA)
    elif weight_mode == "equal":
        w = np.ones(len(names)) / len(names)
    else:
        raise ValueError(weight_mode)
    return pd.Series(esi_series(Xn, w), index=m.index), m, names, w, we, wa


def ranks(x):
    return pd.Series(x).rank(ascending=False, method="min").astype(int)


def main():
    lcdir = io_utils.resolve_lc_dir()
    src = rasterio.open(os.path.join(lcdir, "CLCD_v01_2020_albert.tif"))
    cli = pd.read_csv(os.path.join(DATA, "qilian_climate.csv"))
    cli = cli[cli.unit != "区域(祁连山盒)"]
    cnt_cli = cli.groupby("unit")[["precip_mm", "temp_c"]].mean()

    # 逐窗口计算土地覆被
    rows = []
    for half in HALVES:
        recs = {}
        for unit, (lat, lon) in QILIAN_COUNTIES.items():
            p = window_pcts(src, lat, lon, half)
            recs[unit] = dict(forest_pct=p["forest"], grass_pct=p["grass"],
                              water_pct=p["water"], crop_pct=p["cropland"],
                              barren_pct=p["barren"], shrub_pct=p["shrub"],
                              snow_ice_pct=p["snow_ice"], impervious_pct=p["impervious"],
                              wetland_pct=p["wetland"],
                              five_class_sum=(p["cropland"] + p["forest"] + p["grass"]
                                              + p["water"] + p["barren"]),
                              omitted_sum=(p["shrub"] + p["snow_ice"] + p["impervious"]
                                           + p["wetland"]))
        rows.append((half, pd.DataFrame(recs).T))

    results = {}
    for half, lc in rows:
        for imode in ["residual_barren", "clcd_barren", "no_barren", "composition_full"]:
            for wmode in ["combined", "entropy", "ahp_equal", "equal"]:
                esi, m, names, w, we, wa = build(lc, cnt_cli, imode, wmode)
                results[(half, imode, wmode)] = dict(esi=esi, w=w, we=we, wa=wa, names=names)

    # 参照口径 = 论文现用：±0.10° + residual_barren + combined
    ref_key = (0.10, "residual_barren", "combined")
    ref_esi = results[ref_key]["esi"]
    ref_rank = ranks(ref_esi)

    orow = []

    def add(scope, **kw):
        kw["scope"] = scope
        orow.append(kw)

    # ---- (C) 残差式 vs CLCD 真值：逐县差异 ----
    for half, lc in rows:
        for unit in lc.index:
            r = lc.loc[unit]
            resid = 100.0 - r["forest_pct"] - r["grass_pct"] - r["water_pct"] - r["crop_pct"]
            add("barren_formula", window="±%.2f°" % half, unit=unit,
                value=round(float(r["barren_pct"]), 6),
                baseline_value=round(float(resid), 6),
                delta=round(float(r["barren_pct"] - resid), 6),
                note=("CLCD class-7 真实裸地占比 %.4f vs 残差式 %.4f；差 %.4f 个百分点 = "
                      "未计入的灌丛/冰雪/不透水面/湿地合计 %.4f"
                      % (r["barren_pct"], resid, r["barren_pct"] - resid, r["omitted_sum"])))
        # 五类之和
        for unit in lc.index:
            add("five_class_closure", window="±%.2f°" % half, unit=unit,
                value=round(float(lc.loc[unit, "five_class_sum"]), 6),
                note="五类（耕地+林地+草地+水域+裸地）占比之和；=100 表示无未计入类别")

    # ---- (B) 三类不确定性的排名影响 ----
    def compare(tag, esi, ref_esi, ref_rank):
        rk = ranks(esi)
        sp = C.spearman(esi.values, ref_esi.values)
        shift = (rk - ref_rank)
        add("ranking_uncertainty", window=tag, unit="__SUMMARY__",
            value=round(float(sp[0]), 6), p_value=round(float(sp[1]), 6),
            max_abs_delta=round(float(np.abs(esi.values - ref_esi.values).max()), 6),
            n_rank_changed=int((rk != ref_rank).sum()),
            max_rank_shift=int(shift.abs().max()),
            note=("与参照口径（±0.10° + 残差式裸地 + 组合权）相比：Spearman ρ=%.4f，"
                  "%d/11 个县排名改变，最大位移 %d" % (sp[0], int((rk != ref_rank).sum()),
                                                     int(shift.abs().max()))))
        for unit in esi.index:
            add("ranking_detail", window=tag, unit=unit,
                value=round(float(esi[unit]), 6), rank=int(rk[unit]),
                baseline_value=round(float(ref_esi[unit]), 6), baseline_rank=int(ref_rank[unit]),
                rank_shift=int(rk[unit] - ref_rank[unit]),
                note="")

    for half in HALVES:
        compare("±%.2f°|residual|combined" % half, results[(half, "residual_barren", "combined")]["esi"],
                ref_esi, ref_rank)
    for wmode in ["entropy", "ahp_equal", "equal"]:
        compare("±0.10°|residual|%s" % wmode, results[(0.10, "residual_barren", wmode)]["esi"],
                ref_esi, ref_rank)
    for imode in ["clcd_barren", "no_barren", "composition_full"]:
        compare("±0.10°|%s|combined" % imode, results[(0.10, imode, "combined")]["esi"],
                ref_esi, ref_rank)
    # 交叉：最优组合（修正裸地 + 四窗口）
    for half in HALVES:
        compare("±%.2f°|clcd_barren|combined" % half,
                results[(half, "clcd_barren", "combined")]["esi"], ref_esi, ref_rank)

    # ---- 排名稳定性总表：跨 4 窗口 × 4 权重 × 4 指标口径 ----
    all_ranks = {}
    for key, v in results.items():
        all_ranks["±%.2f°|%s|%s" % key] = ranks(v["esi"])
    rdf = pd.DataFrame(all_ranks)
    for unit in rdf.index:
        add("rank_stability_grid", window="all_combinations", unit=unit,
            value=round(float(rdf.loc[unit].mean()), 3),
            rank_min=int(rdf.loc[unit].min()), rank_max=int(rdf.loc[unit].max()),
            rank_span=int(rdf.loc[unit].max() - rdf.loc[unit].min()),
            n_configs=len(rdf.columns),
            note=("在 %d 个（窗口×权重×指标口径）组合下：排名 %d–%d，跨度 %d；"
                  "参照排名 %d" % (len(rdf.columns), int(rdf.loc[unit].min()),
                                   int(rdf.loc[unit].max()),
                                   int(rdf.loc[unit].max() - rdf.loc[unit].min()),
                                   int(ref_rank[unit]))))

    # ---- (D) 面积加权口径 vs 质心窗口：复用已入库产物 ----
    for f, nm in [("results_county_window_multiscale.csv", "质心窗口多尺度"),
                  ("results_county_window_vs_polygon.csv", "窗口 vs 多边形（面积加权）"),
                  ("results_county_support_sensitivity.csv", "支撑敏感性（多边形/点均值）")]:
        p = os.path.join(DATA, f)
        if not os.path.exists(p):
            add("area_weighted", window=nm, unit="__MISSING__",
                note="文件不存在：data/%s" % f)
            continue
        d = pd.read_csv(p)
        add("area_weighted", window=nm, unit="__FILE__", value=len(d),
            note=("已入库产物 data/%s（%d 行），列：%s"
                  % (f, len(d), "|".join(d.columns[:12]))))
        if "rank_A" in d.columns and "rank_B" in d.columns:
            for _, r in d.iterrows():
                add("area_weighted_detail", window=nm, unit=r.get("unit"),
                    value=float(r.get("esi_published_A", np.nan)),
                    rank=int(r["rank_A"]), baseline_rank=int(r["rank_B"]),
                    rank_shift=int(r.get("rank_shift_B", 0)),
                    note=("窗口口径 ESI=%.4f（排名 %d） vs 面积加权/多边形口径 ESI=%.4f（排名 %d），"
                          "位移 %+d" % (r.get("esi_published_A", np.nan), int(r["rank_A"]),
                                        r.get("esi_polygon_B", np.nan), int(r["rank_B"]),
                                        int(r.get("rank_shift_B", 0)))))

    # ---- (A) 可比性声明 + (E) 数据限制 ----
    add("comparability", window="__STATEMENT__", unit="__ALL__",
        note=("县级 ESI 为相对县际指数：2020 单截面；min-max 只在 11 个县级单元之间做；"
              "土地覆被取县级质心 ±0.10° 窗口；权重在县级截面上重算（熵权+等权 AHP，α=0.4）；"
              "故其数值刻度与区域 ESI 时间序列不可比，五级阈值"
              "（安全[0.8,1]/较安全[0.6,0.8)/轻警[0.4,0.6)/中警[0.2,0.4)/重警[0,0.2)）"
              "是区域年度序列的分级口径，**不能直接套到县级截面上**。"))
    add("data_limitation", window="__STATEMENT__", unit="__ALL__",
        note=("多年份县级 ESI 不可算：本机 data/_raw/lc_data 仅有 CLCD_v01_2020_albert.tif "
              "一个年度（实测枚举见该目录 glob 结果），qilian_county_landcover.csv 也只有 2020 一列；"
              "要算多年县级序列须下载 CLCD 2005/2010/2015 等年度栅格（各约 0.8 GB）。"
              "本轮未下载，故县级结论一律限定为 2020 静态截面。"))
    add("comparability", window="__REFERENCE_RANK__", unit="__ALL__",
        note="参照口径排名：" + "; ".join("%s=%d" % (u, ref_rank[u]) for u in ref_rank.index))

    out = pd.DataFrame(orow)
    out.to_csv(OUT, index=False, encoding="utf-8-sig")

    print("=" * 110)
    print("T8 县级指数不确定性与可比性")
    print("=" * 110)
    print("\n[参照口径] ±0.10° + 残差式裸地 + 组合权；县级排名：")
    print(ref_rank.sort_values().to_string())

    print("\n(C) 残差式 vs CLCD 真实裸地占比（±0.10°）")
    q = out[(out.scope == "barren_formula") & (out.window == "±0.10°")]
    print(q[["unit", "value", "baseline_value", "delta"]].to_string(index=False))

    print("\n(B) 三类不确定性对排名的影响")
    q = out[(out.scope == "ranking_uncertainty")]
    print(q[["window", "value", "n_rank_changed", "max_rank_shift", "max_abs_delta"]]
          .rename(columns={"value": "spearman_rho"}).to_string(index=False))

    print("\n排名稳定性（跨 %d 个组合）" % len(rdf.columns))
    print(out[out.scope == "rank_stability_grid"][
        ["unit", "rank_min", "rank_max", "rank_span", "value"]].to_string(index=False))

    print("\n(D) 面积加权/多边形口径")
    for r in out[out.scope == "area_weighted_detail"].itertuples():
        print("  " + r.note)

    print("\n已写出 data/%s（%d 行）" % (os.path.basename(OUT), len(out)))
    return 0


if __name__ == "__main__":
    sys.exit(main())