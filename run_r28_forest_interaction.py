# -*- coding: utf-8 -*-
"""R28-T4.5/4.6 · 森林小样本 q 的 bootstrap 区间 + 交互探测的不确定性与机械成分
（审稿意见第 3 条：空间归因的内生性）

────────────────────────────────────────────────────────────────────────────
4.5 森林（主导类仅 15 点）
────────────────────────────────────────────────────────────────────────────
· 二分主导类 forest（1/0）与**分数覆被** f_forest（results_fractional_cover_points.csv）
  两种口径的 q；
· 对 1,914 点做 2,000 次有放回自助 → q 的百分位区间；同时记录每次自助中
  森林主导点数；
· 参照系：生态用地二分（森林∪草地∪水域）、主导类标签（6 类）的 q；
· 目标同时给「完整 ESI」与「剔除 forest 后的 ESI」（LOO 口径）。

────────────────────────────────────────────────────────────────────────────
4.6 交互探测
────────────────────────────────────────────────────────────────────────────
· 对 6 个因子对：q1、q2、q12，以及 Wang 两套判据
  （q12 > max(q1,q2) 双因子增强；q12 > q1+q2 非线性增强）；
· 自助 2,000 次 → q12 的区间与关系类型分布；
· **置换检验**：固定因子 1 的分层、随机置换因子 2 的分层，破坏二者的空间配对，
  得到"空间独立"零分布下的 q12 → p = P(q12_perm ≥ q12_obs)。q12 超出该零分布的
  部分才是真正的交互，其余来自分层本身的解释力（机械成分）；
· 机械成分参照：主导类标签（6 类）的 q、每个因子对的非空联合层数。

────────────────────────────────────────────────────────────────────────────
数据来源（已入库）
· data/spatial_samples.csv、data/spatial_esi_points.csv、
  data/_aux_terrain_points.csv、data/results_fractional_cover_points.csv
输出：data/r28_forest_small_sample.csv、data/r28_interaction_uncertainty.csv
运行：python run_r28_forest_interaction.py
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
B = 2000
N_PERM = 999
SEED = 20261017
ALPHA = 0.4
FULL_SPEC = [
    ("precip", "precip", +1), ("temp", "temp", +1), ("forest", "forest", +1),
    ("grass", "grass", +1), ("water", "water", +1), ("barren_neg", "_barren_neg", -1),
]
PAIRS = [("grass", "barren"), ("precip", "barren"), ("precip", "grass"),
         ("temp", "barren"), ("temp", "precip"), ("temp", "grass")]


def disc(v, k=K):
    qs = np.quantile(v, np.linspace(0, 1, k + 1)[1:-1])
    return np.digitize(v, qs)


def q_of(y, x):
    xd = disc(x) if x.dtype != int else x
    return float(geodetector_q(y, xd))


def add_derived(df):
    df = df.copy()
    df["_barren_neg"] = (1 - df["grass"] - df["forest"] - df["water"]).clip(lower=0)
    return df


def build_esi(df, spec):
    X = df[[c for _, c, _ in spec]].values.astype(float)
    dirs = [d for _, _, d in spec]
    Xn = minmax_normalize(X, dirs)
    w = combined_weights(np.ones(len(spec)) / len(spec), entropy_weights(Xn), ALPHA)
    return esi_series(Xn, w)


def main():
    smp = add_derived(pd.read_csv(os.path.join(DATA, "spatial_samples.csv")))
    esp = pd.read_csv(os.path.join(DATA, "spatial_esi_points.csv"))
    ter = pd.read_csv(os.path.join(DATA, "_aux_terrain_points.csv"))
    fc = pd.read_csv(os.path.join(DATA, "results_fractional_cover_points.csv"))
    df = smp.merge(esp[["lat", "lon", "esi"]], on=["lat", "lon"], how="inner")
    df = df.merge(ter[["lat", "lon", "elev", "slope"]], on=["lat", "lon"], how="inner")
    df = df.merge(fc[["lat", "lon", "f_forest", "f_grass", "f_water", "f_barren",
                      "f_crop", "f_snow", "f_shrub"]], on=["lat", "lon"], how="inner")
    n = len(df)
    print("=" * 78)
    print("R28-T4.5/4.6 · 森林小样本与交互探测不确定性（n=%d，B=%d）" % (n, B))
    print("=" * 78)

    y = df["esi"].values
    spec_no_forest = [s for s in FULL_SPEC if s[0] != "forest"]
    y_loo_forest = build_esi(df, spec_no_forest)
    print("[校验] 重建 ESI vs 归档 max|Δ| = %.3e" % np.abs(build_esi(df, FULL_SPEC) - y).max())

    # ---------------- 4.5 森林 ----------------
    n_forest = int((df["forest"] == 1).sum())
    print("\n森林样本：主导类 = %d 点（占 %.2f%%）；f_forest>0 的点 = %d (%.1f%%)"
          % (n_forest, 100 * n_forest / n,
             int((df["f_forest"] > 0).sum()), 100 * (df["f_forest"] > 0).mean()))
    print("f_forest 分布：max=%.4f mean=%.4f 中位数=%.4f；二分化把 %.1f%% 的"
          "f_forest>0 点归零"
          % (df.f_forest.max(), df.f_forest.mean(), df.f_forest.median(),
             100 * float(((df.f_forest > 0) & (df.forest == 0)).sum()) / max(int((df.f_forest > 0).sum()), 1)))

    eco = ((df["forest"] == 1) | (df["grass"] == 1) | (df["water"] == 1)).astype(int).values
    cls_lab = df["class"].values.astype(int)
    ff = df["f_forest"].values.astype(float)
    pos = ff > 0

    def zero_inflated(v, k):
        """零膨胀分层：0 单列一层，正值按 (k-1) 分位再分。"""
        lab = np.zeros(len(v), dtype=int)
        if pos.sum() > 0:
            qs = np.quantile(v[pos], np.linspace(0, 1, k)[1:-1])
            lab[pos] = 1 + np.digitize(v[pos], qs)
        return lab

    cand = [
        # (名称, 分层标签, 目标, 层数, 备注)
        ("forest_quantile4_AS_ARCHIVED", disc(ff), y, int(len(np.unique(disc(ff)))),
         "归档口径：样本分位数 digitize 分层"),
        ("forest_dominant_binary_0_1", df["forest"].values.astype(int), y, 2,
         "主导类二分（0/1），n=15 正类"),
        ("f_forest_presence_binary", pos.astype(int), y, 2,
         "分数覆被存在性二分（f_forest>0，n=%d）" % int(pos.sum())),
        ("f_forest_zeroinflated4", zero_inflated(ff, 4), y,
         int(len(np.unique(zero_inflated(ff, 4)))), "零膨胀 4 层（0 + 正值 3 分位）"),
        ("f_forest_zeroinflated5", zero_inflated(ff, 5), y,
         int(len(np.unique(zero_inflated(ff, 5)))), "零膨胀 5 层（0 + 正值 4 分位）"),
        ("forest_dominant_binary_0_1_loo_target", df["forest"].values.astype(int),
         y_loo_forest, 2, "目标=剔除 forest 后的 ESI"),
        ("f_forest_presence_binary_loo_target", pos.astype(int), y_loo_forest, 2,
         "目标=剔除 forest 后的 ESI"),
        ("f_forest_zeroinflated4_loo_target", zero_inflated(ff, 4), y_loo_forest,
         int(len(np.unique(zero_inflated(ff, 4)))), "目标=剔除 forest 后的 ESI"),
        ("eco_land_binary_reference", eco, y, 2, "参照：生态用地（森林∪草地∪水域）二分"),
        ("dominant_class_label_reference", cls_lab, y, 6, "参照：主导类 6 类标签"),
    ]
    rng = np.random.default_rng(SEED)
    boot_idx = [rng.integers(0, n, size=n) for _ in range(B)]
    # 空间块自助（0.6° 瓦片）——处理空间自相关导致的独立样本量被高估
    gi = np.round((df["lat"].values - df["lat"].values.min()) / 0.15).astype(int)
    gj = np.round((df["lon"].values - df["lon"].values.min()) / 0.15).astype(int)
    tile = gi // 4 * 1000 + gj // 4
    tiles = np.unique(tile)
    tile_idx = {t: np.where(tile == t)[0] for t in tiles}
    rng2 = np.random.default_rng(SEED + 7)
    block_idx = []
    for _ in range(B):
        pick = rng2.choice(tiles, size=len(tiles), replace=True)
        block_idx.append(np.concatenate([tile_idx[t] for t in pick]))
    print("   空间块自助：%d 个 0.6° 瓦片，每次重抽 %d 个瓦片" % (len(tiles), len(tiles)))
    rows = []
    for name, lab, tgt, nlv, note in cand:
        q0 = float(geodetector_q(tgt, lab))
        qb = np.array([float(geodetector_q(tgt[i], lab[i])) for i in boot_idx])
        qb = qb[np.isfinite(qb)]
        qblk = np.array([float(geodetector_q(tgt[i], lab[i])) for i in block_idx])
        qblk = qblk[np.isfinite(qblk)]
        nf = np.array([int((df["forest"].values[i] == 1).sum()) for i in boot_idx])
        rows.append({
            "quantity": name, "note": note,
            "n_levels": int(nlv),
            "degenerate_single_stratum": bool(nlv < 2),
            "q": round(float(q0), 6),
            "q_note": ("分层退化为单层 → q 恒等于 0（该因子的 q 在此分层下不可用）"
                       if nlv < 2 else ""),
            "boot_mean": round(float(qb.mean()), 6),
            "boot_sd": round(float(qb.std(ddof=1)), 6),
            "boot_p2.5": round(float(np.percentile(qb, 2.5)), 6),
            "boot_p25": round(float(np.percentile(qb, 25)), 6),
            "boot_p50": round(float(np.percentile(qb, 50)), 6),
            "boot_p75": round(float(np.percentile(qb, 75)), 6),
            "boot_p97.5": round(float(np.percentile(qb, 97.5)), 6),
            "boot_width95": round(float(np.percentile(qb, 97.5) - np.percentile(qb, 2.5)), 6),
            "n_forest_in_bootstrap_mean": round(float(nf.mean()), 1),
            "n_forest_in_bootstrap_p2.5": int(np.percentile(nf, 2.5)),
            "n_forest_in_bootstrap_p97.5": int(np.percentile(nf, 97.5)),
            "boot_block_p2.5": round(float(np.percentile(qblk, 2.5)), 6),
            "boot_block_p97.5": round(float(np.percentile(qblk, 97.5)), 6),
            "boot_block_width95": round(float(np.percentile(qblk, 97.5)
                                              - np.percentile(qblk, 2.5)), 6),
            "bootstrap_reps": int(len(qb)),
            "block_bootstrap_reps": int(len(qblk)),
        })
    forest = pd.DataFrame(rows)
    forest.to_csv(os.path.join(DATA, "r28_forest_small_sample.csv"),
                  index=False, encoding="utf-8-sig")
    print("\n森林相关 q 的 bootstrap 区间（B=%d）：" % B)
    for _, r in forest.iterrows():
        print("   %-42s q=%.4f 点自助95%%CI %.4f~%.4f（宽 %.4f）| 块自助 %.4f~%.4f（宽 %.4f）| 层数=%d%s"
              % (r.quantity, r.q, r["boot_p2.5"], r["boot_p97.5"], r.boot_width95,
                 r["boot_block_p2.5"], r["boot_block_p97.5"], r.boot_block_width95,
                 r.n_levels, "  ← 退化" if r.degenerate_single_stratum else ""))
    print("   说明：%s" % forest.iloc[0].q_note)
    print("   f_forest>0 的点 %d 个（占 %.1f%%），但仅 15 点以森林为主导；"
          "二分化把 %.1f%% 的 f_forest>0 点归零"
          % (int(pos.sum()), 100 * pos.mean(),
             100 * float((pos & (df["forest"] == 0)).sum()) / max(int(pos.sum()), 1)))
    print("   自助中森林主导点数：均值 %.1f（2.5-97.5%%: %d-%d），原始 %d 个"
          % (forest.iloc[1]["n_forest_in_bootstrap_mean"],
             forest.iloc[1]["n_forest_in_bootstrap_p2.5"],
             forest.iloc[1]["n_forest_in_bootstrap_p97.5"], n_forest))

    # ---------------- 4.6 交互 ----------------
    print("\n" + "-" * 78)
    print("4.6 交互探测：q1/q2/q12、双套判据、自助区间与置换零分布")
    print("-" * 78)
    single = {f: (q_of(y, df[f].values.astype(float))) for f in
              ["temp", "precip", "grass", "barren", "elev", "slope"]}
    q_cls = float(geodetector_q(y, cls_lab))
    print("   单因子 q：", {k: round(v, 4) for k, v in single.items()})
    print("   参照：主导类 6 类标签 q = %.4f（土地覆被 one-hot 的联合分层的上界参照）" % q_cls)

    perm_rng = np.random.default_rng(SEED)
    rows = []
    for f1, f2 in PAIRS:
        s1, s2 = disc(df[f1].values.astype(float)), disc(df[f2].values.astype(float))
        joint = s1 * 10 + s2
        q1, q2 = q_of(y, df[f1].values.astype(float)), q_of(y, df[f2].values.astype(float))
        q12 = float(geodetector_q(y, joint))
        njoint = int(len(np.unique(joint)))
        # 置换零分布：固定 f1，置换 f2
        cnt = 0
        null = []
        for _ in range(N_PERM):
            s2p = perm_rng.permutation(s2)
            qp = float(geodetector_q(y, s1 * 10 + s2p))
            null.append(qp)
            if qp >= q12:
                cnt += 1
        null = np.array(null)
        p_perm = (1.0 + cnt) / (N_PERM + 1.0)
        # 自助
        q12b, q1b, q2b, relB, relN = [], [], [], [], []
        for bi in boot_idx:
            yy = y[bi]
            a1, a2 = s1[bi], s2[bi]
            v1 = float(geodetector_q(yy, a1))
            v2 = float(geodetector_q(yy, a2))
            v12 = float(geodetector_q(yy, a1 * 10 + a2))
            q1b.append(v1)
            q2b.append(v2)
            q12b.append(v12)
            relB.append(v12 > max(v1, v2))
            relN.append(v12 > v1 + v2)
        q12b = np.array(q12b)
        q1b, q2b = np.array(q1b), np.array(q2b)
        rows.append({
            "pair": "%s+%s" % (f1, f2), "q1": round(q1, 6), "q2": round(q2, 6),
            "q_interaction": round(q12, 6),
            "q1_plus_q2": round(q1 + q2, 6), "max_q1_q2": round(max(q1, q2), 6),
            "joint_n_levels": njoint,
            "relation_strict": ("nonlinear_enhance" if q12 > q1 + q2 else
                                ("bivariate_enhance" if q12 > max(q1, q2) else
                                 ("weaken" if q12 < min(q1, q2) else "independent"))),
            "relation_archived_criterion": ("enhance" if q12 > max(q1, q2) else
                                            ("weaken" if q12 < min(q1, q2) else "nonlinear")),
            "boot_q12_mean": round(float(q12b.mean()), 6),
            "boot_q12_p2.5": round(float(np.percentile(q12b, 2.5)), 6),
            "boot_q12_p97.5": round(float(np.percentile(q12b, 97.5)), 6),
            "boot_q12_width95": round(float(np.percentile(q12b, 97.5)
                                            - np.percentile(q12b, 2.5)), 6),
            "boot_frac_q12_gt_max": round(float(np.mean(relB)), 4),
            "boot_frac_q12_gt_sum": round(float(np.mean(relN)), 4),
            "perm_null_mean_q12": round(float(null.mean()), 6),
            "perm_null_p2.5": round(float(np.percentile(null, 2.5)), 6),
            "perm_null_p97.5": round(float(np.percentile(null, 97.5)), 6),
            "perm_p_q12_exceeds_null": round(p_perm, 4),
            "excess_over_null_mean": round(float(q12 - null.mean()), 6),
            "mechanical_share_of_q12": round(float(null.mean() / q12), 4),
            "q_dominant_class_reference": round(q_cls, 6),
            "bootstrap_reps": int(len(q12b)),
        })
    inter = pd.DataFrame(rows)
    inter.to_csv(os.path.join(DATA, "r28_interaction_uncertainty.csv"),
                 index=False, encoding="utf-8-sig")
    print("\n   %-16s %6s %6s %6s %6s %-19s %-8s %-9s %-9s" % (
        "pair", "q1", "q2", "q12", "q1+q2", "relation(strict)", "perm_p",
        "null均值", "机械占比"))
    for _, r in inter.iterrows():
        print("   %-16s %.4f %.4f %.4f %.4f %-19s %.3f  %.4f  %.2f"
              % (r.pair, r.q1, r.q2, r.q_interaction, r.q1_plus_q2,
                 r.relation_strict, r.perm_p_q12_exceeds_null,
                 r.perm_null_mean_q12, r.mechanical_share_of_q12))
    print("\n   q12 的 bootstrap 95% 区间：")
    for _, r in inter.iterrows():
        print("     %-16s %.4f [%.4f, %.4f] 宽度 %.4f | P(q12>max(q1,q2))=%.3f "
              "P(q12>q1+q2)=%.3f"
              % (r.pair, r.q_interaction, r["boot_q12_p2.5"], r["boot_q12_p97.5"],
                 r.boot_q12_width95, r.boot_frac_q12_gt_max, r.boot_frac_q12_gt_sum))
    print("\n已写出：data/r28_forest_small_sample.csv, data/r28_interaction_uncertainty.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())