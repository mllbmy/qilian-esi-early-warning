# -*- coding: utf-8 -*-
"""R28-T4.3 · GeoDetector 采样方案敏感性（全样本 / 随机子样本 / 分层子样本 / 自助）
（审稿意见第 3 条：空间归因的内部效度与敏感性）

────────────────────────────────────────────────────────────────────────────
背景
────────────────────────────────────────────────────────────────────────────
点尺度检测基于 1,914 个 0.15° 规则格点。q 的置信区间未报；采样方案（随机 vs
按主导覆被分层）对 q 的影响未知。

────────────────────────────────────────────────────────────────────────────
方案（每个方案 200 组随机种子）
────────────────────────────────────────────────────────────────────────────
· full_n1914               —— 全样本（基准）
· bootstrap_n1914          —— 有放回自助，n=1914
· random_n1500 / n1000 / n500 —— 无放回随机子样本
· stratified_n1000 / n500  —— 按主导覆被类（class）比例分层抽样
每个方案 × 因子报 q 的均值/标准差/2.5-97.5 分位/极差，并报因子排序稳定性
（与全样本排序的 Spearman 相关，以及 barren/grass 居首的频率）。

注：气候因子为 0.5° CRU 格网（同一 CRU 格点上多点共享同一值），随机子采样因此
不能增加气候场的独立信息量；该限制在结论中说明。

────────────────────────────────────────────────────────────────────────────
数据来源（已入库；不新增下载，不覆盖已跟踪 CSV）
· data/spatial_samples.csv、data/spatial_esi_points.csv、data/_aux_terrain_points.csv
输出：data/r28_sampling_sensitivity.csv
运行：python run_r28_sampling_sensitivity.py
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
from eco_security import geodetector_q  # noqa: E402

N_REP = 200
SEED = 20261017
K = 4
FACTORS = ["precip", "temp", "grass", "barren", "elev", "slope"]


def disc(v, k=K):
    qs = np.quantile(v, np.linspace(0, 1, k + 1)[1:-1])
    return np.digitize(v, qs)


def q_of(y, x):
    return float(geodetector_q(y, disc(x)))


def spearman(a, b):
    ra = pd.Series(a).rank().values
    rb = pd.Series(b).rank().values
    return float(np.corrcoef(ra, rb)[0, 1])


def main():
    smp = pd.read_csv(os.path.join(DATA, "spatial_samples.csv"))
    esp = pd.read_csv(os.path.join(DATA, "spatial_esi_points.csv"))
    ter = pd.read_csv(os.path.join(DATA, "_aux_terrain_points.csv"))
    df = smp.merge(esp[["lat", "lon", "esi"]], on=["lat", "lon"], how="inner")
    df = df.merge(ter[["lat", "lon", "elev", "slope"]], on=["lat", "lon"], how="inner")
    n = len(df)
    print("=" * 78)
    print("R28-T4.3 · 采样方案敏感性（n=%d，每方案 %d 组种子）" % (n, N_REP))
    print("=" * 78)
    y = df["esi"].values
    X = {f: df[f].values.astype(float) for f in FACTORS}
    cls = df["class"].values
    full_q = {f: q_of(y, X[f]) for f in FACTORS}
    print("全样本 q：", {k: round(v, 4) for k, v in full_q.items()})

    rng = np.random.default_rng(SEED)
    schemes = [
        ("bootstrap_n1914", n, "bootstrap"),
        ("random_n1500", 1500, "random"),
        ("random_n1000", 1000, "random"),
        ("random_n500", 500, "random"),
        ("stratified_n1000", 1000, "stratified"),
        ("stratified_n500", 500, "stratified"),
    ]
    cls_idx = {c: np.where(cls == c)[0] for c in np.unique(cls)}
    rows = []
    for sname, nsub, mode in schemes:
        qs = {f: [] for f in FACTORS}
        ranks = []
        for _ in range(N_REP):
            if mode == "bootstrap":
                idx = rng.integers(0, n, size=n)
            elif mode == "random":
                idx = rng.choice(n, size=nsub, replace=False)
            else:  # proportional stratified
                parts = []
                for c, ii in cls_idx.items():
                    m = max(1, int(round(nsub * len(ii) / n)))
                    m = min(m, len(ii))
                    parts.append(rng.choice(ii, size=m, replace=False))
                idx = np.concatenate(parts)
            yy = y[idx]
            qv = {}
            for f in FACTORS:
                qv[f] = q_of(yy, X[f][idx])
                qs[f].append(qv[f])
            ranks.append([f for f in sorted(FACTORS, key=lambda z: -qv[z])])
        for f in FACTORS:
            a = np.array(qs[f])
            rows.append({
                "scheme": sname, "mode": mode, "target_n": nsub, "n_replicates": N_REP,
                "factor": f, "q_full_sample": round(full_q[f], 6),
                "q_mean": round(float(a.mean()), 6), "q_sd": round(float(a.std(ddof=1)), 6),
                "q_min": round(float(a.min()), 6), "q_max": round(float(a.max()), 6),
                "q_p2.5": round(float(np.percentile(a, 2.5)), 6),
                "q_p25": round(float(np.percentile(a, 25)), 6),
                "q_p50": round(float(np.percentile(a, 50)), 6),
                "q_p75": round(float(np.percentile(a, 75)), 6),
                "q_p97.5": round(float(np.percentile(a, 97.5)), 6),
                "q_range": round(float(a.max() - a.min()), 6),
                "spearman_vs_full_ranking": round(spearman(
                    [full_q[z] for z in FACTORS], [np.mean(qs[z]) for z in FACTORS]), 4),
                "frac_rank1": round(float(np.mean([r[0] == f for r in ranks])), 4),
            })
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(DATA, "r28_sampling_sensitivity.csv"),
               index=False, encoding="utf-8-sig")

    print("\nq 均值（各方案）：")
    piv = out.pivot_table(index="factor", columns="scheme", values="q_mean")
    print(piv.round(4).to_string())
    print("\nq 的 95% 区间宽度（p97.5 - p2.5）：")
    piv2 = out.pivot_table(index="factor", columns="scheme",
                           values=["q_p2.5", "q_p97.5"])
    w = (piv2["q_p97.5"] - piv2["q_p2.5"])
    print(w.round(4).to_string())
    print("\n各方案下居首因子的出现频率：")
    for s in out.scheme.unique():
        d = out[out.scheme == s].sort_values("frac_rank1", ascending=False).head(3)
        print("   %-18s %s" % (s, ", ".join("%s %.2f" % (r.factor, r.frac_rank1)
                                           for _, r in d.iterrows())))
    print("\n排序稳定性（与全样本排序的 Spearman，按方案）：")
    for s in out.scheme.unique():
        d = out[out.scheme == s]
        print("   %-18s %.4f" % (s, d.spearman_vs_full_ranking.iloc[0]))
    print("\n已写出：data/r28_sampling_sensitivity.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())