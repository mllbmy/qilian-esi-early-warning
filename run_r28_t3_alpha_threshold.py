# -*- coding: utf-8 -*-
"""R28 · T3 —— α 与阈值的完整稳健性 + 熵权的插值方案敏感性

① 逐年等级转移矩阵：α = 0.0, 0.1, …, 1.0（11 点）× 2005–2023（19 年）
   → 每个 α 下的逐年等级、等级年数分布、相对 α=0.4 的改级年数
   → 复算论文两处断言：(a) 轻警年数由 16 降至 5；(b) α≥0.7 出现重警
② 阈值 ±0.05 扰动：4 个阈值（0.2/0.4/0.6/0.8）各 ±0.05，共 8 个扰动情景
   → 逐年等级变化、改级年数、等级年数分布
③ 熵权解释边界：草地变化率的熵权是否受土地覆被插值方案影响
   → 线性 / 三次样条 / PCHIP / 仅实测年 四种方案下重算熵权与组合权
   → 明确"熵权反映年际变率（离散度）而非生态重要性"

输出
  data/r28_alpha_grade_matrix.csv
  data/r28_threshold_perturbation.csv
  data/r28_interp_weight_sensitivity.csv

运行：python run_r28_t3_alpha_threshold.py
"""
import os
import sys
from collections import Counter

import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
import r28_core as C  # noqa: E402

SCEN = ["baseline9", "drop_X9", "drop_X8", "drop_X8_X9", C.PRIMARY, "substitute5"]
ALPHAS = [round(a, 1) for a in np.arange(0.0, 1.01, 0.1)]
GRADES = ["重警", "中警", "轻警", "较安全", "安全"]


