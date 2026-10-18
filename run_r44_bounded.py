# -*- coding: utf-8 -*-
"""R44 · 任务 2 —— **有界**预测区间（不得超出 [0,1]）

────────────────────────────────────────────────────────────────────────────
问题
────────────────────────────────────────────────────────────────────────────
R29 的预测区间在原始 ESI 空间叠加累积块新息，2028 年 ARIMA(0,1,1) 的 95% 上界为
**1.112674 > 1**，等权混合为 [0.165645, 0.945092]。ESI 由 min–max 归一化构造、
取值恒在 [0,1] 内，故 >1 的上界不是 ESI 可达值。本脚本给出两种**有界**口径。

────────────────────────────────────────────────────────────────────────────
主口径：logit 变换 bootstrap（"logit_main"）
────────────────────────────────────────────────────────────────────────────
· ESI 序列实测已在 (0,1) 内（min 0.288559、max 0.676264），**无需平移**（若出现
  0/1，本脚本按 EPS=1e-12 台平移并计数报告，实测平移次数为 0）。
· 变换：z = logit(ESI)。残差 r_t = logit(y_t) − logit(ŷ_t) 在 logit 尺度计算。
· bootstrap 机制与随机种子与 R29 完全相同（B=2000、seed=20261017、块长 L=3、
  NGBM 每重复重选 γ；见 r44_common.py）。伪历史 = 拟合值 + 重采样残差，经 expit
  回到 (0,1) 后**仍在原始空间重估模型**（⇒ 点预测口径不变），预测水平再映射到
  logit 尺度并叠加 logit 尺度的累积块新息，最后 expit 逆变换。
  ⇒ **全部抽样路径天然落在 (0,1) 内**，区间端点不可能越界。
· ARIMA 首期拟合值：statsmodels 对 (0,1,1) 的首期 fittedvalue 不由递推式定义，
  实测为 0.0（不在 (0,1) 内）。R29 自己的做法是在长度为 n−1 时补 y_0；本脚本把
  同一规则推广到"首期非法"，即取 y_0（first_fix="reg"）。该规则**只影响残差池的
  第 1 个点、不影响任何点预测**。另设 first_fix="naive"（原样保留 0.0）作**诊断**：
  它使首期 logit 残差被 clip 成 +19.8，logit 区间随即退化为近乎整个支撑，说明
  "直接对原始口径的残差做 logit 变换"不可用，必须同时修正首期定义。

────────────────────────────────────────────────────────────────────────────
对照口径：截断 / 约束 bootstrap（"clamp_trunc" 与 "clamp_reject"）
────────────────────────────────────────────────────────────────────────────
以 raw_R29 的抽样路径为基础（不重算 bootstrap，仅对抽样值做约束）：
· clamp_trunc ：把每条路径的每个抽样值**截断**到 [0,1]（clip），并报告 2028 年
                抽样中落在端点的质量（ARIMA 上界处堆积多少概率）。
· clamp_reject：**拒绝**任何一年越出 [0,1] 的整条路径，再用保留的重计算分位，
                并报告保留比例。两种做法并列，便于看清"截断"把质量堆到边界、
                "拒绝"改变分布形状的代价。

────────────────────────────────────────────────────────────────────────────
输出（全部新文件，UTF-8-SIG）
────────────────────────────────────────────────────────────────────────────
  data/r44_bounded_intervals.csv      三模型 + 混合的逐年区间（raw / logit / 两种截断）
  data/r44_grade_prob_bounded.csv     逐年五级等级概率（logit 主口径 + raw 对照）
  data/r44_bounded_2028_summary.csv   2028 点值/区间/等级/margin/等级概率 汇总
  data/r44_bounded_old_vs_new.csv     旧口径（raw_R29）vs 新口径 逐格差异对照
  data/r44_bounded_checks.csv         自检结果

运行：python run_r44_bounded.py
"""
import os
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import r44_common as K  # noqa: E402

DATA = K.DATA
MODELS = K.MODELS
FUT_YEARS = K.FUT_YEARS
N_FUT = K.N_FUT
GRADES = K.GRADES
EPS = K.EPS

