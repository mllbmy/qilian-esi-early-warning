# -*- coding: utf-8 -*-
"""R44 · (4)(5) 性能加权混合 + 有界预测区间（审稿意见必改④⑤）

────────────────────────────────────────────────────────────────────────────
必改④：等权混合缺依据
  NGBM 在八指标五种验证方案下**全部最后** ⇒ 等权不合理。本脚本
  · 从 **已提交的** data/r32_validation_8ind_detail.csv（八指标五方案逐折
    observed/predicted）计算三模型的**池化样本外 RMSE/MSE**；
  · 以 1/RMSE 为权重（主口径，逆 RMSE 加权；权重按方案内评估点池化）得到
    2024–2028 混合序列；另做 **逆 MSE（1/RMSE²，stacking 型）** 与 **等权** 作敏感性；
  · 同时给出混合序列自身的 RMSE/MAE（逐方案 + 池化 + leave-one-scheme-out，
    避免"用同一批折定权重又在同一批折上评分"的乐观性）；
  · 落盘逐年等级概率与 2028 值/区间。

必改⑤：预测区间超出 [0,1]
  三种区间口径同时计算并比较：
  · raw      —— 原始空间残差 bootstrap（复现 R29，用于诊断越界）
  · clamp    —— 截断到 [0,1] 的 bootstrap（有界口径 A）
  · logit    —— logit 尺度残差 bootstrap（有界口径 B，**主口径**）：
                 z = logit(ESI) 在 (0,1) 上定义；残差在 logit 尺度重采样；
                 模型仍在原始空间重估（点预测口径不变）；
                 每个重复的预测水平映射到 logit 尺度后叠加 logit 尺度新息，
                 再 expit 逆变换 ⇒ 所有抽样值天然落在 (0,1)。
              （不对 GM(1,1)/NGBM 直接在 logit 序列上重估，因为 logit 序列含负值，
                NGBM 的 x0[0]^(1-γ) 在负底数上无定义；本方法保持点预测口径不变。）

输出（全部新文件，UTF-8-SIG）：
  data/r44_mixture_weights.csv     权重与依据（逐方案 RMSE/MSE、三套权重）
  data/r44_mixture_accuracy.csv    混合序列 RMSE/MAE（逐方案/池化/LOSO）
  data/r44_bounded_intervals.csv   三口径区间逐年（模型 + 混合）
  data/r44_grade_prob.csv          逐年五级概率（模型 + 混合 × 三口径）
  data/r44_2028_summary.csv        2028 点值/区间/等级概率汇总
  data/r44_checks.csv              复现校验（对 R29 归档值逐格）
运行：python run_r44_mixture_bounded.py
"""
import hashlib
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
sys.path.insert(0, os.path.join(BASE, "eco_security"))
sys.path.insert(0, BASE)
from eco_security import gm11_forecast  # noqa: E402
import r28_core as C  # noqa: E402

ALPHA = 0.4
TRAIN_END = 2018
N_TRAIN = 14
FUT_YEARS = list(range(2024, 2029))
N_FUT = 5
B = 2000
SEED = 20261017          # 与 R29 同一 seed（raw 口径可逐格复现）
SEED_LOGIT = 20261018    # logit 口径独立 seed（可复现）
BLOCK_L = 3
GAMMA_GRID = np.round(np.arange(0.05, 1.96, 0.05), 2)
GRADES = ["severe", "medium", "mild", "rel_safe", "safe"]
THR = [0.2, 0.4, 0.6, 0.8]
METHODS = ["rawR29", "rawfix", "clamp", "logit"]
EPS = 1e-9

MODELS = ["GM(1,1)", "NGBM", "ARIMA(0,1,1)"]
SHORT = {"GM(1,1)": "gm", "NGBM": "ngbm", "ARIMA(0,1,1)": "arima"}
COL = {"GM(1,1)": "gm11_8ind", "NGBM": "ngbm_8ind_gamma_train", "ARIMA(0,1,1)": "arima_011_8ind"}

