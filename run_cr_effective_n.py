# -*- coding: utf-8 -*-
"""Clifford–Richardson 有效样本量（effective sample size）修正

问题：点尺度分析把 1,914 个 0.15° 格点当独立样本（Moran's I = 0.6431）。点尺度
ESI–NDVI 相关 r=0.705（n=1,785）与 4 个因子的 GeoDetector q 的 F 检验，自由度都
按 n 计，标准误被低估。本脚本给出有效样本量 n_eff 与保守自由的 p / 置信区间。

方法（Clifford, Richardson & Hémon 1989, Biometrics 45:123–134；Dutilleul 1993）
  Var(r) ≈ (1/n²) Σ_i Σ_j ρ_x(d_ij) ρ_y(d_ij)
  ⇒ n_eff = n² / Σ_{i,j} ρ_x ρ_y = n / (1 + S/n)，S = Σ_{i≠j} ρ_x(d_ij) ρ_y(d_ij)
  ρ 为两过程的空间自相关函数，由格点上的经验自相关函数估计（平稳假设、全局均值方差）。
  在规则矩形格点上 (di,dj) 与 (−di,−dj) 两类有序对数目相同、ρ 相同，故
  S = 2·Σ_{上半类} N_pair(di,dj)·ρ_x·ρ_y；脚本内校验 Σ w·N_pair = n(n−1)。

估计量的支撑度规则（关键，见 data/_stat_work 诊断）
  朴素地对**全部**滞后类求和会失真：矩形域边缘的滞后类只剩 1–2 对样本，
  ρ 估计方差极大（单对乘积可达数倍方差），把 S/n 从 ~76 抬到 ~212，
  n_eff 由 23 掉到 8。故主口径取**有充分支撑**的滞后带：
     max(|di|,|dj|) ≤ 10 格（=1.5°，即 ESI 相关图由 0.62 衰减到 0.17、趋零的尺度）
     且 每个滞后类成对样本数 ≥ 10%·n
  这一口径与"环面平移零分布"的独立估计互相印证（见下），并在脚本内输出
  截断尺度 5/8/10/14/20 格与全量求和的敏感性范围。

修正推断
  · 相关系数：t = r·sqrt((n_eff−2)/(1−r²))，df = n_eff−2；Fisher z 95% CI，se = 1/sqrt(n_eff−3)。
  · GeoDetector q：F = (q/(k−1))/((1−q)/(n_eff−k))，df = (k−1, n_eff−k)（k = 分层数）。
  · 独立交叉验证①：把所有非平凡环面平移下的 r 作为零分布（不改动任何自相关结构，
    只破坏配准），给出 p_shift 与隐含 n_eff ≈ 1/sd(r_shift)²+2。
  · 独立交叉验证②：空间块 bootstrap（3 格 = 0.45° 整块重抽）的 r 置信区间。

自检
  · Moran's I（k=8 反距离、行标准化）复现归档 0.6431；
  · r 复现归档 0.705413；4 个 q 复现归档 0.8024/0.7077/0.5060/0.1697。

输出 data/results_effective_n.csv
运行：python run_cr_effective_n.py
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
OUT = os.path.join(DATA, "results_effective_n.csv")
sys.path.insert(0, os.path.join(BASE, "eco_security"))
from eco_security import geodetector_q  # noqa: E402

FACTORS = ["barren", "grass", "precip", "temp"]
CELL_DEG = 0.15
MEAN_LAT = 38.3
MAXLAG = 10        # 主口径：滞后带截断（格）
MINPAIR_FRAC = 0.10
TRUNC_SENS = (5, 8, 10, 14, 20)
SEED_BOOT = 20261020

# ---------------------------------------------------------------------------
# 装载 & 还原格点（1,914 点 = 29×66 完整矩形格点）
# ---------------------------------------------------------------------------
pts = pd.read_csv(os.path.join(DATA, "spatial_samples.csv"))
esi = pd.read_csv(os.path.join(DATA, "spatial_esi_points.csv"))
nd = pd.read_csv(os.path.join(DATA, "r28_external_ndvi_points_2020.csv"))
df = esi.merge(pts[["lat", "lon", "temp", "precip", "grass", "barren"]],
               on=["lat", "lon"]).merge(
    nd[["lat", "lon", "ndvi_growing_season_mean"]], on=["lat", "lon"])
lat = np.sort(np.unique(np.round(df["lat"].values, 6)))
lon = np.sort(np.unique(np.round(df["lon"].values, 6)))
R, C = len(lat), len(lon)
assert len(df) == R * C, "样本不是完整矩形格点"
ri = np.searchsorted(lat, np.round(df["lat"].values, 6))
ci = np.searchsorted(lon, np.round(df["lon"].values, 6))


def to_grid(v):
    G = np.full((R, C), np.nan)
    G[ri, ci] = v
    return G


Y = to_grid(df["esi"].values)
NDVI = to_grid(df["ndvi_growing_season_mean"].values)
FAC = {f: to_grid(df[f].values) for f in FACTORS}
print("格点 R=%d × C=%d = %d；NDVI 有效点 %d" % (R, C, R * C,
      int(np.isfinite(NDVI).sum())))

# ---------------------------------------------------------------------------
# 自检 1：Moran's I（k=8 反距离 kNN、行标准化）复现归档 0.6431
# ---------------------------------------------------------------------------
def moran_i_knn(Z, k=8):
    m = np.isfinite(Z)
    z = Z.ravel()[m.ravel()]
    # 与归档 run_r28_t6_trend_moran.py 同口径：P=[lon, lat]，经纬度直接作平面坐标
    P = np.column_stack([np.tile(lon, R)[m.ravel()], np.repeat(lat, C)[m.ravel()]])
    n = len(z)
    d = np.sqrt(((P[:, None, :] - P[None, :, :]) ** 2).sum(axis=2))
    np.fill_diagonal(d, np.inf)
    nb = np.argsort(d, axis=1)[:, :k]
    W = np.zeros((n, n))
    rows = np.repeat(np.arange(n), k)
    cols = nb.ravel()
    W[rows, cols] = 1.0 / d[rows, cols]
    W /= W.sum(axis=1, keepdims=True)
    zc = z - z.mean()
    return float((n / W.sum()) * float(zc @ (W @ zc)) / float(zc @ zc))


I_obs = moran_i_knn(Y)
print("自检 Moran's I(k=8, 反距离) = %.4f（归档 0.6431）" % I_obs)
assert abs(I_obs - 0.6431) < 1e-3, "Moran's I 未复现归档值"

# ---------------------------------------------------------------------------
# 滞后类集合
# ---------------------------------------------------------------------------
LAGS = []
for di in range(0, R):
    for dj in range(1, C):
        LAGS.append((di, dj, 2))          # (di,+dj) 与 (−di,−dj)
        if di > 0:
            LAGS.append((-di, dj, 2))     # (−di,+dj) 与 (di,−dj)
for di in range(1, R):
    LAGS.append((di, 0, 2))               # (di,0) 与 (−di,0)
assert len(LAGS) == (2 * R - 1) * (C - 1) + (R - 1)


def lag_slices(di, dj):
    r0, r1 = max(0, -di), min(R, R - di)
    c0, c1 = max(0, -dj), min(C, C - dj)
    return slice(r0, r1), slice(c0, c1), slice(r0 + di, r1 + di), slice(c0 + dj, c1 + dj)


def _pairs(mask, di, dj):
    sa, sb, ta, tb = lag_slices(di, dj)
    m = mask[sa, sb] & mask[ta, tb]
    return sa, sb, ta, tb, m, int(m.sum())


def check_pair_count(mask):
    """自检 2：Σ w·N_pair 必须等于 n(n−1)，否则滞后类有重复/漏计"""
    n = int(mask.sum())
    tot = sum(w * _pairs(mask, di, dj)[5] for di, dj, w in LAGS)
    assert tot == n * (n - 1), "%d != %d" % (tot, n * (n - 1))
    return n


def cr_n_eff(Zx, Zy, mask, maxlag=MAXLAG, minfrac=MINPAIR_FRAC):
    """Clifford–Richardson 有效样本量；返回 (n_eff, S/n, 使用滞后类数)"""
    n = int(mask.sum())
    mx, vx = float(Zx[mask].mean()), float(Zx[mask].var())
    my, vy = float(Zy[mask].mean()), float(Zy[mask].var())
    S, used = 0.0, 0
    for di, dj, w in LAGS:
        if maxlag is not None and max(abs(di), abs(dj)) > maxlag:
            continue
        sa, sb, ta, tb, m, npr = _pairs(mask, di, dj)
        if npr < max(50, minfrac * n):
            continue
        a = Zx[sa, sb][m] - mx
        b = Zx[ta, tb][m] - mx
        rx = float((a * b).sum()) / (npr * vx)
        a = Zy[sa, sb][m] - my
        b = Zy[ta, tb][m] - my
        ry = float((a * b).sum()) / (npr * vy)
        S += w * npr * rx * ry
        used += 1
    return n / (1.0 + S / n), S / n, used


def fisher_ci(r, n):
    z = np.arctanh(r)
    se = 1.0 / np.sqrt(max(n - 3, 1))
    return float(np.tanh(z - 1.959964 * se)), float(np.tanh(z + 1.959964 * se))


# ---------------------------------------------------------------------------
# 1) 点尺度 ESI–NDVI 相关 r = 0.705
# ---------------------------------------------------------------------------
mask_nd = np.isfinite(NDVI) & np.isfinite(Y)
n_nd = check_pair_count(mask_nd)
r_obs = float(np.corrcoef(Y[mask_nd], NDVI[mask_nd])[0, 1])
print("\n=== 点尺度 ESI–NDVI 相关 ===")
print("n=%d, r=%.6f（归档 0.705413）" % (n_nd, r_obs))
assert abs(r_obs - 0.705413) < 1e-5

n_eff_r, red_r, used_r = cr_n_eff(NDVI, Y, mask_nd)
sens_r = [cr_n_eff(NDVI, Y, mask_nd, maxlag=ml)[0] for ml in TRUNC_SENS]
ne_raw, S_raw, _ = cr_n_eff(NDVI, Y, mask_nd, maxlag=None, minfrac=0.0)
print("CR 主口径（|lag|<=%d 格, minpair>=%d%%n，%d 类）: S/n=%.1f → n_eff=%.1f（收缩 %.1f 倍）"
      % (MAXLAG, MINPAIR_FRAC * 100, used_r, red_r, n_eff_r, n_nd / n_eff_r))
print("  截断敏感性 n_eff（%s 格）= %s；全量求和 n_eff=%.1f（边缘滞后类失真，见下）"
      % ("/".join(map(str, TRUNC_SENS)), ", ".join("%.1f" % v for v in sens_r), ne_raw))

t_naive = r_obs * np.sqrt((n_nd - 2) / (1 - r_obs ** 2))
p_naive = float(2 * stats.t.sf(abs(t_naive), n_nd - 2))
t_corr = r_obs * np.sqrt((n_eff_r - 2) / (1 - r_obs ** 2))
p_corr = float(2 * stats.t.sf(abs(t_corr), n_eff_r - 2))
ci_naive = fisher_ci(r_obs, n_nd)
ci_corr = fisher_ci(r_obs, n_eff_r)
print("  名义: t=%.2f df=%d p=%.2e 95%%CI=[%.3f, %.3f]"
      % (t_naive, n_nd - 2, p_naive, ci_naive[0], ci_naive[1]))
print("  修正: t=%.2f df=%.1f p=%.2e 95%%CI=[%.3f, %.3f]"
      % (t_corr, n_eff_r - 2, p_corr, ci_corr[0], ci_corr[1]))

# 交叉验证①：环面平移零分布（只破坏配准，不改变任何自相关结构）
rs = []
for di in range(R):
    for dj in range(C):
        if di == 0 and dj == 0:
            continue
        S_ = np.roll(np.roll(NDVI, di, axis=0), dj, axis=1)
        m = np.isfinite(S_)
        rs.append(float(np.corrcoef(Y[m], S_[m])[0, 1]))
rs = np.array(rs)
p_shift = (np.sum(rs >= r_obs) + 1) / (len(rs) + 1)
ne_from_shift = 1.0 / rs.std(ddof=1) ** 2 + 2
print("  交叉验证① 环面平移零分布（%d 位移）: sd(r)=%.3f  max=%.3f  p_shift=%.4f  隐含 n_eff=%.1f"
      % (len(rs), rs.std(ddof=1), rs.max(), p_shift, ne_from_shift))

# 交叉验证②：空间块 bootstrap（3 格 = 0.45° 整块重抽）
blocks = []
for b in range(0, R, 3):
    for c in range(0, C, 3):
        rr = np.arange(b, min(R, b + 3))
        cc = np.arange(c, min(C, c + 3))
        blocks.append((rr[:, None] * C + cc[None, :]).ravel())
blocks = np.array(blocks, dtype=object)
rng_b = np.random.default_rng(SEED_BOOT)
yv, nv = Y.ravel(), NDVI.ravel()
boot = []
for _ in range(999):
    pick = rng_b.integers(0, len(blocks), len(blocks))
    ii = np.concatenate([blocks[k] for k in pick])
    ii = ii[np.isfinite(nv[ii])]
    boot.append(float(np.corrcoef(yv[ii], nv[ii])[0, 1]))
boot = np.array(boot)
print("  交叉验证② 块 bootstrap(%d 块 0.45°) 95%%CI=[%.3f, %.3f]（块重抽不移动域尺度趋势，偏窄）"
      % (len(blocks), np.percentile(boot, 2.5), np.percentile(boot, 97.5)))

rows = [dict(item="r(ESI, NDVI)", x="NDVI", y="ESI", n=n_nd, statistic="pearson_r",
             value=r_obs, n_eff=n_eff_r, spatial_redundancy=red_r,
             n_eff_min=float(min(sens_r)), n_eff_max=float(max(sens_r)),
             df_naive=n_nd - 2, df_corrected=n_eff_r - 2,
             p_naive=p_naive, p_corrected=p_corr,
             ci_naive_lo=ci_naive[0], ci_naive_hi=ci_naive[1],
             ci_corrected_lo=ci_corr[0], ci_corrected_hi=ci_corr[1],
             p_shift_null=p_shift, n_eff_from_shift=ne_from_shift,
             boot_ci_lo=float(np.percentile(boot, 2.5)),
             boot_ci_hi=float(np.percentile(boot, 97.5)),
             verdict=("仍显著" if p_corr <= 0.05 else "**不再显著**"),
             note="CR n_eff；Fisher z 95%CI；交叉验证=环面平移零分布+块bootstrap")]

# ---------------------------------------------------------------------------
# 2) 4 个 q 值的修正 F 检验
# ---------------------------------------------------------------------------
print("\n=== GeoDetector q 的有效样本量与修正 F 检验 ===")
print("%-7s %-7s %-3s %-6s %-7s %-7s %-10s %-9s %s"
      % ("factor", "q", "k", "n", "S/n", "n_eff", "p_名义", "p_修正", "判定"))
arch = pd.read_csv(os.path.join(DATA, "results_geodetector_pvalues.csv")).set_index("factor")
mask_all = np.isfinite(Y)
check_pair_count(mask_all)
for f in FACTORS:
    mask = mask_all & np.isfinite(FAC[f])
    lab = np.digitize(FAC[f][mask], np.quantile(FAC[f][mask], [.25, .5, .75]))
    q_obs = float(geodetector_q(Y[mask], lab))
    assert abs(q_obs - float(arch.loc[f, "q"])) < 1e-5, "%s 基线 q 未复现" % f
    k = len(np.unique(lab))
    n = int(mask.sum())
    n_eff, red, used = cr_n_eff(FAC[f], Y, mask)
    sens = [cr_n_eff(FAC[f], Y, mask, maxlag=ml)[0] for ml in TRUNC_SENS]
    df1, df2n = k - 1, n - k
    p_naive = float(stats.f.sf((q_obs / df1) / ((1 - q_obs) / df2n), df1, df2n))
    df2c = max(n_eff - k, 1.0)
    p_corr = float(stats.f.sf((q_obs / df1) / ((1 - q_obs) / df2c), df1, df2c))
    verdict = "仍显著" if p_corr <= 0.05 else "**不再显著**"
    print("%-7s %-7.4f %-3d %-6d %-7.1f %-7.1f %-10.2e %-9.4f %s"
          % (f, q_obs, k, n, red, n_eff, p_naive, p_corr, verdict))
    rows.append(dict(item="q(%s)" % f, x=f, y="ESI", n=n, statistic="geodetector_q",
                     value=q_obs, n_eff=n_eff, spatial_redundancy=red,
                     n_eff_min=float(min(sens)), n_eff_max=float(max(sens)),
                     df_naive=df2n, df_corrected=df2c,
                     p_naive=p_naive, p_corrected=p_corr,
                     ci_naive_lo=np.nan, ci_naive_hi=np.nan,
                     ci_corrected_lo=np.nan, ci_corrected_hi=np.nan,
                     p_shift_null=np.nan, n_eff_from_shift=np.nan,
                     boot_ci_lo=np.nan, boot_ci_hi=np.nan, verdict=verdict,
                     note="F(%d, %.1f)；截断敏感性 n_eff %s"
                          % (df1, df2c, "/".join("%.1f" % v for v in sens))))

print("\nn_eff 范围 %.1f–%.1f（对 n=1,785–1,914 的全部点尺度检验）；"
      "收缩倍数 %.0f–%.0f 倍"
      % (min(r["n_eff"] for r in rows), max(r["n_eff"] for r in rows),
         min(r["n"] / r["n_eff"] for r in rows), max(r["n"] / r["n_eff"] for r in rows)))

out = pd.DataFrame(rows)
PCOLS = [c for c in out.columns if c.startswith("p_")]
for c in out.columns:
    if out[c].dtype.kind != "f":
        continue
    if c in PCOLS:  # p 值保留 4 位有效数字，避免 8.07e-269 被四舍五入成 0.0
        out[c] = out[c].map(lambda v: float("%.4g" % v) if np.isfinite(v) else v)
    else:
        out[c] = out[c].map(lambda v: round(float(v), 6))
out.to_csv(OUT, index=False, encoding="utf-8-sig")
print("已保存: %s（%d 行）" % (OUT, len(out)))
