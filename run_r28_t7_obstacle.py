# -*- coding: utf-8 -*-
"""R28 · T7 —— 障碍度方法补齐（审稿意见第 8 条）

① 公式与权重处理方式（可验证的算式核对）
   障碍度采用「因子贡献度 × 指标偏离度」的经典式：
       偏离度  D_ij = 1 − x'_ij                （x' 为极差标准化值，∈[0,1]）
       因子贡献 F_j = w_j                     （组合权重，Σ_j w_j = 1）
       障碍度  O_ij = D_ij·F_j                （未归一化）
       归一化  O*_ij = O_ij / Σ_j O_ij        （论文图 10 的"每年各指标之和为 1"口径）
   核对项：Σ_j O*_ij = 1（逐年）、O* 与 (1−x')·w 的恒等关系、以及**权重方案**取
   熵权 / AHP / 组合权（α=0.4）三种时 O* 的差异。

② 阶段划分依据（2005–2010 / 2011–2023 的"可验证判据"）
   不预设口径，逐条检验三个候选判据：
     (a) ESI 峰值年：argmax(ESI) = 2010 → 分段点 2010/2011
     (b) 数据驱动变点：Pettitt 检验 / 分段均值差最大化
     (c) 政策阶段：2005–2010 对应"三北防护林四期/退牧还草"等既有政策期，属**叙事判据**，
         无法用本研究数据验证，只能标注为引用性依据
   给出各判据的分段点数值与偏差。

③ 权重方案敏感性
   熵权 / AHP / 组合权（α=0.4）/ 等权 四种方案下，两个阶段各自的 top 障碍因子排序。

输出
  data/r28_obstacle_sensitivity.csv
  data/r28_obstacle_formula_check.csv

运行：python run_r28_t7_obstacle.py
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
OUT_S = os.path.join(DATA, "r28_obstacle_sensitivity.csv")
OUT_F = os.path.join(DATA, "r28_obstacle_formula_check.csv")
import r28_core as C  # noqa: E402

SCEN = ["baseline9", "drop_X9", "drop_X8", "drop_X8_X9", C.PRIMARY, "substitute5"]
PHASES = [(2005, 2010), (2011, 2023)]


def pettitt_k(y):
    y = np.asarray(y, dtype=float)
    n = len(y)
    U = np.zeros(n)
    for t in range(1, n):
        U[t] = sum(np.sign(y[t:] - y[i]).sum() for i in range(t))
    K = float(np.max(np.abs(U)))
    tau = int(np.argmax(np.abs(U)))
    p = float(min(2.0 * np.exp(-6.0 * K ** 2 / (n ** 3 + n ** 2)), 1.0))
    return K, tau, p


def main():
    C.self_check()
    srow, frow = [], []
    scheme_names = ["entropy", "ahp", "combined(alpha=0.4)", "equal"]

    # ---------------------------------------------------------------
    # ① + ③ 逐方案障碍度
    # ---------------------------------------------------------------
    for s in SCEN:
        r = C.compute(C.DEREDUNDANT_SETS[s])
        keep, years = r["keep"], r["years"]
        schemes = {
            "entropy": r["w_ent"],
            "ahp": r["w_ahp"],
            "combined(alpha=0.4)": r["w"],
            "equal": np.ones(len(keep)) / len(keep),
        }
        for wname, w in schemes.items():
            O = (1.0 - r["Xn"]) * w[None, :]
            ssum = O.sum(axis=1, keepdims=True)
            On = O / np.where(ssum == 0, 1.0, ssum)
            for i, y in enumerate(years):
                for j, n in enumerate(keep):
                    frow.append(dict(
                        scope="obstacle_series", scenario=s, weight_scheme=wname, year=int(y),
                        indicator=n, layer=C.LAYER[n],
                        x_norm=round(float(r["Xn"][i, j]), 8),
                        weight=round(float(w[j]), 8),
                        deviation=round(float(1.0 - r["Xn"][i, j]), 8),
                        obstacle_raw=round(float(O[i, j]), 8),
                        obstacle_normalized=round(float(On[i, j]), 8),
                        row_sum_raw=round(float(ssum[i, 0]), 8),
                        row_sum_normalized=round(float(On[i].sum()), 8),
                        identity_residual=round(float(O[i, j] - (1.0 - r["Xn"][i, j]) * w[j]), 12),
                        note="O=(1−x')·w；O*=O/ΣO"))
            for lo, hi in PHASES:
                m = [i for i, y in enumerate(years) if lo <= y <= hi]
                mean_ob = On[m, :].mean(axis=0)
                order = np.argsort(-mean_ob)
                for rank, j in enumerate(order, 1):
                    srow.append(dict(
                        scope="phase", scenario=s, weight_scheme=wname,
                        phase="%d-%d" % (lo, hi), rank=rank, indicator=keep[j],
                        layer=C.LAYER[keep[j]], mean_obstacle=round(float(mean_ob[j]), 6),
                        share_of_phase_sum=round(float(mean_ob[j] / mean_ob.sum()), 4),
                        note="%s 阶段 · %s 权重方案下第 %d 位障碍因子" % ("%d-%d" % (lo, hi), wname, rank)))
                srow.append(dict(
                    scope="phase_topsummary", scenario=s, weight_scheme=wname,
                    phase="%d-%d" % (lo, hi),
                    indicator=" > ".join(keep[j] for j in order[:3]),
                    mean_obstacle=round(float(mean_ob[order[0]]), 6),
                    note="top3 排序（%s）" % wname))
            # 逐年 top1
            for i, y in enumerate(years):
                j = int(np.argmax(On[i]))
                srow.append(dict(
                    scope="year_top1", scenario=s, weight_scheme=wname, year=int(y),
                    rank=1, indicator=keep[j], layer=C.LAYER[keep[j]],
                    mean_obstacle=round(float(On[i, j]), 6),
                    note="该年最大障碍因子"))

    # ---------------------------------------------------------------
    # ② 阶段划分依据
    # ---------------------------------------------------------------
    for s in SCEN:
        r = C.compute(C.DEREDUNDANT_SETS[s])
        y = r["esi"]
        yr = np.array(r["years"])
        K, tau, p = pettitt_k(y)
        cp = int(yr[tau])
        # 分段均值差最大化
        best = None
        for t in range(3, len(y) - 2):
            d = abs(y[t:].mean() - y[:t].mean())
            if best is None or d > best[0]:
                best = (d, t)
        # 峰值年
        peak = int(yr[int(np.argmax(y))])
        # 分段均值（按论文 2005-2010 / 2011-2023）
        m1 = yr <= 2010
        srow.append(dict(
            scope="phase_criterion", scenario=s, weight_scheme="combined(alpha=0.4)",
            phase="criterion",
            indicator="peak/pettitt/maxmeandiff",
            mean_obstacle=round(float(y[m1].mean() - y[~m1].mean()), 6),
            note=("判据(a) ESI 峰值年 = %d（论文分段点 2010/2011 与之%s）；"
                  "判据(b) Pettitt 变点年 = %d（K=%.2f, p=%.4f）；"
                  "判据(c) 分段均值差最大化点 = %d（|Δmean|=%.5f）。"
                  "论文 2005-2010 均值=%.4f、2011-2023 均值=%.4f，差=%.4f。"
                  "政策叙事判据（防护林/退牧还草工程期）无法用本文数据验证。"
                  % (peak, "一致" if peak == 2010 else "不一致", cp, K, p,
                     int(yr[best[1]]), best[0], y[m1].mean(), y[~m1].mean(),
                     y[m1].mean() - y[~m1].mean()))))

    # ---------------------------------------------------------------
    # 公式核对（对已归档的 data/results_obstacle.csv 也做一次）
    # ---------------------------------------------------------------
    arch = pd.read_csv(os.path.join(DATA, "results_obstacle.csv"), index_col=0)
    frow.append(dict(scope="archived_check", scenario="baseline9", weight_scheme="combined(alpha=0.4)",
                     year="ALL", indicator="__row_sum__",
                     row_sum_raw=np.nan, row_sum_normalized=round(float(arch.sum(axis=1).mean()), 8),
                     identity_residual=round(float((arch.sum(axis=1) - 1).abs().max()), 12),
                     note=("data/results_obstacle.csv 逐年行和均值 = %.8f，|行和−1| 最大 = %.2e "
                           "→ 归档障碍度确为逐行归一化口径"
                           % (arch.sum(axis=1).mean(), (arch.sum(axis=1) - 1).abs().max()))))
    # 论文引用值核对（恢复期 top3 / 平台期 top2）
    base = C.compute(C.DEREDUNDANT_SETS["baseline9"])
    O = (1.0 - base["Xn"]) * base["w"][None, :]
    On = O / O.sum(axis=1, keepdims=True)
    yr = np.array(base["years"])
    keep = base["keep"]
    p1 = On[yr <= 2010].mean(axis=0)
    p2 = On[yr >= 2011].mean(axis=0)
    for name, val, claim in [("X5_水域占比%", p1[keep.index("X5_水域占比%")], 0.233),
                             ("X4_森林占比%", p1[keep.index("X4_森林占比%")], 0.221),
                             ("X9_生态用地%", p1[keep.index("X9_生态用地%")], 0.151),
                             ("X8_草地变化率", p2[keep.index("X8_草地变化率")], 0.364),
                             ("X7_农田占比%", p2[keep.index("X7_农田占比%")], 0.206)]:
        frow.append(dict(scope="paper_claim", scenario="baseline9",
                         weight_scheme="combined(alpha=0.4)",
                         phase=("2005-2010" if name.startswith(("X5", "X4", "X9")) else "2011-2023"),
                         indicator=name, obstacle_normalized=round(float(val), 6),
                         paper_value=claim, delta_vs_paper=round(float(val - claim), 6),
                         note=("本脚本复算 %.4f vs 论文引用 %.3f（差 %+.4f）" % (val, claim, val - claim))))

    sdf = pd.DataFrame(srow)
    fdf = pd.DataFrame(frow)
    sdf.to_csv(OUT_S, index=False, encoding="utf-8-sig")
    fdf.to_csv(OUT_F, index=False, encoding="utf-8-sig")

    print("=" * 110)
    print("① 公式核对（O=(1−x')·w，逐行归一化）")
    print("=" * 110)
    chk = fdf[fdf.scope.isin(["archived_check"])]
    print(chk[["scope", "row_sum_normalized", "identity_residual", "note"]].to_string(index=False))
    ser = fdf[fdf.scope == "obstacle_series"]
    print("\n逐年行和与恒等残差（{0} 情景，三套权重方案）".format("baseline9"))
    for wn in scheme_names:
        q = ser[(ser.scenario == "baseline9") & (ser.weight_scheme == wn)]
        print("  %-22s 行和 min=%.8f max=%.8f；恒等残差 max=%.2e"
              % (wn, q.row_sum_normalized.min(), q.row_sum_normalized.max(),
                 q.identity_residual.abs().max()))
    print("\n论文引用值 vs 复算值：")
    print(fdf[fdf.scope == "paper_claim"][
        ["phase", "indicator", "obstacle_normalized", "paper_value", "delta_vs_paper"]].to_string(index=False))

    print("\n" + "=" * 110)
    print("② 阶段划分判据")
    print("=" * 110)
    for s in SCEN:
        q = sdf[(sdf.scope == "phase_criterion") & (sdf.scenario == s)]
        print("\n[%s] %s" % (s, q["note"].iloc[0]))

    print("\n" + "=" * 110)
    print("③ 权重方案敏感性：两阶段 top3")
    print("=" * 110)
    for s in ["baseline9", C.PRIMARY]:
        print("\n[%s]" % s)
        q = sdf[(sdf.scope == "phase_topsummary") & (sdf.scenario == s)]
        print(q[["phase", "weight_scheme", "indicator"]].to_string(index=False))
    print("\ntop1 因子逐年是否随权重方案改变（baseline9）")
    q = sdf[(sdf.scope == "year_top1") & (sdf.scenario == "baseline9")]
    piv = q.pivot_table(index="year", columns="weight_scheme", values="indicator", aggfunc="first")
    print(piv.to_string())
    print("\n已写出 data/%s（%d 数据行）, data/%s（%d 数据行）"
          % (os.path.basename(OUT_S), len(sdf), os.path.basename(OUT_F), len(fdf)))
    return 0


if __name__ == "__main__":
    sys.exit(main())