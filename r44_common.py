# -*- coding: utf-8 -*-
"""R44 公共引擎 —— 八指标主规格三模型 + 残差 bootstrap（三种空间）

本模块被 run_r44_mixture.py（任务 1：加权混合）与 run_r44_bounded.py（任务 2：
有界预测区间）共同调用，保证两个脚本用的是**同一套模型实现、同一套 bootstrap
机制、同一套随机种子**。

────────────────────────────────────────────────────────────────────────────
与 run_r29_forecast_8ind.py 的一致性
────────────────────────────────────────────────────────────────────────────
模型实现（GM(1,1) / NGBM(γ) / ARIMA(0,1,1)）与 bootstrap 机制**逐字沿用**
run_r29_forecast_8ind.py：
  · 目标序列：r28_core.compute(DEREDUNDANT_SETS['drop_X9']) 的 ESI（2005–2023），
    与 data/r28_deredundancy_series.csv::esi_drop_X9 逐位一致（调用方校验）。
  · α = 0.4；五级阈值 [0.2, 0.4, 0.6, 0.8]。
  · NGBM 幂指数 γ：网格 0.05–1.95 步长 0.05，目标 = 训练期 2005–2018（14 点）SSE
    （无泄漏口径，主 NGBM）；bootstrap 中每个重复**重新选 γ**。
  · ARIMA 固定 (0,1,1)（阶数不由数据选）。
  · Bootstrap：B = 2000，seed = 20261017（与 R29 同），块长 L = 3；每重复
      ① 残差重采样索引 idx ← ② 抽 i.i.d. 新息（仅为保持与 R29 完全相同的随机流
      占位）← ③ 抽块新息 e_blk ← ④ 伪历史 = 拟合值 + 重采样残差 → 重估参数
      ← ⑤ 叠加累积块新息。
    三个模型使用**同一个 seed 且调用顺序相同** ⇒ 第 b 条路径在同口径下是同一情景。
    主口径 = total_block（参数重估 + 累积块新息）。

────────────────────────────────────────────────────────────────────────────
本模块新增的三件事
────────────────────────────────────────────────────────────────────────────
(1) 空间（space）
    "raw"   : 原始 ESI 空间。残差 = ESI − 拟合值；新息叠加在原始空间 ⇒ 与 R29
              归档区间**逐格可比**，也是"旧口径"（ARIMA 2028 上界 1.112674）。
    "logit" : logit 尺度。残差 = logit(ESI) − logit(拟合值)；伪历史经 expit 回到
              (0,1) 后仍**在原始空间重估模型**（故点预测口径不变）；新息叠加在
              logit 尺度后 expit 逆变换 ⇒ **全部抽样值天然 ∈ (0,1)**。
              说明：ESI 序列本身已在 (0,1) 内（实测 min 0.2886、max 0.6763），
              **不需要做平移**。
(2) ARIMA 首期拟合值的两种口径（first_fix）
    R29 的 fp_arima 直接取 statsmodels 的 m.fittedvalues；对 (0,1,1) 而言首期
    拟合值不由递推式定义，实测为 **0.0**（不是 (0,1) 内的水平值）。R29 只在其
    长度为 n−1 时才补 series[0]，故该 0.0 被保留，产生一个**虚假的首期残差**
    （原始空间 +0.2886，是最大真实残差 0.2137 的 1.35 倍；logit 空间被 clip 成
    +19.8，直接毁掉区间）。
      first_fix="naive" : 原样保留（= R29 口径，用于复现旧值）。
      first_fix="reg"   : 若首期拟合值不在 (0,1) 内则取 series[0]（= R29 自己在
                          长度为 n−1 时的既定做法，只是把它推广到首期非法值）。
    点预测完全不受影响（首期拟合值不进入任何未来期递推）。
(3) 抽样缓存
    bootstrap 结果以 .npz 缓存在 data/ 下（key = space|first_fix|model|seed），
    两个脚本共享，避免重复计算；缓存命名里写明 seed，便于复现与审计。

运行方式：由 run_r44_mixture.py / run_r44_bounded.py 调用，不单独运行。
"""
import os
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
if BASE not in sys.path:
    sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "eco_security"))

from eco_security import gm11_forecast  # noqa: E402
import r28_core as C  # noqa: E402

