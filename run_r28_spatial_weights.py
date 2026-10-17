# -*- coding: utf-8 -*-
"""R28-T4.4 · 空间权重方案敏感性（Moran's I 与空间自相关稳健性）
（审稿意见第 3 条：空间归因的内部效度）

────────────────────────────────────────────────────────────────────────────
背景
────────────────────────────────────────────────────────────────────────────
归档 data/results_moran.csv 只报了一个 Moran's I = 0.643（p=0.005，n=1914），
未说明权重矩阵。本脚本在多种权重矩阵下重算 Moran's I，并检验：
  · ESI 自身的空间自相关；
  · 严格外生因子（高程、坡度）无法解释的空间结构（OLS 残差的 Moran's I）；
  · 含内生因子（降水、气温）的对照。
若外生因子回归后残差仍显著空间自相关，说明外生地形/气候因子没有解释 ESI 的
整体空间格局。

────────────────────────────────────────────────────────────────────────────
权重矩阵（1914 个 0.15° 规则格点）
────────────────────────────────────────────────────────────────────────────
rook_grid（0.15° 正交 4 邻域）、queen_grid（0.15° 含对角 8 邻域）、
knn4 / knn8 / knn12、距离带 0.15° / 0.30° / 0.50°、反距离（knn8 加权）。
每种均给二值（binary）与行标准化（row_standardised）两版。

Moran's I = (n / S0) · (z' W z) / (z' z)，z 为中心化变量；
推断用 999 次随机置换（seed=42），p = (1 + #{I_perm >= I}) / 1000。

────────────────────────────────────────────────────────────────────────────
数据来源（已入库）
· data/spatial_samples.csv、data/spatial_esi_points.csv、data/_aux_terrain_points.csv
输出：data/r28_spatial_weights.csv
运行：python run_r28_spatial_weights.py
"""
import os
import sys

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.neighbors import NearestNeighbors

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
N_PERM = 999
SEED = 42
GRID_STEP = 0.15


def build_W(coords, kind):
    """返回 (W_sparse, 描述)。coords: (n,2) [lat, lon]。"""
    n = len(coords)
    if kind in ("rook_grid", "queen_grid"):
        # 规则格点：按 0.15° 网格索引
        keys = {}
        gi = np.round((coords[:, 0] - coords[:, 0].min()) / GRID_STEP).astype(int)
        gj = np.round((coords[:, 1] - coords[:, 1].min()) / GRID_STEP).astype(int)
        for k, (a, b) in enumerate(zip(gi, gj)):
            keys[(a, b)] = k
        offs = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        if kind == "queen_grid":
            offs += [(1, 1), (1, -1), (-1, 1), (-1, -1)]
        r, c = [], []
        for k, (a, b) in enumerate(zip(gi, gj)):
            for da, db in offs:
                j = keys.get((a + da, b + db))
                if j is not None:
                    r.append(k)
                    c.append(j)
        W = sparse.csr_matrix((np.ones(len(r)), (r, c)), shape=(n, n))
        return W, "grid contiguity (%s)" % kind
    if kind.startswith("knn") or kind == "invdist_knn8":
        kk = int(kind.replace("invdist_knn8", "knn8").replace("knn", ""))
        nn = NearestNeighbors(n_neighbors=kk + 1).fit(coords)
        dist, idx = nn.kneighbors(coords)
        r = np.repeat(np.arange(n), kk)
        c = idx[:, 1:].ravel()
        if kind == "invdist_knn8":
            d = dist[:, 1:].ravel()
            v = 1.0 / np.maximum(d, 1e-9)
        else:
            v = np.ones(len(r))
        W = sparse.csr_matrix((v, (r, c)), shape=(n, n))
        return W, "k-nearest neighbours k=%d%s" % (kk, " (inverse distance)" if "invdist" in kind else "")
    if kind.startswith("band"):
        rad = float(kind.split("_")[1].replace("p", "."))
        nn = NearestNeighbors(radius=rad).fit(coords)
        dist, idx = nn.radius_neighbors(coords)
        r = np.repeat(np.arange(n), [len(a) - 1 for a in idx])
        c = np.concatenate([a[1:] for a in idx])
        W = sparse.csr_matrix((np.ones(len(r)), (r, c)), shape=(n, n))
        return W, "distance band %.2f deg" % rad
    raise ValueError(kind)


def row_standardise(W):
    s = np.asarray(W.sum(axis=1)).ravel()
    s[s == 0] = 1.0
    return sparse.diags(1.0 / s) @ W


def morans_i(W, z):
    n = len(z)
    S0 = float(W.sum())
    if S0 == 0:
        return np.nan
    zc = z - z.mean()
    denom = float(zc @ zc)
    if denom == 0:
        return np.nan
    num = float(zc @ (W @ zc))
    return (n / S0) * (num / denom)


