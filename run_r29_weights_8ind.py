# -*- coding: utf-8 -*-
"""R29 · T1 —— 八指标主规格（drop_X9）的完整权重表（审稿意见第 2 条）

────────────────────────────────────────────────────────────────────────────
问题
────────────────────────────────────────────────────────────────────────────
第一轮修订把「删 X9_生态用地% 的八指标方案」写成了主规格，但只改了历史评估
部分；权重表（表 4 / 图 5）仍是九指标。审稿人要求主规格的权重**完整、可复算**：
  · 删 X9 后熵权是否重算、如何归一化；
  · Response 层无指标后准则层（D/P/S/I/R）权重如何处理；
  · 八指标下层的权重合计是多少（九指标口径见下）。

────────────────────────────────────────────────────────────────────────────
本轮给出的确定答案（两条规则，均为**均匀重标定**，可逐位复算）
────────────────────────────────────────────────────────────────────────────
熵权 E_j = (1 − e_j) / Σ_j (1 − e_j)，其中 e_j 只由**该列自身**的极差标准化值决定，
故删列**不改变任何存活列的 e_j 与 (1 − e_j)**，只有分母 Σ_j 变小：

    w^E,8_j = w^E,9_j · Σ_9(1−e) / Σ_8(1−e) = w^E,9_j / (1 − w^E,9_X9)
    ⇒ 统一标高因子 = 1/(1 − 0.058959) = 1.062653（对 8 个存活列一律相同）

AHP：准则层由文档化的 5×5 Saaty 矩阵特征向量给出（λmax=5.015284, CR=0.003412），
层内按指标数均分。删 X9 后 Response 层不再有指标，**在存活准则 D/P/S/I 上按
原 5×5 特征向量重新归一化**（tot = 0.081385+0.081385+0.438373+0.148627 = 0.749770）：

    w^A,8_j = w^A,9_j / 0.749770   ⇒ 统一标高因子 = 1.333742

等价的两种说法：①「准则层在存活层上重归一化 + 层内均分」；②「层内均分后把整个
指标层 AHP 向量归一到 1」。二者数值完全相同（见 CSV 的 rule_equivalent 列）。

本脚本同时报**对照规则 D**：删掉判断矩阵的 Response 行/列后重解 4×4 特征向量
（D=0.109270, P=0.109270, S=0.572450, I=0.209009；CR=0.001540）。与规则 A 在
State 层相差 −0.012227。规则 D 需要重新征询专家矩阵，且会破坏 baseline9 的精确可
复现；主规格采用规则 A，规则 D 只作敏感性对照（数值落在 criteria CSV）。

组合权重 w = 0.4·w^A + 0.6·w^E（α=0.4）。注意**组合权不是基准的均匀重标定**，
因为两个标高因子不同（1.333742 vs 1.062653）。

────────────────────────────────────────────────────────────────────────────
输出（全部新文件，r29_ 前缀；不覆盖任何已跟踪 CSV）
────────────────────────────────────────────────────────────────────────────
· data/r29_weights_8ind.csv           逐指标权重（八指标主规格 + 九指标对照 + 层合计）
· data/r29_weights_8ind_criteria.csv  准则层归一化前后（含规则 D 对照与未归一化总量）
· data/r29_weights_8ind_checks.csv    复算校验（恒等式、基准复现、闭合式 vs r28_core）

运行：python run_r29_weights_8ind.py
"""
import os
import sys

import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")

import r28_core as C  # noqa: E402

OUT_W = os.path.join(DATA, "r29_weights_8ind.csv")
OUT_C = os.path.join(DATA, "r29_weights_8ind_criteria.csv")
OUT_K = os.path.join(DATA, "r29_weights_8ind_checks.csv")

ALPHA = 0.4
DROP = "X9_生态用地%"                       # 被删除的恒等重复项（= X3+X4+X5）
CRIT = ["Driving", "Pressure", "State", "Impact", "Response"]
SCEN9, SCEN8 = "baseline9", "drop_X9"
KEEP8 = C.DEREDUNDANT_SETS[SCEN8]
# 论文 Limitations 里称作「约占 69%」的重叠指标组（状态层 + 影响层 + 响应层）
OVERLAP_LAYERS = ["State", "Impact", "Response"]


