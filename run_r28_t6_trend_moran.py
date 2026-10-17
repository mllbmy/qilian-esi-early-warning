# -*- coding: utf-8 -*-
"""R28 · T6 —— 时间序列与空间自相关检验规范化（次要意见）

① Mann-Kendall 的自相关处理
   实现按 Hamed & Rao (1998) 方差修正法（与 CRAN `modifiedmk::mmkh` 同式）：
     · 先用 Sen 斜率去趋势 xn = x − slope·t
     · 对 rank(xn) 求 lag-1…n−1 自相关 ρ_i，只保留显著滞后（|ρ_i| > z_{(1+ci)/2}/√n）
     · n/n* = 1 + [2/(n(n−1)(n−2))]·Σ_i (n−i)(n−i−1)(n−i−2)·ρ_i
     · Var*(S) = Var(S)·(n/n*)，Z* = (S∓1)/√Var*(S)
   同时报未修正 Z 与修正 Z，以及"预白化（TFPW）"对照。
   Sen's slope 与 95% 置信区间按 Sen (1968)/Gilbert 秩方差口径给出。

② 分段趋势：2010–2023 / 2011–2023 / 2012–2023 + 滑动起点扫描

③ Moran's I 的 k 近邻与权重矩阵敏感性（2020 点尺度 ESI，1914 点）
   · k ∈ {4, 6, 8, 10, 12, 16, 20, 25, 30, 40, 50}
   · 四种权重矩阵：行标准化 binary k-NN / 行标准化 1/d k-NN / 行标准化 1/d² k-NN /
     固定距离带（inverse distance，阈值 = k=12 的平均最近邻距离）
   · 置换检验 p（999 次，seed=42）与 Moran's I 的 E[I]、Var[I]

输出
  data/r28_trend_tests.csv
  data/r28_moran_k_sensitivity.csv

运行：python run_r28_t6_trend_moran.py
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
OUT_T = os.path.join(DATA, "r28_trend_tests.csv")
OUT_M = os.path.join(DATA, "r28_moran_k_sensitivity.csv")
import r28_core as C  # noqa: E402

SCEN = ["baseline9", "drop_X9", "drop_X8", "drop_X8_X9", C.PRIMARY, "substitute5"]
N_PERM = 999
SEED = 42
CI = 0.95


# ---------------------------------------------------------------------------
# MK / Hamed-Rao / Sen
# ---------------------------------------------------------------------------
def _S_var(y):
    y = np.asarray(y, dtype=float)
    n = len(y)
    s = float(sum(np.sign(y[i + 1:] - y[i]).sum() for i in range(n - 1)))
    _, cnt = np.unique(y, return_counts=True)
    tie = sum(t * (t - 1) * (2 * t + 5) for t in cnt if t > 1)
    var_s = (n * (n - 1) * (2 * n + 5) - tie) / 18.0
    return s, var_s, n


def sen_slope_ci(x, y, ci=CI):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    n = len(y)
    slopes = np.array([(y[j] - y[i]) / (x[j] - x[i])
                       for i in range(n - 1) for j in range(i + 1, n)])
    beta = float(np.median(slopes))
    _, var_s, _ = _S_var(y)
    z = stats.norm.ppf((1 + ci) / 2)
    d = z * np.sqrt(var_s)
    ns = len(slopes)
    ss = np.sort(slopes)
    lo = float(ss[max(int(np.floor((ns - d) / 2)), 0)])
    hi = float(ss[min(int(np.ceil((ns + d) / 2)) - 1, ns - 1)])
    return beta, lo, hi


def mk_plain(y):
    s, var_s, n = _S_var(y)
    if s > 0:
        z = (s - 1) / np.sqrt(var_s)
    elif s < 0:
        z = (s + 1) / np.sqrt(var_s)
    else:
        z = 0.0
    return dict(S=s, var_s=var_s, Z=float(z), p=float(2 * (1 - stats.norm.cdf(abs(z)))),
                tau=float(s / (0.5 * n * (n - 1))), n=n)


def hamed_rao_mk(y, ci=CI, detrend=True):
    """Hamed & Rao (1998) 方差修正版 MK（与 CRAN `modifiedmk::mmkh` 同式，逐行对照）。

    ⚠ 短序列（n≈11–19）下 Σ(n−i)(n−i−1)(n−i−2)ρ_i 可能为较大负值，使 n/n* ≤ 0，
      此时 √Var*(S) 无意义（|Z| 爆炸）。本函数**不隐藏**这一情形：
      返回 n_nstar 原值与 stable 标志；stable=False 时 Z_corrected/p_corrected 记为 NaN，
      由 TFPW（预白化）结果作为该情形的替代证据。
    """
    y = np.asarray(y, dtype=float)
    n = len(y)
    t = np.arange(1, n + 1)
    beta, _, _ = sen_slope_ci(t, y, ci)
    xn = y - beta * t if detrend else y.copy()
    r = stats.rankdata(xn)
    ro = []
    for k in range(1, n):
        a, b = r[:-k], r[k:]
        ro.append(float(np.sum((a - a.mean()) * (b - b.mean()))
                        / np.sqrt(np.sum((a - a.mean()) ** 2) * np.sum((b - b.mean()) ** 2))))
    ro = np.array(ro)
    sig = stats.norm.ppf((1 + ci) / 2) / np.sqrt(n)
    rof = np.where((ro > sig) | (ro < -sig), ro, 0.0)
    cte = 2.0 / (n * (n - 1) * (n - 2))
    ess = sum((n - i) * (n - i - 1) * (n - i - 2) * rof[i - 1] for i in range(1, n))
    essf = 1.0 + ess * cte
    _, var_s, _ = _S_var(y)
    stable = bool(0.2 <= essf <= 20.0)
    if not stable:
        return dict(n_nstar=float(essf), var_s=float(var_s), var_s_star=float(var_s * max(essf, 0.0)),
                    Z_corrected=np.nan, p_corrected=np.nan,
                    n_sig_lags=int((rof != 0).sum()),
                    max_sig_lag=(int(np.max(np.nonzero(rof)[0]) + 1) if (rof != 0).any() else 0),
                    lag1_acf_rank=float(ro[0]), stable=False,
                    note=("n/n* = %.6f 落在 [0.2, 20] 之外，方差修正不稳定，"
                          "Z_corrected/p_corrected 记为 NaN（不报不可用的数值）" % essf))
    VS = var_s * essf
    s, _, _ = _S_var(y)
    if s > 0:
        z = (s - 1) / np.sqrt(VS)
    elif s < 0:
        z = (s + 1) / np.sqrt(VS)
    else:
        z = 0.0
    return dict(n_nstar=float(essf), var_s=float(var_s), var_s_star=float(VS),
                Z_corrected=float(z), p_corrected=float(2 * (1 - stats.norm.cdf(abs(z)))),
                n_sig_lags=int((rof != 0).sum()),
                max_sig_lag=(int(np.max(np.nonzero(rof)[0]) + 1) if (rof != 0).any() else 0),
                lag1_acf_rank=float(ro[0]), stable=True, note="")


def tfpw_mk(y, ci=CI):
    """趋势自由预白化（TFPW, Yue et al. 2002）后再做 MK。"""
    y = np.asarray(y, dtype=float)
    n = len(y)
    t = np.arange(1, n + 1)
    beta, _, _ = sen_slope_ci(t, y, ci)
    detr = y - beta * t
    r1 = float(np.corrcoef(detr[:-1], detr[1:])[0, 1])
    if abs(r1) < 1e-12:
        yw = detr
    else:
        yw = detr[1:] - r1 * detr[:-1]
    yw = yw + beta * t[1:]
    m = mk_plain(yw)
    b2, lo2, hi2 = sen_slope_ci(t[1:], yw, ci)
    return dict(lag1_acf=float(r1), Z_tfpw=m["Z"], p_tfpw=m["p"],
                sen_slope_tfpw=b2, sen_lo_tfpw=lo2, sen_hi_tfpw=hi2, n_eff=n - 1)


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


# ---------------------------------------------------------------------------
# Moran's I
# ---------------------------------------------------------------------------
def pair_dist(lat, lon, cache={}):
    key = (len(lat), float(lat[0]), float(lon[0]))
    if key in cache:
        return cache[key]
    P = np.column_stack([lon, lat])
    d = np.sqrt(((P[:, None, :] - P[None, :, :]) ** 2).sum(axis=2))
    np.fill_diagonal(d, np.inf)
    cache[key] = d
    return d


def knn_weights(lat, lon, k, scheme="binary", dmat=None):
    """k 近邻空间权重（经纬度欧氏距离；行标准化）。"""
    d = pair_dist(lat, lon) if dmat is None else dmat
    n = len(d)
    W = np.zeros((n, n))
    idx = np.argsort(d, axis=1)[:, :k]
    rows = np.repeat(np.arange(n), k)
    cols = idx.ravel()
    if scheme == "binary":
        W[rows, cols] = 1.0
    elif scheme == "inv_dist":
        W[rows, cols] = 1.0 / d[rows, cols]
    elif scheme == "inv_dist2":
        W[rows, cols] = 1.0 / d[rows, cols] ** 2
    rs = W.sum(axis=1, keepdims=True)
    rs[rs == 0] = 1.0
    return W / rs, d


def dist_band_weights(lat, lon, dmax, scheme="inv_dist", dmat=None):
    d = pair_dist(lat, lon) if dmat is None else dmat
    W = np.where(d <= dmax, (1.0 / d if scheme == "inv_dist" else 1.0), 0.0)
    W[~np.isfinite(W)] = 0.0
    np.fill_diagonal(W, 0.0)
    rs = W.sum(axis=1, keepdims=True)
    rs[rs == 0] = 1.0
    return W / rs


def morans_i(W, z, const=None):
    """Moran's I（行标准化权重）+ E[I] / Var[I]（随机化假设）。

    const 预计算 W 的 S0/S1/S2，可在置换循环中复用（性能关键：1914×1914 稠密矩阵）。
    """
    z = np.asarray(z, dtype=float)
    n = len(z)
    zc = z - z.mean()
    if const is None:
        const = weight_constants(W)
    S0, S1, S2 = const
    num = float(zc @ (W @ zc))
    den = float(zc @ zc)
    I = (n / S0) * num / den
    k = (stats.kurtosis(z, fisher=False, bias=False) if n > 3 else 3.0)
    k = float(k) if np.isfinite(k) else 3.0
    EI = -1.0 / (n - 1)
    VarI = (n * ((n ** 2 - 3 * n + 3) * S1 - n * S2 + 3 * S0 ** 2)
            - k * (n * (n - 1) * S1 - 2 * n * S2 + 6 * S0 ** 2)) / ((n - 1) * (n - 2) * (n - 3) * S0 ** 2) - EI ** 2
    return float(I), float(EI), float(max(VarI, 1e-12))


def weight_constants(W):
    S0 = float(W.sum())
    S1 = float(0.5 * ((W + W.T) ** 2).sum())
    S2 = float(((W.sum(axis=1) + W.sum(axis=0)) ** 2).sum())
    return (S0, S1, S2)


def moran_perm(W, z, seed=SEED, n_perm=N_PERM):
    z = np.asarray(z, dtype=float)
    n = len(z)
    const = weight_constants(W)
    S0, S1, S2 = const
    zc = z - z.mean()
    den = float(zc @ zc)
    I = (n / S0) * float(zc @ (W @ zc)) / den
    k = float(stats.kurtosis(z, fisher=False, bias=False)) if n > 3 else 3.0
    if not np.isfinite(k):
        k = 3.0
    EI = -1.0 / (n - 1)
    VarI = (n * ((n ** 2 - 3 * n + 3) * S1 - n * S2 + 3 * S0 ** 2)
            - k * (n * (n - 1) * S1 - 2 * n * S2 + 6 * S0 ** 2)) / ((n - 1) * (n - 2) * (n - 3) * S0 ** 2) - EI ** 2
    VarI = max(VarI, 1e-12)
    Z = (I - EI) / np.sqrt(VarI)
    p_norm = float(2 * (1 - stats.norm.cdf(abs(Z))))
    rng = np.random.default_rng(seed)
    cnt = 0
    d0 = abs(I - EI)
    for _ in range(n_perm):
        zp = rng.permutation(z)
        zpc = zp - zp.mean()
        Ip = (n / S0) * float(zpc @ (W @ zpc)) / float(zpc @ zpc)
        if abs(Ip - EI) >= d0:
            cnt += 1
    return I, EI, VarI, float(Z), p_norm, (1.0 + cnt) / (n_perm + 1.0)


def main():
    C.self_check()
    # =====================================================================
    # ① + ② 趋势检验
    # =====================================================================
    trow = []
    sig_thr = float(stats.norm.ppf((1 + CI) / 2) / np.sqrt(19))
    for s in SCEN:
        r = C.compute(C.DEREDUNDANT_SETS[s])
        y = r["esi"]
        yr = np.array(r["years"])
        K, tau, p_pet = pettitt_k(y)
        for a, b in [(2005, 2023), (2010, 2023), (2011, 2023), (2012, 2023), (2009, 2023), (2013, 2023)]:
            m = (yr >= a) & (yr <= b)
            ys = y[m]
            xs = yr[m].astype(float)
            if m.sum() < 6:
                continue
            mk = mk_plain(ys)
            hr = hamed_rao_mk(ys)
            tp = tfpw_mk(ys)
            beta, lo, hi = sen_slope_ci(xs, ys)
            trow.append(dict(
                scenario=s, series="%d-%d" % (a, b), n_years=int(m.sum()),
                segment=("full" if (a == 2005 and b == 2023) else ("segment" if a >= 2010 else "rolling")),
                S=round(mk["S"], 3), Z_mk=round(mk["Z"], 4), p_mk=round(mk["p"], 6),
                kendall_tau=round(mk["tau"], 6),
                n_nstar=round(hr["n_nstar"], 6),
                var_s=round(hr["var_s"], 4), var_s_star=round(hr["var_s_star"], 4),
                Z_hamed_rao=round(hr["Z_corrected"], 4) if hr["stable"] else np.nan,
                p_hamed_rao=round(hr["p_corrected"], 6) if hr["stable"] else np.nan,
                hamed_rao_stable=bool(hr["stable"]),
                n_sig_lags=hr["n_sig_lags"], max_sig_lag=hr["max_sig_lag"],
                lag1_acf_rank=round(hr["lag1_acf_rank"], 6),
                lag1_acf_series=round(tp["lag1_acf"], 6),
                Z_tfpw=round(tp["Z_tfpw"], 4), p_tfpw=round(tp["p_tfpw"], 6),
                sen_slope=round(beta, 6), sen_ci_lo=round(lo, 6), sen_ci_hi=round(hi, 6),
                sen_slope_tfpw=round(tp["sen_slope_tfpw"], 6),
                pettitt_K=round(K, 4) if (a == 2005) else np.nan,
                pettitt_p=round(p_pet, 6) if (a == 2005) else np.nan,
                pettitt_change_point=int(yr[tau]) if (a == 2005) else None,
                significant_p05_uncorrected=bool(mk["p"] < 0.05),
                significant_p05_hamed_rao=(bool(hr["p_corrected"] < 0.05) if hr["stable"] else None),
                significant_p05_tfpw=bool(tp["p_tfpw"] < 0.05),
                note=(("Hamed-Rao 方差修正（去趋势秩自相关，显著滞后 |ρ|>1.96/√n）；TFPW 为趋势自由预白化对照"
                       ) if hr["stable"] else hr["note"])))
    tdf = pd.DataFrame(trow)
    tdf.to_csv(OUT_T, index=False, encoding="utf-8-sig")

    print("=" * 130)
    print("① + ② 趋势检验（MK 原始 / Hamed-Rao 方差修正 / TFPW / Sen 斜率 95%CI）")
    print("=" * 130)
    for s in SCEN:
        q = tdf[tdf.scenario == s]
        print("\n[%s]" % s)
        print(q[["series", "n_years", "Z_mk", "p_mk", "n_nstar", "hamed_rao_stable",
                 "Z_hamed_rao", "p_hamed_rao", "Z_tfpw", "p_tfpw", "sen_slope",
                 "sen_ci_lo", "sen_ci_hi"]].to_string(index=False))
        pet = q[q.segment == "full"].iloc[0]
        print("   Pettitt: K=%.4f p=%.6f 变点年=%s" % (pet["pettitt_K"], pet["pettitt_p"],
                                                       pet["pettitt_change_point"]))

    print("\n判读：全期 vs 2010–2023 分段")
    for s in SCEN:
        q = tdf[tdf.scenario == s].set_index("series")
        for ser in ["2005-2023", "2010-2023"]:
            if ser in q.index:
                row = q.loc[ser]
                print("  %-14s %-10s p_mk=%.4f p_HR=%s p_TFPW=%.4f slope=%+.5f [%+.5f,%+.5f] 显著(MK/HR/TFPW)=%s/%s/%s"
                      % (s, ser, row["p_mk"],
                         ("%.4f" % row["p_hamed_rao"]) if row["hamed_rao_stable"] else "不稳定(NaN)",
                         row["p_tfpw"],
                         row["sen_slope"], row["sen_ci_lo"], row["sen_ci_hi"],
                         row["significant_p05_uncorrected"],
                         row["significant_p05_hamed_rao"],
                         row["significant_p05_tfpw"]))

    # =====================================================================
    # ③ Moran's I 的 k 与权重矩阵敏感性
    # =====================================================================
    esp = pd.read_csv(os.path.join(DATA, "spatial_esi_points.csv"))
    lat, lon, z = esp["lat"].values, esp["lon"].values, esp["esi"].values
    print("\n" + "=" * 130)
    print("③ Moran's I 敏感性（点尺度 2020 ESI，n=%d）" % len(z))
    print("=" * 130)
    mrow = []
    # 参照距离：k=12 的平均最近邻距离
    dmat = pair_dist(lat, lon)
    srt = np.sort(dmat, axis=1)[:, :12]
    dmax = float(np.mean(srt.mean(axis=1)))
    for k in [4, 6, 8, 10, 12, 16, 20, 25, 30, 40, 50]:
        for scheme in ["binary", "inv_dist", "inv_dist2"]:
            W, _ = knn_weights(lat, lon, k, scheme, dmat=dmat)
            I, EI, VarI, Z, pn, pp = moran_perm(W, z)
            mrow.append(dict(weight="knn_k%d" % k, k=k, scheme=scheme, dmax=np.nan,
                             morans_i=round(I, 6), expected_i=round(EI, 6),
                             var_i=round(VarI, 10), z_score=round(Z, 4),
                             p_normal=round(pn, 6), p_permutation=round(pp, 4),
                             n_perm=N_PERM, seed=SEED,
                             mean_neighbors=round(float((W > 0).sum(axis=1).mean()), 3),
                             note="行标准化 %s k 近邻权重" % scheme))
    for scheme in ["inv_dist", "binary"]:
        W = dist_band_weights(lat, lon, dmax, scheme, dmat=dmat)
        I, EI, VarI, Z, pn, pp = moran_perm(W, z)
        mrow.append(dict(weight="distband_%.4f" % dmax, k=np.nan, scheme=scheme,
                         dmax=round(dmax, 6), morans_i=round(I, 6), expected_i=round(EI, 6),
                         var_i=round(VarI, 10), z_score=round(Z, 4), p_normal=round(pn, 6),
                         p_permutation=round(pp, 4), n_perm=N_PERM, seed=SEED,
                         mean_neighbors=round(float((W > 0).sum(axis=1).mean()), 3),
                         note="固定距离带（阈值 = k=12 平均最近邻距离 %.4f°）" % dmax))
    # 归档值为基准对照
    arch = pd.read_csv(os.path.join(DATA, "results_moran.csv"))
    mrow.append(dict(weight="archived_results_moran_csv", k=np.nan, scheme="inv_dist_kn",
                     dmax=np.nan, morans_i=round(float(arch["morans_i"].iloc[0]), 6),
                     expected_i=np.nan, var_i=np.nan, z_score=np.nan,
                     p_normal=np.nan, p_permutation=float(arch["p"].iloc[0]),
                     n_perm=np.nan, seed=np.nan, mean_neighbors=np.nan,
                     note="data/results_moran.csv 归档值（n=%d），供对照；本脚本不复现其确切 k 口径"
                          % int(arch["n"].iloc[0])))
    mdf = pd.DataFrame(mrow)
    mdf.to_csv(OUT_M, index=False, encoding="utf-8-sig")

    print("\nk 近邻：Moran's I 随 k 与权重方案")
    piv = mdf[mdf.scheme.isin(["binary", "inv_dist", "inv_dist2"])].pivot_table(
        index="k", columns="scheme", values="morans_i")
    print(piv.to_string())
    print("\n置换 p 值")
    pivp = mdf[mdf.scheme.isin(["binary", "inv_dist", "inv_dist2"])].pivot_table(
        index="k", columns="scheme", values="p_permutation")
    print(pivp.to_string())
    print("\n固定距离带（阈值 %.4f°）：" % dmax)
    print(mdf[mdf.weight.str.startswith("distband")][
        ["weight", "scheme", "morans_i", "z_score", "p_normal", "p_permutation",
         "mean_neighbors"]].to_string(index=False))
    print("\n归档对照：data/results_moran.csv = %.6f (p=%s)"
          % (float(arch["morans_i"].iloc[0]), float(arch["p"].iloc[0])))
    print("已写出 data/%s（%d 行）, data/%s（%d 行）"
          % (os.path.basename(OUT_T), len(tdf), os.path.basename(OUT_M), len(mdf)))
    return 0


if __name__ == "__main__":
    sys.exit(main())