ALPHA = 0.4
TRAIN_END = 2018
N_TRAIN = 14
FUT_YEARS = list(range(2024, 2029))
N_FUT = 5
B = 2000
SEED = 20261017              # 与 run_r29_forecast_8ind.py 完全相同的 seed
SEED_MIX = SEED + 7          # 混合抽样的独立 seed（可复现）
BLOCK_L = 3
GAMMA_GRID = np.round(np.arange(0.05, 1.96, 0.05), 2)
GRADES = ["severe", "medium", "mild", "rel_safe", "safe"]
GRADES_CN = {"severe": "重警", "medium": "中警", "mild": "轻警",
             "rel_safe": "较安全", "safe": "安全"}
THR = [0.2, 0.4, 0.6, 0.8]
EPS = 1e-12
MODELS = ["GM(1,1)", "NGBM", "ARIMA(0,1,1)"]

SOURCES = {
    "series": "data/r28_deredundancy_series.csv::esi_drop_X9",
    "forecast": "data/r29_forecast_8ind.csv",
    "intervals_old": "data/r29_forecast_8ind_intervals.csv",
    "range_old": "data/r29_2028_range.csv",
    "grade_prob_old": "data/r29_grade_prob_8ind.csv",
    "validation": "data/r32_validation_8ind.csv",
    "validation_detail": "data/r32_validation_8ind_detail.csv",
    "table7": "data/r42_table7_accuracy.csv",
    "script_reference": "run_r29_forecast_8ind.py",
}


# ---------------------------------------------------------------------------
# 基础函数
# ---------------------------------------------------------------------------
def logit(p):
    p = np.clip(np.asarray(p, float), EPS, 1.0 - EPS)
    return np.log(p / (1.0 - p))


def expit(z):
    return 1.0 / (1.0 + np.exp(-np.asarray(z, float)))


def grade_index(v):
    return int(sum(1 for t in THR if v >= t))


def grade_of(v):
    return GRADES[grade_index(v)]


def grade_probs(vals):
    """(n,) 抽样值 → 五级概率列表 [severe, medium, mild, rel_safe, safe]。"""
    vals = np.asarray(vals, float)
    vals = vals[np.isfinite(vals)]
    if len(vals) == 0:
        return [np.nan] * 5
    gi = np.array([grade_index(v) for v in vals])
    return [float(np.mean(gi == k)) for k in range(5)]


# ---------------------------------------------------------------------------
# 模型实现（逐字沿用 run_r29_forecast_8ind.py）
# ---------------------------------------------------------------------------
def ngbm_core(x0, gamma, n_pred=N_FUT):
    x0 = np.asarray(x0, float)
    x1 = np.cumsum(x0)
    z1 = 0.5 * (x1[1:] + x1[:-1])
    if abs(gamma - 1.0) < 1e-9:
        a, b = np.linalg.lstsq(np.column_stack([-z1, z1]), x0[1:], rcond=None)[0]
        if abs(a) < 1e-12:
            return None
        c = x0[0] - b / a
        xh = np.array([x0[0]] + [(1 - np.exp(-a)) * c * np.exp(-a * k)
                                 for k in range(1, len(x0))])
        fut = np.array([(1 - np.exp(-a)) * c * np.exp(-a * (len(x0) + k))
                        for k in range(1, n_pred + 1)])
        return fut, xh, (a, b, 1.0)
    a, b = np.linalg.lstsq(np.column_stack([-z1, z1 ** gamma]), x0[1:], rcond=None)[0]
    if abs(a) < 1e-12:
        return None

    def X1(t):
        base = (x0[0] ** (1 - gamma) - b / a) * np.exp(-a * (1 - gamma) * t) + b / a
        if base <= 0:
            raise ValueError("negative base")
        return base ** (1.0 / (1.0 - gamma))

    xh = np.array([x0[0]] + [X1(k) - X1(k - 1) for k in range(1, len(x0))])
    fut = np.array([X1(len(x0) + k) - X1(len(x0) + k - 1) for k in range(1, n_pred + 1)])
    return fut, xh, (a, b, float(gamma))


def ngbm_try(x0, gamma, n_pred=N_FUT):
    try:
        r = ngbm_core(x0, gamma, n_pred)
    except Exception:
        return None
    if r is None or not np.all(np.isfinite(r[0])) or not np.all(np.isfinite(r[1])):
        return None
    return r


