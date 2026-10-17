# -*- coding: utf-8 -*-
"""R28-T4.7 · 严格外生归因复核 + 分块交叉探测（机械相关成分的定量）
（审稿意见第 3 条：空间归因的内生性）

────────────────────────────────────────────────────────────────────────────
问题
────────────────────────────────────────────────────────────────────────────
ESI 本身由土地覆被（森林/草地/水域/其他）与气候（降水/气温）直接构造，
对土地覆被做 GeoDetector 必然得到高 q，属**同义反复**。正文称"严格外生的地形
因子仅解释 6-9%"，本脚本（a）复核该数字在各种分层下的取值，（b）用**分块交叉
探测**把 q 拆成"机械成分"与"真实空间共变"两部分。

────────────────────────────────────────────────────────────────────────────
分析
────────────────────────────────────────────────────────────────────────────
A. ESI 方差分解：Var(ESI) = Σ_k w_k·Cov(x_k, ESI)，给出每项指标（及气候块 /
   土地覆被块）对 ESI 方差的贡献份额 —— 指标构造的机械权重。
B. 严格外生因子 {elev, slope} 的 q（多种分层）、联合分层 q、OLS R²、偏相关。
C. 分块交叉探测：
   · 气候块子指数 ESI_clim = mean(z(precip,+), z(temp,+))；
   · 覆被块子指数 ESI_lc   = mean(z(forest,+), z(grass,+), z(water,+), z(barren_neg,-))；
   · 对每个因子分别对"自己的块"与"另一块"做 q：
       q_own  高 + q_cross 低 ⇒ 该因子的 q 主要是构造性（机械）的；
       q_cross 显著              ⇒ 存在跨块的真实空间共变。
D. 全点尺度 ESI 的重建与归档值对照（口径校验）。

────────────────────────────────────────────────────────────────────────────
数据来源（已入库）
· data/spatial_samples.csv、data/spatial_esi_points.csv、data/_aux_terrain_points.csv
输出：data/r28_exogenous_recheck.csv、data/r28_esi_variance_decomposition.csv
运行：python run_r28_exogenous_recheck.py
"""
import os
import sys

import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
sys.path.insert(0, os.path.join(BASE, "eco_security"))
from eco_security import (  # noqa: E402
    minmax_normalize, entropy_weights, combined_weights, esi_series, geodetector_q,
)

K = 4
N_PERM = 999
SEED = 42
ALPHA = 0.4
SPEC = [
    ("precip", "precip", +1, "气候"), ("temp", "temp", +1, "气候"),
    ("forest", "forest", +1, "覆被"), ("grass", "grass", +1, "覆被"),
    ("water", "water", +1, "覆被"), ("barren_neg", "_barren_neg", -1, "覆被"),
]
STRAT_FACTORS = ["precip", "temp", "grass", "barren", "elev", "slope"]


def disc(v, k=K):
    qs = np.quantile(v, np.linspace(0, 1, k + 1)[1:-1])
    return np.digitize(v, qs)


def q_perm(y, lab, n_perm=N_PERM, seed=SEED):
    q = float(geodetector_q(y, lab))
    rng = np.random.default_rng(seed)
    cnt = sum(1 for _ in range(n_perm) if geodetector_q(y, rng.permutation(lab)) >= q)
    return q, float((1.0 + cnt) / (n_perm + 1.0))