def morans_p(W, z, n_perm=N_PERM, seed=SEED):
    obs = morans_i(W, z)
    rng = np.random.default_rng(seed)
    cnt = sum(1 for _ in range(n_perm) if morans_i(W, rng.permutation(z)) >= obs)
    return obs, float((1.0 + cnt) / (n_perm + 1.0))


def ols_resid(y, X):
    """带截距 OLS，返回 (残差, R2, 系数)。"""
    A = np.column_stack([np.ones(len(y)), X])
    beta, *_ = np.linalg.lstsq(A, y, rcond=None)
    fit = A @ beta
    e = y - fit
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - float(np.sum(e ** 2)) / ss_tot if ss_tot > 0 else np.nan
    return e, r2, beta


def main():
    smp = pd.read_csv(os.path.join(DATA, "spatial_samples.csv"))
    esp = pd.read_csv(os.path.join(DATA, "spatial_esi_points.csv"))
    ter = pd.read_csv(os.path.join(DATA, "_aux_terrain_points.csv"))
    df = smp.merge(esp[["lat", "lon", "esi"]], on=["lat", "lon"], how="inner")
    df = df.merge(ter[["lat", "lon", "elev", "slope"]], on=["lat", "lon"], how="inner")
    n = len(df)
    print("=" * 78)
    print("R28-T4.4 · 空间权重方案敏感性（n=%d，置换 %d 次）" % (n, N_PERM))
    print("=" * 78)
    coords = df[["lat", "lon"]].values.astype(float)
    esi = df["esi"].values.astype(float)

    # 变量与残差
    X_ter = df[["elev", "slope"]].values.astype(float)
    X_exo4 = df[["precip", "temp", "elev", "slope"]].values.astype(float)
    X_all = df[["precip", "temp", "grass", "barren", "elev", "slope"]].values.astype(float)
    r_ter, r2_ter, _ = ols_resid(esi, X_ter)
    r_exo4, r2_exo4, _ = ols_resid(esi, X_exo4)
    r_all, r2_all, _ = ols_resid(esi, X_all)
    print("\nOLS 解释力（线性 R²，带截距）：")
    print("   仅严格外生 {elev, slope}          R² = %.4f" % r2_ter)
    print("   外生 4 因子 {precip,temp,elev,slope} R² = %.4f" % r2_exo4)
    print("   上述 4 因子 + {grass, barren}       R² = %.4f" % r2_all)

    variables = {
        "esi": esi,
        "resid_OLS_exogenous_terrain_only": r_ter,
        "resid_OLS_exogenous4_precip_temp_elev_slope": r_exo4,
        "resid_OLS_all6": r_all,
    }
    kinds = ["rook_grid", "queen_grid", "knn4", "knn8", "knn12",
             "band_0p15", "band_0p30", "band_0p50", "invdist_knn8"]
    rows = []
    for kind in kinds:
        W0, desc = build_W(coords, kind)
        for std in [False, True]:
            W = row_standardise(W0) if std else W0
            nb = np.asarray((W0 > 0).sum(axis=1)).ravel()
            for vname, v in variables.items():
                I, p = morans_p(W, v)
                rows.append({
                    "weight_matrix": kind, "description": desc,
                    "row_standardised": bool(std),
                    "variable": vname,
                    "n": n, "mean_neighbours": round(float(nb.mean()), 3),
                    "morans_i": round(float(I), 6), "p_perm": round(p, 4),
                    "ols_r2_for_this_residual": (round({"esi": np.nan,
                        "resid_OLS_exogenous_terrain_only": r2_ter,
                        "resid_OLS_exogenous4_precip_temp_elev_slope": r2_exo4,
                        "resid_OLS_all6": r2_all}[vname], 6)),
                })
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(DATA, "r28_spatial_weights.csv"),
               index=False, encoding="utf-8-sig")

    print("\nMoran's I（行标准化权重）：")
    piv = out[out.row_standardised].pivot_table(index="weight_matrix",
                                               columns="variable", values="morans_i")
    print(piv.round(4).to_string())
    print("\nMoran's I（二值权重）：")
    piv2 = out[~out.row_standardised].pivot_table(index="weight_matrix",
                                                 columns="variable", values="morans_i")
    print(piv2.round(4).to_string())
    print("\n显著性与取值范围：")
    for v in variables:
        d = out[out.variable == v]
        print("   %-44s I: %.3f-%.3f（中位数 %.3f），p<0.05 的比例 %.2f"
              % (v, d.morans_i.min(), d.morans_i.max(), d.morans_i.median(),
                 float((d.p_perm < 0.05).mean())))
    print("\n归档 data/results_moran.csv: Moran's I = 0.6431, p = 0.005, n = 1914")
    print("已写出：data/r28_spatial_weights.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())