# -*- coding: utf-8 -*-
"""R28 · T2 —— 去冗余 ESI 重构与全链重跑（权重 / 逐年序列 / 障碍度 / 空间归因 / 预测）

重构方案（与 r28_core.DEREDUNDANT_SETS 同源）
  baseline9      论文现用 9 指标（对照）
  drop_X9        删响应层 X9_生态用地%（= X3+X4+X5 的完全重复）
  drop_X8        删影响层 X8_草地变化率（= X3 的年变化率，状态量的导数）
  drop_X8_X9     同时删 X8、X9（= R19 的 S3 口径，7 指标）
  primary6       R28 主推去冗余：再删恒等式残差项 X6_裸地荒漠% → 6 指标 {X1,X2,X3,X4,X5,X7}
  substitute5    替代组合：删 X3/X4/X5/X6，保留 X8 与 X9 → 5 指标 {X1,X2,X7,X8,X9}

重跑范围
  ① 组合权重（熵权/AHP/α=0.4）与逐指标权重差
  ② 2005–2023 逐年去冗余 ESI vs 基准（max|Δ|、Pearson、Spearman、等级是否改变）
  ③ 障碍度诊断（O=(1−x')·w 逐行归一化；top 因子是否改变）
  ④ 空间归因（点尺度 1914 样本 GeoDetector q；基准 vs 去冗余指标集下的留一目标 LOO）
  ⑤ 预警等级序列与 GM(1,1)/NGBM/ARIMA 预测（在去冗余 ESI 序列上）

输出
  data/r28_deredundancy_comparison.csv   统一长表（逐指标 / 逐年 / 逐结论）
  data/r28_deredundancy_series.csv       逐年 ESI 与等级（宽表，便于做图）

运行：python run_r28_t2_deredundancy.py
"""
import os
import sys

import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
OUT = os.path.join(DATA, "r28_deredundancy_comparison.csv")
OUT_SER = os.path.join(DATA, "r28_deredundancy_series.csv")

import r28_core as C  # noqa: E402
sys.path.insert(0, os.path.join(BASE, "eco_security"))
from eco_security import classify_warning, geodetector_q, gm11_forecast  # noqa: E402

SCEN = ["baseline9", "drop_X9", "drop_X8", "drop_X8_X9", "primary6", "substitute5"]
K_STRATA = 4
N_PERM = 999
SEED = 42

rows = []


def add(scope, scenario, item, **kw):
    rec = dict(scope=scope, scenario=scenario, item=item)
    rec.update(kw)
    rows.append(rec)