def main():
    smp = pd.read_csv(os.path.join(DATA, "spatial_samples.csv"))
    esp = pd.read_csv(os.path.join(DATA, "spatial_esi_points.csv"))
    ter = pd.read_csv(os.path.join(DATA, "_aux_terrain_points.csv"))
    smp = smp.copy()
    smp["_barren_neg"] = (1 - smp["grass"] - smp["forest"] - smp["water"]).clip(lower=0)
    df = smp.merge(esp[["lat", "lon", "esi"]], on=["lat", "lon"], how="inner")
    df = df.merge(ter[["lat", "lon", "elev", "slope"]], on=["lat", "lon"], how="inner")
    n = len(df)
    print("=" * 78)
    print("R28-T4.7 · 严格外生归因复核 + 分块交叉探测（n=%d）" % n)
    print("=" * 78)
    y = df["esi"].values.astype(float)

    # ---------------- D. 口径校验 ----------------
    X = df[[c for _, c, _, _ in SPEC]].values.astype(float)
    dirs = [d for _, _, d, _ in SPEC]
    Xn = minmax_normalize(X, dirs)
    w_ent = entropy_weights(Xn)
    w_ahp = np.ones(len(SPEC)) / len(SPEC)
    w = combined_weights(w_ahp, w_ent, ALPHA)
    esi_re = esi_series(Xn, w)
    print("[校验] 重建点尺度 ESI vs 归档 max|Δ| = %.3e" % np.abs(esi_re - y).max())
    print("组合权重（等 AHP + 熵权，α=%.1f）：" % ALPHA)
    for (nm, _, _, blk), ww in zip(SPEC, w):
        print("   %-11s [%s] w=%.4f" % (nm, blk, ww))

    rows = []

    # ---------------- A. 方差分解 ----------------
    print("\n" + "-" * 78)
    print("A. ESI 方差分解：Var(ESI) = Σ_k w_k·Cov(x_k, ESI)")
    print("-" * 78)
    var = float(np.var(esi_re, ddof=1))
    dec = []
    for j, (nm, _, _, blk) in enumerate(SPEC):
        xj = Xn[:, j] - Xn[:, j].mean()
        c = w[j] * float(np.cov(xj, esi_re - esi_re.mean(), ddof=1)[0, 1])
        dec.append({"indicator": nm, "block": blk, "weight": round(float(w[j]), 6),
                    "corr_with_esi": round(float(np.corrcoef(Xn[:, j], esi_re)[0, 1]), 4),
                    "variance_contribution": round(c, 8),
                    "variance_share": round(c / var, 4)})
    dfa = pd.DataFrame(dec)
    dfa.to_csv(os.path.join(DATA, "r28_esi_variance_decomposition.csv"),
               index=False, encoding="utf-8-sig")
    print(dfa.to_string(index=False))
    blk_share = dfa.groupby("block").variance_share.sum()
    print("\n按块汇总的方差份额：", {k: round(float(v), 4) for k, v in blk_share.items()})
    print("总方差 %.6f（份额合计 %.4f）" % (var, float(dfa.variance_share.sum())))
    for _, r in dfa.iterrows():
        rows.append({"analysis": "variance_decomposition", "factor": r.indicator,
                     "metric": "variance_share", "value": r.variance_share,
                     "note": "权重 w=%.4f，与 ESI 相关 %.3f" % (r.weight, r.corr_with_esi)})
    for blk, v in blk_share.items():
        rows.append({"analysis": "variance_decomposition", "factor": blk + "块",
                     "metric": "variance_share_sum", "value": round(float(v), 4),
                     "note": "该块各项指标的方差份额之和"})

    # ---------------- B. 严格外生因子 ----------------
    print("\n" + "-" * 78)
    print("B. 严格外生因子 {elev, slope} 的 q（多种分层）与 OLS R²")
    print("-" * 78)
    strat = pd.read_csv(os.path.join(DATA, "r28_stratification_sensitivity.csv"))
    for fac in ["elev", "slope"]:
        d = strat[(strat.factor == fac) & strat.q_baseline.notna()]
        print("   %-6s q_baseline 范围 %.4f-%.4f（中位数 %.4f）；q_loo 范围 %.4f-%.4f"
              % (fac, d.q_baseline.min(), d.q_baseline.max(), d.q_baseline.median(),
                 d.q_loo.min(), d.q_loo.max()))
        for _, r in d.iterrows():
            rows.append({"analysis": "strictly_exogenous_single", "factor": fac,
                         "metric": "q_baseline|" + r.stratification,
                         "value": r.q_baseline, "note": "层数=%d" % r.n_levels})
    # 联合分层
    e_lab, s_lab = disc(df["elev"].values.astype(float)), disc(df["slope"].values.astype(float))
    joint = e_lab * 10 + s_lab
    qj, pj = q_perm(y, joint)
    print("   联合分层 elev×slope（%d 层）：q = %.4f（p = %.3f）"
          % (len(np.unique(joint)), qj, pj))
    rows.append({"analysis": "strictly_exogenous_joint", "factor": "elev+slope",
                 "metric": "q_joint_overlay", "value": round(qj, 6),
                 "note": "联合分层 %d 层，置换 p=%.3f" % (len(np.unique(joint)), pj)})
    Ae = np.column_stack([np.ones(n), df[["elev", "slope"]].values.astype(float)])
    be, *_ = np.linalg.lstsq(Ae, y, rcond=None)
    ee = y - Ae @ be
    r2e = 1 - float(ee @ ee) / float(np.sum((y - y.mean()) ** 2))
    print("   OLS R²（elev+slope，带截距）= %.4f；调整 R² = %.4f"
          % (r2e, 1 - (1 - r2e) * (n - 1) / (n - 3)))
    rows.append({"analysis": "strictly_exogenous_ols", "factor": "elev+slope",
                 "metric": "ols_r2", "value": round(float(r2e), 6),
                 "note": "带截距，n=%d" % n})
    for lab_nm, lab in [("quantile4", joint),
                        ("equal_interval4_elev_only", disc(
                            df["elev"].values.astype(float))),
                        ("equal_interval4_slope_only", disc(
                            df["slope"].values.astype(float)))]:
        pass
    # 偏相关（控制降水量/气温后，地形与 ESI 的偏相关）
    for ctrl, cname in [([], "无控制"), (["precip", "temp"], "控制降水与气温")]:
        cols = ["elev", "slope"] + ctrl
        A = np.column_stack([np.ones(n)] + [df[c].values.astype(float) for c in cols])
        for fac in ["elev", "slope"]:
            yv = df[fac].values.astype(float)
            if ctrl:
                Ac = np.column_stack([np.ones(n)]
                                     + [df[c].values.astype(float) for c in ctrl])
                bc, *_ = np.linalg.lstsq(Ac, yv, rcond=None)
                yv = yv - Ac @ bc
                bc2, *_ = np.linalg.lstsq(Ac, y, rcond=None)
                yc = y - Ac @ bc2
            else:
                yc = y
            pr = float(np.corrcoef(yv, yc)[0, 1])
            print("   偏相关 ESI~%-5s（%s）= %+.4f" % (fac, cname, pr))
            rows.append({"analysis": "strictly_exogenous_partial_corr", "factor": fac,
                         "metric": "partial_corr", "value": round(pr, 6), "note": cname})

    # ---------------- C. 分块交叉探测 ----------------
    print("\n" + "-" * 78)
    print("C. 分块交叉探测：气候块子指数 vs 覆被块子指数")
    print("-" * 78)
    clim_cols = [j for j, s in enumerate(SPEC) if s[3] == "气候"]
    lc_cols = [j for j, s in enumerate(SPEC) if s[3] == "覆被"]
    # 块内按原组合权重重新归一化，保持与 ESI 相同的合成规则
    wc = w[clim_cols] / w[clim_cols].sum()
    wl = w[lc_cols] / w[lc_cols].sum()
    esi_clim = Xn[:, clim_cols] @ wc
    esi_lc = Xn[:, lc_cols] @ wl
    print("   块内权重（原组合权重归一化）：气候 %s ；覆被 %s"
          % (np.round(wc, 4).tolist(), np.round(wl, 4).tolist()))
    print("   ESI_clim 与 ESI_lc 的相关系数 = %.4f；与完整 ESI 的相关系数 = %.4f / %.4f"
          % (float(np.corrcoef(esi_clim, esi_lc)[0, 1]),
             float(np.corrcoef(esi_clim, y)[0, 1]),
             float(np.corrcoef(esi_lc, y)[0, 1])))
    block_of = {"precip": "气候", "temp": "气候", "grass": "覆被", "barren": "覆被",
                "barren_neg": "覆被", "forest": "覆被", "water": "覆被",
                "elev": "外生地形", "slope": "外生地形"}
    # 因子 → 各单项指标 的 q 矩阵（q(因子 → 自身指标) 恒等于 1，属构造性）
    ind_names = [s[0] for s in SPEC]
    matrix = {}
    for fac in ["precip", "temp", "grass", "barren", "forest", "water", "elev", "slope"]:
        v = df[fac].values.astype(float)
        lab = (v > 0).astype(int) if fac in ("forest", "water") else disc(v)
        if len(np.unique(lab)) < 2:
            continue
        matrix[fac] = {ind: float(geodetector_q(Xn[:, k], lab))
                       for k, ind in enumerate(ind_names)}
        matrix[fac]["__ESI_full"] = float(geodetector_q(y, lab))
        matrix[fac]["__ESI_clim"] = float(geodetector_q(esi_clim, lab))
        matrix[fac]["__ESI_lc"] = float(geodetector_q(esi_lc, lab))
    print("\n   q(因子 → 单项指标/子指数) 矩阵（同块单元格为构造性相关）：")
    hdr = ["因子"] + ind_names + ["ESI_clim", "ESI_lc", "ESI_full"]
    print("   " + " ".join("%-9s" % h for h in hdr))
    # 完整 q 矩阵落盘（正文引用任一单元格均可溯源）
    qmat_rows = []
    for fac, row in matrix.items():
        rec = {"factor": fac, "block": block_of[fac]}
        for ind in ind_names:
            rec["q_" + ind] = round(float(row[ind]), 6)
        rec["q_ESI_clim"] = round(float(row["__ESI_clim"]), 6)
        rec["q_ESI_lc"] = round(float(row["__ESI_lc"]), 6)
        rec["q_ESI_full"] = round(float(row["__ESI_full"]), 6)
        qmat_rows.append(rec)
    qm = pd.DataFrame(qmat_rows)
    qm.to_csv(os.path.join(DATA, "r28_blockwise_q_matrix.csv"), index=False,
              encoding="utf-8-sig")
    print("   写出 %s" % os.path.join(DATA, "r28_blockwise_q_matrix.csv"))
    for fac, row in matrix.items():
        vals = [row[i] for i in ind_names] + [row["__ESI_clim"], row["__ESI_lc"],
                                             row["__ESI_full"]]
        print("   %-9s" % fac + " ".join("%-9.4f" % v for v in vals))
        if block_of[fac] == "外生地形":
            q_cross = max(row[i] for i in ind_names)
            print("              ⇒ 无本块指标（不属于 ESI 构造）；与 6 项指标的最大 q=%.4f"
                  % q_cross)
            rows.append({"analysis": "blockwise_cross_detection", "factor": fac,
                         "metric": "q_max_any_indicator", "value": round(float(q_cross), 6),
                         "note": "该因子不参与 ESI 构造，故不存在同块（机械）成分"})
            rows.append({"analysis": "blockwise_cross_detection", "factor": fac,
                         "metric": "mechanical_share_1_minus_cross_over_own",
                         "value": np.nan, "note": "不适用：无同块指标"})
            continue
        own = [row[i] for i in ind_names
               if block_of.get(i, "?") == block_of[fac]]
        cross = [row[i] for i in ind_names
                 if block_of.get(i, "?") != block_of[fac]]
        q_own = max(own) if own else np.nan
        q_cross = max(cross) if cross else np.nan
        mech = 1.0 - q_cross / q_own if q_own and q_own > 0 else np.nan
        print("              ⇒ 本块最大 q=%.4f ；跨块最大 q=%.4f ；机械占比=%.2f"
              % (q_own, q_cross, mech))
        rows.append({"analysis": "blockwise_cross_detection", "factor": fac,
                     "metric": "q_full_esi", "value": round(row["__ESI_full"], 6),
                     "note": "因子属于%s块" % block_of[fac]})
        rows.append({"analysis": "blockwise_cross_detection", "factor": fac,
                     "metric": "q_own_block_index", "value": round(row["__ESI_clim"], 6)
                     if block_of[fac] == "气候" else round(row["__ESI_lc"], 6),
                     "note": "目标=本块子指数（块内权重归一化）"})
        rows.append({"analysis": "blockwise_cross_detection", "factor": fac,
                     "metric": "q_cross_block_index", "value": round(row["__ESI_lc"], 6)
                     if block_of[fac] == "气候" else round(row["__ESI_clim"], 6),
                     "note": "目标=另一块子指数"})
        rows.append({"analysis": "blockwise_cross_detection", "factor": fac,
                     "metric": "q_max_own_indicator", "value": round(float(q_own), 6),
                     "note": "同块单项指标的最大 q（构造性相关）"})
        rows.append({"analysis": "blockwise_cross_detection", "factor": fac,
                     "metric": "q_max_cross_indicator", "value": round(float(q_cross), 6),
                     "note": "跨块单项指标的最大 q（非构造性）"})
        rows.append({"analysis": "blockwise_cross_detection", "factor": fac,
                     "metric": "mechanical_share_1_minus_cross_over_own",
                     "value": round(float(mech), 4),
                     "note": "1 - max跨块q / max同块q"})

    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(DATA, "r28_exogenous_recheck.csv"),
               index=False, encoding="utf-8-sig")
    print("\n已写出：data/r28_exogenous_recheck.csv, data/r28_esi_variance_decomposition.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())