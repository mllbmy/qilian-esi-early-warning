# -*- coding: utf-8 -*-
"""R44 · (1) 负向归一化复算（审稿意见必改①）

审稿人称式 (2) 的负向分支被写成 (max-min)/(max-min)。实测：manuscript.tex 的负向分支
为 (max_j - x_ij)/(max_j - min_j)。本脚本用**归一化后的值**复算两个负向指标
（X6 裸地/荒漠占比、X7 农田占比），重建 ESI，并落盘逐年证据：

  1. 由 r28_core 冻结口径装载 19 年原始指标矩阵；
  2. 用 `eco_security.minmax_normalize` 得到 x'；
  3. 独立按 (max-x)/(max-min) 重算 X6/X7 的 x'，与库输出逐格比对（max|Δ| 应为 0）；
  4. 同时算**错误口径** (x-min)/(max-min) 作为对照，报告两者差异（用于回应信）；
  5. 由 x' 与组合权重重建 ESI，与 data/r28_deredundancy_series.csv 的 esi_drop_X9 逐格比对。

输出：data/r44_negative_norm_check.csv        （逐年：原始值 / x' / 错误口径 / 差值 / 加权贡献）
      data/r44_negative_norm_checks.csv       （标量汇总：max|Δ|、tex 行号、等）
运行：python r44_negative_norm_check.py
"""
import hashlib
import os
import re
import sys

import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
sys.path.insert(0, os.path.join(BASE, "eco_security"))
sys.path.insert(0, BASE)

from eco_security import minmax_normalize  # noqa: E402
import r28_core as C  # noqa: E402

OUT_Y = os.path.join(DATA, "r44_negative_norm_check.csv")
OUT_S = os.path.join(DATA, "r44_negative_norm_checks.csv")
NEG = ["X6_裸地荒漠%", "X7_农田占比%"]


def md5(path):
    return hashlib.md5(open(path, "rb").read()).hexdigest().upper()


def tex_negative_branch_line():
    """返回 manuscript.tex 中负向分支所在行号与原文（不修改文件）。"""
    p = os.path.join(BASE, "manuscript.tex")
    for i, line in enumerate(open(p, encoding="utf-8"), start=1):
        if "max_j-x_{ij}" in line:
            return i, line.strip()
    return -1, ""


def main():
    r = C.compute(C.DEREDUNDANT_SETS["drop_X9"])
    years = list(r["years"])
    keep = list(r["keep"])
    X = r["raw"][keep].values.astype(float)
    Xn = r["Xn"]
    w = r["w"]

    rows, checks = [], []

    def add(item, value, note):
        checks.append({"item": item, "value": value, "note": note})

    # 独立按式(2)负向分支重算
    wrong_max = 0.0
    for j, name in enumerate(keep):
        if name not in NEG:
            continue
        x = X[:, j]
        mx, mn = float(np.max(x)), float(np.min(x))
        xn_correct = (mx - x) / (mx - mn)          # 式(2) 负向分支
        xn_wrong = (x - mn) / (mx - mn)            # 审稿人所读到的 (max-min)/(max-min) 类伪影口径对照
        d_lib = float(np.abs(xn_correct - Xn[:, j]).max())
        d_wrong = float(np.abs(xn_wrong - Xn[:, j]).max())
        wrong_max = max(wrong_max, d_wrong)
        add("lib_vs_formula_max_abs_delta_%s" % name, d_lib,
            "库 minmax_normalize 输出 vs (max_j-x_ij)/(max_j-min_j) 独立重算")
        add("wrong_direction_max_abs_delta_%s" % name, d_wrong,
            "对照：错误口径 (x_ij-min_j)/(max_j-min_j) 与真实 x' 的最大差（应显著非零）")
        add("range_%s" % name, "%.6f..%.6f" % (mn, mx),
            "该指标 19 年原始取值范围（min..max）")
        for i, y in enumerate(years):
            rows.append({
                "year": y, "indicator": name, "layer": C.LAYER[name],
                "direction": C.LAYER_DIR[name], "x_raw": x[i],
                "min_j": mn, "max_j": mx,
                "x_norm_formula": xn_correct,
                "x_norm_from_library": float(Xn[i, j]),
                "delta_formula_vs_library": xn_correct - Xn[i, j],
                "x_norm_wrong_direction": xn_wrong,
                "delta_wrong_vs_correct": xn_wrong - xn_correct,
                "combined_weight_w": float(w[j]),
                "weighted_contribution": xn_correct * float(w[j]),
            })

    # 由 x' 重建 ESI（逐格）
    esi_re = np.asarray(Xn @ w, float)
    arc = pd.read_csv(os.path.join(DATA, "r28_deredundancy_series.csv"))
    ser = arc.set_index("year")["esi_drop_X9"].reindex(years).values
    d_esi = float(np.abs(esi_re - ser).max())
    add("esi_rebuilt_from_xnorm_vs_archive_max_abs_delta", "%.3e" % d_esi,
        "ESI=Σ w_j x'_ij 重建 vs data/r28_deredundancy_series.csv 的 esi_drop_X9（19 年）")
    add("esi_2023_rebuilt", round(float(esi_re[-1]), 6), "重建的 2023 年八指标 ESI")
    add("esi_2023_in_manuscript", 0.478, "manuscript.tex 报告值（0.478）")

    # x' 落入 [0,1] 与否
    add("xnorm_all_in_0_1", bool(np.all((Xn >= 0) & (Xn <= 1))),
        "全部指标 x' 是否均落在 [0,1]（负向指标归一化方向正确性的必要条件）")
    add("xnorm_neg_at_endpoints", bool(
        all((abs(float(Xn[np.argmax(X[:, keep.index(n)]), keep.index(n)])) < 1e-12) and
            (abs(float(Xn[np.argmin(X[:, keep.index(n)]), keep.index(n)]) - 1.0) < 1e-12)
            for n in NEG)),
        "负向指标：最大值年 x'=0、最小值年 x'=1（方向正确的判定）")

    ln, text = tex_negative_branch_line()
    add("tex_line_of_negative_branch", ln,
        "manuscript.tex 中负向分支行号；原文：%s" % text)
    add("max_abs_delta_wrong_direction_over_negatives", float("%.6f" % wrong_max),
        "两个负向指标上，错误口径与真实 x' 的最大差（用于反驳文本提取伪影）")
    add("source_data_md5_qilian_landcover", md5(os.path.join(DATA, "qilian_landcover.csv")),
        "输入：data/qilian_landcover.csv")
    add("source_data_md5_qilian_climate", md5(os.path.join(DATA, "qilian_climate.csv")),
        "输入：data/qilian_climate.csv")
    add("source_csv_md5_r28_deredundancy_series",
        md5(os.path.join(DATA, "r28_deredundancy_series.csv")),
        "对照真源：data/r28_deredundancy_series.csv")
    add("script", "r44_negative_norm_check.py", "生成脚本（已提交）")

    pd.DataFrame(rows).to_csv(OUT_Y, index=False, encoding="utf-8-sig")
    pd.DataFrame(checks).to_csv(OUT_S, index=False, encoding="utf-8-sig")

    print("=" * 78)
    print("R44 · 负向归一化复算（式 (2) 负向分支）")
    print("=" * 78)
    print("manuscript.tex 负向分支行号 = %d" % ln)
    print("  原文：%s" % text)
    for c in checks:
        print("  %-46s %s" % (c["item"], c["value"]))
    print("\n写出：%s\n      %s" % (OUT_Y, OUT_S))


if __name__ == "__main__":
    main()