def select_gamma(x0, objective="sse"):
    """仅在 x0 内部选 γ（无泄漏）。返回 (best_value, gamma)。"""
    best = None
    for g in GAMMA_GRID:
        r = ngbm_try(x0, g, n_pred=1)
        if r is None:
            continue
        e = np.asarray(x0, float)[1:] - r[1][1:]
        v = float(np.sum(e ** 2)) if objective == "sse" else float(np.mean(np.abs(e)))
        if best is None or v < best[0]:
            best = (v, float(g))
    return best


def fp_gm(series, n_pred=N_FUT):
    fut, fit, Cp, Pp = gm11_forecast(np.asarray(series, float), n_pred=n_pred)
    return np.asarray(fut, float), np.asarray(fit, float)


def fp_ngbm_fixed(series, gamma, n_pred=N_FUT):
    r = ngbm_try(series, gamma, n_pred=n_pred)
    if r is None:
        return None
    return np.asarray(r[0], float), np.asarray(r[1], float)


def fp_ngbm_reselect(series, n_pred=N_FUT):
    b = select_gamma(series, "sse")
    if b is None:
        return None
    return fp_ngbm_fixed(series, b[1], n_pred=n_pred)


def fp_arima(series, n_pred=N_FUT, first_fix="naive"):
    """ARIMA(0,1,1)（与 R29 同：阶数固定，不由数据选）。

    first_fix="naive"：完全照 R29 —— 取 m.fittedvalues，仅当长度为 n−1 时补 series[0]。
    first_fix="reg"  ：再把不在 (0,1) 内的首期拟合值规范为 series[0]（R29 在长度
                       n−1 时的既定做法，只是推广到"首期非法"这一情形）。
    见模块 docstring (2)。点预测不受影响。
    """
    from statsmodels.tsa.arima.model import ARIMA
    m = ARIMA(np.asarray(series, float), order=(0, 1, 1)).fit()
    fit = np.asarray(m.fittedvalues, float).copy()
    if len(fit) == len(series) - 1:
        fit = np.concatenate([[np.asarray(series, float)[0]], fit])
    if first_fix == "reg" and not (np.isfinite(fit[0]) and 0.0 < fit[0] < 1.0):
        fit[0] = float(np.asarray(series, float)[0])
    return np.asarray(m.forecast(n_pred), float), fit


def draw_block(r, n, L, rng):
    if len(r) <= L:
        return rng.choice(r, size=n, replace=True)
    starts = rng.integers(0, len(r) - L + 1, size=int(np.ceil(n / L)))
    return np.concatenate([r[s:s + L] for s in starts])[:n]


# ---------------------------------------------------------------------------
# 拟合 / bootstrap
# ---------------------------------------------------------------------------
def base_fits(series, gamma_fixed, reselect_ngbm=False, first_fix="naive"):
    base = {"GM(1,1)": fp_gm(series),
            "NGBM": (fp_ngbm_reselect(series) if reselect_ngbm
                     else fp_ngbm_fixed(series, gamma_fixed)),
            "ARIMA(0,1,1)": fp_arima(series, first_fix=first_fix)}
    if base["NGBM"] is None:
        raise RuntimeError("base NGBM fit failed")
    return base


def refit(model, y, gamma_fixed, reselect_ngbm):
    if model == "GM(1,1)":
        return fp_gm(y)[0]
    if model == "NGBM":
        r = fp_ngbm_reselect(y) if reselect_ngbm else fp_ngbm_fixed(y, gamma_fixed)
        return None if r is None else r[0]
    return fp_arima(y)[0]