def main():
    C.self_check()
    # =====================================================================
    # ① α 逐年等级转移矩阵
    # =====================================================================
    arows = []
    for s in SCEN:
        keep = C.DEREDUNDANT_SETS[s]
        for a in ALPHAS:
            r = C.compute(keep, alpha=a)
            cnt = Counter(r["levels"])
            for y, e, g in zip(r["years"], r["esi"], r["levels"]):
                arows.append(dict(scenario=s, alpha=a, year=int(y), esi=round(float(e), 6),
                                  grade=g))
            arows.append(dict(scenario=s, alpha=a, year="ALL", esi=np.nan, grade="",
                              n_severe=cnt.get("重警", 0), n_moderate=cnt.get("中警", 0),
                              n_mild=cnt.get("轻警", 0), n_relsafe=cnt.get("较安全", 0),
                              n_safe=cnt.get("安全", 0), n_indicators=len(r["keep"]),
                              esi_2023=round(float(r["esi"][-1]), 6),
                              grade_2023=r["levels"][-1],
                              grades_present="|".join(g for g in GRADES if cnt.get(g, 0) > 0)))
    adf = pd.DataFrame(arows)

    # 相对 α=0.4（论文口径）的改级年数 + 与 α=0.4 序列的 Spearman
    cmp_rows = []
    for s in SCEN:
        sub = adf[(adf.scenario == s) & (adf.year != "ALL")].copy()
        sub["year"] = sub["year"].astype(int)
        ref = sub[sub.alpha == 0.4].set_index("year")
        for a in ALPHAS:
            cur = sub[sub.alpha == a].set_index("year")
            n_chg = int((cur["grade"] != ref["grade"]).sum())
            rho = C.spearman(cur["esi"].values, ref["esi"].values)[0]
            cnt = Counter(cur["grade"])
            cmp_rows.append(dict(
                scenario=s, alpha=a, n_grade_changed_vs_alpha04=n_chg,
                spearman_vs_alpha04=round(float(rho), 6),
                n_severe=cnt.get("重警", 0), n_moderate=cnt.get("中警", 0),
                n_mild=cnt.get("轻警", 0), n_relsafe=cnt.get("较安全", 0), n_safe=cnt.get("安全", 0),
                esi_2023=round(float(cur.loc[2023, "esi"]), 6), grade_2023=cur.loc[2023, "grade"],
                first_year_changed=(",".join(str(y) for y in cur.index[cur["grade"] != ref["grade"]])
                                    if n_chg else "")))
    cdf = pd.DataFrame(cmp_rows)
    adf.to_csv(os.path.join(DATA, "r28_alpha_grade_matrix.csv"), index=False, encoding="utf-8-sig")
    cdf.to_csv(os.path.join(DATA, "r28_alpha_grade_summary.csv"), index=False, encoding="utf-8-sig")

    print("=" * 96)
    print("① α∈[0,1] 逐年等级年数分布（论文断言复算）")
    print("=" * 96)
    for s in SCEN:
        print("\n[%s] %d 指标" % (s, len(C.DEREDUNDANT_SETS[s])))
        print(cdf[cdf.scenario == s][["alpha", "n_severe", "n_moderate", "n_mild", "n_relsafe",
                                      "n_safe", "n_grade_changed_vs_alpha04", "grade_2023"]]
              .to_string(index=False))

    # =====================================================================
    # ② 阈值 ±0.05 扰动
    # =====================================================================
    trows = []
    for s in SCEN:
        keep = C.DEREDUNDANT_SETS[s]
        base = C.compute(keep, alpha=C.ALPHA)
        for i, t0 in enumerate(C.THRESHOLDS):
            for d in (-0.05, +0.05):
                thr = list(C.THRESHOLDS)
                thr[i] = t0 + d
                r = C.compute(keep, alpha=C.ALPHA, thresholds=thr)
                cnt = Counter(r["levels"])
                n_chg = int(sum(1 for a, b in zip(r["levels"], base["levels"]) if a != b))
                trows.append(dict(scenario=s, threshold_index=i + 1, threshold_original=t0,
                                  delta=d, threshold_perturbed=round(t0 + d, 4),
                                  thresholds_used="|".join("%.2f" % v for v in thr),
                                  n_grade_changed=n_chg,
                                  changed_years=",".join(str(y) for y, a, b in
                                                         zip(r["years"], r["levels"], base["levels"])
                                                         if a != b),
                                  n_severe=cnt.get("重警", 0), n_moderate=cnt.get("中警", 0),
                                  n_mild=cnt.get("轻警", 0), n_relsafe=cnt.get("较安全", 0),
                                  n_safe=cnt.get("安全", 0),
                                  grade_2023=r["levels"][-1],
                                  grade_2005=r["levels"][0],
                                  peak_year=int(r["years"][int(np.argmax(r["esi"]))])))
        # 每年逐阈值扰动下的等级集合
        for y in base["years"]:
            j = base["years"].index(y)
            gs = []
            for i, t0 in enumerate(C.THRESHOLDS):
                for d in (-0.05, +0.05):
                    thr = list(C.THRESHOLDS)
                    thr[i] = t0 + d
                    rr = C.compute(keep, alpha=C.ALPHA, thresholds=thr)
                    gs.append(rr["levels"][j])
            trows.append(dict(scenario=s, threshold_index=0, threshold_original=np.nan, delta=np.nan,
                              threshold_perturbed=np.nan, thresholds_used="", n_grade_changed=np.nan,
                              year=int(y), grade_base=base["levels"][j],
                              grades_under_perturbation="|".join(sorted(set(gs))),
                              n_distinct_grades=len(set(gs)),
                              note="该年在 8 个阈值扰动情景下出现过的等级"))
    tdf = pd.DataFrame(trows)
    tdf.to_csv(os.path.join(DATA, "r28_threshold_perturbation.csv"), index=False, encoding="utf-8-sig")

    print("\n" + "=" * 96)
    print("② 阈值 ±0.05 扰动：改级年数")
    print("=" * 96)
    pr = tdf[tdf.threshold_index > 0][["scenario", "threshold_original", "delta",
                                       "n_grade_changed", "changed_years", "grade_2023"]]
    print(pr.to_string(index=False))
    print("\n每年在 8 个扰动情景下的等级稳定性（仅 questionable 年份）")
    qy = tdf[(tdf.threshold_index == 0) & (tdf.n_distinct_grades > 1)][
        ["scenario", "year", "grade_base", "grades_under_perturbation"]]
    print(qy.to_string(index=False) if len(qy) else "  （无年份因阈值 ±0.05 改变等级）")

    # =====================================================================
    # ③ 熵权的插值方案敏感性
    # =====================================================================
    irows = []
    obs_years = [2005, 2010, 2015, 2020, 2023]
    for interp in ["linear", "cubic", "pchip", "observed"]:
        years = obs_years if interp == "observed" else None
        for s in SCEN:
            keep = C.DEREDUNDANT_SETS[s]
            try:
                r = C.compute(keep, interp=interp, alpha=C.ALPHA, years=years)
            except Exception as e:  # noqa: BLE001
                irows.append(dict(interp=interp, scenario=s, indicator="__ERROR__",
                                  note="%s: %s" % (type(e).__name__, e)))
                continue
            for n, we, wa, wc in zip(r["keep"], r["w_ent"], r["w_ahp"], r["w"]):
                irows.append(dict(
                    interp=interp, scenario=s, n_years=len(r["years"]),
                    year_list="|".join(str(y) for y in r["years"]),
                    indicator=n, layer=C.LAYER[n],
                    entropy_w=round(float(we), 6), ahp_w=round(float(wa), 6),
                    combined_w=round(float(wc), 6),
                    raw_series="|".join("%.4f" % v for v in r["raw"][n].values),
                    note=""))
            irows.append(dict(interp=interp, scenario=s, indicator="__SUMMARY__",
                              n_years=len(r["years"]),
                              entropy_w=round(float(r["w_ent"].max()), 6),
                              combined_w=round(float(r["esi"][-1]), 6),
                              note=("ESI_2023=%.4f 等级=%s" % (r["esi"][-1], r["levels"][-1]))))
    idf = pd.DataFrame(irows)
    idf.to_csv(os.path.join(DATA, "r28_interp_weight_sensitivity.csv"), index=False,
               encoding="utf-8-sig")

    print("\n" + "=" * 96)
    print("③ 插值方案 → 熵权（新文件 r28_interp_weight_sensitivity.csv）")
    print("=" * 96)
    key = ["X8_草地变化率", "X3_草地占比%", "X7_农田占比%", "X1_降水mm"]
    for s in ["baseline9", C.PRIMARY]:
        sub = idf[(idf.scenario == s) & (idf.indicator.isin(key))]
        if len(sub) == 0:
            continue
        piv = sub.pivot_table(index="indicator", columns="interp", values="entropy_w")
        print("\n[%s] 熵权" % s)
        print(piv.to_string())
        piv2 = sub.pivot_table(index="indicator", columns="interp", values="combined_w")
        print("[%s] 组合权（α=0.4）" % s)
        print(piv2.to_string())
    print("\n已写出：data/r28_alpha_grade_matrix.csv（%d 行）" % len(adf))
    print("        data/r28_alpha_grade_summary.csv（%d 行）" % len(cdf))
    print("        data/r28_threshold_perturbation.csv（%d 行）" % len(tdf))
    print("        data/r28_interp_weight_sensitivity.csv（%d 行）" % len(idf))
    return 0


if __name__ == "__main__":
    sys.exit(main())