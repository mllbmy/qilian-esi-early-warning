# -*- coding: utf-8 -*-
"""R28 · T5 —— ESI 变化的机制分解、2005 年端点效应、断点检验（审稿意见第 7 条）

① 逐指标贡献分解（2005→2023，以及峰值 2010→2023）
   ΔESI_i = Σ_j w_j·Δx'_ij  （权重在时间上恒定，故无"权重变化项"；残差仅浮点误差）
   并给出每项的符号贡献与占比，解释 2005 年低值与 2010 年峰值由谁主导。

② 2005 年是否为土地覆被插值端点效应
   证据链：
   · qilian_landcover.csv 只有 2005/2010/2015/2020/2023 五个实测年 → 2005 是线性插值的
     西端点，其左邻实测年不存在，故 2005 年 X3/X4/X5/X7/X6/X9 的取值为实测值本身；
   · X8_草地变化率在 2005 年被 pct_change().fillna(0) 人为置 0（无前一年可比），
     这是构造值而非观测；
   · 逐年线性插值是否使 2005 成为"最差点"：与用观测年重算（2005/2010/2015/2020/2023）
     的 ESI 序列对比。

③ 分段趋势 / 断点检验
   · Pettitt 检验（非参数变点，给出突变年与 p 值）
   · 全期 Mann-Kendall（含自相关方差修正，见 T6）
   · 2010–2023 分段 Mann-Kendall + Sen's slope
   · 滑动起点/终点分段扫描（2010/2011/2012 起）

输出
  data/r28_esi_decomposition.csv
  data/r28_trend_break.csv

运行：python run_r28_t5_mechanism.py
"""
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
OUT_D = os.path.join(DATA, "r28_esi_decomposition.csv")
OUT_B = os.path.join(DATA, "r28_trend_break.csv")
import r28_core as C  # noqa: E402
import r28_trend as T  # noqa: E402  （趋势/变点检验的单一真源，与 T6 共用）

mk_sen = T.mk_plain
sen_ci = T.sen_slope_ci
hamed_rao = T.hamed_rao_mk
tfpw_mk = T.tfpw_mk

SCEN = ["baseline9", "drop_X9", "drop_X8", "drop_X8_X9", C.PRIMARY, "substitute5"]
OBS_YEARS = [2005, 2010, 2015, 2020, 2023]