def bootstrap(series, space="raw", first_fix="naive", seed=SEED,
              gamma_fixed=None, reselect_ngbm=None):
    """残差 bootstrap（机制与调用顺序与 R29 完全相同）。

    返回 dict：
      draws[model]  (B, N_FUT)  叠加了累积块新息后的抽样路径（点预测 + 新息）
      points[model] (B, N_FUT)  仅参数重估后的点预测（不含新息）
      n_valid[model]            有效重复数
      resid[model]  (n,)        基础拟合的残差（所用空间下）
      fit[model]    (n,)        基础拟合值（原始空间）
    """
    series = np.asarray(series, float)
    n = len(series)
    if gamma_fixed is None:
        gamma_fixed = float(select_gamma(series[:N_TRAIN], "sse")[1])
    if reselect_ngbm is None:
        reselect_ngbm = {"NGBM": True}
    # 基础拟合**始终用固定的训练期 γ**（与 R29 的 PRIMARY3 一致）：只有重复内的重估
    # 才重选 γ。若基础拟合也重选 γ，会落在全序列最优 γ=0.05 上，残差池随之改变，
    # 原始空间区间就不再能逐格复现 R29 归档（实测 NGBM 2028 上界会由 0.614818 变 0.642966）。
    base = base_fits(series, gamma_fixed, False, first_fix)

    if space == "raw":
        y_obs = series.copy()
    else:
        y_obs = logit(series)
    resid = {}
    for m in MODELS:
        fit = base[m][1]
        resid[m] = y_obs - (fit if space == "raw" else logit(fit))

    draws = {m: np.full((B, N_FUT), np.nan) for m in MODELS}
    points = {m: np.full((B, N_FUT), np.nan) for m in MODELS}
    n_valid = {}
    for m in MODELS:
        rng = np.random.default_rng(seed)
        rc = resid[m]
        rcm = rc - rc.mean()
        fit0 = base[m][1] if space == "raw" else logit(base[m][1])
        nv = 0
        for b in range(B):
            idx = rng.choice(n, size=n, replace=True)          # ①
            rng.choice(rcm, size=N_FUT, replace=True)          # ② 随机流占位（同 R29）
            e_blk = draw_block(rcm, N_FUT, BLOCK_L, rng)       # ③
            y = fit0 + rc[idx]                                 # ④
            if space != "raw":
                y = expit(y)
            try:
                p = refit(m, y, gamma_fixed, reselect_ngbm.get(m, False))
            except Exception:
                p = None
            if p is None or not np.all(np.isfinite(p)):
                continue
            nv += 1
            points[m][b] = p
            draws[m][b] = (p + np.cumsum(e_blk) if space == "raw"
                           else expit(logit(p) + np.cumsum(e_blk)))
        n_valid[m] = nv
    return {"draws": draws, "points": points, "n_valid": n_valid,
            "resid": resid, "fit": {m: base[m][1] for m in MODELS},
            "gamma_fixed": gamma_fixed, "space": space, "first_fix": first_fix,
            "seed": seed}


# ---------------------------------------------------------------------------
# 缓存（两个脚本共享，避免重复 bootstrap）
# ---------------------------------------------------------------------------
def cache_path(space, first_fix):
    return os.path.join(DATA, "r44_bootstrap_%s_%s_seed%d.npz" % (space, first_fix, SEED))


def cache_key(space, first_fix, seed):
    """缓存 key：口径 + 种子 + B + 块长 + 基础拟合口径（base=fixed ⇒ 与 R29 同）。
    任何一项变化都会使旧缓存失效并重算（口径可审计）。"""
    return "%s|%s|%d|B%d|L%d|base=fixed" % (space, first_fix, seed, B, BLOCK_L)


def get_bootstrap(series, space="raw", first_fix="naive", seed=SEED, verbose=True):
    """带磁盘缓存的 bootstrap（缓存 key 写入文件内，key 不符则重算）。"""
    key = cache_key(space, first_fix, seed)
    path = cache_path(space, first_fix)
    if os.path.exists(path):
        z = np.load(path, allow_pickle=True)
        if str(z["key"]) == key:
            out = {"draws": {m: z["d_" + m] for m in MODELS},
                   "points": {m: z["p_" + m] for m in MODELS},
                   "n_valid": {m: int(z["n_" + m]) for m in MODELS},
                   "resid": {m: z["r_" + m] for m in MODELS},
                   "fit": {m: z["f_" + m] for m in MODELS},
                   "gamma_fixed": float(z["gamma"]), "space": space,
                   "first_fix": first_fix, "seed": seed, "from_cache": True}
            if verbose:
                print("   [cache] 复用 %s（key=%s）" % (os.path.basename(path), key))
            return out
    out = bootstrap(series, space=space, first_fix=first_fix, seed=seed)
    np.savez_compressed(
        path, key=key, gamma=out["gamma_fixed"],
        **{"d_" + m: out["draws"][m] for m in MODELS},
        **{"p_" + m: out["points"][m] for m in MODELS},
        **{"r_" + m: out["resid"][m] for m in MODELS},
        **{"f_" + m: out["fit"][m] for m in MODELS},
        **{"n_" + m: out["n_valid"][m] for m in MODELS})
    out["from_cache"] = False
    if verbose:
        print("   [cache] 写出 %s（key=%s）" % (os.path.basename(path), key))
    return out