# ---------------------------------------------------------------------------
# 0) 情景求解
# ---------------------------------------------------------------------------
def main():
    C.self_check()
    res = {}
    for s in SCEN:
        keep = C.DEREDUNDANT_SETS[s]
        res[s] = C.compute(keep)
        r = res[s]
        print("\n[%s] %d 项：%s" % (s, len(r["keep"]), r["keep"]))
        print("   熵权   =", np.round(r["w_ent"], 4))
        print("   AHP权  =", np.round(r["w_ahp"], 4))
        print("   组合权 =", np.round(r["w"], 4))
        print("   ESI2023= %.4f  等级=%s  序列峰值年=%d"
              % (r["esi"][-1], r["levels"][-1], r["years"][int(np.argmax(r["esi"]))]))

    base = res["baseline9"]

    # ---------------------------------------------------------------------------
    # ① 权重对比
    # ---------------------------------------------------------------------------
    w_arch = pd.read_csv(os.path.join(DATA, "results_weights.csv")).set_index("indicator")
    for s in SCEN:
        r = res[s]
        for n, we, wa, wc in zip(r["keep"], r["w_ent"], r["w_ahp"], r["w"]):
            add("weights", s, "weight:" + n, layer=C.LAYER[n],
                value=round(float(wc), 6), entropy_w=round(float(we), 6), ahp_w=round(float(wa), 6),
                baseline_value=(round(float(base["w"][base["keep"].index(n)]), 6)
                                if n in base["keep"] else np.nan),
                delta=(round(float(wc) - float(base["w"][base["keep"].index(n)]), 6)
                       if n in base["keep"] else np.nan),
                note=("该指标在 %s 情景存活" % s))
        # 层权重合计
        for lay in ["Driving", "Pressure", "State", "Impact", "Response"]:
            idx = [i for i, n in enumerate(r["keep"]) if C.LAYER[n] == lay]
            v = float(r["w"][idx].sum()) if idx else 0.0
            add("weights", s, "layer_weight:" + lay, layer=lay, value=round(v, 6),
                note="%s 层在 %s 情景下的组合权重合计" % (lay, s))

    # 逐指标权重差（仅对两套都存活的指标）
    for s in ["drop_X9", "drop_X8", "drop_X8_X9", C.PRIMARY, "substitute5"]:
        r = res[s]
        common = [n for n in base["keep"] if n in r["keep"]]
        d = np.array([r["w"][r["keep"].index(n)] - base["w"][base["keep"].index(n)] for n in common])
        add("weights", s, "weight_delta_summary", n_common=len(common),
            value=round(float(np.abs(d).max()), 6), mean_abs=round(float(np.abs(d).mean()), 6),
            note="在 %d 个两套共有指标上，去冗余组合权 − 基准组合权的 max|Δ| / 平均|Δ|" % len(common))

    # ---------------------------------------------------------------------------
    # ② 逐年 ESI / 等级对比
    # ---------------------------------------------------------------------------
    ser = pd.DataFrame({"year": base["years"], "esi_baseline9": base["esi"],
                        "grade_baseline9": base["levels"]})
    for s in SCEN[1:]:
        r = res[s]
        ser["esi_" + s] = r["esi"]
        ser["grade_" + s] = r["levels"]
    for s in SCEN[1:]:
        r = res[s]
        d = r["esi"] - base["esi"]
        pr = C.pearson(r["esi"], base["esi"])
        sp = C.spearman(r["esi"], base["esi"])
        ndiff = int(sum(1 for a, b in zip(r["levels"], base["levels"]) if a != b))
        add("series", s, "esi_vs_baseline", max_abs_delta=round(float(np.abs(d).max()), 6),
            mean_abs_delta=round(float(np.abs(d).mean()), 6),
            pearson_r=round(pr[0], 6), pearson_p=round(pr[1], 3),
            spearman_rho=round(sp[0], 6), spearman_p=round(sp[1], 3),
            n_grade_changed=ndiff,
            peak_year=int(r["years"][int(np.argmax(r["esi"]))]),
            peak_value=round(float(r["esi"].max()), 6),
            peak_year_baseline=int(base["years"][int(np.argmax(base["esi"]))]),
            esi_2023=round(float(r["esi"][-1]), 6), grade_2023=r["levels"][-1],
            note=("与基准逐指标共同项无关；等级不同的年份数 = %d/19" % ndiff))
        for y, eb, ed, gb, gd in zip(r["years"], base["esi"], r["esi"], base["levels"], r["levels"]):
            add("series_year", s, "year_%d" % y, year=int(y), value=round(float(ed), 6),
                baseline_value=round(float(eb), 6), delta=round(float(ed - eb), 6),
                grade=gd, baseline_grade=gb,
                level_changed=bool(gd != gb),
                note="")

    # ---------------------------------------------------------------------------
    # ③ 障碍度诊断
    # ---------------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("障碍度诊断（O=(1−x')·w，逐行归一化）")
    print("=" * 78)
    for s in SCEN:
        r = res[s]
        ob = C.obstacle_degree(r["Xn"], r["w"])
        r["_ob"] = ob
        # top1 因子逐年
        tops = [r["keep"][int(np.argmax(ob[i]))] for i in range(len(r["years"]))]
        from collections import Counter
        cnt = Counter(tops)
        add("obstacle", s, "top1_counts", note=str(dict(cnt)),
            peak_year=None)
        for y, t in zip(r["years"], tops):
            add("obstacle_year", s, "top1_%d" % y, year=int(y), factor=t,
                value=round(float(ob[list(r["years"]).index(y)][r["keep"].index(t)]), 6),
                baseline_value=(round(float(base["_ob"][list(base["years"]).index(y)][
                    base["keep"].index(t)]), 6) if t in base["keep"] and y in base["years"] else np.nan),
                note="")
        # 论文的两个阶段：2005–2010 / 2011–2023
        def phase_mean(ob_, years_, keep_, lo, hi):
            m = [i for i, y in enumerate(years_) if lo <= y <= hi]
            return {n: float(ob_[m, j].mean()) for j, n in enumerate(keep_)}
        p1 = phase_mean(ob, r["years"], r["keep"], 2005, 2010)
        p2 = phase_mean(ob, r["years"], r["keep"], 2011, 2023)
        b1 = phase_mean(base["_ob"], base["years"], base["keep"], 2005, 2010)
        b2 = phase_mean(base["_ob"], base["years"], base["keep"], 2011, 2023)
        for tag, p, bp in [("2005-2010", p1, b1), ("2011-2023", p2, b2)]:
            order = sorted(p.items(), key=lambda kv: -kv[1])
            for rank, (n, v) in enumerate(order, 1):
                add("obstacle_phase", s, "phase_%s" % tag, factor=n, layer=C.LAYER[n],
                    value=round(v, 6), rank=rank,
                    baseline_value=(round(bp[n], 6) if n in bp else np.nan),
                    note="%s 阶段第 %d 位障碍因子" % (tag, rank))
        # 关键：论文称恢复期 top3 = 水域 0.233 / 森林 0.221 / 生态用地 0.151；平台期 top2 = 草地变化率 0.364 / 农田 0.206
        add("obstacle_phase", s, "paper_claim_check", 
            value=(round(p1.get("X5_水域占比%", np.nan), 4) if "X5_水域占比%" in p1 else np.nan),
            baseline_value=round(p1.get("X4_森林占比%", np.nan), 4),
            note=("恢复期(2005-2010)均值：水域=%.4f 森林=%.4f 生态用地=%.4f；平台期(2011-2023)均值："
                  "草地变化率=%.4f 农田=%.4f。论文引用值 0.233/0.221/0.151 与 0.364/0.206。"
                  % (p1.get("X5_水域占比%", np.nan), p1.get("X4_森林占比%", np.nan),
                     p1.get("X9_生态用地%", np.nan), p2.get("X8_草地变化率", np.nan),
                     p2.get("X7_农田占比%", np.nan))))

    # ---------------------------------------------------------------------------
    # ④ 空间归因（点尺度 GeoDetector；基准 vs 去冗余）
    # ---------------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("空间归因（点尺度，1914 样本，K=%d 分位分层，置换 %d 次，seed=%d）" % (K_STRATA, N_PERM, SEED))
    print("=" * 78)
    smp = pd.read_csv(os.path.join(DATA, "spatial_samples.csv"))
    esp = pd.read_csv(os.path.join(DATA, "spatial_esi_points.csv"))
    dfp = smp.merge(esp[["lat", "lon", "esi"]], on=["lat", "lon"], how="inner")
    print("合并样本 =", len(dfp), "（归档 spatial_esi_points.csv 共", len(esp), "点）")
    dfp["_barren_neg"] = (1 - dfp["grass"] - dfp["forest"] - dfp["water"]).clip(lower=0)

    FULL6 = [("precip", "precip", +1), ("temp", "temp", +1), ("forest", "forest", +1),
             ("grass", "grass", +1), ("water", "water", +1), ("barren_neg", "_barren_neg", -1)]
    # 去冗余：删去补集项（= 1−grass−forest−water），剩 5 项
    CORE5 = [s for s in FULL6 if s[0] != "barren_neg"]
    FACTOR_COL = {"precip": "precip", "temp": "temp", "grass": "grass", "barren": "barren"}


    def build(df_, spec, alpha=C.ALPHA):
        X = df_[[c for _, c, _ in spec]].values.astype(float)
        dirs = [d for _, _, d in spec]
        Xn = C.minmax_normalize(X, dirs)
        we = C.entropy_weights(Xn)
        wa = np.ones(len(spec)) / len(spec)
        w = C.combined_weights(wa, we, alpha)
        return C.esi_series(Xn, w), Xn, we, w


    def discretize(v, k=K_STRATA):
        qs = np.quantile(v, np.linspace(0, 1, k + 1)[1:-1])
        return np.digitize(v, qs)


    def detect(x, y, seed=SEED, n_perm=N_PERM):
        strata = discretize(x)
        q = geodetector_q(y, strata)
        rng = np.random.default_rng(seed)
        cnt = sum(1 for _ in range(n_perm) if geodetector_q(y, rng.permutation(strata)) >= q)
        return float(q), (1.0 + cnt) / (n_perm + 1.0)


    esi6, Xn6, we6, w6 = build(dfp, FULL6)
    print("基准 6 项点尺度 ESI 重建 vs 归档 max|Δ| = %.3e"
          % float(np.abs(esi6 - dfp["esi"].values).max()))
    esi5, Xn5, we5, w5 = build(dfp, CORE5, alpha=C.ALPHA)
    print("去冗余 5 项（删补集项 barren_neg）ESI vs 基准 max|Δ| = %.3e；Spearman = %.4f"
          % (float(np.abs(esi5 - esi6).max()), C.spearman(esi5, esi6)[0]))

    for lab, spec, y in [("point_baseline6", FULL6, esi6), ("point_deredundant5", CORE5, esi5)]:
        for fac in ["precip", "temp", "grass", "barren"]:
            q, p = detect(dfp[FACTOR_COL[fac]].values, y)
            add("spatial_attribution", lab, "q_%s" % fac, factor=fac, value=round(q, 6), p_value=round(p, 4),
                note="目标 = %s 的 ESI" % lab)

    # 留一目标 LOO（在去冗余 5 项集上）
    for lab, spec, y in [("point_baseline6", FULL6, esi6), ("point_deredundant5", CORE5, esi5)]:
        for fac in ["precip", "temp", "grass", "barren"]:
            d = "barren_neg" if fac == "barren" else fac
            spec2 = [s for s in spec if s[0] != d]
            if len(spec2) == len(spec):
                add("spatial_attribution", lab, "q_loo_%s" % fac, factor=fac, value=np.nan,
                    note="该因子不在 %s 指标集内，LOO 不适用" % lab)
                continue
            y2, _, _, _ = build(dfp, spec2)
            q, p = detect(dfp[FACTOR_COL[fac]].values, y2)
            add("spatial_attribution", lab, "q_loo_%s" % fac, factor=fac, value=round(q, 6),
                p_value=round(p, 4), note="目标 = %s 剔除 %s 后的 ESI（剩 %d 项）" % (lab, d, len(spec2)))

    # 排序对比（基准 q 与 LOO q）
    for lab in ["point_baseline6", "point_deredundant5"]:
        qs = {r["factor"]: r["value"] for r in rows
              if r["scope"] == "spatial_attribution" and r["scenario"] == lab
              and r["item"].startswith("q_") and not r["item"].startswith("q_loo_")}
        ql = {r["factor"]: r["value"] for r in rows
              if r["scope"] == "spatial_attribution" and r["scenario"] == lab
              and r["item"].startswith("q_loo_")}
        add("spatial_attribution", lab, "rank_baseline", note=" > ".join(
            f"{k}={v:.4f}" for k, v in sorted(qs.items(), key=lambda kv: -kv[1])))
        add("spatial_attribution", lab, "rank_loo", note=" > ".join(
            f"{k}={v:.4f}" for k, v in sorted(ql.items(), key=lambda kv: -kv[1])))

    # ---------------------------------------------------------------------------
    # ⑤ 预测（在去冗余 ESI 序列上）
    # ---------------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("预测：GM(1,1) / NGBM / ARIMA（2005–2023 拟合，2024–2028 外推）")
    print("=" * 78)


    def ngbm(x0, gamma, n_pred=5):
        x1 = np.cumsum(x0)
        z1 = 0.5 * (x1[1:] + x1[:-1])
        B = np.column_stack([-z1, z1 ** gamma])
        Y = x0[1:]
        a_, b_ = np.linalg.lstsq(B, Y, rcond=None)[0]
        if abs(a_) < 1e-10:
            return None, None

        def X1f(t):
            return ((x0[0] ** (1 - gamma) - b_ / a_) * np.exp(-a_ * (1 - gamma) * t) + b_ / a_) ** (1 / (1 - gamma))
        xh = np.empty(len(x0))
        xh[0] = x0[0]
        for k in range(1, len(x0)):
            xh[k] = X1f(k) - X1f(k - 1)
        return np.array([X1f(len(x0) + k) - X1f(len(x0) + k - 1) for k in range(1, n_pred + 1)]), xh


    for s in SCEN:
        r = res[s]
        esi = r["esi"]
        fut, fit, C_, P_ = gm11_forecast(esi, n_pred=5)
        lvf = classify_warning(fut)
        best = None
        for g in np.arange(0.05, 1.96, 0.05):
            f_, fit_ = ngbm(esi, g)
            if fit_ is None:
                continue
            sse = float(np.sum((esi[1:] - fit_[1:]) ** 2))
            if best is None or sse < best[0]:
                best = (sse, g, f_, fit_)
        _, gopt, fut_n, fit_n = best
        from statsmodels.tsa.arima.model import ARIMA
        ba = None
        for p_, q_ in [(1, 0), (0, 1), (1, 1), (2, 1), (1, 2), (2, 2), (0, 2)]:
            try:
                m = ARIMA(esi, order=(p_, 1, q_)).fit()
                if ba is None or m.aic < ba[0]:
                    ba = (m.aic, (p_, 1, q_), m)
            except Exception:
                continue
        _, order, model = ba
        fut_a = np.asarray(model.forecast(5), dtype=float)
        for k, y in enumerate(range(2024, 2029)):
            add("forecast", s, "fc_%d" % y, year=y,
                value=round(float(fut[k]), 6), gm11=round(float(fut[k]), 6),
                ngbm=round(float(fut_n[k]), 6), arima=round(float(fut_a[k]), 6),
                grade=lvf[k],
                baseline_value=(round(float(res["baseline9"]["esi"][-1]), 6) if k == 0 else np.nan),
                note="GM(1,1) 后验 C=%.4f P=%.4f；NGBM γ=%.2f；ARIMA%s" % (C_, P_, gopt, order))
        add("forecast", s, "gm11_accuracy", value=round(float(C_), 6), p_value=round(float(P_), 6),
            note="C=后验差比值，P=小误差概率；C<0.35 且 P>0.95 为优")
        add("forecast", s, "fc_levels", value=round(float(res[s]["esi"][-1]), 4),
            note=("2024–2028 预测等级序列 = " + str(list(lvf))))

    out_rows = pd.DataFrame(rows)
    out_rows.to_csv(OUT, index=False, encoding="utf-8-sig")
    ser.to_csv(OUT_SER, index=False, encoding="utf-8-sig")

    print("\n" + "=" * 78)
    print("汇总：去冗余 vs 基准")
    print("=" * 78)
    summ = out_rows[out_rows["scope"] == "series"][
        ["scenario", "max_abs_delta", "mean_abs_delta", "pearson_r", "spearman_rho",
         "n_grade_changed", "peak_year", "esi_2023", "grade_2023"]]
    print(summ.to_string(index=False))
    print("\n已写出：data/%s（%d 行）, data/%s（%d 行）"
          % (os.path.basename(OUT), len(out_rows), os.path.basename(OUT_SER), len(ser)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