OUT_I = os.path.join(DATA, "r44_bounded_intervals.csv")
OUT_G = os.path.join(DATA, "r44_grade_prob_bounded.csv")
OUT_S = os.path.join(DATA, "r44_bounded_2028_summary.csv")
OUT_D = os.path.join(DATA, "r44_bounded_old_vs_new.csv")
OUT_C = os.path.join(DATA, "r44_bounded_checks.csv")

CAL_LOGIT = "logit_main"
CAL_LOGIT_NAIVE = "logit_naive_diagnostic"
CAL_RAW = "raw_R29"
CAL_RAW_REG = "raw_firstfix"
CAL_CLIP = "clamp_trunc"
CAL_REJ = "clamp_reject"
MAIN_WS = "invRMSE"

# run_r44_mixture.py 算出的主口径权重（同口径、同依据；此处硬编码以保证本脚本可独立运行，
# 并在运行开头与 data/r44_mixture_weights.csv 逐格核对）
W_INVRMSE = {"GM(1,1)": 0.3886858281381937, "NGBM": 0.2217284875289909,
             "ARIMA(0,1,1)": 0.3895856843328154}
W_EQUAL = {m: 1.0 / 3 for m in MODELS}


def stats_row(vals, target, caliber, ws, note, point):
    """vals (n, N_FUT) → 逐年区间行 + 2028 汇总行。"""
    vals = vals[np.all(np.isfinite(vals), axis=1)]
    lo = np.percentile(vals, 2.5, axis=0)
    hi = np.percentile(vals, 97.5, axis=0)
    irows, probs = [], []
    for k, y in enumerate(FUT_YEARS):
        pr = K.grade_probs(vals[:, k])
        probs.append(pr)
        irows.append({
            "target": target, "caliber": caliber, "weight_scheme": ws, "year": y,
            "point": round(float(point[k]), 6),
            "ci_lo_2.5": float(lo[k]), "ci_hi_97.5": float(hi[k]),
            "width95": float(hi[k] - lo[k]),
            "p50": float(np.percentile(vals[:, k], 50)),
            "lo_ge_0": bool(lo[k] >= 0.0), "hi_le_1": bool(hi[k] <= 1.0),
            "min_draw": float(np.min(vals[:, k])), "max_draw": float(np.max(vals[:, k])),
            "n_draws": int(vals.shape[0]), "note": note,
        })
    pv = float(point[-1])
    srow = {
        "target": target, "caliber": caliber, "weight_scheme": ws,
        "point_2028": round(pv, 6), "grade_2028": K.grade_of(pv),
        "margin_vs_0.400": round(pv - 0.400, 6),
        "ci_lo_2.5_2028": max(float(lo[-1]), 0.0) if caliber == CAL_CLIP else float(lo[-1]),
        "ci_hi_97.5_2028": min(float(hi[-1]), 1.0) if caliber == CAL_CLIP else float(hi[-1]),
        "width95_2028": float(hi[-1] - lo[-1]),
        "raw_lo_2.5_2028": float(lo[-1]), "raw_hi_97.5_2028": float(hi[-1]),
        "hi_exceeds_1_2028": bool(hi[-1] > 1.0), "lo_below_0_2028": bool(lo[-1] < 0.0),
        "p_severe_2028": probs[-1][0], "p_medium_2028": probs[-1][1],
        "p_mild_2028": probs[-1][2], "p_rel_safe_2028": probs[-1][3],
        "p_safe_2028": probs[-1][4],
        "p_below_0.400_2028": float(np.mean(vals[:, -1] < 0.4)),
        "modal_grade_2028": GRADES[int(np.argmax(probs[-1]))],
        "n_draws": int(vals.shape[0]), "note": note,
    }
    return irows, srow, probs


