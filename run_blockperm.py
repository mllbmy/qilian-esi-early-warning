# -*- coding: utf-8 -*-
"""空间块置换检验（block permutation test）——修正 GeoDetector q 的名义 p 值

背景：1,914 个 0.15° 格点存在强空间自相关（Moran's I = 0.6431），而
run_geodetector_pvalues.py 的 999 次置换把点当独立样本重排因子分层标签，
零假设下的样本不独立 ⇒ 名义 p 值偏乐观。本脚本用**空间块置换**重算 p：

零假设与检验量
  · 检验量仍是 GeoDetector q = 1 - Σ_h N_h σ_h² / (N σ²)（与
    eco_security.geodetector_q 逐位一致，见脚本内 assert）。
  · 方案 A（block toroidal shift，主方案）：把响应面（ESI 或等价的因子面）
    在格点环面上整体平移 (di, dj)，di、dj 取块大小的整数倍，环绕回卷。
    平移只破坏"配准"（x–y 的对应关系），完整保留两张面各自的块内与块间
    自相关结构 —— 这是格点数据受限随机化的标准做法（Fortin & Dale 2005;
    Legendre & Legendre 2012: "toroidal shift"）。q(x_i, y_{i+δ}) 与
    q(x_{i-δ}, y_i) 等价，故"移 y"与"移 x"给出同一分布，不存在口径歧义。
  · 方案 B（block unit permutation，对照）：以块为置换单位，整块移动；
    格点尺度上块大小不完全相等（R=29、C=66 不能被 mb 整除以外的情形），
    故按"块内点数相同"分组置换，保证是 y 的严格重排。整块置换保留了块内
    自相关、破坏块间连续性，比方案 A 更激进，作为敏感性对照。

块大小必须与 0.15° 采样格点对齐，故实际块边长为 0.15° 的整数倍：
    mb=2 -> 0.30°（≈33 km，对应任务书 0.25° 档）
    mb=3 -> 0.45°（≈50 km，对应任务书 0.5° 档，也≈CRU 0.5° 气候格网）
    mb=4 -> 0.60°（≈67 km，额外敏感性）
999 次置换，随机种子 SEED 写死；名义 p 用 iid 置换（999 次、seed=42，
与 run_geodetector_pvalues.py 完全同口径）复算以便并列对照。

第三部分（p 值校准 / placebo 检验）：把响应面（ESI）整体随机平移，破坏
其与 4 个因子的真实配准、但完整保留 ESI 的空间自相关结构与边缘分布；此时
真实关联已被破坏（零假设成立），于是"该检验在此情形下的拒真率"就是它的第一类
错误率。名义 5% 下，若某种置换口径的拒真率远高于 5%，即证明其 p 值偏乐观。

输出
  data/results_blockperm_q.csv                   主结果（4 因子 × 名义 + 4 块大小 × 2 方案）
  paper-code/_stat_work/results_pvalue_calibration.csv   第一类错误率校准结果

运行：python run_blockperm.py
"""
import os
import sys

import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
OUT = os.path.join(DATA, "results_blockperm_q.csv")
sys.path.insert(0, os.path.join(BASE, "eco_security"))
from eco_security import geodetector_q  # noqa: E402

NPERM = 999
SEED_IDD = 42          # 与 run_geodetector_pvalues.py 同口径
SEED_BLOCK = 20261020  # 块置换固定种子
FACTORS = ["barren", "grass", "precip", "temp"]  # 按既有 q 值降序
MB_LIST = [1, 2, 3, 4]
CELL_DEG = 0.15
KM_PER_DEG = 111.32
MEAN_LAT = 38.3

# ---------------------------------------------------------------------------
# 数据装载：把 1,914 个点还原成完整的 R×C 经纬度格点
# ---------------------------------------------------------------------------
pts = pd.read_csv(os.path.join(DATA, "spatial_samples.csv"))
esi = pd.read_csv(os.path.join(DATA, "spatial_esi_points.csv"))
df = esi.merge(pts[["lat", "lon", "temp", "precip", "grass", "barren"]],
               on=["lat", "lon"]).reset_index(drop=True)