OUT_W = os.path.join(DATA, "r44_mixture_weights.csv")
OUT_A = os.path.join(DATA, "r44_mixture_accuracy.csv")
OUT_I = os.path.join(DATA, "r44_bounded_intervals.csv")
OUT_G = os.path.join(DATA, "r44_grade_prob.csv")
OUT_S = os.path.join(DATA, "r44_2028_summary.csv")
OUT_K = os.path.join(DATA, "r44_checks.csv")


def md5(path):
    return hashlib.md5(open(path, "rb").read()).hexdigest().upper()


def logit(p):
    p = np.clip(np.asarray(p, float), EPS, 1 - EPS)
    return np.log(p / (1 - p))


def expit(z):
    z = np.asarray(z, float)
    return 1.0 / (1.0 + np.exp(-z))


# ---------------------------------------------------------------------------
# 模型（与 r29_forecast_8ind.py 逐字同口径）
# ---------------------------------------------------------------------------
def ngbm_core(x0, gamma, n_pred=N_FUT):
    """Compatibility helper using the corrected consecutive-index estimator."""
    from forecast_models import ngbm as canonical_ngbm
    return canonical_ngbm(x0, gamma, n_pred)


def ngbm_try(x0, gamma, n_pred=N_FUT):
    try:
        r = ngbm_core(x0, gamma, n_pred)
    except Exception:
        return None
    if r is None or not np.all(np.isfinite(r[0])) or not np.all(np.isfinite(r[1])):
        return None
    return r


def select_gamma(x0, objective="sse"):
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


def fp_arima(series, n_pred=N_FUT, fix_first=True):
    """ARIMA(0,1,1)。

    fix_first=True：把首期拟合值规范为观测值 y[0]。statsmodels 对 (0,1,1) 的
    fittedvalues[0] 不由递推式定义（实测为 0），若直接使用会产生一个**虚假的
    首期离群残差**（八指标序列上为 +0.2886，是全年最大残差的 1.4 倍），
    并因此在残差 bootstrap 中被反复抽到、系统性放大区间。
    该规范只影响残差序列的首期，不影响任何点预测。
    """
    from statsmodels.tsa.arima.model import ARIMA
    m = ARIMA(np.asarray(series, float), order=(0, 1, 1)).fit()
    fit = np.asarray(m.fittedvalues, float)
    if len(fit) == len(series) - 1:
        fit = np.concatenate([[series[0]], fit])
    fit = fit.copy()
    if fix_first and not (np.isfinite(fit[0]) and 0.0 < fit[0] < 1.0):
        fit[0] = series[0]
    return np.asarray(m.forecast(n_pred), float), fit


def draw_block(r, n, L, rng):
    if len(r) <= L:
        return rng.choice(r, size=n, replace=True)
    starts = rng.integers(0, len(r) - L + 1, size=int(np.ceil(n / L)))
    return np.concatenate([r[s:s + L] for s in starts])[:n]


# ---------------------------------------------------------------------------
def _base_fit(series, gamma_fixed, reselect_ngbm, fix_first=True):
    base = {"GM(1,1)": fp_gm(series),
            "NGBM": (fp_ngbm_fixed(series, gamma_fixed) if not reselect_ngbm
                     else fp_ngbm_reselect(series)),
            "ARIMA(0,1,1)": fp_arima(series, fix_first=fix_first)}
    if base["NGBM"] is None:
        raise RuntimeError("base NGBM fit failed")
    return base


def _fp(model, y, gamma_fixed, reselect_ngbm):
    if model == "GM(1,1)":
        return fp_gm(y)[0]
    if model == "NGBM":
        r = fp_ngbm_reselect(y) if reselect_ngbm else fp_ngbm_fixed(y, gamma_fixed)
        return None if r is None else r[0]
    return fp_arima(y)[0]


