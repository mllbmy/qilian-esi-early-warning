# -*- coding: utf-8 -*-
"""任务② 分数覆被（窗口内各类别面积占比）→ 干净留一目标 GeoDetector

问题（R19/R20 审稿意见）
────────────────────────
归档点尺度 ESI 的覆被项是 **3x3 邻域众数 one-hot**：
    grass/forest/water = 0/1 ；barren_neg = 1 - grass - forest - water
于是 (a) 覆被类因子只有 2 层，信息量极低；
     (b) barren_neg 是 grass/forest/water 的确定性补（和为一），任何留一删除都
         切不干净——删掉 grass 列后 barren_neg 里仍然含 grass。

本方案
──────
1) 分数覆被：对每个点，在与主管线**完全相同**的 ±0.02° 窗口内统计各类别像元
   占有效像元的比例（连续分数，不是众数）。
2) 负向"裸地/退化"指标改为**实测裸地类别占比 f_barren**（类别 7），
   而不是"1 - 其它类之和"的补。这样覆被各分量不再互为代数补，
   留一删除 F 后目标中确实不含 F —— 干净切割。
   （同时给出对照变体 barren_deg = 1 - forest - grass - water - crop，即
     run_county_esi.py county_esi() 的字面补口径，用于说明差异来源。）
3) 指标口径照抄 run_county_esi.py county_esi()：
     正向 [precip, temp, forest, grass, water] + 负向 [barren/退化]
     min-max（11/1914 样本间）→ 熵权 → AHP 等权 → alpha=0.4 线性组合
4) 留一目标：测因子 F 时，从指标集删除 F → 重新 min-max → 重新熵权 →
   AHP 等权 → alpha=0.4 → 得到 ESI_{-F}，再以 ESI_{-F} 为因变量计算 q(F)。
   分层 K=4 样本分位、999 次置换、seed=42、p=(1+#)/1000 —— 与
   run_geodetector_loo.py / run_geodetector_pvalues.py 冻结超参一致。

输入（只读，不修改）
  data/spatial_samples.csv   —— 归档点的 precip/temp（气候原值，非本次验证对象）
  _raw/lc_data/CLCD_v01_2020_albert.tif —— 分数覆被来源
输出（全部新增）
  data/results_fractional_cover_loo.csv      —— 基准 / 留一 / Δ / p 完整表
  data/results_fractional_cover_points.csv   —— 1914 点的分数覆被 + 各口径 ESI
  data/results_fractional_cover_windows.csv  —— 窗口实现审计（尺寸/像元数/nodata）

运行：python run_fractional_cover_loo.py
"""
import os
import sys
import time

import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer
from rasterio.windows import from_bounds

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
sys.path.insert(0, BASE)
import io_utils  # noqa: E402  # R22：共享 I/O 层（目录回退）
LC_DIR = io_utils.resolve_lc_dir()  # QILIAN_LC_DATA -> _raw/lc_data -> 递归兜底
TIF = os.path.join(LC_DIR, "CLCD_v01_2020_albert.tif")
sys.path.insert(0, os.path.join(BASE, "eco_security"))
from eco_security import (  # noqa: E402
    minmax_normalize, entropy_weights, combined_weights, esi_series, geodetector_q,
)

K = 4
N_PERM = 999
SEED = 42
ALPHA = 0.4
POINT_HALF = 0.02
LAT0, LAT1, LON0, LON1 = 36.0, 40.5, 93.5, 103.5
STEP = 0.15

# 归档基准 q（data/results_geodetector_pvalues.csv），仅用于对照，不改动
ARCHIVED_Q = {"precip": 0.506016, "temp": 0.169739, "grass": 0.707710, "barren": 0.802431}

CLASS_COLS = {
    1: "f_crop", 2: "f_forest", 3: "f_shrub", 4: "f_grass",
    5: "f_water", 6: "f_snow", 7: "f_barren", 8: "f_impervious", 9: "f_wetland",
}

# ---- ESI 指标集（口径照抄 run_county_esi.py county_esi()）----
# 主口径 sigma1：负向项 = 实测裸地类占比 f_barren
SPEC_PRIMARY = [
    ("precip", "precip", +1), ("temp", "temp", +1),
    ("forest", "f_forest", +1), ("grass", "f_grass", +1), ("water", "f_water", +1),
    ("barren", "f_barren", -1),
]
# 对照口径 sigma2：负向项 = 1 - forest - grass - water - crop（county_esi 的字面补）
SPEC_COMPLEMENT = [
    ("precip", "precip", +1), ("temp", "temp", +1),
    ("forest", "f_forest", +1), ("grass", "f_grass", +1), ("water", "f_water", +1),
    ("barren", "_barren_deg", -1),
]
FACTOR_COLUMN = {"precip": "precip", "temp": "temp", "forest": "f_forest",
                 "grass": "f_grass", "water": "f_water", "barren": "f_barren"}