# ---------------------------------------------------------------------------
# 混合抽样
# ---------------------------------------------------------------------------
N_MIX = 6000


def mixture_draws(bs, weights, n_mix=N_MIX, seed=SEED_MIX, clamp=False):
    """按权重从各模型的**有效重复**中抽样并拼接（= 预测分布的加权混合）。

    返回 (vals (n_mix_eff, N_FUT), counts dict, n_requested)
    这是 R29 的 model-averaged "pooled draws" 口径：p(Δ) = Σ_k w_k p_k(Δ)。

    抽样规则（可复现，写明口径）：对模型 k 需要 counts[k] 条路径，
      · counts[k] <= 有效重复数  → **无放回**抽取 counts[k] 条（等权时 counts=2000
        恰等于有效重复数 ⇒ 得到该模型完整 bootstrap 池，与 R29 的池化口径逐格一致）；
      · counts[k] >  有效重复数  → 先取全部有效重复，不足部分有放回补足。
    随机流 default_rng(seed)，seed 与抽样数写入 CSV。
    """
    counts = {m: int(round(weights[m] * n_mix)) for m in MODELS}
    diff = n_mix - sum(counts.values())
    counts[max(MODELS, key=lambda m: weights[m])] += diff
    rng = np.random.default_rng(seed)
    parts = []
    for m in MODELS:
        pool = bs["draws"][m]
        pool = pool[np.all(np.isfinite(pool), axis=1)]
        if len(pool) == 0 or counts[m] == 0:
            continue
        k = counts[m]
        if k <= len(pool):
            part = pool[rng.permutation(len(pool))[:k]]
        else:
            extra = pool[rng.choice(len(pool), size=k - len(pool), replace=True)]
            part = np.vstack([pool, extra])
        if clamp:
            part = np.clip(part, 0.0, 1.0)
        parts.append(part)
    return np.vstack(parts), counts, n_mix


def mixture_paired(bs, weights):
    """逐重复先对三模型取加权平均（同情景，方差被抵消——诊断行，非标准 BMA）。"""
    m = min(int(np.sum(np.all(np.isfinite(bs["draws"][k]), axis=1))) for k in MODELS)
    stacked = []
    for k in MODELS:
        pool = bs["draws"][k]
        pool = pool[np.all(np.isfinite(pool), axis=1)]
        stacked.append(pool[:m])
    return np.tensordot(np.array([weights[k] for k in MODELS]),
                        np.array(stacked), axes=(0, 0))


def summarize_vals(vals, point):
    """返回 (lo, hi, width, probs5, n)。"""
    vals = vals[np.all(np.isfinite(vals), axis=1)] if vals.ndim == 2 else vals
    lo = np.percentile(vals, 2.5, axis=0)
    hi = np.percentile(vals, 97.5, axis=0)
    return lo, hi, hi - lo, [grade_probs(vals[:, k]) for k in range(N_FUT)], vals.shape[0]


# ---------------------------------------------------------------------------
# 数据装载
# ---------------------------------------------------------------------------
def load_esi():
    r8 = C.compute(C.DEREDUNDANT_SETS["drop_X9"])
    esi = np.asarray(r8["esi"], float)
    years = list(r8["years"])
    arc = pd.read_csv(os.path.join(DATA, "r28_deredundancy_series.csv"))
    dmax = float(np.abs(esi - arc["esi_drop_X9"].values).max())
    return esi, years, dmax


def load_point_forecasts():
    """三模型 2024–2028 点预测：直接取自 R29 归档列（不重算 ⇒ 与论文一致）。"""
    fc = pd.read_csv(os.path.join(DATA, "r29_forecast_8ind.csv"))
    col = {"GM(1,1)": "gm11_8ind",
           "NGBM": "ngbm_8ind_gamma_train",
           "ARIMA(0,1,1)": "arima_011_8ind"}
    pt = {m: fc[col[m]].values.astype(float) for m in MODELS}
    for m in MODELS:
        assert len(pt[m]) == N_FUT, m
    return pt, col


def file_md5(path):
    import hashlib
    return hashlib.md5(open(path, "rb").read()).hexdigest().upper()