lat = np.sort(np.unique(np.round(df["lat"].values, 6)))
lon = np.sort(np.unique(np.round(df["lon"].values, 6)))
R, C = len(lat), len(lon)
assert len(df) == R * C, "样本不是完整经纬度矩形格点：%d != %d*%d" % (len(df), R, C)
ri = np.searchsorted(lat, np.round(df["lat"].values, 6))
ci = np.searchsorted(lon, np.round(df["lon"].values, 6))
assert len(np.unique(ri * C + ci)) == len(df), "格点坐标有重复"

Y = np.empty((R, C))
Y[ri, ci] = df["esi"].values
y = df["esi"].values


def disc(x, k=4):
    """四分位分层（与 run_geodetector_pvalues.py 逐字一致）"""
    qs = np.quantile(x, np.linspace(0, 1, k + 1)[1:-1])
    return np.digitize(x, qs)


STRATA = {}
for f in ["temp", "precip", "grass", "barren"]:
    lab = disc(df[f].values, 4)
    S = np.empty((R, C), dtype=np.int32)
    S[ri, ci] = lab
    STRATA[f] = S


def q_fast(yv, sv):
    """向量化 q（与 geodetector_q 同式；脚本内会做逐位 assert）"""
    yv = np.asarray(yv, dtype=float).ravel()
    sv = np.asarray(sv, dtype=np.int64).ravel()
    N = yv.size
    sst = float(((yv - yv.mean()) ** 2).sum())
    if sst < 1e-12:
        return 0.0
    k = int(sv.max()) + 1
    cnt = np.bincount(sv, minlength=k).astype(float)
    sy = np.bincount(sv, weights=yv, minlength=k)
    sy2 = np.bincount(sv, weights=yv * yv, minlength=k)
    ok = cnt > 0
    ssw = float(np.sum(sy2[ok] - sy[ok] ** 2 / cnt[ok]))
    return 1.0 - ssw / sst


Q_OBS = {}
print("=== 基线 q 复现（与 results_geodetector_pvalues.csv 对照）===")
arch = pd.read_csv(os.path.join(DATA, "results_geodetector_pvalues.csv"))
arch = arch.set_index("factor")
for f in FACTORS:
    s = STRATA[f]
    assert np.allclose(np.sort(s.ravel()), np.sort(disc(df[f].values, 4)))
    qv = q_fast(y, s)
    q_ref = float(geodetector_q(y, disc(df[f].values, 4)))
    Q_OBS[f] = qv
    print("%-8s q=%.6f  geodetector_q=%.6f  归档=%.6f  层数=%d"
          % (f, qv, q_ref, float(arch.loc[f, "q"]), len(np.unique(s))))
    assert abs(qv - q_ref) < 1e-10
    assert abs(qv - float(arch.loc[f, "q"])) < 1e-5, "基线 q 未复现"

print("\n格点：R=%d 行 × C=%d 列 = %d 点（完整矩形），格距 %.2f°，跨度 %.2f°×%.2f°"
      % (R, C, R * C, CELL_DEG, (R - 1) * CELL_DEG, (C - 1) * CELL_DEG))


# ---------------------------------------------------------------------------
# 方案 0：iid 置换（名义 p，复算既有口径）
# ---------------------------------------------------------------------------
def p_iid(yv, sv, q_obs, rng):
    """iid 置换（名义 p 的既有口径）；同时返回零分布统计量用于与块零分布对照。"""
    qs = np.empty(NPERM)
    for i in range(NPERM):
        qs[i] = q_fast(yv, rng.permutation(sv))
    p = (np.sum(qs >= q_obs) + 1) / (NPERM + 1)
    return p, qs


# ---------------------------------------------------------------------------
# 方案 A：块尺度环面平移（toroidal shift）
# ---------------------------------------------------------------------------
def perm_toroidal(Ymat, strata, mb, q_obs, rng):
    di_opts = np.arange(0, R, mb)   # 必须是块大小的整数倍，等价于整块平移
    dj_opts = np.arange(0, C, mb)
    qs = np.empty(NPERM)
    n = 0
    while n < NPERM:
        di = int(di_opts[rng.integers(len(di_opts))])
        dj = int(dj_opts[rng.integers(len(dj_opts))])
        if di == 0 and dj == 0:
            continue
        Ys = np.roll(np.roll(Ymat, di, axis=0), dj, axis=1)
        qs[n] = q_fast(Ys, strata)
        n += 1
    p = (np.sum(qs >= q_obs) + 1) / (NPERM + 1)
    return p, qs