FACTOR_ZH = {"precip": "降水", "temp": "气温", "forest": "林地",
             "grass": "草地", "water": "水域", "barren": "裸地/退化"}


# ---------------------------------------------------------------------------
def fractional_cover_points(src, lats, lons, half=POINT_HALF):
    """分数覆被：±half° 窗口内各类别像元占比。

    窗口实现与 run_county_geodetector.py L110-114 逐字一致：
      Transformer(EPSG:4326 -> src.crs) 把经纬度 ±half 转 Albers 米制，
      rasterio.windows.from_bounds 得到窗口，src.read(1, window=win) 读取。
    像元计数方式：窗口内全部 **非 nodata（!=0）** 像元的算术计数（恰为整数个像元，
      不插值、不加权）；分母为该窗口有效像元总数，故各类别占比之和 = 100%。
    """
    tf = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
    rows, audit = [], []
    t0 = time.time()
    for lat in lats:
        for lon in lons:
            x0, y0 = tf.transform(lon - half, lat - half)
            x1, y1 = tf.transform(lon + half, lat + half)
            win = from_bounds(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1), src.transform)
            arr = src.read(1, window=win)
            vals = arr[arr != 0]
            n_valid = int(vals.size)
            hist = np.bincount(vals.astype(np.int64), minlength=10) if n_valid else np.zeros(10, dtype=np.int64)
            rec = {"lat": float(lat), "lon": float(lon)}
            for c, nm in CLASS_COLS.items():
                rec[nm] = float(hist[c]) / n_valid if n_valid else np.nan
            rec["f_other"] = float(hist[3] + hist[6] + hist[8] + hist[9]) / n_valid if n_valid else np.nan
            rows.append(rec)
            audit.append({"lat": float(lat), "lon": float(lon),
                          "win_rows": arr.shape[0], "win_cols": arr.shape[1],
                          "win_pixels": int(arr.size), "win_valid_pixels": n_valid,
                          "win_nodata_pixels": int(arr.size - n_valid)})
    print("    分数覆被采样完成：%d 点，耗时 %.1f s" % (len(rows), time.time() - t0))
    return pd.DataFrame(rows), pd.DataFrame(audit)


def build_esi(df, spec, alpha=ALPHA):
    X = df[[c for _, c, _ in spec]].values.astype(float)
    dirs = [d for _, _, d in spec]
    Xn = minmax_normalize(X, dirs)
    w_ent = entropy_weights(Xn)
    w_ahp = np.ones(len(spec)) / len(spec)
    w = combined_weights(w_ahp, w_ent, alpha)
    return esi_series(Xn, w), w_ent, w, Xn


def discretize(v, k=K):
    """冻结口径：样本分位等样本分层（与 run_geodetector_pvalues.py / loo 脚本一致）。

    注意 numpy 语义：np.digitize(x, bins) 默认 right=False，等价于
    searchsorted(bins, x, side='right')，即返回“bin 边界 <= x 的个数”。
    若某因子 >75% 的取值为 0（零膨胀），则 0.25/0.5/0.75 分位点全为 0，
    所有样本一起落到同一层 -> 分层退化为 1 层 -> q 恒为 0、p 恒为 1。
    这不是 q 的实质结论，而是分层规则的退化（见 strata_zero_inflated 变体）。
    """
    qs = np.quantile(v, np.linspace(0, 1, k + 1)[1:-1])
    return np.digitize(v, qs), qs


def strata_zero_inflated(v, k=K):
    """零膨胀稳健分层变体：先切 0 / >0，再把正值部分按分位切成 (k-1) 段。

    顶层 1 层（取值为 0 的样本）+ 正值部分 k-1 层，合计 <= k 层，
    与冻结口径的层数上限一致，仅避免零膨胀导致的整层塌缩。
    """
    v = np.asarray(v, dtype=float)
    s = np.zeros(len(v), dtype=int)
    pos = v > 0
    s[pos] = 1
    vp = v[pos]
    if vp.size:
        edges = np.unique(np.quantile(vp, np.linspace(0, 1, k)[1:-1]))
        s[pos] = 1 + np.digitize(vp, edges)
    return s