def bootstrap(series, space, seed, gamma_fixed, reselect_ngbm, fix_first=True):
    """残差 bootstrap（与 R29 同设计、**同随机流**，逐模型独立 seed）。

    每重复：① 重采样残差索引 ② 抽 i.i.d. 新息（保持随机流与 R29 一致）③ 抽块新息
            ④ 以 拟合值+重采样残差 造伪历史 → 重估参数 ⑤ 叠加块新息累积。

    space = "raw"   : 原始 ESI 空间（fix_first=False 即 R29 原口径，可逐格复现归档）
    space = "logit" : logit 尺度（模型仍在原始空间重估 ⇒ 点预测口径不变；
                      残差与累积新息都在 logit 尺度，最后 expit 逆变换 ⇒ 抽样值天然 ∈(0,1)）

    返回 (draws, points)：dict(model -> (B, N_FUT))
    """
    n = len(series)
    base = _base_fit(series, gamma_fixed, reselect_ngbm, fix_first=fix_first)
    y_obs = np.asarray(series, float) if space == "raw" else logit(series)
    resid = {m: y_obs - (base[m][1] if space == "raw" else logit(base[m][1]))
             for m in MODELS}

    draws = {m: np.full((B, N_FUT), np.nan) for m in MODELS}
    points = {m: np.full((B, N_FUT), np.nan) for m in MODELS}
    for m in MODELS:
        rng = np.random.default_rng(seed)          # 每个模型一条独立随机流（同 R29）
        rc = resid[m]
        fit0 = base[m][1] if space == "raw" else logit(base[m][1])
        for b in range(B):
            idx = rng.choice(n, size=n, replace=True)
            rng.choice(rc - rc.mean(), size=N_FUT, replace=True)   # 与 R29 一致的随机流占位
            e_blk = draw_block(rc - rc.mean(), N_FUT, BLOCK_L, rng)
            y = fit0 + rc[idx]
            if space == "logit":
                y = expit(y)                        # 伪历史回到 (0,1)，原始空间重估
            try:
                p = _fp(m, y, gamma_fixed, reselect_ngbm)
            except Exception:
                p = None
            if p is None or not np.all(np.isfinite(p)):
                continue
            points[m][b] = p
            draws[m][b] = (p + np.cumsum(e_blk) if space == "raw"
                           else expit(logit(p) + np.cumsum(e_blk)))
    return draws, points

# ---------------------------------------------------------------------------
def grade_index(v):
    return int(sum(1 for t in THR if v >= t))


def prob_table(vals):
    """vals: (n,) 抽样值 -> 五级概率"""
    gi = np.array([grade_index(v) for v in vals])
    return [float(np.mean(gi == k)) for k in range(5)]


