# -*- coding: utf-8 -*-
"""R32b —— 五种样本外预测验证方案在**八指标主规格 ESI 序列**上的重算（Table 7）

────────────────────────────────────────────────────────────────────────────
问题
────────────────────────────────────────────────────────────────────────────
R29–R32 已把论文主口径改成八指标 DPSI（删去恒等重复项 X9「生态土地比例」），
但 Table 7 的五方案验证仍沿用九指标证据（并附一句明示注）。第二轮审稿人指出的
「历史用八指标、其余仍九指标」同类不一致因此残留。本脚本把**同一套协议**（与
`run_r28_rolling_loocv.py` 逐字一致的折内选参规则）整体搬到八指标序列上重算，
使八指标主规格与九指标对照之间**只差输入序列这一件事**。

────────────────────────────────────────────────────────────────────────────
数据真源与口径（不新建、不覆盖任何已跟踪 CSV 的输入）
────────────────────────────────────────────────────────────────────────────
· 八指标主规格 ESI：`r28_core.compute(DEREDUNDANT_SETS['drop_X9'])["esi"]`
  （α=0.4，五级阈值 [0.2,0.4,0.6,0.8]），构造后与
  `data/r28_deredundancy_series.csv::esi_drop_X9` 及
  `data/r28_alpha_grade_matrix.csv`（scenario=drop_X9, alpha=0.4）逐位校验。
· 九指标对照 ESI：`r28_core.compute(DEREDUNDANT_SETS['baseline9'])["esi"]`，
  与同归档 CSV 的 `esi_baseline9` 校验。
· 年份覆盖 2005–2023，共 19 年。

────────────────────────────────────────────────────────────────────────────
五种方案（与正文 Sec. "Prediction models" 的定义一致）
────────────────────────────────────────────────────────────────────────────
 1. holdout_2019_2023         拟合 2005–2018（origin=2018），评估 2019–2023（5 步）
 2. rolling_1step_from2013    origin = 2013..2022（10 折），逐折预测 origin+1
 3. rolling_1step_from2015    origin = 2015..2022（8 折），逐折预测 origin+1
 4. rolling_5step_from2013    origin = 2013..2018（6 折），逐折预测 origin+1..+5
 5. loocv_leave_one_year_out  留一年（19 折），用其余 18 年拟合，预测被留出年份
    ⚠ LOOCV 的训练子集同时含被留出年份之前与之后的年份 ⇒ 它是插值/平滑能力诊断，
      **不是**预测验证；折内选参仍完全不接触被留出年份。口径与 R28 一致。

────────────────────────────────────────────────────────────────────────────
折内选参（**任何超参数都只用该折训练子集**，不接触评估点）
────────────────────────────────────────────────────────────────────────────
· GM(1,1)：无超参数。
· NGBM 幂指数 γ：在训练子集上按残差平方和 SSE 最小做网格搜索，
  网格 0.05–1.95、步长 0.05（与原文一致）。**若最优 γ 落在网格边界（0.05 或
  1.95），在 detail/checks 中显式记为边界解**，不作内点最优解读。
· ARIMA：**主口径 = 阶数固定 (0,1,1)**，即正文 Sec. "Prediction models" 与
  Table 6 所定义的模型（阶数不由数据选择 ⇒ 无任何选阶自由度）。另附
  「阶数在训练子集上按 AIC 最小选择」变体（候选集与 `run_r28_rolling_loocv.py`
  完全相同，即归档九指标表所用的协议），用于说明选阶与否不改变任何排序——
  这样 Table 7 的 ARIMA 行标签与正文/Table 6 一致，八指标与九指标之间仍只差
  输入序列这一件事。

────────────────────────────────────────────────────────────────────────────
输出（全部新文件）
────────────────────────────────────────────────────────────────────────────
· data/r32_validation_8ind.csv          八指标主规格（ARIMA 固定 0,1,1）：scheme×model 的 RMSE/MAE+折内最优统计
· data/r32_validation_8ind_vs9.csv     八指标 vs 九指标 同方案同协议并列（含排序是否翻转）
· data/r32_validation_8ind_detail.csv  逐折逐预测点明细（含每折所选 γ / ARIMA 阶）
· data/r32_validation_8ind_checks.csv  序列校验、γ 边界解、排序判定等关键读数
· data/r32_validation_8ind_arima_aic.csv  ARIMA 阶数折内 AIC 选择变体（8/9 指标，稳健性）

运行：python run_r32_validation_8ind.py
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
YEARS = np.arange(2005, 2024)
GAMMA_GRID = np.round(np.arange(0.05, 1.96, 0.05), 2)
GAMMA_LO, GAMMA_HI = float(GAMMA_GRID[0]), float(GAMMA_GRID[-1])
ARIMA_ORDERS = [(1, 1, 0), (0, 1, 1), (1, 1, 1), (2, 1, 1), (1, 1, 2), (2, 1, 2), (0, 1, 2)]
ARIMA_FIXED = (0, 1, 1)

MODELS = ["GM(1,1)", "NGBM", "ARIMA"]

SCHEMES = [
    ("holdout_2019_2023", "Holdout 2019-2023 (fit 2005-2018)", 5, [2018]),
    ("rolling_1step_from2013", "Rolling 1-step from 2013", 1, list(range(2013, 2023))),
    ("rolling_1step_from2015", "Rolling 1-step from 2015", 1, list(range(2015, 2023))),
    ("rolling_5step_from2013", "Rolling 5-step from 2013", 5, list(range(2013, 2019))),
    ("loocv_leave_one_year_out", "Leave-one-year-out (19 folds)", 1, list(YEARS)),
]

OUT_MAIN = os.path.join(DATA, "r32_validation_8ind.csv")
OUT_VS9 = os.path.join(DATA, "r32_validation_8ind_vs9.csv")
OUT_DETAIL = os.path.join(DATA, "r32_validation_8ind_detail.csv")
OUT_CHECKS = os.path.join(DATA, "r32_validation_8ind_checks.csv")
OUT_ARFIX = os.path.join(DATA, "r32_validation_8ind_arima_aic.csv")

CHECKS = []


def addcheck(item, value, note):
    CHECKS.append({"item": item, "value": value, "note": note})


# ---------------------------------------------------------------------------
# 序列：八指标主规格 + 九指标对照
# ---------------------------------------------------------------------------
def build_series():
    r8 = C.compute(C.DEREDUNDANT_SETS["drop_X9"])
    r9 = C.compute(C.DEREDUNDANT_SETS["baseline9"])
    esi8 = np.asarray(r8["esi"], float)
    esi9 = np.asarray(r9["esi"], float)
    y8 = [int(v) for v in r8["years"]]
    y9 = [int(v) for v in r9["years"]]
    assert y8 == list(YEARS) and y9 == list(YEARS), "year coverage mismatch"
    arch = pd.read_csv(os.path.join(DATA, "r28_deredundancy_series.csv"))
    d8 = float(np.abs(esi8 - arch["esi_drop_X9"].values).max())
    d9 = float(np.abs(esi9 - arch["esi_baseline9"].values).max())
    am = pd.read_csv(os.path.join(DATA, "r28_alpha_grade_matrix.csv"), dtype={"year": str})
    am = am[(am.scenario == "drop_X9") & (np.isclose(am.alpha.astype(float), ALPHA))]
    am = am[am.year.str.match(r"^\d{4}$")].copy()
    am["year"] = am.year.astype(int)
    am = am.sort_values("year")
    da = float(np.abs(am["esi"].values - arch["esi_drop_X9"].values).max())
    return esi8, esi9, dict(esi_8ind_vs_archive_max_abs_delta=d8,
                            esi_9ind_vs_archive_max_abs_delta=d9,
                            esi_8ind_vs_alpha_matrix_max_abs_delta=da)


# ---------------------------------------------------------------------------
# 模型
# ---------------------------------------------------------------------------
def ngbm(x0, gamma, n_pred=1):
    """Compatibility helper using the corrected consecutive-index estimator."""
    from forecast_models import ngbm as canonical_ngbm
    result = canonical_ngbm(x0, gamma, n_pred)
    return result[:2]


def ngbm_try(x0, gamma, n_pred=1):
    try:
        fut, xh = ngbm(x0, gamma, n_pred)
    except Exception:
        return None
    if fut is None or xh is None:
        return None
    if not np.all(np.isfinite(fut)) or not np.all(np.isfinite(xh)):
        return None
    return fut, xh


def pick_gamma(x0):
    """只在 x0 上按 SSE 选 γ。返回 (sse, gamma)；γ 未找到则 None。"""
    best = None
    for g in GAMMA_GRID:
        r = ngbm_try(x0, g, n_pred=1)
        if r is None:
            continue
        sse = float(np.sum((np.asarray(x0, float)[1:] - r[1][1:]) ** 2))
        if best is None or sse < best[0]:
            best = (sse, float(g))
    return best


def gamma_note(g):
    if g is None:
        return "gamma=none"
    if abs(g - GAMMA_LO) < 1e-9:
        return "gamma=%.2f (AT GRID LOWER BOUND 0.05)" % g
    if abs(g - GAMMA_HI) < 1e-9:
        return "gamma=%.2f (AT GRID UPPER BOUND 1.95)" % g
    return "gamma=%.2f" % g


def pick_arima_order(x0):
    from statsmodels.tsa.arima.model import ARIMA
    best = None
    for order in ARIMA_ORDERS:
        try:
            m = ARIMA(np.asarray(x0, float), order=order).fit()
        except Exception:
            continue
        if best is None or float(m.aic) < best[0]:
            best = (float(m.aic), order)
    return best


def forecast_arima(x0, order, n_pred=1):
    from statsmodels.tsa.arima.model import ARIMA
    m = ARIMA(np.asarray(x0, float), order=order).fit()
    return np.asarray(m.forecast(n_pred), dtype=float)


def forecast_three(x_train, n_pred, arima_mode="aic"):
    """返回 {model: (preds, hyper_info, extras)}；超参数只用 x_train 选择。"""
    out = {}
    fut, _, _, _ = gm11_forecast(np.asarray(x_train, float), n_pred=n_pred)
    out["GM(1,1)"] = (np.asarray(fut, float), "hyper=none",
                      {"gamma": np.nan, "gamma_at_bound": False, "arima_order": ""})
    bg = pick_gamma(x_train)
    if bg is None:
        out["NGBM"] = (np.full(n_pred, np.nan), "gamma=none",
                       {"gamma": np.nan, "gamma_at_bound": False, "arima_order": ""})
    else:
        r = ngbm_try(x_train, bg[1], n_pred=n_pred)
        atb = bool(abs(bg[1] - GAMMA_LO) < 1e-9 or abs(bg[1] - GAMMA_HI) < 1e-9)
        out["NGBM"] = (np.asarray(r[0], float),
                       "%s (train SSE=%.6f)" % (gamma_note(bg[1]), bg[0]),
                       {"gamma": bg[1], "gamma_at_bound": atb, "arima_order": ""})
    if arima_mode == "aic":
        ba = pick_arima_order(x_train)
        if ba is None:
            out["ARIMA"] = (np.full(n_pred, np.nan), "order=none",
                            {"gamma": np.nan, "gamma_at_bound": False, "arima_order": ""})
        else:
            out["ARIMA"] = (forecast_arima(x_train, ba[1], n_pred=n_pred),
                            "order=%s (train AIC=%.2f)" % (ba[1], ba[0]),
                            {"gamma": np.nan, "gamma_at_bound": False,
                             "arima_order": str(ba[1])})
    else:
        out["ARIMA"] = (forecast_arima(x_train, ARIMA_FIXED, n_pred=n_pred),
                        "order=(0, 1, 1) fixed",
                        {"gamma": np.nan, "gamma_at_bound": False,
                         "arima_order": str(ARIMA_FIXED)})
    return out


# ---------------------------------------------------------------------------
# 展布五种方案
# ---------------------------------------------------------------------------
def run_schemes(esi, tag, arima_mode="aic"):
    """返回逐折逐点明细 DataFrame。esi 是 19 年序列。"""
    idx = {int(y): i for i, y in enumerate(YEARS)}
    rows = []

    def emit(scheme, fold, horizon, train_window, target_year, model, hyper, extras,
             pred, obs):
        pv = float(pred) if np.isfinite(pred) else np.nan
        rows.append({
            "series": tag, "arima_protocol": arima_mode,
            "scheme": scheme, "fold": str(fold), "horizon": horizon,
            "train_window": train_window, "target_year": int(target_year), "model": model,
            "hyper": hyper, "gamma": extras["gamma"], "gamma_at_grid_bound": extras["gamma_at_bound"],
            "arima_order": extras["arima_order"],
            "observed": round(float(obs), 6), "predicted": round(pv, 6),
            "err": (round(pv - float(obs), 6) if np.isfinite(pv) else np.nan),
            "abs_err": (round(abs(pv - float(obs)), 6) if np.isfinite(pv) else np.nan),
        })

    # --- 1) holdout：origin 2018，评估 2019-2023 ---
    i_end = idx[2018]
    x_train = esi[:i_end + 1]
    targets = [2019, 2020, 2021, 2022, 2023]
    fc = forecast_three(x_train, len(targets), arima_mode)
    for m, (preds, hyper, extras) in fc.items():
        for h, ty in enumerate(targets, start=1):
            emit("holdout_2019_2023", "holdout_2018", h, "2005-2018", ty, m, hyper,
                 extras, preds[h - 1], esi[idx[ty]])

    # --- 2/3/4) rolling-origin（含 5 步）---
    for scheme, _label, horizon, origins in SCHEMES:
        if not scheme.startswith("rolling"):
            continue
        for origin in origins:
            i_o = idx[origin]
            x_tr = esi[:i_o + 1]
            tg = [origin + h for h in range(1, horizon + 1) if (origin + h) in idx]
            fc = forecast_three(x_tr, len(tg), arima_mode)
            for m, (preds, hyper, extras) in fc.items():
                for h, ty in enumerate(tg, start=1):
                    emit(scheme, origin, h, "2005-%d" % origin, ty, m, hyper, extras,
                         preds[h - 1], esi[idx[ty]])

    # --- 5) LOOCV ---
    for ty in YEARS:
        mask = YEARS != ty
        x_tr = esi[mask]
        fc = forecast_three(x_tr, 1, arima_mode)
        for m, (preds, hyper, extras) in fc.items():
            emit("loocv_leave_one_year_out", "holdout_%d" % ty, 1,
                 "%d years (all except %d)" % (int(mask.sum()), ty), ty, m, hyper, extras,
                 preds[0], esi[idx[int(ty)]])
    return pd.DataFrame(rows)


def summarize(detail, tag, scheme, protocol="fixed"):
    d = detail[(detail.series == tag) & (detail.scheme == scheme)
               & (detail.arima_protocol == protocol)]
    folds = sorted(d.fold.unique())
    fold_best = {}
    for f in folds:
        sub = d[(d.fold == f) & d.abs_err.notna()]
        if len(sub) == 0:
            continue
        r = {m: float(np.sqrt(np.mean(g.err.values ** 2)))
             for m, g in sub.groupby("model")}
        fold_best[f] = min(r, key=r.get)
    out = []
    for m in MODELS:
        sub = d[(d.model == m) & d.abs_err.notna()]
        if len(sub) == 0:
            continue
        e = sub.err.values
        rmse = float(np.sqrt(np.mean(e ** 2)))
        mae = float(np.mean(np.abs(e)))
        nb = int(sum(1 for f in fold_best if fold_best[f] == m))
        gam = sub.gamma.dropna().unique()
        orders = sub.arima_order[sub.arima_order != ""].unique()
        atb = int(sub.gamma_at_grid_bound.sum())
        out.append({
            "series": tag, "scheme": scheme, "model": m,
            "n_folds": int(sub.fold.nunique()), "n_predictions": int(len(sub)),
            "rmse": round(rmse, 6), "mae": round(mae, 6),
            "n_folds_best": nb,
            "best_fold_share": round(nb / max(len(fold_best), 1), 4),
            "gamma_values_used": (", ".join("%.2f" % g for g in np.sort(gam))
                                  if len(gam) else ""),
            "n_gamma_at_grid_bound": atb,
            "arima_orders_used": (", ".join(orders) if len(orders) else ""),
        })
    o = pd.DataFrame(out)
    o["rmse_rank"] = o["rmse"].rank(method="min").astype(int)
    return o


# ---------------------------------------------------------------------------
def main():
    print("=" * 78)
    print("R32b · Table 7 五方案在八指标主规格 ESI 上的重算（折内独立选参）")
    print("=" * 78)
    esi8, esi9, ver = build_series()
    print("[校验] 八指标 ESI  vs r28_deredundancy_series.csv esi_drop_X9   max|Δ| = %.3e"
          % ver["esi_8ind_vs_archive_max_abs_delta"])
    print("[校验] 九指标 ESI  vs 同归档 esi_baseline9                     max|Δ| = %.3e"
          % ver["esi_9ind_vs_archive_max_abs_delta"])
    print("[校验] 八指标 ESI  vs r28_alpha_grade_matrix.csv (drop_X9,0.4) max|Δ| = %.3e"
          % ver["esi_8ind_vs_alpha_matrix_max_abs_delta"])
    print("       年份 2005-2023（19 年）；8 指标 ESI 2010 峰值 %.6f，2023 %.6f"
          % (float(esi8.max()), float(esi8[-1])))
    for k, v in ver.items():
        addcheck(k, float("%.3e" % v), "序列真源一致性校验（八/九指标 ESI）")

    # ---------------- 主口径：ARIMA 阶数固定 (0,1,1) ----------------
    #   变体：阶数在训练子集上按 AIC 选择（= 归档九指标表所用协议）
    det8f = run_schemes(esi8, "eight", "fixed")
    det9f = run_schemes(esi9, "nine", "fixed")
    det8a = run_schemes(esi8, "eight", "aic")
    det9a = run_schemes(esi9, "nine", "aic")
    detail = pd.concat([det8f, det9f, det8a, det9a], ignore_index=True)
    detail.to_csv(OUT_DETAIL, index=False, encoding="utf-8-sig")
    print("\n明细已写出：data/r32_validation_8ind_detail.csv（%d 行）" % len(detail))

    schemes = [s[0] for s in SCHEMES]
    s8 = pd.concat([summarize(detail, "eight", sc, "fixed") for sc in schemes],
                   ignore_index=True)
    s9 = pd.concat([summarize(detail, "nine", sc, "fixed") for sc in schemes],
                   ignore_index=True)
    s8a = pd.concat([summarize(detail, "eight", sc, "aic") for sc in schemes],
                    ignore_index=True)
    s9a = pd.concat([summarize(detail, "nine", sc, "aic") for sc in schemes],
                    ignore_index=True)

    # ---- 主 CSV：八指标 ----
    label = {s[0]: s[1] for s in SCHEMES}
    main = s8.copy()
    main.insert(2, "scheme_label", main.scheme.map(label))
    main["best"] = (main.rmse_rank == 1)
    main["note"] = [
        ("八指标主规格（drop_X9）ESI 序列；ARIMA 阶数固定 (0,1,1)（阶数不由数据选择）；%s；"
         "RMSE/MAE 为该方案全部评估点的池化值；折内最优次数 = 逐折 RMSE 最低的次数"
         % ("NGBM 的 γ 只用该折训练子集选择"
            if r.model != "GM(1,1)" else "GM(1,1) 无超参数"))
        + ("；γ 命中网格边界 %d 折（如实记录）" % r.n_gamma_at_grid_bound
           if r.n_gamma_at_grid_bound else "")
        + ("；该方案所用 γ = %s" % r.gamma_values_used if r.gamma_values_used else "")
        for _, r in main.iterrows()]
    main = main[["scheme", "scheme_label", "n_folds", "n_predictions", "model",
                 "rmse", "mae", "rmse_rank", "best", "n_folds_best", "best_fold_share",
                 "gamma_values_used", "n_gamma_at_grid_bound", "note"]]
    main.to_csv(OUT_MAIN, index=False, encoding="utf-8-sig")

    # ---- vs9 CSV（同协议：ARIMA 固定 (0,1,1)；另附折内 AIC 选阶变体列）----
    m = s8.merge(s9, on=["scheme", "model"], suffixes=("_8ind", "_9ind"))
    m = m.merge(
        s8a[["scheme", "model", "rmse", "rmse_rank"]]
        .rename(columns={"rmse": "rmse_8ind_arima_aic", "rmse_rank": "rmse_rank_8ind_arima_aic"}),
        on=["scheme", "model"]).merge(
        s9a[["scheme", "model", "rmse", "rmse_rank"]]
        .rename(columns={"rmse": "rmse_9ind_arima_aic", "rmse_rank": "rmse_rank_9ind_arima_aic"}),
        on=["scheme", "model"])
    m = m[["scheme", "model", "n_folds_8ind", "n_predictions_8ind",
           "rmse_8ind", "mae_8ind", "rmse_rank_8ind",
           "rmse_9ind", "mae_9ind", "rmse_rank_9ind",
           "rmse_8ind_arima_aic", "rmse_rank_8ind_arima_aic",
           "rmse_9ind_arima_aic", "rmse_rank_9ind_arima_aic",
           "gamma_values_used_8ind", "gamma_values_used_9ind"]]
    m["arima_protocol"] = "ARIMA order fixed at (0,1,1); *_arima_aic columns = order re-selected by AIC inside each training window"
    m["delta_rmse_8ind_minus_9ind"] = (m.rmse_8ind - m.rmse_9ind).round(6)
    m["delta_mae_8ind_minus_9ind"] = (m.mae_8ind - m.mae_9ind).round(6)
    m["rank_same"] = (m.rmse_rank_8ind == m.rmse_rank_9ind)
    best8 = m.loc[m.groupby("scheme").rmse_8ind.idxmin()].set_index("scheme").model
    best9 = m.loc[m.groupby("scheme").rmse_9ind.idxmin()].set_index("scheme").model
    m["scheme_best_8ind"] = m.scheme.map(best8)
    m["scheme_best_9ind"] = m.scheme.map(best9)
    m["scheme_best_flipped"] = m.scheme.map(lambda s: best8[s] != best9[s])
    m.to_csv(OUT_VS9, index=False, encoding="utf-8-sig")

    # ---- ARIMA 阶数折内 AIC 选择变体（稳健性）----
    af = pd.concat([s8a, s9a], ignore_index=True)
    af["arima_protocol"] = "order re-selected by AIC inside each training window"
    af["series_label"] = af.series.map({"eight": "eight-indicator (drop_X9)",
                                        "nine": "nine-indicator (baseline9)"})
    af = af[["arima_protocol", "series", "series_label", "scheme", "model", "n_folds",
             "n_predictions", "rmse", "mae", "rmse_rank", "n_folds_best",
             "gamma_values_used", "n_gamma_at_grid_bound", "arima_orders_used"]]
    af.to_csv(OUT_ARFIX, index=False, encoding="utf-8-sig")

    # ---------------- 打印 ----------------
    def show(df, tag, title):
        print("\n" + "-" * 78)
        print("%s —— %s（池化 RMSE / MAE）" % (title, tag))
        print("-" * 78)
        d = df[df.series == tag].copy()
        piv = d.pivot_table(index="model", columns="scheme", values=["rmse", "mae"])
        for sc in schemes:
            sub = d[d.scheme == sc].sort_values("rmse")
            print("   %-26s " % sc
                  + " | ".join("%s RMSE=%.4f MAE=%.4f%s"
                               % (r.model, r.rmse, r.mae, "*" if r.rmse_rank == 1 else "")
                               for _, r in sub.iterrows()))

    show(s8, "eight", "八指标主规格（drop_X9）")
    show(s9, "nine", "[对照] 九指标（baseline9）")

    print("\n" + "=" * 78)
    print("八指标 vs 九指标：逐模型 RMSE 与排名")
    print("=" * 78)
    print(m[["scheme", "model", "rmse_8ind", "mae_8ind", "rmse_rank_8ind",
             "rmse_9ind", "mae_9ind", "rmse_rank_9ind",
             "delta_rmse_8ind_minus_9ind", "rank_same"]].to_string(index=False))

    print("\n" + "-" * 78)
    print("每方案最优模型：八指标 vs 九指标")
    print("-" * 78)
    flipped = []
    for sc in schemes:
        b8, b9 = best8[sc], best9[sc]
        if b8 != b9:
            flipped.append((sc, b8, b9))
        print("   %-26s 八指标=%-9s 九指标=%-9s %s"
              % (sc, b8, b9, "<== 翻转" if b8 != b9 else ""))
    addcheck("n_schemes_with_flipped_best_model", len(flipped),
             "八指标与九指标下「该方案 RMSE 最低的模型」不同的方案数")
    addcheck("schemes_with_flipped_best_model",
             "; ".join("%s: %s -> %s" % f for f in flipped) if flipped else "none",
             "发生翻转的方案（八指标 -> 九指标）")

    # γ 与边界解
    print("\n" + "-" * 78)
    print("NGBM γ 的逐折取值与网格边界解")
    print("-" * 78)
    gd = detail[(detail.model == "NGBM") & detail.gamma.notna()
                & (detail.arima_protocol == "fixed")]
    for tag in ("eight", "nine"):
        for sc in schemes:
            sub = gd[(gd.series == tag) & (gd.scheme == sc)]
            if len(sub) == 0:
                continue
            per_fold = sub.groupby("fold").agg(
                gamma=("gamma", "first"), atb=("gamma_at_grid_bound", "first"))
            nb = int(per_fold.atb.sum())
            uniq = sorted(set(np.round(per_fold.gamma.values, 2)))
            print("   %-5s %-26s γ 逐折 = %s | 边界解 %d/%d"
                  % (tag, sc, ", ".join("%.2f" % g for g in uniq), nb, len(per_fold)))
    for tag in ("eight", "nine"):
        sub = gd[(gd.series == tag) & (gd.scheme == "loocv_leave_one_year_out")]
        addcheck("gamma_most_common_%sind_loocv" % ("8" if tag == "eight" else "9"),
                 float(sub.gamma.mode().iloc[0]) if len(sub) else np.nan,
                 "LOOCV 折内最常被选中的 γ（%s指标）" % ("八" if tag == "eight" else "九"))
    nbf = {t: int(gd[(gd.series == t)].groupby(["scheme", "fold"])
                  .gamma_at_grid_bound.first().sum()) for t in ("eight", "nine")}
    nb8, nb9 = nbf["eight"], nbf["nine"]
    addcheck("n_folds_gamma_at_grid_bound_8ind", nb8,
             "八指标下 γ 命中网格边界（0.05 或 1.95）的折数（跨全部方案计）")
    addcheck("n_folds_gamma_at_grid_bound_9ind", nb9,
             "九指标下同一计数（对照）")

    # 与归档九指标结果的交叉校验
    print("\n" + "-" * 78)
    print("交叉校验：本脚本九指标重算（折内 AIC 选阶，= 归档协议）vs 归档 R28 CSV")
    print("-" * 78)
    try:
        arch = pd.read_csv(os.path.join(DATA, "r28_rolling_origin.csv"))
        maxd = 0.0
        for sc in ["rolling_1step_from2013", "rolling_1step_from2015",
                   "rolling_5step_from2013"]:
            for _, r in s9a[s9a.scheme == sc].iterrows():
                a = arch[(arch.scheme == sc) & (arch.model == r.model)]
                if len(a):
                    print("   %-24s %-9s 本脚本 %.6f  归档 %.6f  Δ=%+.2e"
                          % (sc, r.model, r.rmse, a.rmse.iloc[0],
                             r.rmse - a.rmse.iloc[0]))
                    maxd = max(maxd, abs(r.rmse - float(a.rmse.iloc[0])))
        lo = pd.read_csv(os.path.join(DATA, "r28_loocv.csv"))
        for _, r in s9a[s9a.scheme == "loocv_leave_one_year_out"].iterrows():
            a = lo[lo.model == r.model]
            if len(a):
                print("   %-24s %-9s 本脚本 %.6f  归档 %.6f  Δ=%+.2e"
                      % ("loocv", r.model, r.rmse, a.rmse.iloc[0],
                         r.rmse - a.rmse.iloc[0]))
                maxd = max(maxd, abs(r.rmse - float(a.rmse.iloc[0])))
        addcheck("nine_ind_rerun_vs_archive_max_abs_rmse_delta", float("%.2e" % maxd),
                 "九指标路径重算（ARIMA 折内 AIC 选阶）与归档 data/r28_rolling_origin.csv / "
                 "r28_loocv.csv 的最大 RMSE 偏差（归档 CSV 仅存 6 位小数）——"
                 "用于证明八/九指标之差只来自输入序列")
    except Exception as exc:  # pragma: no cover
        print("   交叉校验跳过：%s" % exc)

    # ARIMA 选阶变体摘要（稳健性）
    print("\n" + "-" * 78)
    print("ARIMA 阶数折内 AIC 选择变体（稳健性；主口径为固定 (0,1,1)）")
    print("-" * 78)
    for tag in ("eight", "nine"):
        for sc in schemes:
            sub = af[(af.series == tag) & (af.scheme == sc)].sort_values("rmse")
            print("   %-5s %-26s " % (tag, sc)
                  + " | ".join("%s %.6f" % (r.model, r.rmse) for _, r in sub.iterrows()))
    for sc in schemes:
        b_fixed = s8[s8.scheme == sc].sort_values("rmse").iloc[0].model
        b_aic = s8a[s8a.scheme == sc].sort_values("rmse").iloc[0].model
        addcheck("arima_protocol_best_model_%s" % sc,
                 "%s | %s" % (b_fixed, b_aic),
                 "该方案最优模型（八指标）：ARIMA 固定 (0,1,1) | ARIMA 折内 AIC 选阶")
    # 主口径与变体的逐模型 RMSE 最大偏差
    dd = s8[["scheme", "model", "rmse"]].merge(
        s8a[["scheme", "model", "rmse"]], on=["scheme", "model"],
        suffixes=("_fixed", "_aic"))
    addcheck("arima_protocol_max_abs_rmse_delta_8ind",
             float("%.2e" % np.abs(dd.rmse_fixed - dd.rmse_aic).max()),
             "八指标下 ARIMA 固定 (0,1,1) 与折内 AIC 选阶两条协议之间，"
             "逐 方案×模型 RMSE 的最大绝对偏差")

    pd.DataFrame(CHECKS).to_csv(OUT_CHECKS, index=False, encoding="utf-8-sig")
    print("\n已写出：")
    for p in (OUT_MAIN, OUT_VS9, OUT_DETAIL, OUT_ARFIX, OUT_CHECKS):
        print("        data/%s" % os.path.basename(p))
    return 0


if __name__ == "__main__":
    raise SystemExit("Historical round script. Current estimator, validation and bootstrap: "
                     "python run_r47_revision.py --stage all --bootstrap 2000")
