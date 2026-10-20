# -*- coding: utf-8 -*-
"""R46 · 预测起点偏移的可解释性（导师批注 5）

问题：2023 年 ESI 观测 0.478，而三模型 2024 起点为 0.469(GM)/0.424(NGBM)/0.485(ARIMA)；
NGBM 起点低 0.054，读者会质疑"投影起点跳变"。

方法：三模型均为对 2005--2023 全记录拟合后的外推，2024 值是模型自身的一步预测值，
      并非从 2023 观测锚定。因此把 NGBM 起点偏移分解为
        (a) 相对其自身 2023 拟合值的一步变化
        (b) 2023 年的样本内残差（观测 - 拟合）
      并给出 GM/ARIMA 相对观测的偏移。

输出：data/r46_start_offset.csv
"""
import numpy as np
import pandas as pd

BASE = r"D:\比赛\论文\paper-code"
GAMMA = 0.15  # 八指标主规格、仅训练期 SSE 所选（rate-limiting，见 r29 checks）


def ngbm_fit(x0, gamma, n_pred=1):
    x1 = np.cumsum(x0)
    z1 = 0.5 * (x1[1:] + x1[:-1])
    a, b = np.linalg.lstsq(np.column_stack([-z1, z1 ** gamma]), x0[1:], rcond=None)[0]

    def X1(t):
        base = (x0[0] ** (1 - gamma) - b / a) * np.exp(-a * (1 - gamma) * t) + b / a
        return base ** (1.0 / (1 - gamma))

    xh = np.array([x0[0]] + [X1(k) - X1(k - 1) for k in range(1, len(x0))])
    fut = np.array([X1(len(x0) + k) - X1(len(x0) + k - 1) for k in range(1, n_pred + 1)])
    return fut, xh


def main():
    d = pd.read_csv(BASE + r"\data\r28_deredundancy_series.csv")
    s = d.groupby("year")["esi_drop_X9"].first().sort_index()
    obs23 = float(s.loc[2023])
    fut, xh = ngbm_fit(s.values, GAMMA)
    fit23 = float(xh[-1])
    f = pd.read_csv(BASE + r"\data\r29_forecast_8ind.csv").set_index("year")
    start = {"GM(1,1)": float(f.loc[2024, "gm11_8ind"]),
             "NGBM": float(f.loc[2024, "ngbm_8ind_gamma_train"]),
             "ARIMA(0,1,1)": float(f.loc[2024, "arima_011_8ind"])}
    rows = []
    for k, v in start.items():
        rows.append({"model": k, "value_2024": round(v, 6),
                     "offset_vs_observed_2023": round(v - obs23, 6)})
    rows.append({"model": "NGBM internal decomposition",
                 "value_2024": round(start["NGBM"], 6),
                 "offset_vs_observed_2023": round(start["NGBM"] - obs23, 6)})
    out = pd.DataFrame(rows)
    out.loc[len(out)] = {"model": "observed_2023", "value_2024": round(obs23, 6),
                         "offset_vs_observed_2023": 0.0}
    out.loc[len(out)] = {"model": "NGBM_fitted_2023", "value_2024": round(fit23, 6),
                         "offset_vs_observed_2023": round(fit23 - obs23, 6)}
    out.loc[len(out)] = {"model": "NGBM_step_2023fit_to_2024",
                         "value_2024": round(start["NGBM"] - fit23, 6),
                         "offset_vs_observed_2023": np.nan}
    out.loc[len(out)] = {"model": "NGBM_insample_residual_2023",
                         "value_2024": round(obs23 - fit23, 6),
                         "offset_vs_observed_2023": np.nan}
    out.to_csv(BASE + r"\data\r46_start_offset.csv", index=False, encoding="utf-8-sig")
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
