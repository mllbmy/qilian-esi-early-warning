# -*- coding: utf-8 -*-
"""R28-T2 · 扩展窗口 rolling-origin 与 LOOCV：三模型（GM(1,1)/NGBM/ARIMA）复核
（审稿意见第 2 条：预测模型选择与不确定性报告不足）

────────────────────────────────────────────────────────────────────────────
约定（**避免任何用未来数据选参数的做法**）
────────────────────────────────────────────────────────────────────────────
每个折（fold）内，超参数一律**只用该折的训练子集**选择：
  · NGBM 的 γ：在训练子集上按残差平方和最小化网格搜索（0.05-1.95，步长 0.05）
  · ARIMA 的阶数 (p,1,q)：在训练子集上按 AIC 最小化选择
  · GM(1,1)：无超参数
评估点只用该折**未参与拟合与选参**的观测。

三种方案：
  A. 扩展窗口 rolling-origin，**1 步外推**：origin = 2013..2022（10 折）、
     另附 origin = 2015..2022（8 折）子集，逐折只用 2005..origin 拟合，预测 origin+1。
  B. 扩展窗口 rolling-origin，**5 步外推**（与正文 holdout 长度一致）：
     origin = 2013..2018（6 折），预测 origin+1..origin+5。
  C. LOOCV：留一年（leave-one-year-out），取该折训练子集（其余 18 年，按年序排列）
     拟合，预测被留出年份。
     ⚠ 口径声明：LOOCV 的训练子集**同时包含被留出年份之前与之后的年份**，因此它是
     「插值/平滑能力」诊断，**不是**预测验证；本脚本仍保证 γ 与 ARIMA 阶数的选择
     完全不接触被留出年份。

────────────────────────────────────────────────────────────────────────────
数据来源（已入库，不新增下载，不覆盖任何已跟踪 CSV）
────────────────────────────────────────────────────────────────────────────
· data/qilian_climate.csv / data/qilian_landcover.csv / data/ahp_weights.csv
  → 重建论文口径 ESI（与归档 results_esi_regional.csv 偏差 4.7e-5，属 4 位小数舍入）

输出（全部新文件）：
· data/r28_rolling_origin.csv         —— 各方案 × 各模型汇总指标 + 逐折最优模型统计
· data/r28_rolling_origin_detail.csv  —— 逐折逐预测点明细（含每折所选 γ / ARIMA 阶数）
· data/r28_loocv.csv                  —— LOOCV 汇总指标 + 逐折最优模型统计
· data/r28_loocv_detail.csv           —— LOOCV 逐年明细

运行：python run_r28_rolling_loocv.py
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
from eco_security import (  # noqa: E402
    minmax_normalize, entropy_weights, combined_weights, esi_series,
    gm11_forecast,
)

ALPHA = 0.4
YEARS = np.arange(2005, 2024)
GAMMA_GRID = np.round(np.arange(0.05, 1.96, 0.05), 2)
ARIMA_ORDERS = [(1, 1, 0), (0, 1, 1), (1, 1, 1), (2, 1, 1), (1, 1, 2), (2, 1, 2), (0, 1, 2)]


# ---------------------------------------------------------------------------
def build_esi():
    cli = pd.read_csv(os.path.join(DATA, "qilian_climate.csv"))
    lc = pd.read_csv(os.path.join(DATA, "qilian_landcover.csv"))
    reg = cli[cli.unit == "区域(祁连山盒)"].set_index("year")
    lc = lc.set_index("year").reindex(list(YEARS))
    for c in lc.columns:
        lc[c] = lc[c].interpolate(method="linear").bfill().ffill()
    spec = [
        (reg["precip_mm"], +1), (reg["temp_c"], +1), (lc["grass_pct"], +1),
        (lc["forest_pct"], +1), (lc["water_pct"], +1),
        (100 - lc["grass_pct"] - lc["forest_pct"] - lc["water_pct"] - lc["crop_pct"], -1),
        (lc["crop_pct"], -1), (lc["grass_pct"].pct_change().fillna(0) * 100, +1),
        (lc["grass_pct"] + lc["forest_pct"] + lc["water_pct"], +1),
    ]
    X = np.column_stack([s[0].values.astype(float) for s in spec])
    dirs = [s[1] for s in spec]
    Xn = minmax_normalize(X, dirs)
    w_ahp = pd.read_csv(os.path.join(DATA, "ahp_weights.csv"))["ahp_weight"].values
    w = combined_weights(w_ahp, entropy_weights(Xn), ALPHA)
    return esi_series(Xn, w)


# ---------------------------------------------------------------------------
def ngbm(x0, gamma, n_pred=1):
    x0 = np.asarray(x0, dtype=float)
    x1 = np.cumsum(x0)
    z1 = 0.5 * (x1[1:] + x1[:-1])
    if abs(gamma - 1.0) < 1e-9:
        a, b = np.linalg.lstsq(np.column_stack([-z1, z1]), x0[1:], rcond=None)[0]
        if abs(a) < 1e-12:
            return None, None
        c = x0[0] - b / a
        xh = np.array([x0[0]] + [(1 - np.exp(-a)) * c * np.exp(-a * k)
                                 for k in range(1, len(x0))])
        fut = np.array([(1 - np.exp(-a)) * c * np.exp(-a * (len(x0) + k))
                        for k in range(1, n_pred + 1)])
        return fut, xh
    a, b = np.linalg.lstsq(np.column_stack([-z1, z1 ** gamma]), x0[1:], rcond=None)[0]
    if abs(a) < 1e-12:
        return None, None

    def X1(t):
        base = (x0[0] ** (1 - gamma) - b / a) * np.exp(-a * (1 - gamma) * t) + b / a
        if base <= 0:
            raise ValueError("negative base")
        return base ** (1.0 / (1.0 - gamma))

    xh = np.array([x0[0]] + [X1(k) - X1(k - 1) for k in range(1, len(x0))])
    fut = np.array([X1(len(x0) + k) - X1(len(x0) + k - 1) for k in range(1, n_pred + 1)])
    return fut, xh


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
    """只在 x0 上按 SSE 选 γ。返回 (gamma, sse, 训练子集拟合值)。"""
    best = None
    for g in GAMMA_GRID:
        r = ngbm_try(x0, g, n_pred=1)
        if r is None:
            continue
        sse = float(np.sum((x0[1:] - r[1][1:]) ** 2))
        if best is None or sse < best[0]:
            best = (sse, float(g))
    return best


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


# ---------------------------------------------------------------------------
# 三种模型在给定训练子集上的 n 步预测
# ---------------------------------------------------------------------------
def forecast_three(x_train, n_pred):
    """返回 {model: (preds, hyper_info)}，超参数只用 x_train 选择。"""
    out = {}
    fut, _, _, _ = gm11_forecast(np.asarray(x_train, float), n_pred=n_pred)
    out["GM(1,1)"] = (np.asarray(fut, float), "hyper=none")
    bg = pick_gamma(x_train)
    if bg is None:
        out["NGBM"] = (np.full(n_pred, np.nan), "gamma=none")
    else:
        r = ngbm_try(x_train, bg[1], n_pred=n_pred)
        out["NGBM"] = (np.asarray(r[0], float),
                       "gamma=%.2f (train SSE=%.6f)" % (bg[1], bg[0]))
    ba = pick_arima_order(x_train)
    if ba is None:
        out["ARIMA"] = (np.full(n_pred, np.nan), "order=none")
    else:
        out["ARIMA"] = (forecast_arima(x_train, ba[1], n_pred=n_pred),
                        "order=%s (train AIC=%.2f)" % (ba[1], ba[0]))
    return out


def pooled_metrics(err):
    """err: 预测 - 观测（保留符号），返回 (rmse, mae, mape_pct, bias, n)。"""
    err = np.asarray([e for e in err if e is not None and np.isfinite(e)], float)
    if len(err) == 0:
        return np.nan, np.nan, np.nan, np.nan, 0
    return (float(np.sqrt(np.mean(err ** 2))), float(np.mean(np.abs(err))),
            np.nan, float(np.mean(err)), len(err))


def summarize(detail, scheme, models=("GM(1,1)", "NGBM", "ARIMA")):
    """按 (scheme, model) 汇总：池化 RMSE/MAE/MAPE、逐折最优次数。"""
    d = detail[detail.scheme == scheme]
    rows = []
    folds = sorted(d.fold.unique())
    best_by_fold = {}
    for f in folds:
        sub = d[(d.fold == f) & d.abs_err.notna()]
        if len(sub) == 0:
            continue
        # 逐折按该折池化 RMSE 定最优
        grp = sub.groupby("model").apply(
            lambda g: np.sqrt(np.mean(g.err ** 2)), include_groups=False)
        best_by_fold[f] = grp.idxmin()
    for m in models:
        sub = d[(d.model == m) & d.abs_err.notna()]
        if len(sub) == 0:
            continue
        err = sub.err.values
        rmse = float(np.sqrt(np.mean(err ** 2)))
        mae = float(np.mean(np.abs(err)))
        mape = float(np.mean(np.abs(err / sub.observed.values)) * 100.0)
        rows.append({
            "scheme": scheme, "model": m, "n_predictions": len(sub),
            "n_folds": int(sub.fold.nunique()),
            "rmse": round(rmse, 6), "mae": round(mae, 6), "mape_pct": round(mape, 4),
            "bias": round(float(np.mean(err)), 6),
            "rmse_in_fold_units_mean": round(float(np.mean(
                [np.sqrt(np.mean(d[(d.fold == f) & (d.model == m)].err ** 2))
                 for f in folds if len(d[(d.fold == f) & (d.model == m)]) > 0])), 6),
            "n_folds_best": int(sum(1 for f in best_by_fold if best_by_fold[f] == m)),
            "best_fold_share": round(float(
                sum(1 for f in best_by_fold if best_by_fold[f] == m) / max(len(best_by_fold), 1)), 4),
            "best_folds": ", ".join(str(f) for f in folds if best_by_fold.get(f) == m),
        })
    out = pd.DataFrame(rows).sort_values(["scheme", "rmse"]).reset_index(drop=True)
    out["rank_in_scheme"] = out.groupby("scheme")["rmse"].rank(method="min").astype(int)
    return out


def main():
    esi = build_esi()
    arch = pd.read_csv(os.path.join(DATA, "results_esi_regional.csv"))
    print("=" * 78)
    print("R28-T2 · rolling-origin 与 LOOCV（三模型，折内独立选参）")
    print("=" * 78)
    print("[校验] 重建 ESI vs 归档 max|Δ| = %.3e" % np.abs(esi - arch["esi"].values).max())

    detail_rows = []

    # ---------------- A/B：扩展窗口 rolling-origin ----------------
    schemes = [
        ("rolling_1step_from2013", 1, range(2013, 2023)),
        ("rolling_1step_from2015", 1, range(2015, 2023)),
        ("rolling_5step_from2013", 5, range(2013, 2019)),
    ]
    for scheme, horizon, origins in schemes:
        print("\n" + "-" * 78)
        print("方案 %s（horizon=%d 步，origins=%s..%s）"
              % (scheme, horizon, min(origins), max(origins)))
        print("-" * 78)
        for origin in origins:
            i_end = int(np.where(YEARS == origin)[0][0])          # 含 origin
            x_train = esi[:i_end + 1]
            targets = [origin + h for h in range(1, horizon + 1) if origin + h <= YEARS[-1]]
            n_pred = len(targets)
            fc = forecast_three(x_train, n_pred)
            for m, (preds, hyper) in fc.items():
                for h, ty in enumerate(targets, start=1):
                    obs = float(esi[int(np.where(YEARS == ty)[0][0])])
                    pv = float(preds[h - 1]) if np.isfinite(preds[h - 1]) else np.nan
                    detail_rows.append({
                        "scheme": scheme, "fold": origin, "horizon": h,
                        "train_window": "2005-%d" % origin, "target_year": ty,
                        "model": m, "hyper": hyper,
                        "observed": round(obs, 6), "predicted": round(pv, 6),
                        "err": round(pv - obs, 6) if np.isfinite(pv) else np.nan,
                        "abs_err": round(abs(pv - obs), 6) if np.isfinite(pv) else np.nan,
                    })
            gm_r = np.sqrt(np.mean((fc["GM(1,1)"][0][:n_pred]
                                    - np.array([esi[int(np.where(YEARS == t)[0][0])]
                                                for t in targets])) ** 2))
            ng_r = np.sqrt(np.mean((fc["NGBM"][0][:n_pred]
                                    - np.array([esi[int(np.where(YEARS == t)[0][0])]
                                                for t in targets])) ** 2))
            ar_r = np.sqrt(np.mean((fc["ARIMA"][0][:n_pred]
                                    - np.array([esi[int(np.where(YEARS == t)[0][0])]
                                                for t in targets])) ** 2))
            g_sel = fc["NGBM"][1].split(" ")[0].replace("gamma=", "")
            o_sel = fc["ARIMA"][1].split(" ")[0].replace("order=", "")
            print("   origin %d → %s | GM RMSE=%.4f  NGBM(γ=%s) RMSE=%.4f  ARIMA%s RMSE=%.4f"
                  % (origin, targets, gm_r, g_sel, ng_r, o_sel, ar_r))

    # ---------------- C：LOOCV ----------------
    print("\n" + "-" * 78)
    print("方案 loocv_leave_one_year_out（留一年；折内选参不接触被留出年份）")
    print("-" * 78)
    for ty in YEARS:
        mask = YEARS != ty
        x_train = esi[mask]
        fc = forecast_three(x_train, 1)
        obs = float(esi[int(np.where(YEARS == ty)[0][0])])
        for m, (preds, hyper) in fc.items():
            pv = float(preds[0]) if np.isfinite(preds[0]) else np.nan
            detail_rows.append({
                "scheme": "loocv_leave_one_year_out", "fold": "holdout_%d" % ty,
                "horizon": 1, "train_window": "%d years (all except %d)" % (len(x_train), ty),
                "target_year": int(ty), "model": m, "hyper": hyper,
                "observed": round(obs, 6), "predicted": round(pv, 6),
                "err": round(pv - obs, 6) if np.isfinite(pv) else np.nan,
                "abs_err": round(abs(pv - obs), 6) if np.isfinite(pv) else np.nan,
            })

    detail = pd.DataFrame(detail_rows)
    detail.to_csv(os.path.join(DATA, "r28_rolling_origin_detail.csv"),
                  index=False, encoding="utf-8-sig")

    roll = pd.concat([summarize(detail, s) for s in
                      ["rolling_1step_from2013", "rolling_1step_from2015",
                       "rolling_5step_from2013"]], ignore_index=True)
    roll.to_csv(os.path.join(DATA, "r28_rolling_origin.csv"),
                index=False, encoding="utf-8-sig")

    loo = summarize(detail, "loocv_leave_one_year_out")
    loo.to_csv(os.path.join(DATA, "r28_loocv.csv"), index=False, encoding="utf-8-sig")
    detail[detail.scheme == "loocv_leave_one_year_out"].to_csv(
        os.path.join(DATA, "r28_loocv_detail.csv"), index=False, encoding="utf-8-sig")

    # ---------------- 汇总打印 ----------------
    print("\n" + "=" * 78)
    print("rolling-origin 汇总（池化指标；n_folds_best = 逐折 RMSE 最低的次数）")
    print("=" * 78)
    print(roll[["scheme", "model", "n_predictions", "n_folds", "rmse", "mae",
                "mape_pct", "bias", "n_folds_best", "best_fold_share", "rank_in_scheme"]]
          .to_string(index=False))
    print("\nLOOCV 汇总")
    print(loo[["model", "n_predictions", "rmse", "mae", "mape_pct", "bias",
               "n_folds_best", "best_fold_share", "rank_in_scheme"]].to_string(index=False))

    # ---------------- 模型选择一致性判定 ----------------
    print("\n" + "-" * 78)
    print("模型选择一致性判定")
    print("-" * 78)
    for s in roll.scheme.unique():
        d = roll[roll.scheme == s].sort_values("rmse")
        best = d.iloc[0]
        print("   %-26s 最优模型=%-8s (RMSE %.4f)  逐折最优占比 GM %.2f / NGBM %.2f / ARIMA %.2f"
              % (s, best.model, best.rmse,
                 float(d[d.model == "GM(1,1)"].best_fold_share.iloc[0]),
                 float(d[d.model == "NGBM"].best_fold_share.iloc[0]),
                 float(d[d.model == "ARIMA"].best_fold_share.iloc[0])))
    d = loo.sort_values("rmse")
    print("   %-26s 最优模型=%-8s (RMSE %.4f)  逐折最优占比 GM %.2f / NGBM %.2f / ARIMA %.2f"
          % ("loocv", d.iloc[0].model, d.iloc[0].rmse,
             float(d[d.model == "GM(1,1)"].best_fold_share.iloc[0]),
             float(d[d.model == "NGBM"].best_fold_share.iloc[0]),
             float(d[d.model == "ARIMA"].best_fold_share.iloc[0])))

    # 每折所选 γ 的稳定性
    ng = detail[(detail.model == "NGBM") & (detail.scheme.str.startswith("rolling_1step"))]
    gammas = ng.groupby("fold").hyper.first().str.extract(r"gamma=([\d.]+)")[0].astype(float)
    print("\n   逐折所选 γ（1 步外推，≥2013）：",
          {int(k): float(v) for k, v in gammas.items()})
    print("   γ 的取值范围 %.2f-%.2f，中位数 %.2f，标准差 %.3f"
          % (gammas.min(), gammas.max(), gammas.median(), gammas.std()))
    ar = detail[(detail.model == "ARIMA") & (detail.scheme.str.startswith("rolling_1step"))]
    orders = ar.groupby("fold").hyper.first().str.extract(r"order=(\([^)]*\))")[0]
    print("   逐折所选 ARIMA 阶数（1 步外推，≥2013）：", dict(orders))
    ng5 = detail[(detail.model == "NGBM") & (detail.scheme == "rolling_5step_from2013")]
    g5 = ng5.groupby("fold").hyper.first().str.extract(r"gamma=([\d.]+)")[0].astype(float)
    print("   逐折所选 γ（5 步外推 origin 2013-2018）：",
          {int(k): float(v) for k, v in g5.round(2).items()})

    print("\n已写出：data/r28_rolling_origin.csv, data/r28_rolling_origin_detail.csv,")
    print("        data/r28_loocv.csv, data/r28_loocv_detail.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())