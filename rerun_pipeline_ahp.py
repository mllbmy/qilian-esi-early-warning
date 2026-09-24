# -*- coding: utf-8 -*-
"""用真实 AHP 权重重跑全管线：权重→ESI→α敏感性→三模型预测→结果CSV 更新"""
import os
import sys, os
import numpy as np
import pandas as pd

# 路径自解析：仓库克隆/解压到任意目录均可运行
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "eco_security"))
from eco_security import minmax_normalize, entropy_weights, combined_weights, esi_series, gm11_forecast, classify_warning

cli = pd.read_csv(os.path.join(BASE, "data", "qilian_climate.csv"))
lc = pd.read_csv(os.path.join(BASE, "data", "qilian_landcover.csv"))
YEARS = list(range(2005, 2024))
reg_cli = cli[cli.unit == "区域(祁连山盒)"].set_index("year")
lc = lc.set_index("year").reindex(YEARS)
for c in lc.columns:
    lc[c] = lc[c].interpolate(method="linear").bfill().ffill()

indicators = {
    "X1_降水mm": (reg_cli["precip_mm"], +1), "X2_气温C": (reg_cli["temp_c"], +1),
    "X3_草地占比%": (lc["grass_pct"], +1), "X4_森林占比%": (lc["forest_pct"], +1),
    "X5_水域占比%": (lc["water_pct"], +1),
    "X6_裸地荒漠%": (100 - lc["grass_pct"] - lc["forest_pct"] - lc["water_pct"] - lc["crop_pct"], -1),
    "X7_农田占比%": (lc["crop_pct"], -1),
    "X8_草地变化率": (lc["grass_pct"].pct_change().fillna(0) * 100, +1),
    "X9_生态用地%": (lc["grass_pct"] + lc["forest_pct"] + lc["water_pct"], +1),
}
names = list(indicators.keys())
X = np.column_stack([indicators[n][0].values for n in names])
directions = [indicators[n][1] for n in names]
Xn = minmax_normalize(X, directions)
w_ent = entropy_weights(Xn)

# 真实 AHP 权重（已存）
ahp = pd.read_csv(os.path.join(BASE, "data", "ahp_weights.csv"))
w_ahp = ahp.set_index("indicator").loc[names, "ahp_weight"].values

alpha = 0.4
w = combined_weights(w_ahp, w_ent, alpha)
esi = esi_series(Xn, w)
fut, fit, C, P = gm11_forecast(esi, n_pred=5)
levels = classify_warning(esi)
fut_levels = classify_warning(fut)

print("组合权重(α=0.4, 真实AHP):")
for n_, w_ in zip(names, w):
    print(f"  {n_:<14} {w_:.4f}")
print("\nESI 时序(2005-2023):", np.round(esi, 4))
print("预警等级:", levels)
print(f"GM(1,1) 预测: {np.round(fut,4)}  等级: {fut_levels}")
print(f"精度: C={C:.4f} P={P:.4f}")

# 保存更新
pd.DataFrame({"year": YEARS, "esi": esi.round(4), "warning": levels,
              "forecast": list(np.round(fut, 4)) + [np.nan]*14,
              "fc_warning": fut_levels + [""]*14}).to_csv(
    os.path.join(BASE, "data", "results_esi_regional.csv"), index=False, encoding="utf-8-sig")
pd.DataFrame({"indicator": names, "entropy_w": w_ent.round(4), "ahp_w": w_ahp.round(4),
              "combined_w": w.round(4), "direction": directions}).to_csv(
    os.path.join(BASE, "data", "results_weights.csv"), index=False, encoding="utf-8-sig")

# α 敏感性（真实 AHP）
rows = []
for a in np.arange(0, 1.01, 0.1):
    ww = combined_weights(w_ahp, w_ent, a)
    e = esi_series(Xn, ww)
    lv = classify_warning(e)
    from collections import Counter
    rows.append({"alpha": round(a, 1), "esi_2023": round(e[-1], 4), "level_2023": lv[-1],
                 "mean_last5": round(e[-5:].mean(), 4), "level_dist": str(dict(Counter(lv)))})
pd.DataFrame(rows).to_csv(os.path.join(BASE, "data", "results_alpha_sensitivity.csv"), index=False, encoding="utf-8-sig")
print("\nα=0.4: ESI_2023=", round(esi[-1], 4), "等级=", levels[-1])

# 三模型预测对比（NGBM + ARIMA）
def ngbm(x0, gamma, n_pred=5):
    x1 = np.cumsum(x0); z1 = 0.5 * (x1[1:] + x1[:-1])
    B = np.column_stack([-z1, z1 ** gamma]); Y = x0[1:]
    a_, b_ = np.linalg.lstsq(B, Y, rcond=None)[0]
    if abs(a_) < 1e-10: return None, None
    def X1f(t):
        return ((x0[0] ** (1 - gamma) - b_ / a_) * np.exp(-a_ * (1 - gamma) * t) + b_ / a_) ** (1 / (1 - gamma))
    xh = np.empty(len(x0)); xh[0] = x0[0]
    for k in range(1, len(x0)): xh[k] = X1f(k) - X1f(k - 1)
    fut_ = [X1f(len(x0) + k) - X1f(len(x0) + k - 1) for k in range(1, n_pred + 1)]
    return np.array(fut_), xh
best = None
for g in np.arange(0.05, 1.96, 0.05):
    f_, fit_ = ngbm(esi, g)
    if fit_ is None: continue
    sse = np.sum((esi[1:] - fit_[1:]) ** 2)
    if best is None or sse < best[0]: best = (sse, g, f_, fit_)
_, gopt, fut_n, fit_n = best
e_n = esi - fit_n
C_n = e_n.std(ddof=1) / esi.std(ddof=1)
P_n = np.mean(np.abs(e_n - e_n.mean()) < 0.6745 * esi.std(ddof=1))
from statsmodels.tsa.arima.model import ARIMA
ba = None
for p_, q_ in [(1, 0), (0, 1), (1, 1), (2, 1), (1, 2), (2, 2), (0, 2)]:
    try:
        m = ARIMA(esi, order=(p_, 1, q_)).fit()
        if ba is None or m.aic < ba[0]: ba = (m.aic, (p_, 1, q_), m)
    except Exception: pass
_, order, model = ba
fit_a = np.asarray(model.fittedvalues, dtype=float); fut_a = np.asarray(model.forecast(5), dtype=float)
e_a = esi - fit_a
C_a = e_a.std(ddof=1) / esi.std(ddof=1)
P_a = np.mean(np.abs(e_a - e_a.mean()) < 0.6745 * esi.std(ddof=1))
print("\n=== 预测对比（新 ESI）===")
for nm_, fit_, C_, P_ in [("GM(1,1)", fit, C, P), ("NGBM", fit_n, C_n, P_n), ("ARIMA", fit_a, C_a, P_a)]:
    rmse = np.sqrt(np.mean((esi - fit_) ** 2))
    print(f"  {nm_:<7} RMSE={rmse:.4f} C={C_:.4f} P={P_:.4f}")
print(f"NGBM γ={gopt:.2f} 预测:", np.round(fut_n, 4))
print(f"ARIMA{order} 预测:", np.round(fut_a, 4))
pd.DataFrame({"year": range(2024, 2029), "gm11": np.round(fut, 4), "ngbm": np.round(fut_n, 4),
              "arima": np.round(fut_a, 4)}).to_csv(
    os.path.join(BASE, "data", "results_forecast_comparison.csv"), index=False, encoding="utf-8-sig")
print("全部结果已更新")