def main():
    print("=" * 78)
    print("R44 · 任务 2 —— 有界预测区间（logit 主口径 + 截断对照）")
    print("=" * 78)

    esi, years, dmax = K.load_esi()
    pt, _ = K.load_point_forecasts()
    checks = []

    def addcheck(item, value, note):
        checks.append({"item": item, "value": value, "note": note})

    # 权重核对
    wp = os.path.join(DATA, "r44_mixture_weights.csv")
    wmaxd = float("nan")
    if os.path.exists(wp):
        wdf = pd.read_csv(wp)
        sub = wdf[wdf.weight_scheme == MAIN_WS]
        wmaxd = float(max(abs(float(sub[sub.model == m].weight.iloc[0]) - W_INVRMSE[m])
                          for m in MODELS))
        addcheck("invRMSE_weight_vs_mixture_csv_max_abs_delta", "%.3e" % wmaxd,
                 "本脚本内置的 invRMSE 权重 vs data/r44_mixture_weights.csv（应一致）")

    # ---------- 0) logit 前提与 ARIMA 首期残差诊断 ----------
    print("\n" + "-" * 78)
    print("0) logit 变换前提与 ARIMA 首期拟合值诊断")
    print("-" * 78)
    n_at_bound = int(np.sum((esi <= 0.0) | (esi >= 1.0)))
    print("   八指标 ESI ∈ [%.6f, %.6f]；落在 0/1 边界的点数 = %d（0 ⇒ 无需平移）"
          % (esi.min(), esi.max(), n_at_bound))
    bf_naive = K.base_fits(esi, 0.15, False, "naive")
    bf_reg = K.base_fits(esi, 0.15, False, "reg")
    ar_naive = bf_naive["ARIMA(0,1,1)"][1]
    ar_reg = bf_reg["ARIMA(0,1,1)"][1]
    r_raw = esi - ar_naive
    r_raw_fix = esi - ar_reg
    r_log_naive = K.logit(esi) - K.logit(ar_naive)
    r_log = K.logit(esi) - K.logit(ar_reg)
    print("   ARIMA 首期 fittedvalue：naive %.6f / reg %.6f（实测 y_0 = %.6f）"
          % (ar_naive[0], ar_reg[0], esi[0]))
    print("   原始空间首期残差 naive %+.4f → reg %+.4f；最大**真实**残差（t≥1）%.4f"
          % (r_raw[0], r_raw_fix[0], float(np.max(np.abs(r_raw_fix[1:])))))
    print("   logit 尺度首期残差 naive %+.2f → reg %+.2f；最大真实 logit 残差 %.4f"
          % (r_log_naive[0], r_log[0], float(np.max(np.abs(r_log[1:])))))
    addcheck("esi_in_open_unit_interval", bool(n_at_bound == 0),
             "ESI 是否严格落在 (0,1)（0/1 点数 = %d）⇒ logit 无需平移" % n_at_bound)
    addcheck("arima_first_fitted_naive", "%.6f" % ar_naive[0],
             "statsmodels ARIMA(0,1,1) 首期 fittedvalue（不由递推式定义，实测 0）")
    addcheck("arima_first_resid_raw_naive", "%.4f" % r_raw[0],
             "该 0 值产生的虚假首期原始残差（R29 归档区间因此偏宽）")
    addcheck("arima_first_resid_logit_naive", "%.2f" % r_log_naive[0],
             "同一 0 值在 logit 尺度被 clip 成 +19.8，直接毁掉 logit 区间 ⇒ "
             "logit 口径必须同时用 first_fix=reg（仅影响第 1 个残差，不影响点预测）")
    addcheck("arima_max_true_resid_raw", "%.4f" % float(np.max(np.abs(r_raw_fix[1:]))),
             "首期规范后 ARIMA 原始空间残差的最大绝对值（真实值，用于说明残差池重尾程度）")
    addcheck("arima_max_true_resid_logit", "%.4f" % float(np.max(np.abs(r_log[1:]))),
             "首期规范后 ARIMA logit 尺度残差的最大绝对值（2006/2007 水平跃迁被 logit 放大）")

    # ---------- 1) bootstrap（三种空间口径，磁盘缓存共享） ----------
    print("\n" + "-" * 78)
    print("1) bootstrap（B=%d，seed=%d，块长=%d；与 run_r29_forecast_8ind.py 同机制）"
          % (K.B, K.SEED, K.BLOCK_L))
    print("-" * 78)
    bs = {}
    bs[CAL_RAW] = K.get_bootstrap(esi, space="raw", first_fix="naive")
    bs[CAL_RAW_REG] = K.get_bootstrap(esi, space="raw", first_fix="reg")
    bs[CAL_LOGIT] = K.get_bootstrap(esi, space="logit", first_fix="reg")
    bs[CAL_LOGIT_NAIVE] = K.get_bootstrap(esi, space="logit", first_fix="naive")
    for cal in [CAL_RAW, CAL_RAW_REG, CAL_LOGIT, CAL_LOGIT_NAIVE]:
        addcheck("bootstrap_n_valid_%s" % cal,
                 ";".join("%s=%d" % (m, bs[cal]["n_valid"][m]) for m in MODELS),
                 "口径 %s 的有效重复数（应为 2000）" % cal)

    # 复现 R29 归档（旧口径）
    r29r = pd.read_csv(os.path.join(DATA, "r29_2028_range.csv"))
    for m in MODELS:
        p = bs[CAL_RAW]["draws"][m]
        p = p[np.all(np.isfinite(p), axis=1)]
        got = float(np.percentile(p[:, -1], 97.5))
        exp = float(r29r[(r29r.row_type == "model")
                         & (r29r.model_or_scheme == m)]["ci_hi_97.5"].iloc[0])
        addcheck("repro_r29_2028_hi_%s" % m, "%.6f" % got,
                 "raw_R29 口径 2028 上界 vs R29 归档 %.6f（应一致）" % exp)

    # ---------- 2) 各口径的抽样值集合 ----------
    def clamp_trunc(vals):
        return np.clip(vals, 0.0, 1.0)

    def clamp_reject(vals):
        ok = np.all((vals >= 0.0) & (vals <= 1.0), axis=1)
        return vals[ok], float(np.mean(ok))

    print("\n" + "-" * 78)
    print("2) 三模型 2028 区间：raw（旧）/ logit（主）/ 截断 / 拒绝")
    print("-" * 78)
    irows, srows, grows = [], [], []
    for m in MODELS:
        pools = {
            CAL_RAW: bs[CAL_RAW]["draws"][m],
            CAL_RAW_REG: bs[CAL_RAW_REG]["draws"][m],
            CAL_LOGIT: bs[CAL_LOGIT]["draws"][m],
            CAL_LOGIT_NAIVE: bs[CAL_LOGIT_NAIVE]["draws"][m],
        }
        for cal in [CAL_RAW, CAL_RAW_REG, CAL_LOGIT, CAL_LOGIT_NAIVE]:
            v = pools[cal]
            v = v[np.all(np.isfinite(v), axis=1)]
            note = {"raw_R29": "旧口径：原始空间累积块新息（可逐格复现 R29 归档）",
                    "raw_firstfix": "诊断：原始空间，但 ARIMA 首期拟合值已规范为 y_0 —— 用于说明"
                                    "'只修首期残差'仍不能把区间压回 [0,1]",
                    "logit_main": "主口径：logit 尺度残差与累积新息，expit 逆变换 ⇒ 天然 ∈(0,1)；"
                                  "ARIMA 首期拟合值规范为 y_0",
                    "logit_naive_diagnostic": "诊断：logit 尺度但 ARIMA 首期拟合值原样保留 0.0"
                                              "（首期 logit 残差被 clip 成 +19.8）——说明该口径不可用"
                    }[cal]
            ir, sr, pr = stats_row(v, m, cal, "", note, pt[m])
            irows += ir
            srows.append(sr)
            for k, y in enumerate(FUT_YEARS):
                grows.append({"target": m, "caliber": cal, "weight_scheme": "", "year": y,
                              **{n: pr[k][j] for j, n in enumerate(
                                  ["p_severe", "p_medium", "p_mild", "p_rel_safe", "p_safe"])},
                              "prob_sum": float(sum(pr[k])),
                              "modal_grade": GRADES[int(np.argmax(pr[k]))],
                              "p_below_0.400": float(np.mean(v[:, k] < 0.4)),
                              "n_draws": int(v.shape[0]), "note": note})
        # 截断口径（基于旧口径抽样值）
        v = pools[CAL_RAW]
        v = v[np.all(np.isfinite(v), axis=1)]
        vt = clamp_trunc(v)
        ir, sr, pr = stats_row(vt, m, CAL_CLIP, "",
                               "对照口径 A：把 raw_R29 的抽样值**截断**到 [0,1]（clip）", pt[m])
        sr["mass_at_1_2028"] = float(np.mean(v[:, -1] >= 1.0))
        sr["mass_at_0_2028"] = float(np.mean(v[:, -1] <= 0.0))
        sr["mass_at_bound_2028"] = sr["mass_at_1_2028"] + sr["mass_at_0_2028"]
        irows += ir
        srows.append(sr)
        vr, keep = clamp_reject(v)
        ir, sr, pr = stats_row(vr, m, CAL_REJ, "",
                               "对照口径 B：**拒绝**任何一年越界（[0,1]）的整条路径后重算分位；"
                               "保留比例 %.4f" % keep, pt[m])
        sr["reject_keep_share"] = keep
        irows += ir
        srows.append(sr)
        print("   %-12s raw 2028 [%.4f, %.4f]%s | logit [%.4f, %.4f] | clip [%.4f, %.4f] "
              "| reject [%.4f, %.4f]（保留 %.3f）"
              % (m, np.percentile(v[:, -1], 2.5), np.percentile(v[:, -1], 97.5),
                 " ←>1" if np.percentile(v[:, -1], 97.5) > 1 else "",
                 np.percentile(pools[CAL_LOGIT][np.all(np.isfinite(pools[CAL_LOGIT]), axis=1)][:, -1], 2.5),
                 np.percentile(pools[CAL_LOGIT][np.all(np.isfinite(pools[CAL_LOGIT]), axis=1)][:, -1], 97.5),
                 np.percentile(vt[:, -1], 2.5), np.percentile(vt[:, -1], 97.5),
                 np.percentile(vr[:, -1], 2.5), np.percentile(vr[:, -1], 97.5), keep))

    # ---------- 3) 混合（主权重 invRMSE + 等权对照） ----------
    print("\n" + "-" * 78)
    print("3) 加权混合的区间（主口径 invRMSE；另报等权以对照 R29 归档 0.165645–0.945092）")
    print("-" * 78)

    def mix_pt(ws):
        w = W_INVRMSE if ws == MAIN_WS else W_EQUAL
        return np.array([sum(w[m] * pt[m][k] for m in MODELS) for k in range(N_FUT)])

    for ws, w in ((MAIN_WS, W_INVRMSE), ("equal", W_EQUAL)):
        for cal in [CAL_RAW, CAL_RAW_REG, CAL_LOGIT, CAL_LOGIT_NAIVE]:
            vals, counts, nreq = K.mixture_draws(bs[cal], w)
            note = ("预测分布的加权混合（N_MIX=%d, seed=%d）；权重方案 %s；口径 %s"
                    % (K.N_MIX, K.SEED_MIX, ws, cal))
            ir, sr, pr = stats_row(vals, "mixture", cal, ws, note, mix_pt(ws))
            sr["mix_counts"] = ";".join("%s=%d" % (m, counts[m]) for m in MODELS)
            irows += ir
            srows.append(sr)
            for k, y in enumerate(FUT_YEARS):
                grows.append({"target": "mixture", "caliber": cal, "weight_scheme": ws,
                              "year": y,
                              **{n: pr[k][j] for j, n in enumerate(
                                  ["p_severe", "p_medium", "p_mild", "p_rel_safe", "p_safe"])},
                              "prob_sum": float(sum(pr[k])),
                              "modal_grade": GRADES[int(np.argmax(pr[k]))],
                              "p_below_0.400": float(np.mean(vals[:, k] < 0.4)),
                              "n_draws": int(vals.shape[0]), "note": note})
        vals, counts, nreq = K.mixture_draws(bs[CAL_RAW], w)
        vt = clamp_trunc(vals)
        ir, sr, pr = stats_row(vt, "mixture", CAL_CLIP, ws,
                               "对照口径 A：截断到 [0,1]（clip）", mix_pt(ws))
        sr["mass_at_1_2028"] = float(np.mean(vals[:, -1] >= 1.0))
        sr["mass_at_bound_2028"] = sr["mass_at_1_2028"] + float(np.mean(vals[:, -1] <= 0.0))
        irows += ir
        srows.append(sr)
        vr, keep = clamp_reject(vals)
        ir, sr, pr = stats_row(vr, "mixture", CAL_REJ, ws,
                               "对照口径 B：拒绝越界路径，保留比例 %.4f" % keep, mix_pt(ws))
        sr["reject_keep_share"] = keep
        irows += ir
        srows.append(sr)
        vl = bs[CAL_LOGIT]
        pv = K.mixture_paired(vl, w)
        ir, sr, pr = stats_row(pv, "mixture", "logit_main_paired_diagnostic", ws,
                               "诊断：逐重复先加权平均（同情景误差抵消），非标准 BMA", mix_pt(ws))
        irows += ir
        srows.append(sr)
        o_ = [r for r in srows if r["target"] == "mixture" and r["caliber"] == CAL_RAW
              and r["weight_scheme"] == ws][0]
        l_ = [r for r in srows if r["target"] == "mixture" and r["caliber"] == CAL_LOGIT
              and r["weight_scheme"] == ws][0]
        print("   %-8s 2028 点值 %.6f | raw [%.4f, %.4f]%s | logit [%.4f, %.4f]%s "
              "| P(<0.4): raw %.4f / logit %.4f"
              % (ws, mix_pt(ws)[-1], o_["raw_lo_2.5_2028"], o_["raw_hi_97.5_2028"],
                 " >1" if o_["hi_exceeds_1_2028"] else "",
                 l_["raw_lo_2.5_2028"], l_["raw_hi_97.5_2028"],
                 " >1" if l_["hi_exceeds_1_2028"] else "",
                 o_["p_below_0.400_2028"], l_["p_below_0.400_2028"]))

    idf = pd.DataFrame(irows)
    idf.to_csv(OUT_I, index=False, encoding="utf-8-sig")
    gdf = pd.DataFrame(grows)
    gdf.to_csv(OUT_G, index=False, encoding="utf-8-sig")
    sdf = pd.DataFrame(srows)
    sdf.to_csv(OUT_S, index=False, encoding="utf-8-sig")

    # ---------- 4) 旧口径 vs 新口径 对照 ----------
    print("\n" + "-" * 78)
    print("4) 旧口径（raw_R29）vs 新口径（logit_main / 截断）差异对照")
    print("-" * 78)

    def get(target, cal, ws=""):
        s = sdf[(sdf.target == target) & (sdf.caliber == cal) & (sdf.weight_scheme == ws)]
        return s.iloc[0] if len(s) else None

    drows = []
    for target, ws in [(m, "") for m in MODELS] + [("mixture", MAIN_WS), ("mixture", "equal")]:
        o = get(target, CAL_RAW, ws)
        l = get(target, CAL_LOGIT, ws)
        c = get(target, CAL_CLIP, ws)
        rj = get(target, CAL_REJ, ws)
        drows.append({
            "target": target, "weight_scheme": ws,
            "old_caliber": CAL_RAW,
            "old_lo_2028": o["raw_lo_2.5_2028"], "old_hi_2028": o["raw_hi_97.5_2028"],
            "old_width95_2028": o["width95_2028"],
            "old_hi_exceeds_1": o["hi_exceeds_1_2028"],
            "new_logit_lo_2028": l["raw_lo_2.5_2028"], "new_logit_hi_2028": l["raw_hi_97.5_2028"],
            "new_logit_width95_2028": l["width95_2028"],
            "new_logit_hi_exceeds_1": l["hi_exceeds_1_2028"],
            "delta_lo_logit_minus_old": l["raw_lo_2.5_2028"] - o["raw_lo_2.5_2028"],
            "delta_hi_logit_minus_old": l["raw_hi_97.5_2028"] - o["raw_hi_97.5_2028"],
            "delta_width_logit_minus_old": l["width95_2028"] - o["width95_2028"],
            "clip_lo_2028": c["raw_lo_2.5_2028"], "clip_hi_2028": c["raw_hi_97.5_2028"],
            "clip_mass_at_bound_2028": c.get("mass_at_bound_2028", np.nan),
            "reject_lo_2028": rj["raw_lo_2.5_2028"], "reject_hi_2028": rj["raw_hi_97.5_2028"],
            "reject_keep_share": rj.get("reject_keep_share", np.nan),
            "note": ("旧口径上界 >1 时，logit 口径把同一不确定性压回 (0,1)；"
                     "截断口径把质量堆在端点，拒绝口径改变分布形状"),
        })
        print("   %-14s(%-8s) 旧 [%.4f, %.4f]%s → logit [%.4f, %.4f]%s（Δlo %+.4f, Δhi %+.4f, "
              "Δwidth %+.4f）"
              % (target, ws, o["raw_lo_2.5_2028"], o["raw_hi_97.5_2028"],
                 " >1" if o["hi_exceeds_1_2028"] else "",
                 l["raw_lo_2.5_2028"], l["raw_hi_97.5_2028"],
                 " >1" if l["hi_exceeds_1_2028"] else "",
                 l["raw_lo_2.5_2028"] - o["raw_lo_2.5_2028"],
                 l["raw_hi_97.5_2028"] - o["raw_hi_97.5_2028"],
                 l["width95_2028"] - o["width95_2028"]))
    pd.DataFrame(drows).to_csv(OUT_D, index=False, encoding="utf-8-sig")

    # ---------- 5) 自检 ----------
    print("\n" + "-" * 78)
    print("5) 自检")
    print("-" * 78)
    logit_rows = idf[idf.caliber == CAL_LOGIT]
    addcheck("logit_all_lo_ge_0", bool(logit_rows["lo_ge_0"].all()),
             "logit 主口径：全部目标/全部年份的下界是否 >= 0")
    addcheck("logit_all_hi_le_1", bool(logit_rows["hi_le_1"].all()),
             "logit 主口径：全部目标/全部年份的上界是否 <= 1")
    addcheck("logit_all_draws_in_open_unit_interval",
             bool((logit_rows["min_draw"] > 0).all() and (logit_rows["max_draw"] < 1).all()),
             "logit 主口径：抽样值是否严格落在 (0,1)（用各年 min/max 抽样值判定）")
    addcheck("clamp_trunc_all_bounds_in_0_1",
             bool(idf[idf.caliber == CAL_CLIP]["lo_ge_0"].all()
                  and idf[idf.caliber == CAL_CLIP]["hi_le_1"].all()),
             "截断口径（clip）：全部区间是否落在 [0,1]")
    addcheck("clamp_reject_all_bounds_in_0_1",
             bool(idf[idf.caliber == CAL_REJ]["lo_ge_0"].all()
                  and idf[idf.caliber == CAL_REJ]["hi_le_1"].all()),
             "拒绝口径：全部区间是否落在 [0,1]")
    addcheck("raw_hi_exceeds_1_targets",
             ";".join(sorted(set(sdf[(sdf.caliber == CAL_RAW)
                                     & (sdf["hi_exceeds_1_2028"])]["target"]))),
             "旧口径（raw_R29）2028 上界 >1 的目标（复现审稿意见⑤）")
    addcheck("grade_prob_sum_max_abs_dev", "%.3e" % float(np.abs(gdf["prob_sum"] - 1.0).max()),
             "全部（目标 × 口径 × 年）五级等级概率和与 1 的最大偏差")
    addcheck("logit_2028_grade_prob_reported_for",
             ";".join(sorted(set(gdf[(gdf.caliber == CAL_LOGIT)]["target"]))),
             "logit 主口径等级概率覆盖的目标（三模型 + 混合）")
    ar = get("ARIMA(0,1,1)", CAL_RAW, "")
    al = get("ARIMA(0,1,1)", CAL_LOGIT, "")
    addcheck("arima_2028_old_hi", round(float(ar["raw_hi_97.5_2028"]), 6),
             "旧口径 ARIMA 2028 上界（= R29 归档 1.112674，越界）")
    addcheck("arima_2028_logit_interval", "[%.6f, %.6f]" % (al["raw_lo_2.5_2028"],
                                                            al["raw_hi_97.5_2028"]),
             "logit 主口径 ARIMA 2028 区间（有界，但**几乎覆盖整个支撑**⇒ 不宜引用为 ESI 区间）")
    addcheck("arima_2028_logit_p_below_0.4", round(float(al["p_below_0.400_2028"]), 6),
             "logit 主口径 ARIMA 2028 P(ESI<0.400)；与点值 0.484610（轻警）矛盾 ⇒ "
             "ARIMA 的块 bootstrap 区间由少数早期残差驱动，应改报条件概率而非区间")
    me = get("mixture", CAL_RAW, "equal")
    addcheck("mixture_equal_2028_old_interval",
             "[%.6f, %.6f]" % (me["raw_lo_2.5_2028"], me["raw_hi_97.5_2028"]),
             "旧等权混合 2028 区间；R29 归档 [0.165645, 0.945092]")
    ml = get("mixture", CAL_LOGIT, "equal")
    mc = get("mixture", CAL_LOGIT, MAIN_WS)
    addcheck("mixture_logit_2028_interval",
             "[%.6f, %.6f]" % (mc["raw_lo_2.5_2028"], mc["raw_hi_97.5_2028"]),
             "主口径（invRMSE）混合 logit 2028 区间（有界）")
    addcheck("mixture_logit_2028_interval_equal",
             "[%.6f, %.6f]" % (ml["raw_lo_2.5_2028"], ml["raw_hi_97.5_2028"]),
             "等权混合 logit 2028 区间（与旧等权归档对照）")
    addcheck("source_csv_md5_r28_deredundancy",
             K.file_md5(os.path.join(DATA, "r28_deredundancy_series.csv")),
             "输入：八指标 ESI 序列")

    # ---- 首期拟合值规范**不改变任何点预测**的逐位证据 ----
    pt_naive = {"ARIMA(0,1,1)": K.fp_arima(esi, first_fix="naive")[0],
                "GM(1,1)": K.fp_gm(esi)[0], "NGBM": K.fp_ngbm_fixed(esi, 0.15)[0]}
    pt_reg = {"ARIMA(0,1,1)": K.fp_arima(esi, first_fix="reg")[0],
              "GM(1,1)": K.fp_gm(esi)[0], "NGBM": K.fp_ngbm_fixed(esi, 0.15)[0]}
    for m in MODELS:
        d = float(np.max(np.abs(np.asarray(pt_naive[m]) - np.asarray(pt_reg[m]))))
        da = float(np.max(np.abs(np.asarray(pt_reg[m]) - pt[m])))
        addcheck("point_forecast_identical_naive_vs_reg_%s" % m, "%.1e" % d,
                 "首期拟合值 naive vs reg 的 2024–2028 点预测最大绝对差（应为 0.0e+00，"
                 "逐位相同）")
        addcheck("point_forecast_vs_r29_archive_%s" % m, "%.1e" % da,
                 "本脚本重算点预测 vs data/r29_forecast_8ind.csv 归档值最大绝对差")

    addcheck("script", "run_r44_bounded.py", "生成脚本（新建，未改动任何既有脚本）")
    pd.DataFrame(checks).to_csv(OUT_C, index=False, encoding="utf-8-sig")

    # ---- 发布父 agent 指定的最终文件名（内容与上列一致，便于主笔直接引用） ----
    alias = {}
    try:
        gdf.to_csv(os.path.join(DATA, "r44_grade_prob.csv"), index=False,
                   encoding="utf-8-sig")
        alias["r44_grade_prob.csv"] = "= r44_grade_prob_bounded.csv"
        sdf.to_csv(os.path.join(DATA, "r44_2028_summary.csv"), index=False,
                   encoding="utf-8-sig")
        alias["r44_2028_summary.csv"] = "= r44_bounded_2028_summary.csv"
        mc = os.path.join(DATA, "r44_mixture_checks.csv")
        parts = []
        if os.path.exists(mc):
            t = pd.read_csv(mc)
            t.insert(0, "task", "1_mixture")
            parts.append(t)
        t2 = pd.read_csv(OUT_C)
        t2.insert(0, "task", "2_bounded")
        parts.append(t2)
        pd.concat(parts, ignore_index=True).to_csv(
            os.path.join(DATA, "r44_checks.csv"), index=False, encoding="utf-8-sig")
        alias["r44_checks.csv"] = "= r44_mixture_checks.csv + r44_bounded_checks.csv（含 task 列）"
    except Exception as e:                                    # pragma: no cover
        print("   [警告] 别名文件写出失败：%r" % e)
    for k, v in alias.items():
        print("   [别名] %s %s" % (k, v))
    for c in checks:
        print("   %-46s %s" % (c["item"], c["value"]))
    print("\n写出：\n  %s\n  %s\n  %s\n  %s\n  %s"
          % (OUT_I, OUT_G, OUT_S, OUT_D, OUT_C))
    return 0


if __name__ == "__main__":
    sys.exit(main())