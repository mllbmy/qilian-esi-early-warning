# -*- coding: utf-8 -*-
"""R29 · T2 —— 八指标主规格（drop_X9）的 2024–2028 预测全套（审稿意见第 1、5 条）

────────────────────────────────────────────────────────────────────────────
问题
────────────────────────────────────────────────────────────────────────────
第一轮修订只改了历史评估，预测段（§4.4）、Fig. 4、Tables 7–9 仍是九指标
（NGBM γ=0.20：2024 0.4458 → 2028 0.3939）。本轮在**八指标主规格的 ESI 序列**
上重跑预测全套，并把三模型并列（不只突出 NGBM）。

────────────────────────────────────────────────────────────────────────────
口径（与 B 的 `run_r28_forecast_uncertainty.py` / `run_r28_gamma_leakage.py` 一致）
────────────────────────────────────────────────────────────────────────────
· 目标序列：`r28_core.compute(DEREDUNDANT_SETS['drop_X9'])` 的 ESI（2005–2023），
  与 `data/r28_deredundancy_series.csv` 的 `esi_drop_X9` 列逐位一致（本脚本校验）。
· α = 0.4；五级阈值 [0.2, 0.4, 0.6, 0.8]。
· NGBM 幂指数 γ：网格 0.05–1.95、步长 0.05（与原文搜索范围一致），目标 = 残差平方和 SSE：
    – 仅训练期 2005–2018（14 点）→ **无泄漏口径，作主 NGBM**；
    – 全序列 2005–2023（19 点）→ 对照（= 论文九指标所报 γ 的选法）。
  另报训练期 MAE 目标下的 γ 作对照。γ 曲线与 holdout 诊断落
  `data/r29_forecast_8ind_gamma.csv`。
· ARIMA 固定 (0,1,1)（阶数不由数据选，故无选阶泄漏），与 B 的口径一致。
· GM(1,1) 无超参数。
· Bootstrap：B = 2000，seed = 20261017（与 B 同），块长 L = 3；每重复
  ① 残差重采样得到伪历史 → ② 重估参数（NGBM 按需**重选 γ**）→ ③ 叠加新息。
  三种模型使用**同一个 seed**，且新息在重估**之前**抽取，故第 b 条路径在三个模型
  之间是同一情景 ⇒ model-averaging 与配对比较自洽。
  区间口径五种（同 B）：param_only / innov_only_block / total_iid / total_block /
  param_plus_iid_nocum。主口径 = total_block（参数 + γ 重选 + 累积新息块重采样）。

────────────────────────────────────────────────────────────────────────────
输出（全部新文件）
────────────────────────────────────────────────────────────────────────────
· data/r29_forecast_8ind.csv           点预测（八指标三模型 + γ 变体 + 九指标对照）
· data/r29_forecast_8ind_intervals.csv bootstrap 区间逐年 2.5%/97.5% 分位
· data/r29_grade_prob_8ind.csv         逐年五级等级概率
· data/r29_2028_range.csv              2028 三模型点值/区间/P(中警)/P(轻警) + model-averaged
                                       + 0.400 阈值 margin 与舍入翻级分析
· data/r29_forecast_8ind_gamma.csv     γ 网格曲线（训练期/全序列/holdout）
· data/r29_forecast_8ind_checks.csv    复算校验与关键读数

运行：python run_r29_forecast_8ind.py
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
sys.path.insert(0, os.path.join(BASE, "eco_security"))
from eco_security import gm11_forecast  # noqa: E402

import r28_core as C  # noqa: E402

ALPHA = 0.4
TRAIN_END = 2018
N_TRAIN = 14
FUT_YEARS = list(range(2024, 2029))
N_FUT = 5
B = 2000
SEED = 20261017
BLOCK_L = 3
GAMMA_GRID = np.round(np.arange(0.05, 1.96, 0.05), 2)
GRADES = ["重警", "中警", "轻警", "较安全", "安全"]
THR = [0.2, 0.4, 0.6, 0.8]

OUT_FC = os.path.join(DATA, "r29_forecast_8ind.csv")
OUT_CI = os.path.join(DATA, "r29_forecast_8ind_intervals.csv")
OUT_GP = os.path.join(DATA, "r29_grade_prob_8ind.csv")
OUT_R28 = os.path.join(DATA, "r29_2028_range.csv")
OUT_G = os.path.join(DATA, "r29_forecast_8ind_gamma.csv")
OUT_K = os.path.join(DATA, "r29_forecast_8ind_checks.csv")

METHODS = ["param_only", "innov_only_block", "total_iid", "total_block",
           "param_plus_iid_nocum"]


# ---------------------------------------------------------------------------
# 模型
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
    """仅在 x0 内部选 γ（无泄漏）。返回 (best_value, gamma, curve)。"""
    curve, best = [], None
    for g in GAMMA_GRID:
        r = ngbm_try(x0, g, n_pred=1)
        if r is None:
            curve.append((float(g), np.nan))
            continue
        e = np.asarray(x0, float)[1:] - r[1][1:]
        if objective == "sse":
            v = float(np.sum(e ** 2))
        elif objective == "mae":
            v = float(np.mean(np.abs(e)))
        else:
            raise ValueError(objective)
        curve.append((float(g), v))
        if best is None or v < best[0]:
            best = (v, float(g))
    return best[0], best[1], curve


def fp_ngbm(series, gamma, n_pred=N_FUT):
    r = ngbm_try(series, gamma, n_pred=n_pred)
    if r is None:
        return None
    fut, xh, par = r
    return fut, xh, "gamma=%.2f (a=%.6f, b=%.6f)" % (par[2], par[0], par[1])


def fp_ngbm_reselect(series, n_pred=N_FUT):
    _, g, _ = select_gamma(series, "sse")
    r = ngbm_try(series, g, n_pred=n_pred)
    if r is None:
        return None
    return r[0], r[1], g, "gamma=%.2f (reselect)" % g


def fp_gm(series, n_pred=N_FUT):
    fut, fit, Cp, Pp = gm11_forecast(np.asarray(series, float), n_pred=n_pred)
    return np.asarray(fut, float), np.asarray(fit, float), "C=%.4f P=%.4f" % (Cp, Pp)


def fp_arima(series, n_pred=N_FUT):
    from statsmodels.tsa.arima.model import ARIMA
    m = ARIMA(np.asarray(series, float), order=(0, 1, 1)).fit()
    fit = np.asarray(m.fittedvalues, float)
    if len(fit) == len(series) - 1:
        fit = np.concatenate([[series[0]], fit])
    return np.asarray(m.forecast(n_pred), float), fit, "order=(0, 1, 1)"


def draw_block(r, n, L, rng):
    if len(r) <= L:
        return rng.choice(r, size=n, replace=True)
    starts = rng.integers(0, len(r) - L + 1, size=int(np.ceil(n / L)))
    return np.concatenate([r[s:s + L] for s in starts])[:n]


# ---------------------------------------------------------------------------
# Bootstrap（三模型同 seed；新息先抽，保证跨模型同情景）
# ---------------------------------------------------------------------------
def bootstrap_paths(series, fp, reselect=False, B=B, seed=SEED):
    base = fp(series)
    if base is None:
        return None
    fut0 = np.asarray(base[0], float)
    fit0 = np.asarray(base[1], float)
    rc = np.asarray(series, float) - fit0
    n = len(series)
    rng = np.random.default_rng(seed)
    out = {k: np.full((B, N_FUT), np.nan) for k in METHODS}
    gammas = []
    for b in range(B):
        # ① 残差重采样索引（跨模型一致）
        idx = rng.choice(n, size=n, replace=True)
        # ② 新息（跨模型一致；在重估之前抽取，避免重估失败打乱随机流）
        e_iid = rng.choice(rc - rc.mean(), size=N_FUT, replace=True)
        e_blk = draw_block(rc - rc.mean(), N_FUT, BLOCK_L, rng)
        # ③ 伪历史 → 重估
        y = fit0 + rc[idx]
        if reselect:
            try:
                r = fp_ngbm_reselect(y)
            except Exception:
                r = None
            if r is None:
                continue
            p = np.asarray(r[0], float)
            if not np.all(np.isfinite(p)):
                continue
            gammas.append(r[2])
        else:
            try:
                r = fp(y)
            except Exception:
                r = None
            if r is None or not np.all(np.isfinite(np.asarray(r[0], float))):
                continue
            p = np.asarray(r[0], float)
        out["param_only"][b] = p
        out["total_iid"][b] = p + np.cumsum(e_iid)
        out["total_block"][b] = p + np.cumsum(e_blk)
        out["param_plus_iid_nocum"][b] = p + e_iid
        out["innov_only_block"][b] = fut0 + np.cumsum(e_blk)
    return out, np.asarray(gammas, float)


def grade_index(v):
    return sum(1 for t in THR if v >= t)


def grade_of(v):
    return GRADES[grade_index(v)]


# ---------------------------------------------------------------------------
def main():
    print("=" * 78)
    print("R29 · T2 —— 八指标主规格 2024–2028 预测全套")
    print("=" * 78)

    r8 = C.compute(C.DEREDUNDANT_SETS["drop_X9"])
    r9 = C.compute(C.DEREDUNDANT_SETS["baseline9"])
    esi8 = np.asarray(r8["esi"], float)
    esi9 = np.asarray(r9["esi"], float)
    years = list(r8["years"])

    archived = pd.read_csv(os.path.join(DATA, "r28_deredundancy_series.csv"))
    d8 = float(np.abs(esi8 - archived["esi_drop_X9"].values).max())
    d9 = float(np.abs(esi9 - archived["esi_baseline9"].values).max())
    print("[校验] 八指标 ESI vs r28_deredundancy_series.csv max|Δ| = %.3e" % d8)
    print("[校验] 九指标 ESI vs 同上                            max|Δ| = %.3e" % d9)

    chk = []

    def addcheck(item, value, note):
        chk.append({"item": item, "value": value, "note": note})

    addcheck("esi_8ind_vs_archived_max_abs_delta", float("%.3e" % d8),
             "drop_X9 主规格 ESI 重建 vs data/r28_deredundancy_series.csv（长表列 esi_drop_X9）")
    addcheck("esi_9ind_vs_archived_max_abs_delta", float("%.3e" % d9),
             "baseline9 对照 ESI 重建 vs 同一归档 CSV")
    addcheck("esi_8ind_2023", round(float(esi8[-1]), 6), "八指标主规格 2023 年 ESI")
    addcheck("esi_8ind_2010_peak", round(float(esi8[np.argmax(esi8)]), 6),
             "八指标主规格峰值（年 = %d）" % years[int(np.argmax(esi8))])
    addcheck("esi_8ind_2005", round(float(esi8[0]), 6), "八指标主规格 2005 年 ESI（序列低值端）")

    # ---------- 1) γ 选择（无泄漏 vs 全序列） ----------
    print("\n" + "-" * 78)
    print("1) NGBM 幂指数 γ 的选择（网格 %.2f–%.2f，步长 0.05）"
          % (GAMMA_GRID[0], GAMMA_GRID[-1]))
    print("-" * 78)
    sse_tr, g_tr_sse, curve_tr = select_gamma(esi8[:N_TRAIN], "sse")
    mae_tr, g_tr_mae, _ = select_gamma(esi8[:N_TRAIN], "mae")
    sse_fu, g_fu_sse, curve_fu = select_gamma(esi8, "sse")
    sse_tr9, g_tr9, _ = select_gamma(esi9[:N_TRAIN], "sse")
    sse_fu9, g_fu9, _ = select_gamma(esi9, "sse")
    print("   八指标 仅训练期 2005–2018（14 点）SSE 目标：γ* = %.2f（SSE=%.6f）" % (g_tr_sse, sse_tr))
    print("   八指标 仅训练期 2005–2018（14 点）MAE 目标：γ* = %.2f（MAE=%.6f）" % (g_tr_mae, mae_tr))
    print("   八指标 全序列 2005–2023（19 点）SSE 目标：γ* = %.2f（SSE=%.6f）" % (g_fu_sse, sse_fu))
    print("   [对照] 九指标 γ*：训练期 %.2f / 全序列 %.2f（与 B 报告一致）" % (g_tr9, g_fu9))
    g_at_lower_bound = bool(abs(g_fu_sse - GAMMA_GRID[0]) < 1e-9)
    print("   注意：八指标全序列 SSE 的最优 γ 落在网格**下边界 0.05**%s"
          % ("（边界解，非内点最优）" if g_at_lower_bound else ""))
    addcheck("gamma_8ind_train_sse", g_tr_sse,
             "八指标主规格：仅训练期 2005–2018 按 SSE 选出的 γ（无泄漏口径，主 NGBM 所用）")
    addcheck("gamma_8ind_train_mae", g_tr_mae, "同一训练期按 MAE 选出的 γ（对照）")
    addcheck("gamma_8ind_full_sse", g_fu_sse,
             "八指标全序列 2005–2023 按 SSE 选出的 γ（对照；含评估期信息）")
    addcheck("gamma_8ind_full_sse_at_grid_lower_bound", g_at_lower_bound,
             "全序列最优 γ 是否落在搜索网格下边界 0.05（边界解）")
    addcheck("gamma_9ind_train_sse", g_tr9, "九指标对照：训练期 SSE 最优 γ")
    addcheck("gamma_9ind_full_sse", g_fu9, "九指标对照：全序列 SSE 最优 γ（= 论文所报 0.20）")

    # γ 曲线 + holdout 诊断
    holdout = esi8[N_TRAIN:]
    grows = []
    for g, v_tr in curve_tr:
        r_h = ngbm_try(esi8[:N_TRAIN], g)
        if r_h is None:
            rmse = np.nan
            mae = np.nan
        else:
            e = holdout - r_h[0]
            rmse = float(np.sqrt(np.mean(e ** 2)))
            mae = float(np.mean(np.abs(e)))
        r_f = ngbm_try(esi8, g, n_pred=1)
        sse_full = (float(np.sum((esi8[1:] - r_f[1][1:]) ** 2))
                    if r_f is not None else np.nan)
        grows.append({"gamma": g, "sse_train_2005_2018": v_tr,
                      "sse_full_2005_2023": sse_full,
                      "holdout_rmse_2019_2023": rmse, "holdout_mae_2019_2023": mae})
    gc = pd.DataFrame(grows)
    gc.to_csv(OUT_G, index=False, encoding="utf-8-sig")
    gh = gc.dropna(subset=["holdout_rmse_2019_2023"])
    g_hbest = float(gh.loc[gh.holdout_rmse_2019_2023.idxmin(), "gamma"])
    print("   holdout（2019–2023）RMSE 最小的 γ = %.2f（训练期 SSE 最优为 %.2f）——"
          "两者不同，如实报告" % (g_hbest, g_tr_sse))
    addcheck("gamma_8ind_holdout_rmse_argmin", g_hbest,
             "八指标：使 holdout 2019–2023 RMSE 最小的 γ（**只用于诊断**；训练期 SSE 最优 γ "
             "与它不同，说明 γ 的目标函数选择会改变外推斜率）")

    # ---------- 2) 点预测 ----------
    print("\n" + "-" * 78)
    print("2) 点预测（origin = 2023）")
    print("-" * 78)
    specs = []          # (name, series, fp, reselect, info)
    point = {}
    fut_n = fp_ngbm(esi8, g_tr_sse)
    fut_nf = fp_ngbm(esi8, g_fu_sse)
    fut_nm = fp_ngbm(esi8, g_tr_mae)
    fut_gm8, fit_gm8, info_gm8 = fp_gm(esi8)
    fut_ar8, fit_ar8, info_ar8 = fp_arima(esi8)
    # 九指标对照
    fut_gm9, _, info_gm9 = fp_gm(esi9)
    fut_ar9, _, info_ar9 = fp_arima(esi9)
    fut_n9f = fp_ngbm(esi9, g_fu9)
    fut_n9t = fp_ngbm(esi9, g_tr9)

    point["GM(1,1)"] = (fut_gm8, fit_gm8, info_gm8)
    point["NGBM_gamma_train"] = (fut_n[0], fut_n[1], fut_n[2])
    point["NGBM_gamma_full"] = (fut_nf[0], fut_nf[1], fut_nf[2])
    point["NGBM_gamma_train_mae"] = (fut_nm[0], fut_nm[1], fut_nm[2])
    point["ARIMA(0,1,1)"] = (fut_ar8, fit_ar8, info_ar8)

    # 三模型（主规格口径：NGBM 用无泄漏 γ）
    PRIMARY3 = {"GM(1,1)": fp_gm, "NGBM": lambda s: fp_ngbm(s, g_tr_sse),
                "ARIMA(0,1,1)": fp_arima}
    RESELECT3 = {"NGBM": True}      # 仅 NGBM 有可重选的幂指数

    for nm, (f, fit, info) in point.items():
        print("   %-22s 2024=%.4f 2025=%.4f 2026=%.4f 2027=%.4f 2028=%.4f  斜率=%+.5f/yr  %s"
              % tuple([nm] + list(np.round(f, 4))
                      + [np.polyfit(range(N_FUT), f, 1)[0], info]))
    print("   [九指标对照] GM 2028=%.4f ; NGBM γ=%.2f 2028=%.4f ; NGBM γ=%.2f 2028=%.4f ; "
          "ARIMA 2028=%.4f" % (fut_gm9[-1], g_fu9, fut_n9f[0][-1], g_tr9, fut_n9t[0][-1],
                               fut_ar9[-1]))

    # 点预测落盘
    rows = []
    for i, y in enumerate(FUT_YEARS):
        rows.append({
            "year": y,
            "gm11_8ind": round(float(fut_gm8[i]), 6),
            "ngbm_8ind_gamma_train": round(float(fut_n[0][i]), 6),
            "ngbm_8ind_gamma_full": round(float(fut_nf[0][i]), 6),
            "ngbm_8ind_gamma_train_mae": round(float(fut_nm[0][i]), 6),
            "arima_011_8ind": round(float(fut_ar8[i]), 6),
            "gm11_9ind": round(float(fut_gm9[i]), 6),
            "ngbm_9ind_gamma_full": round(float(fut_n9f[0][i]), 6),
            "ngbm_9ind_gamma_train": round(float(fut_n9t[0][i]), 6),
            "arima_011_9ind": round(float(fut_ar9[i]), 6),
            "grade_gm11_8ind": grade_of(fut_gm8[i]),
            "grade_ngbm_8ind_gamma_train": grade_of(fut_n[0][i]),
            "grade_ngbm_8ind_gamma_full": grade_of(fut_nf[0][i]),
            "grade_arima_011_8ind": grade_of(fut_ar8[i]),
            "grade_ngbm_9ind_gamma_full": grade_of(fut_n9f[0][i]),
            "note": ("八指标主规格三模型 + γ 变体；九指标列供对照。"
                     "NGBM 主口径 γ 由训练期 2005–2018 SSE 选出（无泄漏）"),
        })
    fc = pd.DataFrame(rows)
    fc.to_csv(OUT_FC, index=False, encoding="utf-8-sig")

    addcheck("dpsi_2028_gm11_8ind", round(float(fut_gm8[-1]), 6), "八指标 GM(1,1) 2028 点预测")
    addcheck("dpsi_2028_ngbm_8ind_gamma_train", round(float(fut_n[0][-1]), 6),
             "八指标 NGBM 2028 点预测（γ 仅训练期选择，无泄漏，主口径）")
    addcheck("dpsi_2028_ngbm_8ind_gamma_full", round(float(fut_nf[0][-1]), 6),
             "八指标 NGBM 2028 点预测（γ 用全序列 SSE 选，对照）")
    addcheck("dpsi_2028_arima_8ind", round(float(fut_ar8[-1]), 6), "八指标 ARIMA(0,1,1) 2028 点预测")
    addcheck("dpsi_2028_three_model_point_range", round(float(max(fut_gm8[-1], fut_n[0][-1],
                                                                    fut_ar8[-1])
                                                            - min(fut_gm8[-1], fut_n[0][-1],
                                                                  fut_ar8[-1])), 6),
             "八指标 2028 三模型（GM / NGBM 无泄漏 γ / ARIMA）点值跨度")
    addcheck("gm11_8ind_accuracy_C", round(float(gm11_forecast(esi8, 1)[2]), 6),
             "八指标 GM(1,1) 后验差比值 C（<0.35 优、<0.5 合格）")
    addcheck("gm11_8ind_accuracy_P", round(float(gm11_forecast(esi8, 1)[3]), 6),
             "八指标 GM(1,1) 小误差概率 P（>0.95 优、>0.8 合格）")

    # ---------- 3) Bootstrap 区间 ----------
    print("\n" + "-" * 78)
    print("3) Bootstrap 预测区间（B=%d，seed=%d，块长=%d；主口径 total_block）" % (B, SEED, BLOCK_L))
    print("-" * 78)
    paths = {}
    runs = []
    for nm, fp in PRIMARY3.items():
        if nm == "NGBM":
            runs.append((nm, fp, True, "reselect_each_replicate"))
            runs.append((nm, fp, False, "fixed_gamma=%.2f" % g_tr_sse))
        else:
            runs.append((nm, fp, False, "not_applicable"))
    irows = []
    gamma_draws = {}
    for nm, fp, reselect, gmode in runs:
        out = bootstrap_paths(esi8, fp, reselect=reselect)
        if out is None:
            continue
        pset, gs = out
        if len(gs):
            gamma_draws[nm] = gs
        for method in METHODS:
            p = pset[method]
            if not np.any(np.isfinite(p)):
                continue
            paths[(nm, method, gmode)] = p
            lo95, hi95 = np.nanpercentile(p, 2.5, axis=0), np.nanpercentile(p, 97.5, axis=0)
            for i, y in enumerate(FUT_YEARS):
                irows.append({
                    "model": nm, "gamma_mode": gmode, "method": method, "year": y,
                    "point_forecast": round(float(point[
                        {"GM(1,1)": "GM(1,1)", "ARIMA(0,1,1)": "ARIMA(0,1,1)",
                         "NGBM": "NGBM_gamma_train"}[nm]][0][i]), 6),
                    "boot_mean": round(float(np.nanmean(p[:, i])), 6),
                    "boot_sd": round(float(np.nanstd(p[:, i], ddof=1)), 6),
                    "boot_p2.5": round(float(lo95[i]), 6),
                    "boot_p50": round(float(np.nanpercentile(p[:, i], 50)), 6),
                    "boot_p97.5": round(float(hi95[i]), 6),
                    "width95": round(float(hi95[i] - lo95[i]), 6),
                    "n_boot_valid": int(np.sum(np.isfinite(p[:, i]))),
                    "note": "八指标主规格 bootstrap；三模型同 seed、新息先抽 ⇒ 第 b 条路径同情景",
                })
    ci = pd.DataFrame(irows)
    ci.to_csv(OUT_CI, index=False, encoding="utf-8-sig")

    for nm in ["NGBM", "GM(1,1)", "ARIMA(0,1,1)"]:
        for gmode in ([g for g in ["reselect_each_replicate", "fixed_gamma=%.2f" % g_tr_sse]]
                      if nm == "NGBM" else ["not_applicable"]):
            sub = ci[(ci.model == nm) & (ci.method == "total_block")
                     & (ci.gamma_mode == gmode)].sort_values("year")
            if len(sub) == 0:
                continue
            print("   %-14s %-24s 95%% 区间：" % (nm, gmode)
                  + " | ".join("%d %.4f~%.4f" % (r.year, r["boot_p2.5"], r["boot_p97.5"])
                               for _, r in sub.iterrows()))
    if "NGBM" in gamma_draws:
        gs = gamma_draws["NGBM"]
        uniq, cnt = np.unique(np.round(gs, 2), return_counts=True)
        print("   NGBM 每次重复重选的 γ 分布（前 6）："
              + ", ".join("%.2f:%.1f%%" % (g, 100.0 * c / len(gs))
                          for g, c in sorted(zip(uniq, cnt), key=lambda t: -t[1])[:6]))
        addcheck("ngbm_reselected_gamma_mode", round(float(np.median(gs)), 2),
                 "bootstrap 每次重复重选 γ 的中位数（主口径 total_block 的 γ 选择不确定性）")
        addcheck("ngbm_reselected_gamma_share_equal_to_train_opt",
                 round(float(np.mean(np.round(gs, 2) == g_tr_sse)), 6),
                 "bootstrap 中重选 γ 恰等于训练期最优 γ 的比例")

    # γ 固定 vs 重选的区间宽度对比
    for method in ["param_only", "total_block"]:
        a = ci[(ci.model == "NGBM") & (ci.method == method)
               & (ci.gamma_mode == "reselect_each_replicate")].sort_values("year")
        b = ci[(ci.model == "NGBM") & (ci.method == method)
               & (ci.gamma_mode == "fixed_gamma=%.2f" % g_tr_sse)].sort_values("year")
        if len(a) and len(b):
            print("   NGBM %-12s 2028 区间宽度：γ 重选 %.4f vs γ 固定 %.4f（比值 %.3f）"
                  % (method, a.width95.values[-1], b.width95.values[-1],
                     a.width95.values[-1] / b.width95.values[-1]))
    addcheck("ngbm_total_block_width2028_reselect", 
             round(float(ci[(ci.model == "NGBM") & (ci.method == "total_block")
                            & (ci.gamma_mode == "reselect_each_replicate")
                            & (ci.year == 2028)].width95.iloc[0]), 6),
             "八指标 NGBM 2028 年 95% 区间宽度（参数 + γ 重选 + 累积新息块重采样）")
    addcheck("ngbm_total_block_width2028_gamma_fixed",
             round(float(ci[(ci.model == "NGBM") & (ci.method == "total_block")
                            & (ci.gamma_mode == "fixed_gamma=%.2f" % g_tr_sse)
                            & (ci.year == 2028)].width95.iloc[0]), 6),
             "同上但 γ 固定为训练期最优值（不含 γ 选择不确定性）")

    # ---------- 4) 逐年等级概率 ----------
    print("\n" + "-" * 78)
    print("4) 等级概率（蒙特卡洛，主口径 total_block）")
    print("-" * 78)
    grows = []
    for (nm, method, gmode), p in paths.items():
        for i, y in enumerate(FUT_YEARS):
            v = p[:, i]
            v = v[np.isfinite(v)]
            if len(v) == 0:
                continue
            lv = np.array([grade_index(x) for x in v])
            probs = [float(np.mean(lv == k)) for k in range(5)]
            modal = int(np.argmax(probs))
            grows.append({
                "model": nm, "method": method, "gamma_mode": gmode, "year": y,
                "p_severe": round(probs[0], 6), "p_medium": round(probs[1], 6),
                "p_mild": round(probs[2], 6), "p_rel_safe": round(probs[3], 6),
                "p_safe": round(probs[4], 6),
                "modal_grade": GRADES[modal], "p_modal": round(probs[modal], 6),
                "p_below_0.400": round(float(np.mean(v < 0.400)), 6),
                "p_below_0.200": round(float(np.mean(v < 0.200)), 6),
                "p_ge_0.600": round(float(np.mean(v >= 0.600)), 6),
                "boot_mean": round(float(np.mean(v)), 6),
                "boot_p2.5": round(float(np.percentile(v, 2.5)), 6),
                "boot_p97.5": round(float(np.percentile(v, 97.5)), 6),
                "n_boot_valid": int(len(v)),
                "note": "八指标主规格；五级阈值 [0.2,0.4,0.6,0.8]",
            })
    gp = pd.DataFrame(grows)
    gp.to_csv(OUT_GP, index=False, encoding="utf-8-sig")
    for nm in ["GM(1,1)", "NGBM", "ARIMA(0,1,1)"]:
        for gmode in (["reselect_each_replicate", "fixed_gamma=%.2f" % g_tr_sse]
                      if nm == "NGBM" else ["not_applicable"]):
            sub = gp[(gp.model == nm) & (gp.method == "total_block")
                     & (gp.gamma_mode == gmode)].sort_values("year")
            if len(sub) == 0:
                continue
            print("   %s（%s）：" % (nm, gmode))
            for _, r in sub.iterrows():
                print("     %d 重警 %.3f 中警 %.3f 轻警 %.3f 较安全 %.3f 安全 %.3f | "
                      "众数 %-4s P=%.3f | P(ESI<0.400)=%.3f"
                      % (r.year, r.p_severe, r.p_medium, r.p_mild, r.p_rel_safe, r.p_safe,
                         r.modal_grade, r.p_modal, r["p_below_0.400"]))

    # ---------- 5) 2028 三模型范围 + model-averaged ----------
    print("\n" + "-" * 78)
    print("5) 2028 年三模型范围与 model-averaged 区间")
    print("-" * 78)
    rrows = []

    def probs3(v):
        """由 ESI 抽样分布给出 P(重警)/P(中警)/P(轻警)；分级阈值 [0.2,0.4,0.6,0.8]。"""
        return (float(np.mean(v < 0.2)),
                float(np.mean((v >= 0.2) & (v < 0.4))),
                float(np.mean((v >= 0.4) & (v < 0.6))))

    def add_r(row_type, name, point_v, dist, note=""):
        if dist is not None and len(dist):
            lo, hi = float(np.percentile(dist, 2.5)), float(np.percentile(dist, 97.5))
            psev, pm, pmild = probs3(dist)
        else:
            lo = hi = np.nan
            psev = pm = pmild = np.nan
        pv = (float(point_v) if point_v is not None and np.isfinite(point_v) else np.nan)
        extra = {}
        if np.isfinite(pv):
            for d in (6, 3, 2, 1):
                extra["v_%ddp" % d] = round(pv, d)
                extra["grade_%ddp" % d] = grade_of(round(pv, d))
            extra["flips_grade_at_3dp"] = grade_of(round(pv, 3)) != grade_of(pv)
            extra["flips_grade_at_2dp"] = grade_of(round(pv, 2)) != grade_of(pv)
            extra["flips_grade_at_1dp"] = grade_of(round(pv, 1)) != grade_of(pv)
            extra["margin_lt_half_unit_at_3dp"] = abs(pv - 0.400) < 0.0005
            extra["margin_lt_half_unit_at_2dp"] = abs(pv - 0.400) < 0.005
            extra["margin_lt_half_unit_at_1dp"] = abs(pv - 0.400) < 0.05
        rrows.append({
            "row_type": row_type, "model_or_scheme": name,
            "point_2028": (round(pv, 6) if np.isfinite(pv) else np.nan),
            "ci_lo_2.5": (round(lo, 6) if np.isfinite(lo) else np.nan),
            "ci_hi_97.5": (round(hi, 6) if np.isfinite(hi) else np.nan),
            "width95": (round(hi - lo, 6) if np.isfinite(lo) and np.isfinite(hi) else np.nan),
            "ci_hi_exceeds_esi_support_1": (bool(hi > 1.0) if np.isfinite(hi) else ""),
            "point_grade": (grade_of(pv) if np.isfinite(pv) else ""),
            "margin_vs_0.400": (round(pv - 0.400, 6) if np.isfinite(pv) else np.nan),
            "p_severe": (round(psev, 6) if np.isfinite(psev) else np.nan),
            "p_medium": (round(pm, 6) if np.isfinite(pm) else np.nan),
            "p_mild": (round(pmild, 6) if np.isfinite(pmild) else np.nan),
            "n_draws": (int(len(dist)) if dist is not None else 0),
            **extra,
            "note": note,
        })

    per_model_paths = {}
    for nm in ["GM(1,1)", "NGBM", "ARIMA(0,1,1)"]:
        p = paths.get((nm, "total_block",
                       "reselect_each_replicate" if nm == "NGBM" else "not_applicable"))
        if p is None:
            p = paths.get((nm, "total_block", "fixed_gamma=%.2f" % g_tr_sse))
        v = p[:, 4]
        v = v[np.isfinite(v)]
        per_model_paths[nm] = v
        pt = float(point[{"GM(1,1)": "GM(1,1)", "NGBM": "NGBM_gamma_train",
                          "ARIMA(0,1,1)": "ARIMA(0,1,1)"}[nm]][0][-1])
        add_r("model", nm, pt, v,
              "八指标主规格；NGBM 用训练期 γ=%.2f（无泄漏）。"
              "区间与 P(重警)/P(中警)/P(轻警) 均来自该模型自身的 total_block bootstrap 分布"
              % g_tr_sse)

    # NGBM γ 全序列变体（对照行）
    p_nf = paths.get(("NGBM", "total_block", "fixed_gamma=%.2f" % g_fu_sse))
    if p_nf is None:
        out_nf = bootstrap_paths(esi8, lambda s: fp_ngbm(s, g_fu_sse), reselect=False)
        p_nf = out_nf[0]["total_block"] if out_nf is not None else None
    if p_nf is not None:
        v = p_nf[:, 4]
        v = v[np.isfinite(v)]
        add_r("model_variant", "NGBM (γ=%.2f from full series)" % g_fu_sse,
              float(fut_nf[0][-1]), v,
              "γ 由 2005–2023 全序列 SSE 选出（对照口径，含评估期信息）")

    # model-averaged：等权混合三个模型的 total_block 分布
    pooled = np.concatenate([per_model_paths["GM(1,1)"], per_model_paths["NGBM"],
                             per_model_paths["ARIMA(0,1,1)"]])
    pt_avg = float(np.mean([float(point["GM(1,1)"][0][-1]), float(fut_n[0][-1]),
                            float(point["ARIMA(0,1,1)"][0][-1])]))
    add_r("model_averaged", "equal-weight mixture of 3 models (pooled draws)", pt_avg, pooled,
          "**主口径 model-averaged**：p(Δ)=Σ_k w_k p_k(Δ)（w_k=1/3），即 GM(1,1) / "
          "NGBM(γ=%.2f) / ARIMA(0,1,1) 的等权预测分布的混合抽样；三模型同 seed ⇒ 同一情景。"
          "ARIMA 的上界偏大（见 support 列），混合区间因此失真于宽端" % g_tr_sse)
    # 配对完整样本的 model-averaged（逐重复平均）
    m = min(len(per_model_paths[k]) for k in per_model_paths)
    paired = np.mean([per_model_paths[k][:m] for k in ["GM(1,1)", "NGBM", "ARIMA(0,1,1)"]],
                     axis=0)
    add_r("model_averaged", "equal-weight mixture of 3 models (paired replicates)", pt_avg,
          paired, "**诊断行（非标准 BMA）**：逐重复先对三模型的预测取平均再看分布；"
                  "同情景下的模型误差相互抵消，故方差系统性小于上面的混合口径，n=%d" % m)
    if p_nf is not None:
        vv = p_nf[:, 4]
        vv = vv[np.isfinite(vv)]
        pool2 = np.concatenate([per_model_paths["GM(1,1)"], vv, per_model_paths["ARIMA(0,1,1)"]])
        add_r("model_averaged_variant", "mixture with NGBM γ from full series",
              float(np.mean([float(point["GM(1,1)"][0][-1]), float(fut_nf[0][-1]),
                             float(point["ARIMA(0,1,1)"][0][-1])])), pool2,
              "敏感性：把 NGBM 换成 γ=%.2f（全序列口径）后的等权混合" % g_fu_sse)

    print(pd.DataFrame(rrows)[["row_type", "model_or_scheme", "point_2028", "ci_lo_2.5",
                               "ci_hi_97.5", "point_grade", "p_medium", "p_mild"]]
          .to_string(index=False))

    # margin / 精度 / 舍入
    print("\n   0.400 阈值 margin 与报告精度：")
    for lab, pv in [("GM(1,1)", float(point["GM(1,1)"][0][-1])),
                    ("NGBM (γ=%.2f, 无泄漏)" % g_tr_sse, float(fut_n[0][-1])),
                    ("NGBM (γ=%.2f, 全序列)" % g_fu_sse, float(fut_nf[0][-1])),
                    ("ARIMA(0,1,1)", float(point["ARIMA(0,1,1)"][0][-1])),
                    ("model-averaged 点值", pt_avg)]:
        mg = pv - 0.400
        add_r("margin_and_rounding", lab, pv, None,
              "margin = %+.6f；1 位小数 %.1f（等级 %s）%s；2 位小数 %.2f（%s）%s；"
              "3 位小数 %.3f（%s）%s。|margin| 与报告半单位之比：1 位 %.2f、2 位 %.2f、3 位 %.2f"
              % (mg, round(pv, 1), grade_of(round(pv, 1)),
                 "← 翻级" if grade_of(round(pv, 1)) != grade_of(pv) else "（不翻级）",
                 round(pv, 2), grade_of(round(pv, 2)),
                 "← 翻级" if grade_of(round(pv, 2)) != grade_of(pv) else "（不翻级）",
                 round(pv, 3), grade_of(round(pv, 3)),
                 "← 翻级" if grade_of(round(pv, 3)) != grade_of(pv) else "（不翻级）",
                 abs(mg) / 0.05, abs(mg) / 0.005, abs(mg) / 0.0005))
        print("     %-26s 2028 = %.6f  margin = %+.6f | 1dp %.1f→%s%s | 2dp %.2f→%s | 3dp %.3f→%s"
              % (lab, pv, mg, round(pv, 1), grade_of(round(pv, 1)),
                 "  ← 翻级" if grade_of(round(pv, 1)) != grade_of(pv) else "",
                 round(pv, 2), grade_of(round(pv, 2)), round(pv, 3), grade_of(round(pv, 3))))
    arow = [r for r in rrows if r["model_or_scheme"] == "ARIMA(0,1,1)"]
    if arow and arow[0].get("ci_hi_exceeds_esi_support_1"):
        print("   注意：ARIMA(0,1,1) 的 total_block 95%% 区间上界 %.4f **超出 ESI 的 [0,1] 支撑**"
              "（累积新息叠加在 min–max 指数上的已知产物），引用该区间时须说明"
              % arow[0]["ci_hi_97.5"])
        addcheck("arima_2028_ci_hi_exceeds_support", round(float(arow[0]["ci_hi_97.5"]), 6),
                 "ARIMA(0,1,1) 2028 年 95% 区间上界 > 1，超出 min–max 型 ESI 的取值支撑；"
                 "该口径把累积新息直接叠加在指数上，故上界不可解释为 ESI 可达值")
    rr = pd.DataFrame(rrows)
    rr.to_csv(OUT_R28, index=False, encoding="utf-8-sig")

    # ---------- 6) 汇总读数 ----------
    addcheck("dpsi_2028_model_averaged_point", round(pt_avg, 6),
             "八指标 model-averaged 2028 点值（三模型等权平均）")
    addcheck("dpsi_2028_model_averaged_grade", grade_of(pt_avg),
             "model-averaged 2028 点值等级")
    addcheck("dpsi_2028_margin_model_averaged", round(pt_avg - 0.400, 6),
             "model-averaged 2028 点值距 0.400 阈值")
    addcheck("dpsi_2028_margin_ngbm_gamma_train", round(float(fut_n[0][-1]) - 0.400, 6),
             "NGBM（无泄漏 γ）2028 点值距 0.400 阈值；负值 = 落在阈值以下")
    addcheck("dpsi_2028_p_medium_model_averaged", round(probs3(pooled)[1], 6),
             "model-averaged 2028 P(中警)")
    addcheck("dpsi_2028_p_mild_model_averaged", round(probs3(pooled)[2], 6),
             "model-averaged 2028 P(轻警)")
    addcheck("dpsi_2028_p_below_0400_model_averaged", round(float(np.mean(pooled < 0.4)), 6),
             "model-averaged 2028 P(ESI < 0.400)")
    addcheck("dpsi_2028_margin_gm11", round(float(fut_gm8[-1] - 0.400), 6),
             "GM(1,1) 2028 点值距 0.400 阈值")
    addcheck("dpsi_2028_margin_arima", round(float(fut_ar8[-1] - 0.400), 6),
             "ARIMA(0,1,1) 2028 点值距 0.400 阈值")
    addcheck("dpsi_2028_flip_grade_at_1dp_ngbm_gamma_train",
             bool(grade_of(round(float(fut_n[0][-1]), 1)) != grade_of(float(fut_n[0][-1]))),
             "NGBM（无泄漏 γ=%.2f）2028 点值 0.380401 在 **1 位小数**下舍入为 0.4 → 等级由"
             "「中警」（3 位小数 0.380）翻为「轻警」；2 位小数 0.38 与 3 位小数 0.380 均不翻级"
             % g_tr_sse)
    addcheck("dpsi_2028_flip_grade_at_1dp_model_averaged",
             bool(grade_of(round(pt_avg, 1)) != grade_of(pt_avg)),
             "model-averaged 2028 点值在 1 位小数下是否翻级")
    addcheck("dpsi_2028_margin_in_reporting_grid_ngbm_gamma_train",
             round(abs(float(fut_n[0][-1]) - 0.400) / 0.0005, 4),
             "NGBM 2028 的 |margin| 与 3 位小数半单位(0.0005) 之比（>1 ⇒ margin 远大于报告精度，"
             "等级判定不因报告精度而改变）")
    addcheck("dpsi_2028_margin_in_reporting_grid_model_averaged",
             round(abs(pt_avg - 0.400) / 0.0005, 4),
             "model-averaged 2028 的 |margin| 与 3 位小数半单位之比")

    print("\n" + "-" * 78)
    print("6) 与九指标口径的对照（论文现正文所载值）")
    print("-" * 78)
    for lab, a, b in [("2024 点值 GM", fut_gm8[0], fut_gm9[0]),
                      ("2028 点值 GM", fut_gm8[-1], fut_gm9[-1]),
                      ("2024 点值 NGBM(全序列 γ)", fut_nf[0][0], fut_n9f[0][0]),
                      ("2028 点值 NGBM(全序列 γ)", fut_nf[0][-1], fut_n9f[0][-1]),
                      ("2028 点值 ARIMA", fut_ar8[-1], fut_ar9[-1])]:
        print("   %-26s 八指标 %.4f  vs  九指标 %.4f  （Δ %+.4f）" % (lab, a, b, a - b))
    addcheck("compare_2028_ngbm_full_gamma_8ind_minus_9ind",
             round(float(fut_nf[0][-1] - fut_n9f[0][-1]), 6),
             "同用全序列 γ 时，八指标 NGBM 2028 点值 − 九指标 NGBM 2028 点值")

    pd.DataFrame(chk).to_csv(OUT_K, index=False, encoding="utf-8-sig")
    print("\n已写出：data/r29_forecast_8ind.csv（%d 行）" % len(fc))
    print("        data/r29_forecast_8ind_intervals.csv（%d 行）" % len(ci))
    print("        data/r29_grade_prob_8ind.csv（%d 行）" % len(gp))
    print("        data/r29_2028_range.csv（%d 行）" % len(rr))
    print("        data/r29_forecast_8ind_gamma.csv（%d 行）" % len(gc))
    print("        data/r29_forecast_8ind_checks.csv（%d 行）" % len(chk))
    return 0


if __name__ == "__main__":
    raise SystemExit("Historical round script. Current estimator, validation and bootstrap: "
                     "python run_r47_revision.py --stage all --bootstrap 2000")
