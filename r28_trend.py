# -*- coding: utf-8 -*-
"""R28 · 趋势/变点检验的共用实现（单一真源，供 T5 与 T6 复用）

实现内容与出处：
  · Mann-Kendall 原始检验（含并列校正的 Var(S)）
  · Sen (1968) 斜率及其置信区间（Gilbert 1987 秩方差口径，名义 95%）
  · Hamed & Rao (1998) 方差修正版 MK —— 与 CRAN `modifiedmk::mmkh` 同式：
        n/n* = 1 + [2/(n(n−1)(n−2))]·Σ_i (n−i)(n−i−1)(n−i−2)·ρ_i
        Var*(S) = Var(S)·(n/n*)
    其中 ρ_i 为**去趋势后序列的秩序列**在滞后 i 的自相关，只保留显著滞后
    （|ρ_i| > z_{(1+ci)/2}/√n）。
  · TFPW（趋势自由预白化，Yue et al. 2002）对照
  · Pettitt (1979) 非参数变点检验

⚠ 已知不稳定情形（不隐藏）：短序列下 Σ 可能为较大负值使 n/n* ≤ 0，
  此时 √Var*(S) 无意义。函数返回 stable=False 且 Z/p 记 NaN。
"""
from __future__ import annotations

import numpy as np
from scipy import stats

CI = 0.95


def s_and_var(y):
    """MK 的 S 统计量与 Var(S)（含并列校正）。"""
    y = np.asarray(y, dtype=float)
    n = len(y)
    s = float(sum(np.sign(y[i + 1:] - y[i]).sum() for i in range(n - 1)))
    _, cnt = np.unique(y, return_counts=True)
    tie = sum(t * (t - 1) * (2 * t + 5) for t in cnt if t > 1)
    return s, (n * (n - 1) * (2 * n + 5) - tie) / 18.0, n


def sen_slope_ci(x, y, ci=CI):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    n = len(y)
    slopes = np.array([(y[j] - y[i]) / (x[j] - x[i])
                       for i in range(n - 1) for j in range(i + 1, n)])
    beta = float(np.median(slopes))
    _, var_s, _ = s_and_var(y)
    z = stats.norm.ppf((1 + ci) / 2)
    d = z * np.sqrt(var_s)
    ss = np.sort(slopes)
    ns = len(slopes)
    lo = float(ss[max(int(np.floor((ns - d) / 2)), 0)])
    hi = float(ss[min(int(np.ceil((ns + d) / 2)) - 1, ns - 1)])
    return beta, lo, hi


def mk_plain(y):
    s, var_s, n = s_and_var(y)
    if s > 0:
        z = (s - 1) / np.sqrt(var_s)
    elif s < 0:
        z = (s + 1) / np.sqrt(var_s)
    else:
        z = 0.0
    return dict(S=s, var_s=float(var_s), Z=float(z),
                p=float(2 * (1 - stats.norm.cdf(abs(z)))),
                tau=float(s / (0.5 * n * (n - 1))), n=n)


def hamed_rao_mk(y, ci=CI, detrend=True):
    y = np.asarray(y, dtype=float)
    n = len(y)
    t = np.arange(1, n + 1)
    beta, _, _ = sen_slope_ci(t, y, ci)
    xn = y - beta * t if detrend else y.copy()
    r = stats.rankdata(xn)
    ro = []
    for k in range(1, n):
        a, b = r[:-k], r[k:]
        va = float(np.sum((a - a.mean()) ** 2))
        vb = float(np.sum((b - b.mean()) ** 2))
        # 去趋势后秩序列在短滞后上可能几乎常数（方差≈0）；此时自相关无定义，记 0
        if va < 1e-12 or vb < 1e-12:
            ro.append(0.0)
            continue
        ro.append(float(np.sum((a - a.mean()) * (b - b.mean())) / np.sqrt(va * vb)))
    ro = np.array(ro)
    sig = stats.norm.ppf((1 + ci) / 2) / np.sqrt(n)
    rof = np.where((ro > sig) | (ro < -sig), ro, 0.0)
    cte = 2.0 / (n * (n - 1) * (n - 2))
    ess = sum((n - i) * (n - i - 1) * (n - i - 2) * rof[i - 1] for i in range(1, n))
    essf = float(1.0 + ess * cte)
    _, var_s, _ = s_and_var(y)
    stable = bool(0.2 <= essf <= 20.0)
    out = dict(n_nstar=essf, var_s=float(var_s),
               var_s_star=float(var_s * max(essf, 0.0)),
               n_sig_lags=int((rof != 0).sum()),
               max_sig_lag=(int(np.max(np.nonzero(rof)[0]) + 1) if (rof != 0).any() else 0),
               lag1_acf_rank=float(ro[0]), stable=stable, note="")
    if not stable:
        out.update(Z_corrected=np.nan, p_corrected=np.nan,
                   note=("n/n* = %.6f 落在 [0.2, 20] 之外；方差修正不稳定，"
                         "Z/p 记为 NaN（不报不可用数值）" % essf))
        return out
    s, _, _ = s_and_var(y)
    VS = var_s * essf
    if s > 0:
        z = (s - 1) / np.sqrt(VS)
    elif s < 0:
        z = (s + 1) / np.sqrt(VS)
    else:
        z = 0.0
    out.update(Z_corrected=float(z),
               p_corrected=float(2 * (1 - stats.norm.cdf(abs(z)))))
    return out


def tfpw_mk(y, ci=CI):
    y = np.asarray(y, dtype=float)
    n = len(y)
    t = np.arange(1, n + 1)
    beta, _, _ = sen_slope_ci(t, y, ci)
    detr = y - beta * t
    r1 = float(np.corrcoef(detr[:-1], detr[1:])[0, 1])
    yw = detr if abs(r1) < 1e-12 else detr[1:] - r1 * detr[:-1]
    yw = yw + beta * t[1:]
    m = mk_plain(yw)
    b2, lo2, hi2 = sen_slope_ci(t[1:], yw, ci)
    return dict(lag1_acf=float(r1), Z_tfpw=m["Z"], p_tfpw=m["p"],
                sen_slope_tfpw=b2, sen_lo_tfpw=lo2, sen_hi_tfpw=hi2, n_eff=n - 1)


def pettitt(y):
    """Pettitt (1979) 变点检验。返回 (K, 变点索引 0-based, 近似 p)。"""
    y = np.asarray(y, dtype=float)
    n = len(y)
    U = np.zeros(n)
    for t in range(1, n):
        U[t] = sum(np.sign(y[t:] - y[i]).sum() for i in range(t))
    K = float(np.max(np.abs(U)))
    tau = int(np.argmax(np.abs(U)))
    p = float(min(2.0 * np.exp(-6.0 * K ** 2 / (n ** 3 + n ** 2)), 1.0))
    return K, tau, p


def robust_z_2005(y):
    """相对序列中位数的稳健 z 分数（MAD 口径，1.4826·MAD 为尺度）。"""
    y = np.asarray(y, dtype=float)
    med = float(np.median(y))
    mad = float(np.median(np.abs(y - med)))
    return (float((y[0] - med) / (1.4826 * mad)) if mad > 0 else np.nan), med, mad