# -*- coding: utf-8 -*-
"""R28-T4.2 · GeoDetector 分层方案敏感性（四分位 / 5 分位 / 自然断点 Jenks / 等间隔）
（审稿意见第 3 条：空间归因的内生性与敏感性）

────────────────────────────────────────────────────────────────────────────
背景
────────────────────────────────────────────────────────────────────────────
正文与归档管线（run_geodetector_pvalues.py / run_geodetector_loo.py）只用
**样本分位数 4 等样本分层**（one-hot 变量退化为 2 层）。q 值对分层方案敏感，
需给出替代分层下的对比，才能支撑"分层不改变结论"或指出结论的适用边界。

────────────────────────────────────────────────────────────────────────────
方法
────────────────────────────────────────────────────────────────────────────
分层方案：
  · quantile4   —— 四分位等样本分层（基准，= 论文口径）
  · quantile5   —— 5 分位等样本分层
  · jenks       —— 自然断点（Fisher-Jenks 一维最优 DP，最小化组内平方和）
  · equal_interval —— 等间隔分层
  · binary      —— one-hot 变量的自然二分（grass/barren 的实际取值分层）
对每个因子 × 每种分层，计算：
  · q_baseline  —— 目标 = 完整点尺度 ESI（论文基准口径）
  · q_loo       —— 目标 = 剔除该因子后的重构 ESI（切断机械相关，口径同
                   run_geodetector_loo.py）
  · 置换检验 p（999 次，seed=42，每次检验独立重置）

因子：precip / temp / grass / barren(one-hot) / elev / slope
（另附 barren_neg —— ESI 的真实输入列，用于展示"同一构造的不同列"差异）

────────────────────────────────────────────────────────────────────────────
数据来源（已入库；不新增下载，不覆盖任何已跟踪 CSV）
· data/spatial_samples.csv      —— 1914 点位 precip/temp/grass/forest/water/barren
· data/spatial_esi_points.csv   —— 归档点尺度 ESI（目标）
· data/_aux_terrain_points.csv  —— elev/slope

输出：data/r28_stratification_sensitivity.csv
运行：python run_r28_stratification_sensitivity.py
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

N_PERM = 999
SEED = 42
ALPHA = 0.4
FULL_SPEC = [
    ("precip", "precip", +1), ("temp", "temp", +1), ("forest", "forest", +1),
    ("grass", "grass", +1), ("water", "water", +1), ("barren_neg", "_barren_neg", -1),
]
FACTORS = [("precip", "precip"), ("temp", "temp"), ("grass", "grass"),
           ("barren", "barren"), ("barren_neg", "_barren_neg"),
           ("elev", "elev"), ("slope", "slope")]
DROP_MAP = {"precip": "precip", "temp": "temp", "grass": "grass",
            "barren": "barren_neg", "barren_neg": "barren_neg"}


# ---------------------------------------------------------------------------
# 分层
# ---------------------------------------------------------------------------
def strat_quantile(v, k):
    qs = np.quantile(v, np.linspace(0, 1, k + 1)[1:-1])
    return np.digitize(v, qs)


def strat_equal_interval(v, k):
    lo, hi = float(np.min(v)), float(np.max(v))
    if hi - lo < 1e-12:
        return np.zeros(len(v), dtype=int)
    return np.clip(((v - lo) / (hi - lo) * k).astype(int), 0, k - 1)


def _ssd_matrix(x):
    """SSD[i, j] = 区间 [i, j] 内的平方偏差和（含端点）。"""
    n = len(x)
    c1 = np.concatenate([[0.0], np.cumsum(x)])
    c2 = np.concatenate([[0.0], np.cumsum(x ** 2)])
    i_idx = np.arange(n)[:, None]
    j_idx = np.arange(n)[None, :]
    cnt = (j_idx - i_idx + 1).astype(float)
    s1 = c1[j_idx + 1] - c1[i_idx]
    s2 = c2[j_idx + 1] - c2[i_idx]
    ssd = s2 - s1 ** 2 / cnt
    ssd[j_idx < i_idx] = np.inf
    return np.where(ssd < 0, 0.0, ssd)


def strat_jenks(v, k):
    """一维 Fisher-Jenks 自然断点（精确 DP）。返回 0..L-1 的层标签。"""
    x = np.asarray(v, float)
    order = np.argsort(x, kind="mergesort")
    xs = x[order]
    n = len(xs)
    n_uniq = len(np.unique(xs))
    kk = int(min(k, n_uniq))
    if kk <= 1:
        lab = np.zeros(n, dtype=int)
        out = np.empty(n, dtype=int)
        out[order] = lab
        return out
    ssd = _ssd_matrix(xs)
    INF = np.inf
    dp = np.full((kk + 1, n), INF)
    prev = np.zeros((kk + 1, n), dtype=int)
    dp[1] = ssd[0]
    for c in range(2, kk + 1):
        for j in range(c - 1, n):
            # 前 c-1 段覆盖 [0, i]，第 c 段覆盖 [i+1, j]
            ii = np.arange(0, j)
            cand = dp[c - 1, ii] + ssd[ii + 1, j]
            idx = int(np.argmin(cand))
            dp[c, j] = cand[idx]
            prev[c, j] = ii[idx]
    brk = np.zeros(kk + 1, dtype=int)
    brk[kk] = n - 1
    j = n - 1
    for c in range(kk, 1, -1):
        i = prev[c, j]
        brk[c - 1] = i
        j = i
    lab_sorted = np.zeros(n, dtype=int)
    for c in range(1, kk + 1):
        start = 0 if c == 1 else brk[c - 1] + 1
        lab_sorted[start:brk[c] + 1] = c - 1
    out = np.empty(n, dtype=int)
    out[order] = lab_sorted
    return out


SCHEMES = [
    ("quantile4_baseline", lambda v: strat_quantile(v, 4)),
    ("quantile5", lambda v: strat_quantile(v, 5)),
    ("jenks4", lambda v: strat_jenks(v, 4)),
    ("jenks5", lambda v: strat_jenks(v, 5)),
    ("equal_interval4", lambda v: strat_equal_interval(v, 4)),
    ("equal_interval5", lambda v: strat_equal_interval(v, 5)),
]


# ---------------------------------------------------------------------------
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


def detect(strata, y, n_perm=N_PERM, seed=SEED):
    q = geodetector_q(y, strata)
    rng = np.random.default_rng(seed)
    cnt = sum(1 for _ in range(n_perm)
              if geodetector_q(y, rng.permutation(strata)) >= q)
    return float(q), float((1.0 + cnt) / (n_perm + 1.0))


def main():
    smp = add_derived(pd.read_csv(os.path.join(DATA, "spatial_samples.csv")))
    esp = pd.read_csv(os.path.join(DATA, "spatial_esi_points.csv"))
    ter = pd.read_csv(os.path.join(DATA, "_aux_terrain_points.csv"))
    df = smp.merge(esp[["lat", "lon", "esi"]], on=["lat", "lon"], how="inner")
    df = df.merge(ter[["lat", "lon", "elev", "slope"]], on=["lat", "lon"], how="inner")
    print("=" * 78)
    print("R28-T4.2 · 分层方案敏感性（n=%d，置换 %d 次，seed=%d）" % (len(df), N_PERM, SEED))
    print("=" * 78)

    y_full = df["esi"].values
    esi_re = build_esi(df, FULL_SPEC)
    print("[校验] 重建点尺度 ESI vs 归档 max|Δ| = %.3e"
          % np.abs(esi_re - y_full).max())

    # LOO 目标
    loo_target = {}
    for fac, drop in DROP_MAP.items():
        spec2 = [s for s in FULL_SPEC if s[0] != drop]
        loo_target[fac] = build_esi(df, spec2)
    loo_target["elev"] = y_full
    loo_target["slope"] = y_full

    rows = []
    for fac, col in FACTORS:
        v = df[col].values.astype(float)
        for sname, sfun in SCHEMES:
            st = sfun(v)
            lv = int(len(np.unique(st)))
            sizes = np.bincount(st)
            keep = sizes > 0
            if lv >= 2:
                qb, pb = detect(st, y_full)
                ql, pl = detect(st, loo_target[fac])
            else:
                qb = ql = np.nan
                pb = pl = np.nan
            rows.append({
                "factor": fac, "column": col, "stratification": sname,
                "n_levels": lv,
                "n_unique_values": int(len(np.unique(v))),
                "min_stratum_n": int(sizes[keep].min()) if keep.any() else 0,
                "max_stratum_n": int(sizes[keep].max()) if keep.any() else 0,
                "q_baseline": round(qb, 6), "p_baseline": round(pb, 4),
                "q_loo": round(ql, 6), "p_loo": round(pl, 4),
                "delta_q_loo": round(ql - qb, 6),
                "drop_pct_loo": round((ql - qb) / qb * 100, 2) if qb else np.nan,
            })
    out = pd.DataFrame(rows)

    # 排序（每种分层下按 q_baseline 降序）
    def rank_str(s):
        d = out[(out.stratification == s) & out.q_baseline.notna()]
        d = d.sort_values("q_baseline", ascending=False)
        return " > ".join("%s(%.3f)" % (r.factor, r.q_baseline) for _, r in d.iterrows())

    out.to_csv(os.path.join(DATA, "r28_stratification_sensitivity.csv"),
               index=False, encoding="utf-8-sig")

    print("\n基准口径 q（目标=完整 ESI）：")
    piv = out.pivot_table(index="factor", columns="stratification", values="q_baseline")
    print(piv.round(4).to_string())
    print("\nLOO 口径 q（目标=剔除该因子后的 ESI）：")
    piv2 = out.pivot_table(index="factor", columns="stratification", values="q_loo")
    print(piv2.round(4).to_string())
    print("\n实际层数：")
    print(out.pivot_table(index="factor", columns="stratification",
                          values="n_levels").to_string())
    print("\n各分层方案下的因子排序（基准口径）：")
    for s, _ in SCHEMES:
        print("   %-20s %s" % (s, rank_str(s)))

    # 稳健性判定
    print("\n" + "-" * 78)
    print("判定")
    print("-" * 78)
    for fac, _ in FACTORS:
        d = out[(out.factor == fac) & out.q_baseline.notna()]
        print("   %-11s q_baseline 在 %d 种分层下：%.3f-%.3f（中位数 %.3f，极差 %.3f）"
              % (fac, len(d), d.q_baseline.min(), d.q_baseline.max(),
                 d.q_baseline.median(), d.q_baseline.max() - d.q_baseline.min()))
    top = {}
    for s, _ in SCHEMES:
        d = out[(out.stratification == s) & out.q_baseline.notna()]
        top[s] = d.sort_values("q_baseline", ascending=False).iloc[0].factor
    print("\n   基准口径 Top-1 因子：", top)
    loo_top = {}
    for s, _ in SCHEMES:
        d = out[(out.stratification == s) & out.q_loo.notna()]
        loo_top[s] = d.sort_values("q_loo", ascending=False).iloc[0].factor
    print("   LOO 口径 Top-1 因子：", loo_top)
    print("\n已写出：data/r28_stratification_sensitivity.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())