# ---------------------------------------------------------------------------
# 方案 B：整块置换（block unit permutation，按块内点数同组置换）
# ---------------------------------------------------------------------------
def block_groups(mb):
    """返回 {块内点数: (nb, 该点数) 的平坦索引数组}，用于整块搬移。"""
    grow = (np.arange(R) // mb)
    gcol = (np.arange(C) // mb)
    groups = {}
    for gb in range(grow.max() + 1):
        for gc in range(gcol.max() + 1):
            rows = np.where(grow == gb)[0]
            cols = np.where(gcol == gc)[0]
            idx = (rows[:, None] * C + cols[None, :]).ravel()
            groups.setdefault(idx.size, []).append(idx)
    out = {}
    for size, lst in groups.items():
        # 该组内每块点数相同；拼成 (nb, size) 便于整体置换
        out[size] = np.stack(lst)
    return out


def perm_blockunit(Ymat, strata, mb, q_obs, rng):
    groups = block_groups(mb)
    Yflat = Ymat.ravel().copy()
    qs = np.empty(NPERM)
    for t in range(NPERM):
        newy = np.empty_like(Yflat)
        for size, idx in groups.items():
            nb = idx.shape[0]
            perm = rng.permutation(nb)          # 目标块 <- 源块（同块内点数）
            vals = Yflat[idx]                   # (nb, size)
            np.put(newy, idx.ravel(), vals[perm].ravel())
        qs[t] = q_fast(newy, strata)
    p = (np.sum(qs >= q_obs) + 1) / (NPERM + 1)
    return p, qs


def n_blocks_of(mb):
    return (int(np.ceil(R / mb)) * int(np.ceil(C / mb)))


def block_km(mb):
    return mb * CELL_DEG * KM_PER_DEG


# ---------------------------------------------------------------------------
# 主循环
# ---------------------------------------------------------------------------
rows = []

print("\n=== 名义（iid）置换 p（999 次，seed=%d）===" % SEED_IDD)
rng_iid = np.random.default_rng(SEED_IDD)
P_NOM = {}
for f in FACTORS:
    p, qs = p_iid(y, STRATA[f].ravel(), Q_OBS[f], rng_iid)
    P_NOM[f] = p
    print("%-8s q=%.6f  p_nominal=%.4f  null: mean=%.5f sd=%.5f p95=%.5f max=%.5f"
          % (f, Q_OBS[f], p, qs.mean(), qs.std(ddof=1),
             np.percentile(qs, 95), qs.max()))
    rows.append(dict(factor=f, q_observed=Q_OBS[f], p_nominal=p, p_block=float("nan"),
                     n_blocks=len(y), block_size_km=0.0, block_deg=0.0,
                     block_cells=0, scheme="iid", n_perm=NPERM, seed=SEED_IDD,
                     null_mean_q=qs.mean(), null_sd_q=qs.std(ddof=1),
                     null_p95_q=float(np.percentile(qs, 95)),
                     null_max_q=qs.max(), n_null_ge_obs=int(np.sum(qs >= Q_OBS[f]))))

for mb in MB_LIST:
    rows_scheme = {}
    for scheme, fn, seed in (("toroidal_shift", perm_toroidal, SEED_BLOCK + mb),
                             ("block_unit", perm_blockunit, SEED_BLOCK + 100 + mb)):
        print("\n=== 块置换：%s，块大小 %d 格 = %.2f° ≈ %.0f km，%d 块，seed=%d ==="
              % (scheme, mb, mb * CELL_DEG, block_km(mb), n_blocks_of(mb), seed))
        if mb == 1:
            print("  (mb=1 = 无块约束的细尺度环面平移：保真度最高、最保守的零假设)")
        rng = np.random.default_rng(seed)
        for f in FACTORS:
            p, qs = fn(Y, STRATA[f], mb, Q_OBS[f], rng)
            nb_ge = int(np.sum(qs >= Q_OBS[f]))
            print("%-8s q=%.4f  p_block=%.4f  null: mean=%.4f sd=%.4f p95=%.4f max=%.4f  (#>=obs=%d)"
                  % (f, Q_OBS[f], p, qs.mean(), qs.std(ddof=1), np.percentile(qs, 95), qs.max(), nb_ge))
            rows.append(dict(factor=f, q_observed=Q_OBS[f], p_nominal=P_NOM[f], p_block=p,
                             n_blocks=n_blocks_of(mb), block_size_km=round(block_km(mb), 1),
                             block_deg=round(mb * CELL_DEG, 2), block_cells=mb,
                             scheme=scheme, n_perm=NPERM, seed=seed,
                             null_mean_q=qs.mean(), null_sd_q=qs.std(ddof=1),
                             null_p95_q=float(np.percentile(qs, 95)),
                             null_max_q=qs.max(), n_null_ge_obs=nb_ge))

out = pd.DataFrame(rows)
for c in ["q_observed", "p_nominal", "p_block", "null_mean_q", "null_sd_q",
          "null_p95_q", "null_max_q"]:
    out[c] = out[c].astype(float).round(6)
out.to_csv(OUT, index=False, encoding="utf-8-sig")
print("\n已保存: %s（%d 行）" % (OUT, len(out)))

# ---------------------------------------------------------------------------
# 排序稳定性判定
# ---------------------------------------------------------------------------
print("\n=== q 排序与显著性汇总（主方案 = toroidal_shift, mb=2 与 mb=3）===")
for mb in MB_LIST:
    sub = out[(out.scheme == "toroidal_shift") & (out.block_cells == mb)]
    o = sub.sort_values("q_observed", ascending=False)
    print("块 %d 格（%.2f°≈%.0f km, %d 块）：" % (mb, mb * CELL_DEG, block_km(mb), n_blocks_of(mb)))
    for _, r_ in o.iterrows():
        print("   %-8s q=%.4f  名义 p=%.3f  块 p=%.3f  %s"
              % (r_["factor"], r_["q_observed"], r_["p_nominal"], r_["p_block"],
                 "显著" if r_["p_block"] <= 0.05 else "**不显著**"))

# ---------------------------------------------------------------------------
# 第三部分：p 值校准（placebo 目标，实测第一类错误率）
# ---------------------------------------------------------------------------
N_PLACEBO = 100
SEED_CAL = 20261025
CAL_CSV = os.path.join(BASE, "_stat_work", "results_pvalue_calibration.csv")
MB_PRIMARY = 2

print("\n=== p 值校准：placebo 目标（ESI 面整体平移，真实配准被破坏，零假设成立）===")
print("    名义检验水准 0.05；若实测拒真率 >> 0.05 即说明 p 值偏乐观")
rng_cal = np.random.default_rng(SEED_CAL)

# 平移量：环面位移的格点数（保证位移 >= 10 格 ≈ 1.5°，远超自相关长度，避免残余真实关联）
offsets = []
seen = set()
while len(offsets) < N_PLACEBO:
    di = int(rng_cal.integers(0, R))
    dj = int(rng_cal.integers(0, C))
    d2 = di ** 2 + (dj * np.cos(np.deg2rad(MEAN_LAT))) ** 2
    if np.sqrt(d2) < 10.0 or (di, dj) in seen:
        continue
    seen.add((di, dj))
    offsets.append((di, dj))

di_opts = np.arange(0, R, MB_PRIMARY)
dj_opts = np.arange(0, C, MB_PRIMARY)


def p_toroidal_one(Ymat, strata, q_obs, rng, nperm):
    qs = np.empty(nperm)
    n = 0
    while n < nperm:
        di = int(di_opts[rng.integers(len(di_opts))])
        dj = int(dj_opts[rng.integers(len(dj_opts))])
        if di == 0 and dj == 0:
            continue
        qs[n] = q_fast(np.roll(np.roll(Ymat, di, axis=0), dj, axis=1), strata)
        n += 1
    return (np.sum(qs >= q_obs) + 1) / (nperm + 1)


def p_iid_one(yv, strata_flat, q_obs, rng, nperm):
    qs = np.empty(nperm)
    for i in range(nperm):
        qs[i] = q_fast(yv, rng.permutation(strata_flat))
    return (np.sum(qs >= q_obs) + 1) / (nperm + 1)


def p_blockunit_one(Ymat, strata, q_obs, rng, nperm):
    groups = block_groups(MB_PRIMARY)
    Yflat = Ymat.ravel().copy()
    qs = np.empty(nperm)
    for t in range(nperm):
        newy = np.empty_like(Yflat)
        for size, idx in groups.items():
            nb = idx.shape[0]
            perm = rng.permutation(nb)
            vals = Yflat[idx]
            np.put(newy, idx.ravel(), vals[perm].ravel())
        qs[t] = q_fast(newy, strata)
    return (np.sum(qs >= q_obs) + 1) / (nperm + 1)


CAL_SCHEMES = ("iid", "toroidal_shift", "block_unit")
cal_rows = []
pvals = {s: {f: [] for f in FACTORS} for s in CAL_SCHEMES}
q_placebo = {f: [] for f in FACTORS}
for k, (di, dj) in enumerate(offsets):
    Yp = np.roll(np.roll(Y, di, axis=0), dj, axis=1)
    yp = Yp[ri, ci]
    rng_i = np.random.default_rng(SEED_CAL + 1000 + k)
    rng_b = np.random.default_rng(SEED_CAL + 2000 + k)
    rng_u = np.random.default_rng(SEED_CAL + 3000 + k)
    for f in FACTORS:
        qp = q_fast(yp, STRATA[f])
        q_placebo[f].append(qp)
        pvals["iid"][f].append(p_iid_one(yp, STRATA[f].ravel(), qp, rng_i, NPERM))
        pvals["toroidal_shift"][f].append(
            p_toroidal_one(Yp, STRATA[f], qp, rng_b, NPERM))
        pvals["block_unit"][f].append(
            p_blockunit_one(Yp, STRATA[f], qp, rng_u, NPERM))
    if (k + 1) % 20 == 0:
        print("  placebo %d/%d 完成" % (k + 1, N_PLACEBO))

for scheme in CAL_SCHEMES:
    for f in FACTORS:
        pv = np.array(pvals[scheme][f])
        cal_rows.append(dict(
            convention=scheme, factor=f, n_placebo=N_PLACEBO, n_perm=NPERM,
            min_offset_cells=10.0, block_cells=(0 if scheme == "iid" else MB_PRIMARY),
            frac_p_le_0p05=float(np.mean(pv <= 0.05)),
            frac_p_le_0p01=float(np.mean(pv <= 0.01)),
            mean_p=float(pv.mean()), median_p=float(np.median(pv)),
            mean_placebo_q=float(np.mean(q_placebo[f])),
            block_size_km=(0.0 if scheme == "iid" else round(block_km(MB_PRIMARY), 1))))

cal = pd.DataFrame(cal_rows)
for c in ["frac_p_le_0p05", "frac_p_le_0p01", "mean_p", "median_p", "mean_placebo_q"]:
    cal[c] = cal[c].astype(float).round(4)
cal.to_csv(CAL_CSV, index=False, encoding="utf-8-sig")

print("\n%-18s %-8s %-10s %-12s %-10s %-10s" %
      ("口径", "因子", "拒真率(p<=.05)", "拒真率(p<=.01)", "p 中位数", "placebo q 均值"))
for scheme in CAL_SCHEMES:
    for f in FACTORS:
        r_ = cal[(cal.convention == scheme) & (cal.factor == f)].iloc[0]
        print("%-18s %-8s %-14.3f %-14.3f %-10.3f %.4f"
              % (scheme, f, r_["frac_p_le_0p05"], r_["frac_p_le_0p01"],
                 r_["median_p"], r_["mean_placebo_q"]))
for scheme in CAL_SCHEMES:
    sub = cal[cal.convention == scheme]
    print("%s：4 因子平均拒真率（名义 0.05）= %.3f；p<=0.01 拒真率 = %.3f"
          % (scheme, sub["frac_p_le_0p05"].mean(), sub["frac_p_le_0p01"].mean()))
print("已保存: %s" % CAL_CSV)