def layer_of(name):
    return C.LAYER[name]


def criterion_matrix():
    """run_ahp_weights.py 的 5×5 Saaty 判断矩阵（单一真源，此处逐字复刻以做规则对照）。"""
    return np.array([
        [1, 1, 1 / 5, 1 / 2, 1 / 3],   # D
        [1, 1, 1 / 5, 1 / 2, 1 / 3],   # P
        [5, 5, 1, 3, 2],               # S
        [2, 2, 1 / 3, 1, 1 / 2],       # I
        [3, 3, 1 / 2, 2, 1],           # R
    ], dtype=float)


def eigenvector_w(cmp):
    ev, evec = np.linalg.eig(cmp)
    k = int(np.argmax(ev.real))
    w = np.abs(evec[:, k].real)
    return w / w.sum(), float(ev.real[k])


def main():
    print("=" * 78)
    print("R29 · T1 —— 八指标主规格（drop_X9）权重表")
    print("=" * 78)

    chk = []

    def addcheck(item, value, note):
        chk.append({"item": item, "value": value, "note": note})

    # ---------- 0) 一致性自检 ----------
    sc = C.self_check(verbose=True)
    addcheck("baseline9_esi_vs_archive_max_abs_delta", round(sc["esi_max_abs_delta"], 8),
             "r28_core 重建九指标 ESI vs data/results_esi_regional.csv（归档 4 位小数舍入）")
    addcheck("baseline9_weight_vs_archive_max_abs_delta", round(sc["weight_max_abs_delta"], 8),
             "r28_core 重建九指标组合权 vs data/results_weights.csv（归档 4 位小数舍入）")
    addcheck("baseline9_levels_match_archive", bool(sc["levels_match"]),
             "九指标逐年等级与归档一致")

    r9 = C.compute(C.DEREDUNDANT_SETS[SCEN9])
    r8 = C.compute(C.DEREDUNDANT_SETS[SCEN8])

    arch_w = pd.read_csv(os.path.join(DATA, "results_weights.csv")).set_index("indicator")
    crit = pd.read_csv(os.path.join(DATA, "results_ahp_criteria.csv")).set_index("criterion")
    crit_cons = pd.read_csv(os.path.join(DATA, "results_ahp_consistency.csv"))

    # ---------- 1) 闭合式（不依赖 r28_core；准则层用全精度特征向量） ----------
    # 熵权：w^E,8 = w^E,9 / (1 - w^E,9_X9)
    w_ent_9_full = {n: float(v) for n, v in zip(r9["keep"], r9["w_ent"])}  # 全精度
    ent_scale = 1.0 / (1.0 - w_ent_9_full[DROP])
    # AHP：w^A,8 = w^A,9 / Σ(存活准则层原始权重)
    live = sorted({layer_of(n) for n in KEEP8})
    w5_full, _ = eigenvector_w(criterion_matrix())          # 全精度准则层权重
    crit_full = dict(zip(CRIT, w5_full))
    ahp_tot_live = float(sum(crit_full[l] for l in live))
    ahp_scale = 1.0 / ahp_tot_live
    # 逐指标 AHP（全精度）：层内均分 → 除以存活层合计
    closed = {}
    for n in KEEP8:
        l = layer_of(n)
        cnt = sum(1 for m in KEEP8 if layer_of(m) == l)
        wa = (crit_full[l] / ahp_tot_live) / cnt
        we = w_ent_9_full[n] * ent_scale
        closed[n] = (we, wa, ALPHA * wa + (1 - ALPHA) * we)

    # 与 r28_core 逐位比对
    d_ent = max(abs(closed[n][0] - float(r8["w_ent"][r8["keep"].index(n)])) for n in KEEP8)
    d_ahp = max(abs(closed[n][1] - float(r8["w_ahp"][r8["keep"].index(n)])) for n in KEEP8)
    d_com = max(abs(closed[n][2] - float(r8["w"][r8["keep"].index(n)])) for n in KEEP8)
    crit_round_max = float(np.abs(w5_full - crit["weight"].values).max())
    print("\n[规则校验] 闭合式 vs r28_core  max|Δ|：熵权 %.2e / AHP %.2e / 组合 %.2e"
          % (d_ent, d_ahp, d_com))
    print("[规则校验] r28_core 读的是 6 位小数的 results_ahp_criteria.csv，五层权重合计 = "
          "%.6f（归档舍入），故 AHP 列的差异即来自该处" % crit["weight"].sum())
    addcheck("closedform_vs_r28core_max_abs_delta_entropy", float("%.3e" % d_ent),
             "闭合式 w^E,8=w^E,9/(1−w^E,9_X9) 与 r28_core 熵权重算的最大绝对差（≈浮点 0）")
    addcheck("closedform_vs_r28core_max_abs_delta_ahp", float("%.3e" % d_ahp),
             "闭合式（全精度准则层特征向量）与 r28_core（读 6 位小数的 "
             "results_ahp_criteria.csv，五层合计 1.000001）的 AHP 权重最大绝对差 ⇒ "
             "纯归档舍入，远低于任何报告精度")
    addcheck("closedform_vs_r28core_max_abs_delta_combined", float("%.3e" % d_com),
             "由两个闭合式推得的组合权重与 r28_core 组合权重的最大绝对差")
    addcheck("criteria_csv_rounding_max_abs_delta", float("%.3e" % crit_round_max),
             "全精度特征向量 vs 归档 results_ahp_criteria.csv（6 位小数）的最大绝对差")
    addcheck("entropy_uniform_rescale_factor", round(ent_scale, 6),
             "删 X9 后熵权的统一放大因子 = 1/(1 − w^E,9_X9)")
    addcheck("ahp_uniform_rescale_factor", round(ahp_scale, 6),
             "删 X9 后 AHP 指标层权重的统一放大因子 = 1 / Σ(存活准则层权重)")
    addcheck("ahp_criterion_sum_over_live_layers", round(ahp_tot_live, 6),
             "存活准则层 D/P/S/I 在 5×5 判断矩阵下的原始（未归一化）权重合计")

    # 熵权均匀性：8 个存活列的 w^E,8/w^E,9 必须完全一致
    ratios = [float(r8["w_ent"][r8["keep"].index(n)]) / w_ent_9_full[n] for n in KEEP8]
    addcheck("entropy_rescale_ratio_spread", float("%.3e" % (max(ratios) - min(ratios))),
             "8 个存活列 w^E,8/w^E,9 的极差（应为 0，证明只有分母变化）")
    print("[规则校验] 熵权标高比极差 = %.3e（8 列一律相同）；标高因子 = %.6f"
          % (max(ratios) - min(ratios), ent_scale))

    # ---------- 2) 准则层两种规则 ----------
    w5, lam5 = eigenvector_w(criterion_matrix())
    w4, lam4 = eigenvector_w(criterion_matrix()[:4, :4])
    w5_renorm = w5[:4] / w5[:4].sum()
    print("\n[准则层] 规则 A（5×5 特征向量在 D/P/S/I 上重归一化）= "
          + ", ".join("%s=%.6f" % (c, v) for c, v in zip(CRIT[:4], w5_renorm)))
    print("[准则层] 规则 D（删 Response 行/列后重解 4×4）= "
          + ", ".join("%s=%.6f" % (c, v) for c, v in zip(CRIT[:4], w4)))
    addcheck("criterion_ruleD_vs_ruleA_max_abs_delta", round(float(np.abs(w4 - w5_renorm).max()), 6),
             "删 Response 后重解 4×4 特征向量 vs 在 D/P/S/I 上重归一化 5×5 → 最大差（在 State 层）")
    addcheck("criterion_4x4_lambda_max", round(lam4, 6), "4×4 子矩阵 λmax")
    addcheck("criterion_4x4_CR", round((lam4 - 4) / 3 / 0.90, 6), "4×4 子矩阵 CR（RI=0.90）")

    crit_rows = []
    for i, c in enumerate(CRIT):
        alive8 = c in live
        n9 = sum(1 for n in C.ALL9 if layer_of(n) == c)
        n8 = sum(1 for n in KEEP8 if layer_of(n) == c)
        crit_rows.append({
            "criterion": c,
            "n_indicators_9ind": n9,
            "n_indicators_8ind": n8,
            "in_8ind_spec": bool(alive8),
            "crit_w_9ind_original": round(float(w5[i]), 6),
            "crit_w_8ind_ruleA_renorm_over_live": (round(float(w5[i] / w5[:4].sum()), 6)
                                                   if alive8 else 0.0),
            "crit_w_8ind_ruleD_eig4x4": (round(float(w4[i]), 6) if alive8 else 0.0),
            "ruleA_minus_ruleD": (round(float(w5[i] / w5[:4].sum() - w4[i]), 6)
                                  if alive8 else np.nan),
            "indicator_ahp_w_9ind": ("(per indicator) " + " / ".join(
                "%.6f" % float(arch_w.loc[n, "ahp_w"]) for n in C.ALL9 if layer_of(n) == c)),
            "indicator_ahp_w_8ind": ("(per indicator) " + " / ".join(
                "%.6f" % closed[n][1] for n in KEEP8 if layer_of(n) == c)) if alive8 else "",
            "note": ("五层之一；八指标主规格下仍有指标存活" if alive8
                     else "八指标主规格下 Response 层无指标，其 0.250231 按下列重归一化规则"
                          "重新分配给 D/P/S/I"),
        })
    crit_rows.append({
        "criterion": "TOTAL", "n_indicators_9ind": 9, "n_indicators_8ind": 8,
        "in_8ind_spec": True,
        "crit_w_9ind_original": round(float(w5.sum()), 6),
        "crit_w_8ind_ruleA_renorm_over_live": 1.0,
        "crit_w_8ind_ruleD_eig4x4": 1.0, "ruleA_minus_ruleD": 0.0,
        "indicator_ahp_w_9ind": "指标层 AHP 向量合计 = 1.000000",
        "indicator_ahp_w_8ind": "指标层 AHP 向量合计 = 1.000000",
        "note": "两条规则都归一到 1；区别只在 D/P/S/I 之间的相对分配",
    })
    crit_rows.append({
        "criterion": "D+P+S+I (9ind, unnormalised)", "n_indicators_9ind": 8,
        "n_indicators_8ind": np.nan, "in_8ind_spec": False,
        "crit_w_9ind_original": round(ahp_tot_live, 6),
        "crit_w_8ind_ruleA_renorm_over_live": np.nan,
        "crit_w_8ind_ruleD_eig4x4": np.nan, "ruleA_minus_ruleD": np.nan,
        "indicator_ahp_w_9ind": "= 0.749770（若**保留原值不归一化**，指标层 AHP 合计仅 0.749770，"
                                "组合权重合计 ≠ 1，与 ESI 的凸组合定义矛盾 ⇒ 该选项不可用）",
        "indicator_ahp_w_8ind": "",
        "note": "此项证明「保留原值」不可行，故必须重归一化",
    })
    pd.DataFrame(crit_rows).to_csv(OUT_C, index=False, encoding="utf-8-sig")

    # ---------- 3) 逐指标权重表 ----------
    rows = []
    for n in KEEP8:
        i8 = r8["keep"].index(n)
        i9 = r9["keep"].index(n)
        rows.append({
            "row_type": "indicator", "indicator": n, "layer": layer_of(n),
            "entropy_w": round(float(r8["w_ent"][i8]), 6),
            "ahp_w": round(float(r8["w_ahp"][i8]), 6),
            "combined_w": round(float(r8["w"][i8]), 6),
            "entropy_w_9ind": round(float(r9["w_ent"][i9]), 6),
            "ahp_w_9ind": round(float(r9["w_ahp"][i9]), 6),
            "combined_w_9ind": round(float(r9["w"][i9]), 6),
            "delta_entropy_vs_9ind": round(float(r8["w_ent"][i8] - r9["w_ent"][i9]), 6),
            "delta_ahp_vs_9ind": round(float(r8["w_ahp"][i8] - r9["w_ahp"][i9]), 6),
            "delta_combined_vs_9ind": round(float(r8["w"][i8] - r9["w"][i9]), 6),
            "entropy_rescale_factor": round(ent_scale, 6),
            "ahp_rescale_factor": round(ahp_scale, 6),
            "combined_w_4dp_for_paper": round(float(r8["w"][i8]), 4),
            "note": "熵权与 AHP 各自被**统一因子**放大；组合权因两因子不同而**不是**均匀重标定",
        })
    # 九指标中被删项，作对照行
    i9x = r9["keep"].index(DROP)
    rows.append({
        "row_type": "removed_indicator", "indicator": DROP, "layer": layer_of(DROP),
        "entropy_w": 0.0, "ahp_w": 0.0, "combined_w": 0.0,
        "entropy_w_9ind": round(float(r9["w_ent"][i9x]), 6),
        "ahp_w_9ind": round(float(r9["w_ahp"][i9x]), 6),
        "combined_w_9ind": round(float(r9["w"][i9x]), 6),
        "delta_entropy_vs_9ind": round(-float(r9["w_ent"][i9x]), 6),
        "delta_ahp_vs_9ind": round(-float(r9["w_ahp"][i9x]), 6),
        "delta_combined_vs_9ind": round(-float(r9["w"][i9x]), 6),
        "entropy_rescale_factor": np.nan, "ahp_rescale_factor": np.nan,
        "combined_w_4dp_for_paper": 0.0,
        "note": "X9 = X3+X4+X5 的完全重复列（残差 0），八指标主规格删除；其权重按上述两个"
                "统一因子全额再分配给存活指标",
    })
    # 层合计
    for lay in CRIT:
        idx8 = [i for i, n in enumerate(r8["keep"]) if layer_of(n) == lay]
        idx9 = [i for i, n in enumerate(r9["keep"]) if layer_of(n) == lay]
        rows.append({
            "row_type": "layer_total", "indicator": "layer_weight:" + lay, "layer": lay,
            "entropy_w": round(float(r8["w_ent"][idx8].sum()) if idx8 else 0.0, 6),
            "ahp_w": round(float(r8["w_ahp"][idx8].sum()) if idx8 else 0.0, 6),
            "combined_w": round(float(r8["w"][idx8].sum()) if idx8 else 0.0, 6),
            "entropy_w_9ind": round(float(r9["w_ent"][idx9].sum()) if idx9 else 0.0, 6),
            "ahp_w_9ind": round(float(r9["w_ahp"][idx9].sum()) if idx9 else 0.0, 6),
            "combined_w_9ind": round(float(r9["w"][idx9].sum()) if idx9 else 0.0, 6),
            "delta_entropy_vs_9ind": round(float((r8["w_ent"][idx8].sum() if idx8 else 0.0)
                                                 - (r9["w_ent"][idx9].sum() if idx9 else 0.0)), 6),
            "delta_ahp_vs_9ind": round(float((r8["w_ahp"][idx8].sum() if idx8 else 0.0)
                                             - (r9["w_ahp"][idx9].sum() if idx9 else 0.0)), 6),
            "delta_combined_vs_9ind": round(float((r8["w"][idx8].sum() if idx8 else 0.0)
                                                  - (r9["w"][idx9].sum() if idx9 else 0.0)), 6),
            "entropy_rescale_factor": np.nan, "ahp_rescale_factor": np.nan,
            "combined_w_4dp_for_paper": round(float(r8["w"][idx8].sum()) if idx8 else 0.0, 4),
            "note": "层内指标组合权重合计",
        })
    # 组合计
    def lsum(r, lays):
        idx = [i for i, n in enumerate(r["keep"]) if layer_of(n) in lays]
        return float(r["w"][idx].sum()) if idx else 0.0

    def lsum_ent(r, lays):
        idx = [i for i, n in enumerate(r["keep"]) if layer_of(n) in lays]
        return float(r["w_ent"][idx].sum()) if idx else 0.0

    def lsum_ahp(r, lays):
        idx = [i for i, n in enumerate(r["keep"]) if layer_of(n) in lays]
        return float(r["w_ahp"][idx].sum()) if idx else 0.0

    groups = [
        ("D+P+S+I (four live layers, 8ind)",
         ["Driving", "Pressure", "State", "Impact"],
         "八指标主规格下四个存活层的组合权重合计；Response 层无指标 ⇒ 按其忠实定义合计为 1.000000"),
        ("State+Impact+Response (paper's ~69% overlap group)",
         OVERLAP_LAYERS,
         "论文 Limitations 第 (1) 条所指的重叠指标组（状态层 X3/X4/X5 + 影响层 X8 + 响应层 X9）；"
         "九指标 0.692904 = 69.29%；八指标删 X9 后为 State+Impact = 0.656013 = 65.60%"),
    ]
    for label, lays, note in groups:
        rows.append({
            "row_type": "group_total", "indicator": label,
            "layer": "+".join(lays),
            "entropy_w": round(lsum_ent(r8, lays), 6),
            "ahp_w": round(lsum_ahp(r8, lays), 6),
            "combined_w": round(lsum(r8, lays), 6),
            "entropy_w_9ind": round(lsum_ent(r9, lays), 6),
            "ahp_w_9ind": round(lsum_ahp(r9, lays), 6),
            "combined_w_9ind": round(lsum(r9, lays), 6),
            "delta_entropy_vs_9ind": round(lsum_ent(r8, lays) - lsum_ent(r9, lays), 6),
            "delta_ahp_vs_9ind": round(lsum_ahp(r8, lays) - lsum_ahp(r9, lays), 6),
            "delta_combined_vs_9ind": round(lsum(r8, lays) - lsum(r9, lays), 6),
            "entropy_rescale_factor": np.nan, "ahp_rescale_factor": np.nan,
            "combined_w_4dp_for_paper": round(lsum(r8, lays), 4),
            "note": note,
        })
    wdf = pd.DataFrame(rows)
    wdf.to_csv(OUT_W, index=False, encoding="utf-8-sig")

    # ---------- 4) 关键读数 ----------
    ov9 = lsum(r9, OVERLAP_LAYERS)
    ov8 = lsum(r8, OVERLAP_LAYERS)
    dpsi9 = lsum(r9, ["Driving", "Pressure", "State", "Impact"])
    dpsi8 = lsum(r8, ["Driving", "Pressure", "State", "Impact"])
    addcheck("overlap_group_combined_share_9ind", round(ov9, 6),
             "重叠指标组（State+Impact+Response）组合权重合计，九指标 = 69.29%")
    addcheck("overlap_group_combined_share_8ind", round(ov8, 6),
             "同一重叠组在八指标主规格下（State+Impact，X9 已删）的组合权重合计 = 65.60%")
    addcheck("dpsi_four_layers_combined_share_9ind", round(dpsi9, 6),
             "D/P/S/I 四层合计，九指标口径")
    addcheck("dpsi_four_layers_combined_share_8ind", round(dpsi8, 6),
             "D/P/S/I 四层合计，八指标主规格（四层即全部存活层）⇒ 恒为 1")

    print("\n" + "-" * 78)
    print("八指标主规格逐指标权重（对照九指标）")
    print("-" * 78)
    show = wdf[wdf.row_type == "indicator"][
        ["indicator", "layer", "entropy_w", "ahp_w", "combined_w",
         "entropy_w_9ind", "ahp_w_9ind", "combined_w_9ind", "delta_combined_vs_9ind"]]
    print(show.to_string(index=False))
    print("\n层合计：")
    show = wdf[wdf.row_type.isin(["layer_total", "group_total"])][
        ["indicator", "entropy_w", "ahp_w", "combined_w",
         "entropy_w_9ind", "ahp_w_9ind", "combined_w_9ind"]]
    print(show.to_string(index=False))
    print("\n权重合计校验：八指标 熵权=%.6f AHP=%.6f 组合=%.6f"
          % (r8["w_ent"].sum(), r8["w_ahp"].sum(), r8["w"].sum()))
    print("D/P/S/I 四层组合权重合计：八指标 %.6f（九指标同四层 %.6f）" % (dpsi8, dpsi9))
    print("重叠指标组（State+Impact+Response）：九指标 %.6f (69.29%%) → 八指标 %.6f (65.60%%)"
          % (ov9, ov8))

    pd.DataFrame(chk).to_csv(OUT_K, index=False, encoding="utf-8-sig")
    print("\n已写出：data/r29_weights_8ind.csv（%d 行）, data/r29_weights_8ind_criteria.csv"
          "（%d 行）, data/r29_weights_8ind_checks.csv（%d 行）"
          % (len(wdf), len(crit_rows), len(chk)))
    return 0


if __name__ == "__main__":
    sys.exit(main())