def main():
    print("=" * 78)
    print("R44 · 性能加权混合 + 有界预测区间")
    print("=" * 78)

    # ---------- 0) 序列 ----------
    r8 = C.compute(C.DEREDUNDANT_SETS["drop_X9"])
    esi8 = np.asarray(r8["esi"], float)
    years = list(r8["years"])
    arc = pd.read_csv(os.path.join(DATA, "r28_deredundancy_series.csv"))
    d_arc = float(np.abs(esi8 - arc["esi_drop_X9"].values).max())

    fc = pd.read_csv(os.path.join(DATA, "r29_forecast_8ind.csv"))
    pt = {m: fc[COL[m]].values.astype(float) for m in MODELS}
    for m in MODELS:
        assert len(pt[m]) == N_FUT, m
    gamma_train = float(select_gamma(esi8[:N_TRAIN], "sse")[1])
    print("[口径] 训练期 SSE 最优 γ = %.2f（无泄漏，主 NGBM）" % gamma_train)

    checks = []

    def addcheck(item, value, note):
        checks.append({"item": item, "value": value, "note": note})

    addcheck("esi_8ind_vs_archive_max_abs_delta", "%.3e" % d_arc,
             "drop_X9 ESI 重建 vs data/r28_deredundancy_series.csv")

    # ---------- 1) 样本外精度与权重 ----------
    det = pd.read_csv(os.path.join(DATA, "r32_validation_8ind_detail.csv"))
    det = det[det["series"] == "eight"].copy()
    key = ["scheme", "fold", "horizon", "target_year"]
    wide = det.pivot_table(index=key, columns="model", values="predicted",
                           aggfunc="first").reset_index()
    obs = det.groupby(key)["observed"].first().reset_index()
    wide = wide.merge(obs, on=key, how="left")
    assert wide["observed"].notna().all()
    DETNAME = {"GM(1,1)": "GM(1,1)", "NGBM": "NGBM", "ARIMA(0,1,1)": "ARIMA"}
    for m in MODELS:
        assert DETNAME[m] in wide.columns, m

    def rmse_mae(pred, ob):
        e = np.asarray(pred, float) - np.asarray(ob, float)
        return float(np.sqrt(np.mean(e ** 2))), float(np.mean(np.abs(e)))

    acc_rows, wrows = [], []
    per_scheme = {}
    for sch, g in wide.groupby("scheme"):
        rec = {}
        for m in MODELS:
            rec[m] = rmse_mae(g[DETNAME[m]].values, g["observed"].values)
        per_scheme[sch] = rec
    pooled = {m: rmse_mae(wide[DETNAME[m]].values, wide["observed"].values) for m in MODELS}

    basis_rmse = {m: pooled[m][0] for m in MODELS}
    basis_mse = {m: pooled[m][0] ** 2 for m in MODELS}

    def inv_weights(basis):
        inv = {m: 1.0 / basis[m] for m in MODELS}
        s = sum(inv.values())
        return {m: inv[m] / s for m in MODELS}

    W = {
        "invRMSE": inv_weights(basis_rmse),
        "invMSE": inv_weights(basis_mse),
        "equal": {m: 1.0 / 3 for m in MODELS},
    }
    # 变体：全序列拟合精度（Table 7 口径）的逆 RMSE 权重
    fit7 = pd.read_csv(os.path.join(DATA, "r42_table7_accuracy.csv"))
    FIT7 = {"GM(1,1)": "GM(1,1)", "NGBM": "NGBM (gamma=0.15)", "ARIMA(0,1,1)": "ARIMA(0,1,1)"}
    fit_rmse = {m: float(fit7.loc[fit7["model"] == FIT7[m], "rmse"].iloc[0]) for m in MODELS}
    W["invRMSE_fitTable7"] = inv_weights({m: fit_rmse[m] for m in MODELS})

    for m in MODELS:
        wrows.append({"weight_scheme": "invRMSE", "model": m,
                      "basis_rmse_pooled_oos": basis_rmse[m],
                      "basis_mse_pooled_oos": basis_mse[m],
                      "weight": W["invRMSE"][m],
                      "note": "权重依据：五方案池化样本外 RMSE 的倒数归一（主口径）"})
    for m in MODELS:
        wrows.append({"weight_scheme": "invMSE", "model": m,
                      "basis_rmse_pooled_oos": basis_rmse[m],
                      "basis_mse_pooled_oos": basis_mse[m],
                      "weight": W["invMSE"][m],
                      "note": "权重依据：1/RMSE^2（stacking 型）"})
    for m in MODELS:
        wrows.append({"weight_scheme": "equal", "model": m,
                      "basis_rmse_pooled_oos": basis_rmse[m],
                      "basis_mse_pooled_oos": basis_mse[m],
                      "weight": W["equal"][m], "note": "等权（原口径，敏感性对照）"})
    for m in MODELS:
        wrows.append({"weight_scheme": "invRMSE_fitTable7", "model": m,
                      "basis_rmse_pooled_oos": float(fit_rmse[m]),
                      "basis_mse_pooled_oos": float(fit_rmse[m]) ** 2,
                      "weight": W["invRMSE_fitTable7"][m],
                      "note": "敏感性：权重依据换成 Table 7 全序列拟合 RMSE 的倒数"})
    for sch in sorted(per_scheme):
        for m in MODELS:
            r_, a_ = per_scheme[sch][m]
            acc_rows.append({"scope": sch, "target": m, "rmse": r_, "mae": a_,
                             "n_points": int((wide["scheme"] == sch).sum()),
                             "weight_scheme": "", "note": "逐模型样本外精度"})
    for m in MODELS:
        acc_rows.append({"scope": "pooled_5_schemes", "target": m,
                         "rmse": pooled[m][0], "mae": pooled[m][1],
                         "n_points": len(wide), "weight_scheme": "",
                         "note": "五方案池化（权重依据）"})

    # 混合精度：逐方案 + 池化；权重方案 × 池化/LOSO
    mix_point_acc = {}
    for ws, w in W.items():
        for sch, g in wide.groupby("scheme"):
            pred = sum(w[m] * g[DETNAME[m]].values for m in MODELS)
            r_, a_ = rmse_mae(pred, g["observed"].values)
            acc_rows.append({"scope": sch, "target": "mixture", "rmse": r_, "mae": a_,
                             "n_points": len(g), "weight_scheme": ws,
                             "note": "混合序列样本外精度（权重来自同一批折，含乐观性）"})
            mix_point_acc[(ws, sch)] = (r_, a_)
        pred = sum(w[m] * wide[DETNAME[m]].values for m in MODELS)
        r_, a_ = rmse_mae(pred, wide["observed"].values)
        acc_rows.append({"scope": "pooled_5_schemes", "target": "mixture",
                         "rmse": r_, "mae": a_, "n_points": len(wide),
                         "weight_scheme": ws, "note": "混合序列池化样本外精度"})
        # LOSO：用其余四方案定权重，在被留出的方案上评分
        for sch in sorted(per_scheme):
            rest = wide[wide["scheme"] != sch]
            b = {m: rmse_mae(rest[DETNAME[m]].values, rest["observed"].values)[0] for m in MODELS}
            wl = inv_weights(b) if ws.startswith("invRMSE") else W[ws]
            g = wide[wide["scheme"] == sch]
            pred = sum(wl[m] * g[DETNAME[m]].values for m in MODELS)
            r_, a_ = rmse_mae(pred, g["observed"].values)
            acc_rows.append({"scope": sch, "target": "mixture", "rmse": r_, "mae": a_,
                             "n_points": len(g), "weight_scheme": ws + "_LOSO",
                             "note": "leave-one-scheme-out：权重只由其余四方案估计"})

    # 混合点预测（2024–2028）
    mix_pt = {ws: np.array([sum(W[ws][m] * pt[m][k] for m in MODELS)
                            for k in range(N_FUT)]) for ws in W}
    print("[权重] invRMSE = " + ", ".join("%s %.4f" % (m, W["invRMSE"][m]) for m in MODELS))
    print("[权重] invMSE  = " + ", ".join("%s %.4f" % (m, W["invMSE"][m]) for m in MODELS))
    print("[点预测 2028] 三模型 %s | invRMSE 混合 %.6f | 等权 0.437623（R29 归档）"
          % (", ".join("%s %.6f" % (m, pt[m][-1]) for m in MODELS), mix_pt["invRMSE"][-1]))

    # ---------- 2) bootstrap 四口径 ----------
    print("\n[bootstrap] B=%d, seed raw=%d, seed logit=%d, 块长=%d"
          % (B, SEED, SEED_LOGIT, BLOCK_L))
    draws_raw, points_raw = bootstrap(esi8, "raw", SEED, gamma_train, True, fix_first=False)
    draws_fix, points_fix = bootstrap(esi8, "raw", SEED, gamma_train, True, fix_first=True)
    draws_log, points_log = bootstrap(esi8, "logit", SEED_LOGIT, gamma_train, True,
                                      fix_first=True)
    draws = {"rawR29": draws_raw, "rawfix": draws_fix, "clamp": draws_fix, "logit": draws_log}
    points = {"rawR29": points_raw, "rawfix": points_fix, "clamp": points_fix,
              "logit": points_log}

    # ---------- 3) 混合抽样（按权重从各模型有效重复中抽样，总样本固定 6000） ----------
    N_MIX = 6000

    def mix_draws(method, ws, rng_seed=SEED + 7):
        w = W[ws]
        counts = {m: int(round(w[m] * N_MIX)) for m in MODELS}
        diff = N_MIX - sum(counts.values())
        counts["ARIMA(0,1,1)"] += diff
        rng = np.random.default_rng(rng_seed)
        parts = []
        for m in MODELS:
            pool = draws[method][m]
            pool = pool[np.all(np.isfinite(pool), axis=1)]
            if len(pool) == 0 or counts[m] == 0:
                continue
            part = pool[rng.choice(len(pool), size=counts[m], replace=True)]
            if method == "clamp":
                part = np.clip(part, 0.0, 1.0)
            parts.append(part)
        return np.vstack(parts), counts

    # ---------- 4) 汇总输出 ----------
    interval_rows, grade_rows, summ_rows = [], [], []

    def summarize(target, method, ws, vals, point2028):
        """vals: (n, N_FUT)"""
        lo = np.percentile(vals, 2.5, axis=0)
        hi = np.percentile(vals, 97.5, axis=0)
        for k, y in enumerate(FUT_YEARS):
            interval_rows.append({
                "target": target, "method": method, "weight_scheme": ws, "year": y,
                "point": float(point2028[k]), "ci_lo_2.5": float(lo[k]),
                "ci_hi_97.5": float(hi[k]), "width95": float(hi[k] - lo[k]),
                "hi_exceeds_1": bool(hi[k] > 1.0), "lo_below_0": bool(lo[k] < 0.0),
                "n_draws": int(vals.shape[0]),
            })
            pr = prob_table(vals[:, k])
            grade_rows.append({
                "target": target, "method": method, "weight_scheme": ws, "year": y,
                "p_severe": pr[0], "p_medium": pr[1], "p_mild": pr[2],
                "p_rel_safe": pr[3], "p_safe": pr[4],
                "modal_grade": GRADES[int(np.argmax(pr))],
                "p_modal": float(max(pr)),
                "median": float(np.median(vals[:, k])),
                "n_draws": int(vals.shape[0]),
            })
        pr28 = prob_table(vals[:, -1])
        summ_rows.append({
            "target": target, "method": method, "weight_scheme": ws,
            "point_2028": float(point2028[-1]),
            "ci_lo_2.5_2028": float(lo[-1]), "ci_hi_97.5_2028": float(hi[-1]),
            "width95_2028": float(hi[-1] - lo[-1]),
            "grade_2028": GRADES[grade_index(point2028[-1])],
            "p_severe_2028": pr28[0], "p_medium_2028": pr28[1], "p_mild_2028": pr28[2],
            "p_rel_safe_2028": pr28[3], "p_safe_2028": pr28[4],
            "modal_grade_2028": GRADES[int(np.argmax(pr28))],
            "n_draws": int(vals.shape[0]),
        })

    for m in MODELS:
        for method in METHODS:
            v = draws[method][m]
            v = v[np.all(np.isfinite(v), axis=1)]
            summarize(m, method, "", v, pt[m])

    for ws in W:
        for method in METHODS:
            mv, counts = mix_draws(method, ws)
            summarize("mixture", method, ws, mv, mix_pt[ws])
            summ_rows[-1]["mix_counts"] = ";".join("%s=%d" % (m, counts[m]) for m in MODELS)

    # ---------- 5) 复现校验（对 R29 归档） ----------
    r29r = pd.read_csv(os.path.join(DATA, "r29_2028_range.csv"))

    def r29val(row_type, model_or_scheme, col):
        s = r29r[(r29r.row_type == row_type) & (r29r.model_or_scheme == model_or_scheme)]
        return float(s[col].iloc[0]) if len(s) else float("nan")

    v = draws["rawR29"]["ARIMA(0,1,1)"]
    v = v[np.all(np.isfinite(v), axis=1)]
    addcheck("repro_arima_2028_hi_rawR29", "%.6f" % np.percentile(v[:, -1], 97.5),
             "R29 原口径 ARIMA 2028 上界；R29 归档值 %.6f（应一致）"
             % r29val("model", "ARIMA(0,1,1)", "ci_hi_97.5"))
    addcheck("repro_arima_2028_lo_rawR29", "%.6f" % np.percentile(v[:, -1], 2.5),
             "R29 原口径 ARIMA 2028 下界；R29 归档值 %.6f（应一致）"
             % r29val("model", "ARIMA(0,1,1)", "ci_lo_2.5"))
    vg = draws["rawR29"]["GM(1,1)"]
    vg = vg[np.all(np.isfinite(vg), axis=1)]
    addcheck("repro_gm_2028_hi_rawR29", "%.6f" % np.percentile(vg[:, -1], 97.5),
             "R29 原口径 GM 2028 上界；R29 归档值 %.6f（应一致）"
             % r29val("model", "GM(1,1)", "ci_hi_97.5"))
    vn = draws["rawR29"]["NGBM"]
    vn = vn[np.all(np.isfinite(vn), axis=1)]
    addcheck("repro_ngbm_2028_hi_rawR29", "%.6f" % np.percentile(vn[:, -1], 97.5),
             "R29 原口径 NGBM 2028 上界；R29 归档值 %.6f（应一致）"
             % r29val("model", "NGBM", "ci_hi_97.5"))
    eqv, _ = mix_draws("rawR29", "equal", rng_seed=SEED + 7)
    addcheck("equal_mixture_2028_lo_pooled", "%.6f" % np.percentile(eqv[:, -1], 2.5),
             "等权混合（池化 6000）2028 下界；R29 归档 0.165645（抽样实现不同，量级对照）")
    addcheck("equal_mixture_2028_hi_pooled", "%.6f" % np.percentile(eqv[:, -1], 97.5),
             "等权混合（池化 6000）2028 上界；R29 归档 0.945092（同上）")
    vf = draws["rawfix"]["ARIMA(0,1,1)"]
    vf = vf[np.all(np.isfinite(vf), axis=1)]
    addcheck("arima_2028_hi_rawfix", "%.6f" % np.percentile(vf[:, -1], 97.5),
             "规范 ARIMA 首期拟合值后的原始空间 2028 上界（对照 rawR29）")
    addcheck("n_models_with_full_B_valid",
             ";".join("%s=%d" % (m, int(np.all(np.isfinite(draws["logit"][m]), axis=1).sum()))
                      for m in MODELS), "logit 口径各模型有效重复数（应为 2000）")
    addcheck("logit_intervals_within_support", bool(np.all(np.concatenate(
        [draws["logit"][m][np.all(np.isfinite(draws["logit"][m]), axis=1)].ravel()
         for m in MODELS]) > 0.0) and np.all(np.concatenate(
        [draws["logit"][m][np.all(np.isfinite(draws["logit"][m]), axis=1)].ravel()
         for m in MODELS]) < 1.0)),
        "logit 口径：全部模型的全部抽样值是否严格落在 (0,1)")
    addcheck("raw_arima_2028_hi_exceeds_1", bool(np.percentile(vf[:, -1], 97.5) > 1.0),
             "规范首期拟合值后，原始空间 ARIMA 2028 上界是否仍越界（对应审稿意见⑤）")
    addcheck("clamp_mass_at_1_arima_2028", "%.4f" % float(np.mean(vf[:, -1] >= 1.0)),
             "规范首期后，原始空间 ARIMA 2028 抽样中 >=1 的比例（= 截断口径堆积在 1 的质量）")
    addcheck("logit_vs_rawfix_arima_2028_width", "%.4f vs %.4f" % (
        np.percentile(draws["logit"]["ARIMA(0,1,1)"][
            np.all(np.isfinite(draws["logit"]["ARIMA(0,1,1)"]), axis=1)][:, -1], 97.5)
        - np.percentile(draws["logit"]["ARIMA(0,1,1)"][
            np.all(np.isfinite(draws["logit"]["ARIMA(0,1,1)"]), axis=1)][:, -1], 2.5),
        np.percentile(vf[:, -1], 97.5) - np.percentile(vf[:, -1], 2.5)),
        "ARIMA 2028 区间宽度：logit 口径 vs 原始空间（对照口径保守性）")
    addcheck("gamma_train_fixed", gamma_train, "主 NGBM 所用 γ（训练期 SSE 最优）")
    addcheck("source_csv_md5_r32_validation_detail",
             md5(os.path.join(DATA, "r32_validation_8ind_detail.csv")),
             "输入：五方案逐折精度")
    addcheck("source_csv_md5_r29_forecast_8ind",
             md5(os.path.join(DATA, "r29_forecast_8ind.csv")), "输入：点预测")
    addcheck("script", "run_r44_mixture_bounded.py", "生成脚本（已提交）")

    # ---------- 6) 落盘 ----------
    pd.DataFrame(wrows).to_csv(OUT_W, index=False, encoding="utf-8-sig")
    pd.DataFrame(acc_rows).to_csv(OUT_A, index=False, encoding="utf-8-sig")
    pd.DataFrame(interval_rows).to_csv(OUT_I, index=False, encoding="utf-8-sig")
    pd.DataFrame(grade_rows).to_csv(OUT_G, index=False, encoding="utf-8-sig")
    pd.DataFrame(summ_rows).to_csv(OUT_S, index=False, encoding="utf-8-sig")
    pd.DataFrame(checks).to_csv(OUT_K, index=False, encoding="utf-8-sig")

    print("\n--- 权重与 2028 ---")
    for ws in W:
        print("  %-18s w=%s  2028 点值 %.4f  等级 %s"
              % (ws, {m: round(W[ws][m], 4) for m in MODELS}, mix_pt[ws][-1],
                 GRADES[grade_index(mix_pt[ws][-1])]))
    print("\n--- 2028 区间（四口径，invRMSE 混合）---")
    for method in METHODS:
        s = [r for r in summ_rows if r["target"] == "mixture"
             and r["method"] == method and r["weight_scheme"] == "invRMSE"][0]
        print("  %-6s 点值 %.6f  95%% [%.4f, %.4f]  P(medium)=%.4f P(mild)=%.4f"
              % (method, s["point_2028"], s["ci_lo_2.5_2028"], s["ci_hi_97.5_2028"],
                 s["p_medium_2028"], s["p_mild_2028"]))
    print("\n--- 2028 区间（三口径，逐模型，logit 为主）---")
    for m in MODELS:
        for method in METHODS:
            s = [r for r in summ_rows if r["target"] == m and r["method"] == method][0]
            print("  %-14s %-6s 点值 %.6f  95%% [%.4f, %.4f]  等级 %s"
                  % (m, method, s["point_2028"], s["ci_lo_2.5_2028"],
                     s["ci_hi_97.5_2028"], s["grade_2028"]))
    print("\n--- 复现校验 ---")
    for c in checks:
        print("  %-42s %s" % (c["item"], c["value"]))
    print("\n写出：\n  %s\n  %s\n  %s\n  %s\n  %s\n  %s"
          % (OUT_W, OUT_A, OUT_I, OUT_G, OUT_S, OUT_K))


if __name__ == "__main__":
    raise SystemExit("Historical round script. Current estimator, validation and bootstrap: "
                     "python run_r47_revision.py --stage all --bootstrap 2000")
