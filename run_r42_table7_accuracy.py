# -*- coding: utf-8 -*-
"""R42 —— 表 7 / 表 5 精度四列的订正与复现。

背景（R41 报告 §4）
-------------------
英文 Table~\\ref{tab:forecast}（中文表 5）α=0.4 三模型对比中，NGBM 4 格
（RMSE 0.031 / MAE 0.024 / C 0.428 / P 0.947）与 ARIMA 4 格
（RMSE 0.097 / MAE 0.066 / C 1.090 / P 0.632）在本仓库无任何生成脚本或结果表。
穷尽溯源（R42 报告 §1）结论：NGBM 四元组在 7 条序列 × γ∈[0.01,2.99] × 8 种 C/P 口径
共 2,086 个候选点上**无一点同时支配**（四项全优）；ARIMA 行则等于九指标归档行
`results_forecast_accuracy.csv` 的 ARIMA 行（0.0977/0.0666/1.0861/0.6316）经截断与手调 C。
⇒ 按可复现优先原则订正。

本脚本做三件事
--------------
1. **单一实现的复算**：口径函数直接 `import` 自 `run_r41_accuracy_8ind.py`
   （`metrics` / `ngbm_core` / `grade_of`），该实现已在九指标归档序列上逐格复现
   `results_forecast_accuracy.csv`（max|Δ|=4.5e-05）。本脚本不另写一套口径。
2. **口径自检**：每次运行都重跑九指标 12 格复现检验；不通过即 assert 失败。
3. **回归断言 + 落盘**：把三模型 12 格四舍五入到论文表内位数（3 位）后与
   **订正后的印出值** `TABLE7_R42` 逐格 assert 相等；同时保留订正前的印出值
   `TABLE7_PRE_R42` 作为审计记录。结果写入 `data/r42_table7_accuracy.csv`。

分母口径的选择（必须在报告中说明）
----------------------------------
RMSE/MAE 用分母 **n**（不是 n−1），理由：
  · 论文自己的九指标归档精度表 `results_forecast_accuracy.csv` 用的就是 n
    （本脚本运行时的自检以 max|Δ|≤5e-5 复现该表）；
  · 同一篇论文的两张精度表必须同口径；表 7 表注只写 “full-series fitting accuracy”，
    未声明分母，若一张用 n、另一张用 n−1 即为未声明的不一致；
  · 该选择**不可能影响任何精度等级**：判级只依赖 C 与 P，二者是比值，与 RMSE/MAE
    的分母无关。故本选择不存在“为让某模型好看而选口径”的空间。
GM 行原印出 0.047/0.034 只在 n−1 分母下成立，本脚本一并统一为 n 口径的 0.046/0.032。

运行：python run_r42_table7_accuracy.py
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
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "eco_security"))

# —— 单一实现：口径函数逐字复用 R41 已提交脚本（该实现已在九指标上验证）
from run_r41_accuracy_8ind import (  # noqa: E402
    N_FUT, grade_of, metrics, ngbm_core,
)
from eco_security import gm11_forecast  # noqa: E402
from statsmodels.tsa.arima.model import ARIMA  # noqa: E402

# 订正前的印出值（R29 起沿用至 R41 交付版；无生成脚本，见 R42 报告 §1）
TABLE7_PRE_R42 = {
    "GM(1,1)": (0.047, 0.034, 0.603, 0.789),
    "NGBM": (0.031, 0.024, 0.428, 0.947),
    "ARIMA": (0.097, 0.066, 1.090, 0.632),
}
# 订正后的印出值 = 本脚本实算值四舍五入到 3 位
TABLE7_R42 = {
    "GM(1,1)": (0.046, 0.032, 0.603, 0.789),
    "NGBM": (0.046, 0.037, 0.604, 0.684),
    "ARIMA": (0.104, 0.068, 1.320, 0.526),
}
MODEL_LABEL = {"GM(1,1)": "GM(1,1)", "NGBM": "NGBM (gamma=0.15)", "ARIMA": "ARIMA(0,1,1)"}
SPEC = ("八指标主口径（drop_X9, alpha=0.4）2005-2023 全序列拟合；RMSE/MAE 分母 n"
        "（与 results_forecast_accuracy.csv 同口径）；NGBM gamma=0.15（训练期 SSE 最优）；"
        "C=std(e,ddof=1)/std(x,ddof=1)；P=mean(|e-mean(e)|<0.6745*std(x,ddof=1))")


def main():
    ser = pd.read_csv(os.path.join(DATA, "r28_deredundancy_series.csv"))
    esi = ser["esi_drop_X9"].values.astype(float)
    n = len(esi)
    ck = pd.read_csv(os.path.join(DATA, "r29_forecast_8ind_checks.csv"))
    gamma_main = float(ck.loc[ck["item"] == "gamma_8ind_train_sse", "value"].iloc[0])

    # ---------- 口径自检：九指标归档序列 12 格复现 results_forecast_accuracy.csv
    ref = pd.read_csv(os.path.join(DATA, "results_forecast_accuracy.csv"))
    esi9 = pd.read_csv(os.path.join(DATA, "results_esi_regional.csv"))["esi"].values.astype(float)
    _, fit_gm9, _, _ = gm11_forecast(esi9, n_pred=N_FUT)
    fit_n9 = ngbm_core(esi9, 0.20)
    ma9 = ARIMA(esi9, order=(0, 1, 1)).fit()
    fit_a9 = np.asarray(ma9.fittedvalues, dtype=float)
    if len(fit_a9) == len(esi9) - 1:
        fit_a9 = np.concatenate([[esi9[0]], fit_a9[1:]])
    dmax = 0.0
    for name, fit in (("GM(1,1)", fit_gm9), ("NGBM", fit_n9), ("ARIMA", fit_a9)):
        m9 = metrics(esi9, fit)
        rr = ref[ref.model == name].iloc[0]
        dmax = max(dmax, abs(m9["rmse"] - rr.rmse), abs(m9["mae"] - rr.mae),
                   abs(m9["C"] - rr.C), abs(m9["P"] - rr.P))
    print("口径自检（九指标 12 格复现 results_forecast_accuracy.csv）: max|Δ|=%.1e" % dmax)
    assert dmax <= 5e-5, "口径自检失败（max|Δ|=%.2e），不得据此订正" % dmax

    # ---------- 八指标主口径三模型拟合
    _, fit_gm, _, _ = gm11_forecast(esi, n_pred=N_FUT)
    fit_n = ngbm_core(esi, gamma_main)
    assert fit_n is not None, "NGBM 拟合并未收敛"
    ma = ARIMA(esi, order=(0, 1, 1)).fit()
    fit_a = np.asarray(ma.fittedvalues, dtype=float)
    if len(fit_a) == n - 1:
        fit_a = np.concatenate([[esi[0]], fit_a[1:]])

    rows, ok = [], True
    print("\n%-16s %-28s %-28s %s" % ("模型", "实算 (n 分母)", "订正后印出值", "订正前印出值"))
    for name, fit in (("GM(1,1)", fit_gm), ("NGBM", fit_n), ("ARIMA", fit_a)):
        m = metrics(esi, fit)
        printed = (round(m["rmse"], 3), round(m["mae"], 3), round(m["C"], 3), round(m["P"], 3))
        want = TABLE7_R42[name]
        pre = TABLE7_PRE_R42[name]
        match = printed == want
        ok = ok and match
        print("%-16s %-28s %-28s %s  %s"
              % (name, "%.4f/%.4f/%.4f/%.4f" % (m["rmse"], m["mae"], m["C"], m["P"]),
                 "%.3f/%.3f/%.3f/%.3f" % printed, "%.3f/%.3f/%.3f/%.3f" % pre,
                 "OK" if match else "**MISMATCH**"))
        assert match, "%s: 实算 %s != 订正后印出值 %s" % (name, printed, want)
        rows.append({
            "model": MODEL_LABEL[name],
            "rmse": round(m["rmse"], 4), "mae": round(m["mae"], 4),
            "C": round(m["C"], 6), "P": round(m["P"], 6),
            "rmse_3dp": printed[0], "mae_3dp": printed[1],
            "C_3dp": printed[2], "P_3dp": printed[3],
            "grade": grade_of(m["C"], m["P"]),
            "rmse_n_minus_1den": round(m["rmse_n_minus_1den"], 4),
            "mae_n_minus_1den": round(m["mae_n_minus_1den"], 4),
            "pre_r42_rmse": pre[0], "pre_r42_mae": pre[1],
            "pre_r42_C": pre[2], "pre_r42_P": pre[3],
            "pre_r42_grade": grade_of(pre[2], pre[3]),
            "pre_r42_source": ("无生成脚本/结果表；NGBM 四元组超出本仓库模型族可达精度，"
                               "ARIMA 行等于九指标归档行 results_forecast_accuracy.csv"
                               "（0.0977/0.0666/1.0861/0.6316）截断并手调 C"
                               if name != "GM(1,1)" else
                               "C/P 与 r29_forecast_8ind_checks.csv 一致；RMSE/MAE 为 n-1 分母值"),
            "verdict": "与论文表 7 订正后印出值逐格一致（本脚本复现）",
            "spec": SPEC,
            "script": "run_r42_table7_accuracy.py",
        })

    print("\n等级重判（论文自定规则：合格 C<0.50 且 P>0.80；勉强合格 C<0.65 且 P>0.70；其余不合格）")
    for r in rows:
        print("  %-16s C=%.6f P=%.6f ⇒ %-6s （订正前印出行 %s）"
              % (r["model"], r["C"], r["P"], r["grade"], r["pre_r42_grade"]))

    assert ok, "存在未复现的格"
    out = pd.DataFrame(rows)
    path = os.path.join(DATA, "r42_table7_accuracy.csv")
    out.to_csv(path, index=False, encoding="utf-8-sig")
    print("\n全部 12 格复现通过。已写入 %s（%d B, %d 行）"
          % (path, os.path.getsize(path), len(out)))


if __name__ == "__main__":
    main()