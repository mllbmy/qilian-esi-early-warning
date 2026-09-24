# -*- coding: utf-8 -*-
"""NGBM / ARIMA 对比预测（补强 GM(1,1) 精度短板）
对真实 ESI 序列（2005-2023）用 GM(1,1)、NGBM(非线性灰色伯努利)、ARIMA 三种模型
做拟合与 5 步预测对比，输出 RMSE/MAE/后验差比值 C/小误差概率 P。
"""
import os
import sys, os
import numpy as np
import pandas as pd
from scipy.stats import t as tdist
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "eco_security"))
from eco_security import gm11_forecast

# 路径自解析：仓库克隆/解压到任意目录均可运行
BASE = os.path.dirname(os.path.abspath(__file__))
esi = pd.read_csv(os.path.join(BASE, "data", "results_esi_regional.csv"))["esi"].values
n = len(esi)
print("真实 ESI 序列:", np.round(esi, 3))

# ---------- 1) GM(1,1) ----------
fut_gm, fit_gm, C_gm, P_gm = gm11_forecast(esi, n_pred=5)

# ---------- 2) NGBM(1,1) 非线性灰色伯努利模型 ----------
def ngbm(x0, gamma, n_pred=5):
    x1 = np.cumsum(x0)
    z1 = 0.5 * (x1[1:] + x1[:-1])
    B = np.column_stack([-z1, z1 ** gamma])
    Y = x0[1:]
    a, b = np.linalg.lstsq(B, Y, rcond=None)[0]
    if abs(a) < 1e-10:
        return None, None, (a, b)  # 退化情况
    x0_hat = np.empty(len(x0))
    x0_hat[0] = x0[0]
    def X1(t):
        return ((x0[0] ** (1 - gamma) - b / a) * np.exp(-a * (1 - gamma) * t) + b / a) ** (1 / (1 - gamma))
    for k in range(1, len(x0)):
        x0_hat[k] = X1(k) - X1(k - 1)
    fut = [X1(len(x0) + k) - X1(len(x0) + k - 1) for k in range(1, n_pred + 1)]
    return np.array(fut), x0_hat, (a, b)

# 网格搜索最优 gamma
best = None
for gamma in np.arange(0.05, 1.96, 0.05):
    try:
        _, fit, _ = ngbm(esi, gamma)
        if fit is None: continue
        sse = np.sum((esi[1:] - fit[1:]) ** 2)
        if best is None or sse < best[0]:
            best = (sse, gamma)
    except Exception:
        continue
_, gamma_opt = best
fut_n, fit_n, params_n = ngbm(esi, gamma_opt)
# NGBM 精度
e = esi - fit_n
S1 = esi.std(ddof=1); S2 = e.std(ddof=1)
C_n = S2 / S1; em = e.mean()
P_n = np.mean(np.abs(e - em) < 0.6745 * S1)

# ---------- 3) ARIMA ----------
from statsmodels.tsa.arima.model import ARIMA
best_aic = None
for p, q in [(1, 0), (0, 1), (1, 1), (2, 1), (1, 2), (2, 2), (0, 2)]:
    try:
        m = ARIMA(esi, order=(p, 1, q)).fit()
        if best_aic is None or m.aic < best_aic[0]:
            best_aic = (m.aic, (p, 1, q), m)
    except Exception:
        pass
aic, order, model = best_aic
fit_a = np.asarray(model.fittedvalues, dtype=float)
fut_a = np.asarray(model.forecast(5), dtype=float)
# 对齐拟合长度
fit_a = np.concatenate([[esi[0]], fit_a[1:]]) if len(fit_a) == n - 1 else fit_a
e2 = esi - fit_a
C_a = e2.std(ddof=1) / S1
P_a = np.mean(np.abs(e2 - e2.mean()) < 0.6745 * S1)

# ---------- 汇总 ----------
def metrics(esi, fit):
    e = esi - fit
    rmse = np.sqrt(np.mean(e ** 2))
    mae = np.mean(np.abs(e))
    return rmse, mae

def grade_of(C, P):
    return "优" if (C < 0.35 and P > 0.95) else ("合格" if (C < 0.50 and P > 0.80) else ("勉强" if (C < 0.65 and P > 0.70) else "不合格"))

print("\n=== 模型对比（2005-2023 拟合）===")
acc_rows = []
for name, fit, C, P in [("GM(1,1)", fit_gm, C_gm, P_gm), ("NGBM", fit_n, C_n, P_n), ("ARIMA", fit_a, C_a, P_a)]:
    rmse, mae = metrics(esi, fit)
    grade = grade_of(C, P)
    print(f"{name:<8} RMSE={rmse:.4f} MAE={mae:.4f} C={C:.4f} P={P:.4f} 等级={grade}")
    acc_rows.append({"model": name, "rmse": round(rmse, 4), "mae": round(mae, 4),
                     "C": round(C, 4), "P": round(P, 4), "grade": grade})
print("\n=== 2024-2028 预测 ===")
print(f"GM(1,1):  {np.round(fut_gm, 4)}")
print(f"NGBM(γ={gamma_opt:.2f}): {np.round(fut_n, 4)}")
print(f"ARIMA({order}): {np.round(fut_a, 4)}")
np.set_printoptions(precision=4, suppress=True)
pd.DataFrame({"year": range(2024, 2029), "gm11": fut_gm, "ngbm": fut_n, "arima": fut_a}).round(4).to_csv(
    os.path.join(BASE, "data", "results_forecast_comparison.csv"), index=False, encoding="utf-8-sig")
print("\n对比结果已保存: results_forecast_comparison.csv")

# ---------- 精度指标落盘（供论文表 3 溯源）----------
pd.DataFrame(acc_rows).to_csv(os.path.join(BASE, "data", "results_forecast_accuracy.csv"),
                              index=False, encoding="utf-8-sig")
print("精度指标已保存: results_forecast_accuracy.csv")

# ---------- 参数化 95% 预测区间（与上面的 NGBM 同一拟合，保证口径一致）----------
resid_n = esi - fit_n
sigma = np.std(resid_n, ddof=2)
tcrit = tdist.ppf(0.975, max(n - 2, 1))
half = tcrit * sigma * np.sqrt(1 + 1 / n)
ci_rows = []
print(f"\n=== NGBM 参数化 95% 预测区间（gamma={gamma_opt:.2f}, sigma={sigma:.4f}, t={tcrit:.3f}, 半宽={half:.4f}）===")
for i, y in enumerate(range(2024, 2029)):
    lo, hi = fut_n[i] - half, fut_n[i] + half
    print(f"  {y}: {fut_n[i]:.4f}  ({lo:.4f} ~ {hi:.4f})")
    ci_rows.append({"year": y, "ngbm": round(fut_n[i], 4), "ci_lo": round(lo, 4), "ci_hi": round(hi, 4)})
pd.DataFrame(ci_rows).to_csv(os.path.join(BASE, "data", "results_forecast_ci.csv"),
                             index=False, encoding="utf-8-sig")
print("预测区间已保存: results_forecast_ci.csv（与 results_forecast_comparison.csv 同源）")