def main():
    C.self_check()
    drow, brow = [], []

    # =====================================================================
    # ① 逐指标贡献分解
    # =====================================================================
    for s in SCEN:
        r = C.compute(C.DEREDUNDANT_SETS[s])
        years = r["years"]
        Xn, w, keep = r["Xn"], r["w"], r["keep"]
        esi = r["esi"]
        i0, i1 = 0, len(years) - 1
        peak = int(np.argmax(esi))
        for tag, a, b in [("2005->2023", i0, i1), ("%d(peak)->2023" % years[peak], peak, i1)]:
            d_esi = esi[b] - esi[a]
            contrib = w * (Xn[b] - Xn[a])
            resid = d_esi - contrib.sum()
            for n, c, wa in zip(keep, contrib, w):
                drow.append(dict(
                    scope="contribution", scenario=s, window=tag,
                    year_from=int(years[a]), year_to=int(years[b]), indicator=n,
                    layer=C.LAYER[n], direction=int(r["directions"][keep.index(n)]),
                    combined_w=round(float(wa), 6),
                    x_from=round(float(Xn[a][keep.index(n)]), 6),
                    x_to=round(float(Xn[b][keep.index(n)]), 6),
                    delta_x=round(float(Xn[b][keep.index(n)] - Xn[a][keep.index(n)]), 6),
                    contribution=round(float(c), 6),
                    contribution_pct_of_delta_esi=(round(float(c / d_esi * 100), 4)
                                                   if abs(d_esi) > 1e-12 else np.nan),
                    delta_esi=round(float(d_esi), 6),
                    residual=round(float(resid), 12),
                    note="ΔESI = Σ_j w_j·Δx'_j（权重恒定，无权重变化项；残差=浮点误差）"))
            # 分层合计
            for lay in sorted(set(C.LAYER[n] for n in keep)):
                idx = [i for i, n in enumerate(keep) if C.LAYER[n] == lay]
                drow.append(dict(
                    scope="contribution_layer", scenario=s, window=tag,
                    year_from=int(years[a]), year_to=int(years[b]), layer=lay,
                    combined_w=round(float(w[idx].sum()), 6),
                    contribution=round(float(contrib[idx].sum()), 6),
                    delta_esi=round(float(d_esi), 6),
                    contribution_pct_of_delta_esi=(round(float(contrib[idx].sum() / d_esi * 100), 4)
                                                   if abs(d_esi) > 1e-12 else np.nan),
                    note="%s 层对 ΔESI 的合计贡献" % lay))
        # 逐项逐年差分贡献（2006→2023 的相邻年差分，用于"谁在拉低")
        for k in range(1, len(years)):
            d_esi = esi[k] - esi[k - 1]
            contrib = w * (Xn[k] - Xn[k - 1])
            for n, c in zip(keep, contrib):
                drow.append(dict(
                    scope="contribution_yoy", scenario=s, window="%d->%d" % (years[k - 1], years[k]),
                    year_from=int(years[k - 1]), year_to=int(years[k]), indicator=n,
                    layer=C.LAYER[n], combined_w=round(float(w[keep.index(n)]), 6),
                    delta_x=round(float(Xn[k][keep.index(n)] - Xn[k - 1][keep.index(n)]), 6),
                    contribution=round(float(c), 6), delta_esi=round(float(d_esi), 6),
                    contribution_pct_of_delta_esi=(round(float(c / d_esi * 100), 4)
                                                   if abs(d_esi) > 1e-12 else np.nan),
                    note=""))
        # 2005 年"最差"由哪些指标造成：以各指标在该年的标准化值排序
        order05 = sorted(zip(keep, Xn[0], w), key=lambda t: t[1] * t[2])
        drow.append(dict(scope="diagnosis_2005", scenario=s, window="2005",
                         indicator="|".join(n for n, _, _ in order05),
                         combined_w=np.nan, x_to=round(float(esi[0]), 6),
                         contribution=np.nan, delta_esi=np.nan,
                         note=("%s 情景 2005 年标准化值加权项升序（最差在前）：" % s
                               + "; ".join("%s x'=%.4f w=%.4f 加权=%.4f" % (n, xv, wv, xv * wv)
                                           for n, xv, wv in order05))))
    # 2005 端点效应：观测年 vs 全插值年
    for s in SCEN:
        keep = C.DEREDUNDANT_SETS[s]
        r_all = C.compute(keep, interp="linear")
        r_obs = C.compute(keep, interp="observed")
        j = r_all["years"].index(2005)
        drow.append(dict(
            scope="endpoint_2005", scenario=s, window="2005",
            indicator="__ESI@2005__", combined_w=np.nan,
            x_to=round(float(r_all["esi"][j]), 6),
            contribution=round(float(r_obs["esi"][0]), 6),
            delta_esi=round(float(r_all["esi"][j] - r_obs["esi"][0]), 6),
            note=("全期插值口径 ESI_2005=%.4f（%.4f 分位，排名第 %d/%d）；"
                  "仅用 5 个实测年重算 ESI_2005=%.4f。2005 年是线性插值的西端点，"
                  "其覆被值 = 实测值本身（无外推），故 2005 年覆被不由插值引入偏差；"
                  "但 X8_草地变化率在 2005 年被 pct_change().fillna(0) 置 0，属构造值。"
                  % (r_all["esi"][j], stats.percentileofscore(r_all["esi"], r_all["esi"][j]) / 100.0,
                     int(stats.rankdata(r_all["esi"])[j]), len(r_all["esi"]), r_obs["esi"][0]))))
        # 具体到各指标 2005 年是否实测
        raw = r_all["raw"]
        for n in keep:
            drow.append(dict(
                scope="endpoint_2005_detail", scenario=s, window="2005", indicator=n,
                x_to=round(float(raw.loc[2005, n]), 6),
                note=("2005 年为 CLCD 实测年（qilian_landcover.csv 首个实测年）" if n.startswith("X3")
                      or n.startswith("X4") or n.startswith("X5") or n.startswith("X7")
                      or n.startswith("X6") or n.startswith("X9") else
                      ("2005 年由 pct_change().fillna(0) 人为置 0（无前一年可比）" if n.startswith("X8")
                       else "气候为逐年 CRU 实测值，与插值无关"))))
    ddf = pd.DataFrame(drow)
    ddf.to_csv(OUT_D, index=False, encoding="utf-8-sig")

    print("=" * 100)
    print("① 2005→2023 与 2010(峰值)→2023 的逐指标贡献分解（ΔESI = Σ w·Δx'）")
    print("=" * 100)
    for s in ["baseline9", C.PRIMARY]:
        sub = ddf[(ddf.scope == "contribution") & (ddf.scenario == s)]
        for tag in sub.window.unique():
            q = sub[sub.window == tag].sort_values("contribution")
            print("\n[%s] %s  ΔESI=%.4f" % (s, tag, q["delta_esi"].iloc[0]))
            print(q[["indicator", "layer", "combined_w", "x_from", "x_to", "delta_x",
                     "contribution", "contribution_pct_of_delta_esi"]].to_string(index=False))
    print("\n分层贡献：")
    lz = ddf[ddf.scope == "contribution_layer"][
        ["scenario", "window", "layer", "combined_w", "contribution", "delta_esi",
         "contribution_pct_of_delta_esi"]]
    print(lz[lz.scenario.isin(["baseline9", C.PRIMARY])].to_string(index=False))

    print("\n" + "=" * 100)
    print("② 2005 年诊断")
    print("=" * 100)
    for s in ["baseline9", C.PRIMARY]:
        q = ddf[(ddf.scope == "diagnosis_2005") & (ddf.scenario == s)]
        print("\n[%s] %s" % (s, q["note"].iloc[0]))
        q2 = ddf[(ddf.scope == "endpoint_2005") & (ddf.scenario == s)]
        print("   " + q2["note"].iloc[0])

    # =====================================================================
    # ③ 断点与分段趋势
    # =====================================================================
    for s in SCEN:
        r = C.compute(C.DEREDUNDANT_SETS[s])
        y = r["esi"]
        yr = np.array(r["years"])
        K, tau, p = T.pettitt(y)
        mk = T.mk_plain(y)
        hr = T.hamed_rao_mk(y)
        brow.append(dict(scenario=s, test="pettitt_full", series="2005-2023",
                         statistic=round(K, 4), p_value=round(p, 6),
                         Z=round(K, 4),
                         change_point_year=int(yr[tau]) if tau > 0 else None,
                         note="Pettitt 非参数变点检验；U_t 绝对值最大处即变点"))
        for i, (a, b) in enumerate([(2005, 2023), (2010, 2023), (2011, 2023), (2012, 2023)]):
            m = (yr >= a) & (yr <= b)
            r2 = T.mk_plain(y[m])
            r3 = T.hamed_rao_mk(y[m])
            b_, lo_, hi_ = T.sen_slope_ci(yr[m].astype(float), y[m])
            brow.append(dict(scenario=s, test="MK_full" if i == 0 else "MK_segment",
                             series="%d-%d" % (a, b), n_years=int(m.sum()),
                             S=round(r2["S"], 3), Z=round(r2["Z"], 4), p_value=round(r2["p"], 6),
                             sen_slope=round(b_, 6),
                             sen_lo=round(lo_, 6), sen_hi=round(hi_, 6),
                             Z_hamed_rao=round(r3["Z_corrected"], 4) if r3["stable"] else np.nan,
                             p_hamed_rao=round(r3["p_corrected"], 6) if r3["stable"] else np.nan,
                             hamed_rao_stable=bool(r3["stable"]),
                             hamed_rao_factor=round(r3["n_nstar"], 4),
                             n_sig_lags=r3["n_sig_lags"],
                             Z_uncorrected=round(r2["Z"], 4), p_uncorrected=round(r2["p"], 6),
                             note=("分段 MK + Sen's slope（斜率置信区间为 Sen 1968 秩方差口径，"
                                   "名义 95%）" if i else "全期 MK + Sen's slope")))
        # 滑动起点扫描
        for a in [2009, 2010, 2011, 2012, 2013]:
            m = yr >= a
            r2 = T.mk_plain(y[m])
            b_, lo_, hi_ = T.sen_slope_ci(yr[m].astype(float), y[m])
            brow.append(dict(scenario=s, test="MK_rolling_start", series="%d-2023" % a,
                             n_years=int(m.sum()), Z=round(r2["Z"], 4), p_value=round(r2["p"], 6),
                             sen_slope=round(b_, 6), sen_lo=round(lo_, 6),
                             sen_hi=round(hi_, 6),
                             note="以 %d 为起点的分段趋势扫描" % a))
        # 2005 是否异常值：相对中位数的 z 分数
        rz, med, mad = T.robust_z_2005(y)
        brow.append(dict(scenario=s, test="outlier_2005", series="2005",
                         statistic=round(rz, 4) if np.isfinite(rz) else None,
                         p_value=np.nan, sen_slope=np.nan,
                         note=("2005 年相对序列中位数的稳健 z 分数（MAD 口径）；"
                               "|z|>3.5 通常记为离群")))
        # 去掉 2005 后的全期趋势
        r2 = T.mk_plain(y[1:])
        b_, lo_, hi_ = T.sen_slope_ci(yr[1:].astype(float), y[1:])
        brow.append(dict(scenario=s, test="MK_drop2005", series="2006-2023", n_years=len(y) - 1,
                         Z=round(r2["Z"], 4), p_value=round(r2["p"], 6),
                         sen_slope=round(b_, 6), sen_lo=round(lo_, 6),
                         sen_hi=round(hi_, 6),
                         note="剔除 2005 年后的全期 MK（检验 2005 年是否主导趋势方向）"))
    bdf = pd.DataFrame(brow)
    bdf.to_csv(OUT_B, index=False, encoding="utf-8-sig")

    print("\n" + "=" * 100)
    print("③ 断点与分段趋势（Pettitt / MK 全期 / MK 分段 / Hamed-Rao 修正 / Sen 斜率 CI）")
    print("=" * 100)
    for s in ["baseline9", C.PRIMARY, "substitute5"]:
        q = bdf[(bdf.scenario == s) & (bdf.test.isin(["pettitt_full", "MK_full", "MK_segment",
                                                      "MK_drop2005", "outlier_2005"]))]
        print("\n[%s]" % s)
        print(q[["test", "series", "n_years", "Z", "p_value", "sen_slope", "sen_lo", "sen_hi",
                 "Z_hamed_rao", "p_hamed_rao", "named"]].to_string(index=False)
              if "named" in q.columns else
              q[["test", "series", "n_years", "Z", "p_value", "sen_slope", "sen_lo", "sen_hi",
                 "Z_hamed_rao", "p_hamed_rao"]].to_string(index=False))
    print("\n已写出 data/%s（%d 行）, data/%s（%d 行）"
          % (os.path.basename(OUT_D), len(ddf), os.path.basename(OUT_B), len(bdf)))
    return 0


if __name__ == "__main__":
    sys.exit(main())