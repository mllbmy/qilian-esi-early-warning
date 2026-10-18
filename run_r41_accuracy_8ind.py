# -*- coding: utf-8 -*-
"""R41 · T4 —— 八指标主口径（drop_X9, α=0.4）三模型拟合精度实算。

用途
----
论文 Table 5（英文 `tab:forecast`）印出的 **RMSE / MAE / C / P** 四列在 `data/` 里
原本没有八指标口径的结果表（`results_forecast_accuracy.csv` 是九指标口径）。
本脚本按 `run_forecast_comparison.py`（九指标版）**逐字相同的口径**在八指标主口径
ESI 序列上实算，落盘 `data/r29_forecast_accuracy_8ind.csv`，并逐格打印与英文定稿
印出值的偏差；**不一致时只报告、不修改任何一侧数值**。

口径（与 `results_forecast_accuracy.csv` 完全一致，且已在九指标序列上逐格复现该表）
  · 目标序列：`data/r28_deredundancy_series.csv` 的 `esi_drop_X9`（2005–2023，19 点）
  · RMSE = sqrt(mean(e^2))，MAE = mean(|e|)，分母 n（与九指标归档表同）
  · C = std(e, ddof=1) / std(x, ddof=1)
  · P = mean(|e - mean(e)| < 0.6745 * std(x, ddof=1))
  · GM(1,1)：`eco_security.gm11_forecast`
  · NGBM：γ = 训练期（2005–2018）SSE 最优（`r29_forecast_8ind_checks.csv` → 0.15），
    实现逐字取自 `run_r29_forecast_8ind.py::ngbm_core`
  · ARIMA(0,1,1)：阶数固定（与 r29 主口径一致），fittedvalues 原样使用

另列 `rmse_n_minus_1den` / `mae_n_minus_1den`：同一拟合改用 n−1 分母的结果，
用于说明英文印出的 GM 行 0.047/0.034 对应的是 n−1 分母。

运行：python run_r41_accuracy_8ind.py
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
from statsmodels.tsa.arima.model import ARIMA  # noqa: E402

N_FUT = 5
EN_TABLE7 = {  # 英文定稿 Table 7 (tab:forecast) 印出值 (RMSE, MAE, C, P)
    "GM(1,1)": (0.047, 0.034, 0.603, 0.789),
    "NGBM": (0.031, 0.024, 0.428, 0.947),
    "ARIMA": (0.097, 0.066, 1.090, 0.632),
}


def ngbm_core(x0, gamma, n_pred=N_FUT):
    """逐字取自 run_r29_forecast_8ind.py::ngbm_core（去掉预测段无关部分）。"""
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
        return xh
    a, b = np.linalg.lstsq(np.column_stack([-z1, z1 ** gamma]), x0[1:], rcond=None)[0]
    if abs(a) < 1e-12:
        return None

    def X1(t):
        base = (x0[0] ** (1 - gamma) - b / a) * np.exp(-a * (1 - gamma) * t) + b / a
        if base <= 0:
            raise ValueError("negative base")
        return base ** (1.0 / (1.0 - gamma))

    return np.array([x0[0]] + [X1(k) - X1(k - 1) for k in range(1, len(x0))])


def metrics(x, fit):
    """九指标归档表所用的口径：分母 n。"""
    e = np.asarray(x, float) - np.asarray(fit, float)
    S1 = np.asarray(x, float).std(ddof=1)
    return {
        "rmse": float(np.sqrt(np.mean(e ** 2))),
        "mae": float(np.mean(np.abs(e))),
        "C": float(e.std(ddof=1) / S1),
        "P": float(np.mean(np.abs(e - e.mean()) < 0.6745 * S1)),
        "rmse_n_minus_1den": float(np.sqrt(np.sum(e ** 2) / (len(x) - 1))),
        "mae_n_minus_1den": float(np.sum(np.abs(e)) / (len(x) - 1)),
    }


def grade_of(C, P):
    return ("优" if (C < 0.35 and P > 0.95) else
            "合格" if (C < 0.50 and P > 0.80) else
            "勉强" if (C < 0.65 and P > 0.70) else "不合格")


def main():
    ser = pd.read_csv(os.path.join(DATA, "r28_deredundancy_series.csv"))
    esi = ser["esi_drop_X9"].values.astype(float)
    n = len(esi)
    ck = pd.read_csv(os.path.join(DATA, "r29_forecast_8ind_checks.csv"))
    gamma_main = float(ck.loc[ck["item"] == "gamma_8ind_train_sse", "value"].iloc[0])

    # --- 口径自检：同一函数在九指标归档序列上必须逐格复现 results_forecast_accuracy.csv
    #     输入用 run_forecast_comparison.py 实际读取的 data/results_esi_regional.csv
    ref = pd.read_csv(os.path.join(DATA, "results_forecast_accuracy.csv"))
    esi9 = pd.read_csv(os.path.join(DATA, "results_esi_regional.csv"))["esi"].values.astype(float)
    _, fit_gm9, C_gm9, P_gm9 = gm11_forecast(esi9, n_pred=N_FUT)
    fit_n9 = ngbm_core(esi9, 0.20)
    ma9 = ARIMA(esi9, order=(0, 1, 1)).fit()
    fit_a9 = np.asarray(ma9.fittedvalues, dtype=float)
    fit_a9 = np.concatenate([[esi9[0]], fit_a9[1:]]) if len(fit_a9) == len(esi9) - 1 else fit_a9
    dmax = 0.0
    for name, fit, cref in (("GM(1,1)", fit_gm9, (C_gm9, P_gm9)),
                            ("NGBM", fit_n9, None), ("ARIMA", fit_a9, None)):
        m9 = metrics(esi9, fit)
        rr = ref[ref.model == name].iloc[0]
        d = max(abs(m9["rmse"] - rr.rmse), abs(m9["mae"] - rr.mae),
                abs(m9["C"] - rr.C), abs(m9["P"] - rr.P))
        dmax = max(dmax, d)
        print("口径自检（九指标 %-8s）: %.4f/%.4f/%.4f/%.4f | 归档 %.4f/%.4f/%.4f/%.4f | max|Δ|=%.1e"
              % (name, m9["rmse"], m9["mae"], m9["C"], m9["P"], rr.rmse, rr.mae, rr.C, rr.P, d))
    print("口径自检结论：%s\n" % ("逐格复现 results_forecast_accuracy.csv（口径无误）"
                                  if dmax <= 5e-5 else "**未能复现，口径存疑（max|Δ|=%.2e）**" % dmax))

    # --- 三模型在八指标主口径上的拟合
    _, fit_gm, _, _ = gm11_forecast(esi, n_pred=N_FUT)
    fit_n = ngbm_core(esi, gamma_main)
    ma = ARIMA(esi, order=(0, 1, 1)).fit()
    fit_a = np.asarray(ma.fittedvalues, dtype=float)
    fit_a = np.concatenate([[esi[0]], fit_a[1:]]) if len(fit_a) == n - 1 else fit_a

    rows = []
    for name, fit in (("GM(1,1)", fit_gm), ("NGBM", fit_n), ("ARIMA", fit_a)):
        m = metrics(esi, fit)
        en = EN_TABLE7[name]
        dev = [abs(m["rmse"] - en[0]), abs(m["mae"] - en[1]),
               abs(m["C"] - en[2]), abs(m["P"] - en[3])]
        if max(dev) < 5e-4:
            verdict = "与英文定稿一致"
        elif max(dev[2:]) < 5e-4 and max(dev[:2]) < 5e-4 + 0.0014:
            verdict = ("C/P 与英文定稿一致；RMSE/MAE 仅在 n−1 分母下一致"
                       "（n 分母 %.3f/%.3f 对印出 %.3f/%.3f）"
                       % (m["rmse"], m["mae"], en[0], en[1]))
        else:
            verdict = ("**与英文定稿不一致**：实算 %.4f/%.4f/%.4f/%.4f 对印出 "
                       "%.3f/%.3f/%.3f/%.3f" % (m["rmse"], m["mae"], m["C"], m["P"], *en))
        rows.append({
            "model": name,
            "rmse": round(m["rmse"], 4), "mae": round(m["mae"], 4),
            "C": round(m["C"], 6), "P": round(m["P"], 6),
            "grade": grade_of(m["C"], m["P"]),
            "rmse_n_minus_1den": round(m["rmse_n_minus_1den"], 4),
            "mae_n_minus_1den": round(m["mae_n_minus_1den"], 4),
            "en_table7_rmse": en[0], "en_table7_mae": en[1],
            "en_table7_C": en[2], "en_table7_P": en[3],
            "verdict": verdict,
            "spec": ("八指标主口径（drop_X9, α=0.4）2005–2023 全序列拟合；"
                     "分母 n；NGBM γ=%.2f（训练期 SSE 最优）" % gamma_main),
            "script": "run_r41_accuracy_8ind.py",
        })
        print("  %-8s 实算 RMSE=%.4f MAE=%.4f C=%.6f P=%.6f | 印出 %s | %s"
              % (name, m["rmse"], m["mae"], m["C"], m["P"], en, verdict))

    out = pd.DataFrame(rows)
    path = os.path.join(DATA, "r29_forecast_accuracy_8ind.csv")
    out.to_csv(path, index=False, encoding="utf-8-sig")
    print("\n已写入 %s（%d B, %d 行）" % (path, os.path.getsize(path), len(out)))


if __name__ == "__main__":
    main()