def detect_strata(strata, y, seed=SEED, n_perm=N_PERM):
    n_levels = int(len(np.unique(strata)))
    q = geodetector_q(y, strata)
    rng = np.random.default_rng(seed)
    cnt = 0
    for _ in range(n_perm):
        if geodetector_q(y, rng.permutation(strata)) >= q:
            cnt += 1
    return q, (1.0 + cnt) / (n_perm + 1.0), n_levels


def detect(x, y, seed=SEED, n_perm=N_PERM):
    strata, _ = discretize(x)
    return detect_strata(strata, y, seed, n_perm)


def main():
    print("=" * 88)
    print("任务② 分数覆被 → 干净留一目标 GeoDetector（K=%d, N_per=%d, seed=%d, alpha=%.1f）"
          % (K, N_PERM, SEED, ALPHA))
    print("=" * 88)
    rows_out = []

    # ---------- 1) 分数覆被 ----------
    print("\n[1] 由 CLCD 2020 重建 ±%.2f° 窗口分数覆被" % POINT_HALF)
    lats = np.arange(LAT0 + 0.2, LAT1, STEP)
    lons = np.arange(LON0 + 0.2, LON1, STEP)
    src = rasterio.open(TIF)
    fc, audit = fractional_cover_points(src, [float(v) for v in lats], [float(v) for v in lons])
    print("    窗口尺寸 %d x %d px ；有效像元 min %d / median %d / max %d ；含 nodata 点数 %d"
          % (audit.win_rows.iloc[0], audit.win_cols.iloc[0], audit.win_valid_pixels.min(),
             int(audit.win_valid_pixels.median()), audit.win_valid_pixels.max(),
             int((audit.win_nodata_pixels > 0).sum())))
    print("    窗口内各类别占比之和校验: min %.6f max %.6f（应为 1）"
          % (fc[list(CLASS_COLS.values())].sum(axis=1).min(),
             fc[list(CLASS_COLS.values())].sum(axis=1).max()))

    # ---------- 2) 合并气候 + 派生列 ----------
    arch = pd.read_csv(os.path.join(DATA, "spatial_samples.csv"))
    print("\n[2] 合并归档气候原值（precip/temp 非本次验证对象，直接沿用归档）")
    print("    归档点数 %d ；分数覆被点数 %d" % (len(arch), len(fc)))
    if len(arch) != len(fc):
        print("    !! 点数不一致，终止。"); return 3
    df = fc.copy()
    df["precip"] = arch["precip"].values
    df["temp"] = arch["temp"].values
    df["class_onehot_archived"] = arch["class"].values
    df["_barren_deg"] = (1.0 - df["f_forest"] - df["f_grass"] - df["f_water"] - df["f_crop"]).clip(lower=0.0)
    if bool((audit["win_nodata_pixels"].values > 0).any()):
        print("    注意：%d 个点窗口内含 nodata 像元（已按非 nodata 像元为分母）"
              % int((audit["win_nodata_pixels"].values > 0).sum()))

    # ---------- 3) 两种口径的完整 ESI ----------
    print("\n[3] 重建点尺度 ESI")
    esi_p, w_ent_p, w_p, _ = build_esi(df, SPEC_PRIMARY)
    esi_c, w_ent_c, w_c, _ = build_esi(df, SPEC_COMPLEMENT)
    print("    sigma1（负向=实测 f_barren）       ESI: min %.4f mean %.4f max %.4f"
          % (esi_p.min(), esi_p.mean(), esi_p.max()))
    print("      熵权 %s  组合权重 %s"
          % (np.round(w_ent_p, 5), np.round(w_p, 5)))
    print("    sigma2（负向=1-forest-grass-water-crop，county_esi 字面补）")
    print("      熵权 %s  组合权重 %s" % (np.round(w_ent_c, 5), np.round(w_c, 5)))
    arch_esi = pd.read_csv(os.path.join(DATA, "spatial_esi_points.csv"))["esi"].values
    print("    与归档 one-hot ESI 的相关: sigma1 r = %.4f ; sigma2 r = %.4f"
          % (np.corrcoef(esi_p, arch_esi)[0, 1], np.corrcoef(esi_c, arch_esi)[0, 1]))
    y_p, y_c = esi_p, esi_c

    # ---------- 4) 基准 q（分数覆被 ESI 为目标） ----------
    print("\n[4] 基准 q：目标 = 分数覆被 ESI（sigma1），连续因子按样本分位分 4 层")
    base = {}
    print("    %-8s %10s %10s %8s %6s %12s" % ("factor", "q_baseline", "q_archived", "delta", "p", "levels"))
    for fac in ["precip", "temp", "forest", "grass", "water", "barren"]:
        q, p, lv = detect(df[FACTOR_COLUMN[fac]].values, y_p)
        base[fac] = (q, p, lv)
        aq = ARCHIVED_Q.get(fac, np.nan)
        print("    %-8s %10.6f %10s %8s %6.4f %12d"
              % (fac, q, ("%.6f" % aq) if not np.isnan(aq) else "-",
                 ("%+.4f" % (q - aq)) if not np.isnan(aq) else "-", p, lv))
    # sigma2 基准（对照）
    base_c = {}
    print("    对照 sigma2（负向=补口径）基准 q：")
    for fac in ["precip", "temp", "grass", "barren"]:
        q, p, lv = detect(df[FACTOR_COLUMN[fac]].values, y_c)
        base_c[fac] = (q, p, lv)
        aq = ARCHIVED_Q[fac]
        print("      %-8s q = %.6f  Δ vs 归档 = %+.4f  p = %.4f  (%d 层)" % (fac, q, q - aq, p, lv))

    # ---------- 5) 留一目标（干净切割） ----------
    print("\n[5] 留一目标 LOO：目标 = 剔除 F 后的 ESI_{-F}（sigma1 口径）")
    loo = {}
    for fac in ["precip", "temp", "forest", "grass", "water", "barren"]:
        spec2 = [s for s in SPEC_PRIMARY if s[0] != fac]
        esi_loo, _, _, _ = build_esi(df, spec2)
        q, p, lv = detect(df[FACTOR_COLUMN[fac]].values, esi_loo)
        loo[fac] = (q, p, lv)
        r = float(np.corrcoef(y_p, esi_loo)[0, 1])
        contains = [c for _, c, _ in spec2]
        assert FACTOR_COLUMN[fac] not in contains, "留一目标仍在用 F 的列！"
        print("    %-8s 删除 %-9s 剩 %d 项 %s" % (fac, FACTOR_COLUMN[fac], len(spec2),
                                                  [n for n, _, _ in spec2]))
        print("             q_loo = %.6f  p = %.4f  (%d 层)  corr(ESI_full, ESI_-F) = %.4f"
              % (q, p, lv, r))

    # ---------- 6) 对照：sigma2 的 LOO ----------
    print("\n[6] 对照：sigma2（补口径）下的 LOO —— 说明「补口径切不干净」的残留")
    loo_c = {}
    for fac in ["grass", "barren"]:
        spec2 = [s for s in SPEC_COMPLEMENT if s[0] != fac]
        esi_loo, _, _, _ = build_esi(df, spec2)
        q, p, lv = detect(df[FACTOR_COLUMN[fac]].values, esi_loo)
        loo_c[fac] = (q, p, lv)
        still = "_barren_deg" in [c for _, c, _ in spec2]
        print("    %-8s q_loo(sigma2) = %.6f  p = %.4f  (%d 层)  ; 目标是否仍含 F 经由补项: %s"
              % (fac, q, p, lv, "是(补口径残留)" if still else "否"))

    # ---------- 6b) 零膨胀分层退化诊断 + 稳健分层变体 ----------
    print("\n[6b] 分层退化诊断：分数覆被是零膨胀变量，冻结 K=4 分位分层可能塌缩")
    print("    %-8s %10s %14s %9s %9s %12s" % ("factor", "非零占比", "分位切点", "冻结层数", "变体层数", "变体 q (p)"))
    zi = {}
    for fac in ["precip", "temp", "forest", "grass", "water", "barren"]:
        v = df[FACTOR_COLUMN[fac]].values
        s_frozen, cuts = discretize(v)
        lv_f = int(len(np.unique(s_frozen)))
        q_f, p_f, _ = detect_strata(s_frozen, y_p)
        s_zi = strata_zero_inflated(v)
        q_z, p_z, lv_z = detect_strata(s_zi, y_p)
        zi[fac] = (q_z, p_z, lv_z, float((v > 0).mean()), np.round(cuts, 5))
        print("    %-8s %9.1f%% %14s %9d %9d %6.4f (p=%.4f)"
              % (fac, (v > 0).mean() * 100, str(np.round(cuts, 5)), lv_f, lv_z, q_z, p_z))
        if lv_f == 1:
            print("             !! 冻结口径分层塌缩为 1 层 -> q=0、p=1 属分层伪影，非实质结论")
    # 变体 LOO
    for fac in ["forest", "water"]:
        spec2 = [s for s in SPEC_PRIMARY if s[0] != fac]
        esi_loo, _, _, _ = build_esi(df, spec2)
        q_z, p_z, lv_z = detect_strata(strata_zero_inflated(df[FACTOR_COLUMN[fac]].values), esi_loo)
        zi[fac + "_loo"] = (q_z, p_z, lv_z, float((df[FACTOR_COLUMN[fac]].values > 0).mean()), None)
        print("    变体 LOO %-8s q=%.6f p=%.4f (%d 层)" % (fac, q_z, p_z, lv_z))

    # ---------- 6c) 组成约束（分数覆被的统计共线性） ----------
    print("\n[6c] 分数覆被分量的相关结构（代数上独立，但成分数据仍相互约束）")
    cols = ["f_grass", "f_barren", "f_forest", "f_water", "f_crop"]
    cm = df[cols].corr()
    print(cm.round(3).to_string())
    print("    corr(f_grass, f_barren) = %.3f  （负相关来自成分约束，非代数恒等）"
          % cm.loc["f_grass", "f_barren"])
    print("    一手证据：f_barren 是实测类别 7 占比，不等价于 1-f_forest-f_grass-f_water；")
    print("              max|f_barren - (1 - f_forest - f_grass - f_water)| = %.4f"
          % float(np.abs(df["f_barren"] - (1 - df["f_forest"] - df["f_grass"] - df["f_water"])).max()))

    # ---------- 7) 汇总 ----------
    for fac in ["barren", "grass", "precip", "temp", "forest", "water"]:
        qb, pb, _ = base[fac]
        ql, pl, _ = loo[fac]
        aq = ARCHIVED_Q.get(fac, np.nan)
        rows_out.append({
            "scheme": "fractional_sigma1", "factor": fac, "factor_zh": FACTOR_ZH[fac],
            "q_baseline_fractional": round(qb, 6), "q_loo_fractional": round(ql, 6),
            "delta_q": round(ql - qb, 6),
            "drop_pct": round((ql - qb) / qb * 100, 2) if qb > 0 else np.nan,
            "p_baseline": round(pb, 4), "p_loo": round(pl, 4),
            "q_archived_onehot": (round(aq, 6) if not np.isnan(aq) else np.nan),
            "delta_vs_archived": (round(qb - aq, 6) if not np.isnan(aq) else np.nan),
            "note": "分数覆被；负向项=实测 f_barren；LOO 目标不含 F",
        })
    for fac in ["precip", "temp", "grass", "barren"]:
        qb, pb, _ = base_c[fac]
        aq = ARCHIVED_Q[fac]
        rows_out.append({
            "scheme": "fractional_sigma2_complement", "factor": fac, "factor_zh": FACTOR_ZH[fac],
            "q_baseline_fractional": round(qb, 6), "q_loo_fractional": np.nan, "delta_q": np.nan,
            "drop_pct": np.nan, "p_baseline": round(pb, 4), "p_loo": np.nan,
            "q_archived_onehot": round(aq, 6), "delta_vs_archived": round(qb - aq, 6),
            "note": "对照口径：负向项=1-forest-grass-water-crop（county_esi 字面补）",
        })
    for fac in ["grass", "barren"]:
        ql, pl, _ = loo_c[fac]
        rows_out.append({
            "scheme": "fractional_sigma2_complement_loo", "factor": fac, "factor_zh": FACTOR_ZH[fac],
            "q_baseline_fractional": round(base_c[fac][0], 6), "q_loo_fractional": round(ql, 6),
            "delta_q": round(ql - base_c[fac][0], 6),
            "drop_pct": round((ql - base_c[fac][0]) / base_c[fac][0] * 100, 2),
            "p_baseline": round(base_c[fac][1], 4), "p_loo": round(pl, 4),
            "q_archived_onehot": round(ARCHIVED_Q[fac], 6),
            "delta_vs_archived": round(base_c[fac][0] - ARCHIVED_Q[fac], 6),
            "note": "补口径 LOO：目标经补项仍含 F 的成分 -> 切不干净（对照用）",
        })
    for fac in ["precip", "temp", "forest", "grass", "water", "barren"]:
        qz, pz, lvz, nzs, _ = zi[fac]
        rows_out.append({
            "scheme": "fractional_sigma1_zeroinflated_strata", "factor": fac, "factor_zh": FACTOR_ZH[fac],
            "q_baseline_fractional": round(qz, 6), "q_loo_fractional": np.nan, "delta_q": np.nan,
            "drop_pct": np.nan, "p_baseline": round(pz, 4), "p_loo": np.nan,
            "q_archived_onehot": (round(ARCHIVED_Q[fac], 6) if fac in ARCHIVED_Q else np.nan),
            "delta_vs_archived": (round(qz - ARCHIVED_Q[fac], 6) if fac in ARCHIVED_Q else np.nan),
            "note": "稳健分层变体：先切0/>0，正值部分再切分位；该因子非零占比 %.1f%%，%d 层"
                    % (nzs * 100, lvz),
        })
    for fac in ["forest", "water"]:
        qz, pz, lvz, nzs, _ = zi[fac + "_loo"]
        rows_out.append({
            "scheme": "fractional_sigma1_zeroinflated_strata_loo", "factor": fac,
            "factor_zh": FACTOR_ZH[fac],
            "q_baseline_fractional": round(zi[fac][0], 6), "q_loo_fractional": round(qz, 6),
            "delta_q": round(qz - zi[fac][0], 6),
            "drop_pct": round((qz - zi[fac][0]) / zi[fac][0] * 100, 2) if zi[fac][0] > 0 else np.nan,
            "p_baseline": round(zi[fac][1], 4), "p_loo": round(pz, 4),
            "q_archived_onehot": np.nan, "delta_vs_archived": np.nan,
            "note": "变体 LOO：目标剔除该因子，分层用零膨胀稳健口径（%d 层）" % lvz,
        })
    out = pd.DataFrame(rows_out)
    out.to_csv(os.path.join(DATA, "results_fractional_cover_loo.csv"), index=False, encoding="utf-8-sig")

    # 点位明细
    pts = df[["lat", "lon", "precip", "temp"] + list(CLASS_COLS.values()) + ["f_other", "_barren_deg"]].copy()
    pts["esi_fractional_sigma1"] = esi_p
    pts["esi_fractional_sigma2"] = esi_c
    pts["esi_archived_onehot"] = arch_esi
    pts["class_onehot_archived"] = arch["class"].values
    pts.to_csv(os.path.join(DATA, "results_fractional_cover_points.csv"), index=False, encoding="utf-8-sig")
    audit.to_csv(os.path.join(DATA, "results_fractional_cover_windows.csv"), index=False, encoding="utf-8-sig")

    # ---------- 8) 关键红线判定 ----------
    print("\n" + "=" * 88)
    print("关键红线：新基准 q（分数覆被）vs 归档 q（one-hot）")
    print("=" * 88)
    print("    %-8s %12s %12s %10s %8s" % ("factor", "q_new", "q_archived", "delta", "|Δ|>0.05"))
    flag = False
    for fac in ["precip", "temp", "grass", "barren"]:
        d = base[fac][0] - ARCHIVED_Q[fac]
        bad = abs(d) > 0.05
        flag = flag or bad
        print("    %-8s %12.6f %12.6f %10.6f %8s" % (fac, base[fac][0], ARCHIVED_Q[fac], d,
                                                    "是" if bad else "否"))
    rank_new = sorted(["precip", "temp", "grass", "barren"], key=lambda f: -base[f][0])
    rank_arch = sorted(["precip", "temp", "grass", "barren"], key=lambda f: -ARCHIVED_Q[f])
    print("    排序（分数覆被）= %s" % " > ".join(rank_new))
    print("    排序（归档 one-hot）= %s" % " > ".join(rank_arch))
    order_changed = rank_new != rank_arch
    print("    排序是否改变: %s" % ("是" if order_changed else "否"))
    print("    留一后排序（干净切割）= %s" % " > ".join(sorted(loo, key=lambda f: -loo[f][0])))
    print("    留一后 降水是否仍非最强: %s"
          % ("是" if sorted(loo, key=lambda f: -loo[f][0])[0] != "precip" else "否"))
    clean = all(loo[f][0] < base[f][0] for f in ("grass", "barren"))
    print("    覆被类因子在 LOO 下是否下降（机械相关被切掉）: %s" % ("是" if clean else "否"))
    verdict = "STOP-AND-REPORT" if (flag or order_changed) else "OK：差异很小，结论方向一致"
    print("\n判定: %s" % verdict)
    if flag or order_changed:
        print("    ⇒ 按红线要求：不得自行建议或改论文，仅报告差异。")
    print("已写入: results_fractional_cover_loo.csv / _points.csv / _windows.csv")
    src.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())