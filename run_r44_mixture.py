# -*- coding: utf-8 -*-
"""R44 · 任务 1 —— 用**逆性能权重**替换等权混合（八指标主规格 2024–2028）

────────────────────────────────────────────────────────────────────────────
问题
────────────────────────────────────────────────────────────────────────────
R29 的 model-averaged 采用**等权**（w_k = 1/3）混合 GM(1,1) / NGBM / ARIMA，
但八指标五种验证方案里 NGBM **全部最差**（五个方案 RMSE 排名均为第 3），
等权因此没有依据。本脚本用样本外精度定权，并把权重敏感性一并报出。

────────────────────────────────────────────────────────────────────────────
权重依据（写明用哪一张表、哪一列）
────────────────────────────────────────────────────────────────────────────
主口径 = **data/r32_validation_8ind.csv，列 `rmse`**（八指标主规格 drop_X9 的
         五方案样本外 RMSE），跨五方案按列 `n_predictions` **加权池化**：
             RMSE_pooled = sqrt( Σ_s n_s · rmse_s² / Σ_s n_s )
         该池化值与 data/r32_validation_8ind_detail.csv 逐评估点重算的池化
         RMSE 逐位一致（本脚本校验，容差 1e-12）。
  w_i ∝ 1 / RMSE_i，归一化。
  （不用 data/r42_table7_accuracy.csv::rmse 作主口径：那是 2005–2023 **全序列
    拟合**精度，属样本内口径；且 r42 自查已注明该表 NGBM 行"超出本仓库模型族
    可达精度"、不可由本仓库脚本复现。它作为**敏感性**方案之一报出。）

对照 / 敏感性权重方案：
  invMSE            w ∝ 1/RMSE²（对差模型惩罚更重）
  stacking          w = argmin_w ||Σ w_i · pred_i − obs||², s.t. Σw=1, w≥0，
                    在 r32_validation_8ind_detail.csv 的 72 个样本外评估点上求解
                    （scipy SLSQP）；另报 leave-one-scheme-out 交叉验证版 stacking
                    （权重只由其余四方案估计）与同一协议的 invRMSE_LOSO，
                    用于判断"用同一批折定权重又在同一批折上评分"的乐观程度。
  equal             w = 1/3（现状对照）
  invRMSE_schemeMean  敏感性：五方案 RMSE 的**简单平均**作依据（不按点数加权）
  invRMSE_fitTable7   敏感性：data/r42_table7_accuracy.csv::rmse（全序列拟合口径）

────────────────────────────────────────────────────────────────────────────
口径与种子
────────────────────────────────────────────────────────────────────────────
· 目标序列、α=0.4、五级阈值、三模型实现、bootstrap 机制与种子**全部**沿用
  run_r29_forecast_8ind.py（见 r44_common.py 的 docstring）；B=2000，seed=20261017，
  块长 L=3，NGBM 每个重复重选 γ（训练期 2005–2018 SSE 目标，γ*=0.15）。
· 混合点预测 = Σ w_k · 点预测_k（点预测直接取 data/r29_forecast_8ind.csv 的三列，
  不重算，保证与论文一致）。
· 混合区间主口径 = 预测分布的加权混合（R29 的 "pooled draws"）：按 w_k 从各模型
  的 bootstrap 有效重复中抽样拼接（N_MIX=6000，seed=20261024）；同时给
  "paired replicates"（逐重复先加权平均，方差被同情景抵消）作诊断行。
· 区间空间：raw_R29（原始空间，可逐格复现 R29 归档旧口径）与 logit_main
  （有界口径，见 run_r44_bounded.py；任务 2 的主口径）。

────────────────────────────────────────────────────────────────────────────
输出（全部新文件，UTF-8-SIG）
────────────────────────────────────────────────────────────────────────────
  data/r44_mixture_weights.csv       每种权重方案的逐模型权重与依据
  data/r44_mixture_forecast.csv      2024–2028 三模型 + 各权重方案混合点值/等级
  data/r44_mixture_accuracy.csv      混合序列 RMSE/MAE（逐方案 / 池化 / LOSO）
  data/r44_mixture_grade_prob.csv    逐年五级等级概率（混合 × 权重方案 × 口径）
  data/r44_mixture_2028.csv          2028 点值/区间/等级/margin/等级概率/敏感性
  data/r44_mixture_checks.csv        自检结果

运行：python run_r44_mixture.py
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
THR = K.THR

OUT_W = os.path.join(DATA, "r44_mixture_weights.csv")
OUT_F = os.path.join(DATA, "r44_mixture_forecast.csv")
OUT_A = os.path.join(DATA, "r44_mixture_accuracy.csv")
OUT_G = os.path.join(DATA, "r44_mixture_grade_prob.csv")
OUT_2K = os.path.join(DATA, "r44_mixture_2028.csv")
OUT_C = os.path.join(DATA, "r44_mixture_checks.csv")

DETNAME = {"GM(1,1)": "GM(1,1)", "NGBM": "NGBM", "ARIMA(0,1,1)": "ARIMA"}
SCHEME_ORDER = ["holdout_2019_2023", "loocv_leave_one_year_out",
                "rolling_1step_from2013", "rolling_1step_from2015",
                "rolling_5step_from2013"]
MAIN_WS = "invRMSE"
CALIBERS = ["raw_R29", "logit_main"]


# ---------------------------------------------------------------------------
def rmse_mae(pred, obs):
    e = np.asarray(pred, float) - np.asarray(obs, float)
    return float(np.sqrt(np.mean(e ** 2))), float(np.mean(np.abs(e)))


def basis_from_r32():
    """主口径与两个 rmse 依据变体：全部取自 data/r32_validation_8ind.csv::rmse。"""
    v = pd.read_csv(os.path.join(DATA, "r32_validation_8ind.csv"))
    v = v[v.model.isin(["GM(1,1)", "NGBM", "ARIMA"])].copy()
    assert set(v.scheme.unique()) == set(SCHEME_ORDER), v.scheme.unique()
    n = dict(zip(v.scheme, v.n_predictions.astype(float)))
    pooled, smean = {}, {}
    for m in MODELS:
        sub = v[v.model == DETNAME[m]]
        assert len(sub) == 5, m
        num = float(sum(sub.rmse.values ** 2 * sub.n_predictions.values))
        den = float(sum(sub.n_predictions.values))
        pooled[m] = float(np.sqrt(num / den))
        smean[m] = float(np.mean(sub.rmse.values))
    return pooled, smean, v


def basis_from_table7():
    t = pd.read_csv(os.path.join(DATA, "r42_table7_accuracy.csv"))
    name = {"GM(1,1)": "GM(1,1)", "NGBM": "NGBM (gamma=0.15)", "ARIMA(0,1,1)": "ARIMA(0,1,1)"}
    return {m: float(t.loc[t.model == name[m], "rmse"].iloc[0]) for m in MODELS}


def load_detail():
    """r32_validation_8ind_detail.csv 的八指标 / 固定阶数协议子集（72 个评估点）。"""
    d = pd.read_csv(os.path.join(DATA, "r32_validation_8ind_detail.csv"))
    d = d[(d.series == "eight") & (d.arima_protocol == "fixed")].copy()
    key = ["scheme", "fold", "horizon", "target_year"]
    wide = d.pivot_table(index=key, columns="model", values="predicted",
                         aggfunc="first").reset_index()
    obs = d.groupby(key)["observed"].first().reset_index()
    wide = wide.merge(obs, on=key, how="left")
    assert wide["observed"].notna().all()
    for m in MODELS:
        assert DETNAME[m] in wide.columns, m
    # 与 r32_validation_8ind.csv 的逐方案 RMSE 对齐校验
    v = pd.read_csv(os.path.join(DATA, "r32_validation_8ind.csv"))
    maxd = 0.0
    for sch in SCHEME_ORDER:
        g = wide[wide.scheme == sch]
        for m in MODELS:
            r1 = rmse_mae(g[DETNAME[m]].values, g["observed"].values)[0]
            r2 = float(v[(v.scheme == sch) & (v.model == DETNAME[m])].rmse.iloc[0])
            maxd = max(maxd, abs(r1 - r2))
    return wide, maxd


def fit_stacking(P, y):
    from scipy.optimize import minimize
    P = np.asarray(P, float)
    y = np.asarray(y, float)

    def f(w):
        r = P @ w - y
        return float(r @ r)

    res = minimize(f, np.ones(P.shape[1]) / P.shape[1], method="SLSQP",
                   bounds=[(0.0, 1.0)] * P.shape[1],
                   constraints=[{"type": "eq", "fun": lambda w: float(w.sum() - 1.0)}],
                   options={"maxiter": 800, "ftol": 1e-14})
    w = res.x if (res.success and np.all(np.isfinite(res.x))) else np.ones(P.shape[1]) / P.shape[1]
    return np.clip(w, 0.0, 1.0) / np.clip(w, 0.0, 1.0).sum()


def inv_w(basis):
    inv = {m: 1.0 / basis[m] for m in MODELS}
    s = sum(inv.values())
    return {m: inv[m] / s for m in MODELS}


def main():
    print("=" * 78)
    print("R44 · 任务 1 —— 逆性能加权混合（替换等权）")
    print("=" * 78)

    esi, years, dmax = K.load_esi()
    pt, ptcol = K.load_point_forecasts()
    gamma_train = float(K.select_gamma(esi[:K.N_TRAIN], "sse")[1])
    print("[序列] 八指标 ESI 2005–2023，与归档 max|Δ| = %.3e；训练期 SSE 最优 γ = %.2f"
          % (dmax, gamma_train))

    checks = []

    def addcheck(item, value, note):
        checks.append({"item": item, "value": value, "note": note})

    addcheck("esi_8ind_vs_r28_archive_max_abs_delta", "%.3e" % dmax,
             "八指标 ESI 重建 vs %s" % K.SOURCES["series"])
    addcheck("ngbm_gamma_train_sse", gamma_train,
             "主 NGBM 的 γ（仅训练期 2005–2018 SSE 目标，无泄漏）；bootstrap 内每重复重选")

    # ---------- 1) 精度依据与权重 ----------
    print("\n" + "-" * 78)
    print("1) 精度依据（主口径：r32_validation_8ind.csv::rmse，按 n_predictions 池化）")
    print("-" * 78)
    pooled, smean, vraw = basis_from_r32()
    fit7 = basis_from_table7()
    wide, align_dmax = load_detail()
    addcheck("detail_vs_r32_scheme_rmse_max_abs_delta", "%.3e" % align_dmax,
             "逐评估点重算的逐方案 RMSE vs %s::rmse 逐格对齐（应为 0）"
             % K.SOURCES["validation"])
    for m in MODELS:
        print("   %-12s 池化样本外 RMSE %.6f | 五方案简单平均 %.6f | Table7 拟合 RMSE %.6f"
              % (m, pooled[m], smean[m], fit7[m]))

    P = wide[[DETNAME[m] for m in MODELS]].values
    obs = wide["observed"].values
    w_stack = fit_stacking(P, obs)
    # LOSO 交叉验证版权重
    loso_w = {}
    for sch in SCHEME_ORDER:
        rest = wide[wide.scheme != sch]
        Pr = rest[[DETNAME[m] for m in MODELS]].values
        loso_w[sch] = fit_stacking(Pr, rest["observed"].values)
    w_stack_loso = {m: float(np.mean([loso_w[s][i] for s in SCHEME_ORDER]))
                    for i, m in enumerate(MODELS)}
    loso_inv = {}
    for sch in SCHEME_ORDER:
        rest = wide[wide.scheme != sch]
        b = {m: rmse_mae(rest[DETNAME[m]].values, rest["observed"].values)[0] for m in MODELS}
        loso_inv[sch] = inv_w(b)
    loso_wd = {s: {m: float(loso_w[s][i]) for i, m in enumerate(MODELS)} for s in SCHEME_ORDER}

    W = {
        "invRMSE": inv_w(pooled),
        "invMSE": inv_w({m: pooled[m] ** 2 for m in MODELS}),
        "stacking": {m: float(w_stack[i]) for i, m in enumerate(MODELS)},
        "equal": {m: 1.0 / 3 for m in MODELS},
        "invRMSE_schemeMean": inv_w(smean),
        "invRMSE_fitTable7": inv_w(fit7),
        "pair_GM_ARIMA": {"GM(1,1)": 0.5, "NGBM": 0.0, "ARIMA(0,1,1)": 0.5},
    }
    BASIS_LABEL = {
        "invRMSE": ("r32_validation_8ind.csv::rmse 五方案按 n_predictions 池化（主口径）",
                    pooled),
        "invMSE": ("同主口径，权重 ∝ 1/RMSE²", pooled),
        "stacking": ("r32_validation_8ind_detail.csv 的 72 个样本外评估点，SLSQP 求 "
                     "Σw=1,w≥0 的最小二乘解", pooled),
        "equal": ("等权（R29 现口径）", pooled),
        "invRMSE_schemeMean": ("r32_validation_8ind.csv::rmse 五方案**简单平均**（敏感性）",
                               smean),
        "invRMSE_fitTable7": ("r42_table7_accuracy.csv::rmse 全序列拟合（敏感性，样本内口径）",
                              fit7),
        "pair_GM_ARIMA": ("等权两模型混合（剔除五方案中全部最差的 NGBM；敏感性）", pooled),
    }
    for ws in W:
        assert abs(sum(W[ws].values()) - 1.0) < 1e-12, ws
        print("   %-20s w = %s" % (ws, {m: round(W[ws][m], 6) for m in MODELS}))
    print("   [LOSO 版 stacking 权重均值] %s" % {m: round(w_stack_loso[m], 6) for m in MODELS})
    addcheck("weight_sum_invRMSE", round(sum(W["invRMSE"].values()), 12), "逆 RMSE 权重和（应为 1）")
    addcheck("weight_sum_invMSE", round(sum(W["invMSE"].values()), 12), "逆 MSE 权重和（应为 1）")
    addcheck("weight_sum_stacking", round(sum(W["stacking"].values()), 12), "stacking 权重和（应为 1）")
    addcheck("weight_sum_equal", round(sum(W["equal"].values()), 12), "等权权重和（应为 1）")

    wrows = []
    for ws in W:
        lab, basis = BASIS_LABEL[ws]
        for m in MODELS:
            wrows.append({"weight_scheme": ws, "model": m,
                          "basis_rmse": float(basis[m]),
                          "basis_mse": float(basis[m]) ** 2,
                          "weight": float(W[ws][m]),
                          "is_main": bool(ws == MAIN_WS),
                          "basis_source": lab,
                          "note": ("w_i ∝ 1/RMSE_i 归一（invRMSE 系）" if ws.startswith("invRMSE")
                                   else ("w_i ∝ 1/RMSE_i² 归一" if ws == "invMSE"
                                         else ("SLSQP 最小二乘单纯形解" if ws == "stacking"
                                               else "等权对照"))),
                          })
    for sch in SCHEME_ORDER:
        for i, m in enumerate(MODELS):
            wrows.append({"weight_scheme": "invRMSE_LOSO", "model": m,
                          "basis_rmse": np.nan, "basis_mse": np.nan,
                          "weight": float(loso_inv[sch][m]), "is_main": False,
                          "basis_source": "leave-one-scheme-out：权重只由其余四方案估计",
                          "note": "held-out scheme = %s" % sch})
            wrows.append({"weight_scheme": "stacking_LOSO", "model": m,
                          "basis_rmse": np.nan, "basis_mse": np.nan,
                          "weight": float(loso_w[sch][i]), "is_main": False,
                          "basis_source": "leave-one-scheme-out：权重只由其余四方案估计",
                          "note": "held-out scheme = %s" % sch})
    pd.DataFrame(wrows).to_csv(OUT_W, index=False, encoding="utf-8-sig")

    # ---------- 2) 混合精度（与三模型可比口径） ----------
    print("\n" + "-" * 78)
    print("2) 混合序列 RMSE/MAE（样本外，同一批 72 个评估点）")
    print("-" * 78)
    arows = []
    per_scheme = {}
    for sch in SCHEME_ORDER:
        g = wide[wide.scheme == sch]
        per_scheme[sch] = {}
        for m in MODELS:
            r_, a_ = rmse_mae(g[DETNAME[m]].values, g["observed"].values)
            per_scheme[sch][m] = (r_, a_)
            arows.append({"scope": sch, "target": m, "rmse": r_, "mae": a_,
                          "n_points": int(len(g)), "weight_scheme": "",
                          "note": "逐模型样本外精度（权重依据的底层数据）"})
    pooled_acc = {m: rmse_mae(wide[DETNAME[m]].values, obs) for m in MODELS}
    for m in MODELS:
        arows.append({"scope": "pooled_72_oos_points", "target": m, "rmse": pooled_acc[m][0],
                      "mae": pooled_acc[m][1], "n_points": int(len(wide)),
                      "weight_scheme": "", "note": "池化样本外精度（= 主口径权重依据）"})
        print("   %-12s 池化 RMSE %.6f  MAE %.6f" % (m, pooled_acc[m][0], pooled_acc[m][1]))

    mixed_pred = {}
    for ws in W:
        pred = sum(W[ws][m] * wide[DETNAME[m]].values for m in MODELS)
        mixed_pred[(ws, "pooled")] = pred
        r_, a_ = rmse_mae(pred, obs)
        arows.append({"scope": "pooled_72_oos_points", "target": "mixture", "rmse": r_,
                      "mae": a_, "n_points": int(len(wide)), "weight_scheme": ws,
                      "note": "混合池化样本外精度（**权重与评分同折，含乐观性**）"})
        print("   混合 %-20s 池化 RMSE %.6f  MAE %.6f" % (ws, r_, a_))
        for sch in SCHEME_ORDER:
            g = wide[wide.scheme == sch]
            pr = sum(W[ws][m] * g[DETNAME[m]].values for m in MODELS)
            r_, a_ = rmse_mae(pr, g["observed"].values)
            arows.append({"scope": sch, "target": "mixture", "rmse": r_, "mae": a_,
                          "n_points": int(len(g)), "weight_scheme": ws,
                          "note": "混合逐方案样本外精度（权重与评分同折，含乐观性）"})
        # LOSO（诚实口径）
        for sch in SCHEME_ORDER:
            g = wide[wide.scheme == sch]
            for tag, wl_d in (("invRMSE_LOSO", loso_inv[sch]),
                              ("stacking_LOSO", loso_wd[sch])):
                if ws not in ("invRMSE", "stacking"):
                    continue
                pr = sum(wl_d[m] * g[DETNAME[m]].values for m in MODELS)
                r_, a_ = rmse_mae(pr, g["observed"].values)
                arows.append({"scope": sch, "target": "mixture", "rmse": r_, "mae": a_,
                              "n_points": int(len(g)), "weight_scheme": tag,
                              "note": "leave-one-scheme-out：权重只由其余四方案估计（诚实口径）"})
    for tag, wfun in (("invRMSE_LOSO", lambda s: loso_inv[s]),
                      ("stacking_LOSO", lambda s: loso_wd[s])):
        pr = np.concatenate([sum(wfun(s)[m] * wide[wide.scheme == s][DETNAME[m]].values
                                 for m in MODELS) for s in SCHEME_ORDER])
        r_, a_ = rmse_mae(pr, obs)
        arows.append({"scope": "pooled_72_oos_points", "target": "mixture", "rmse": r_,
                      "mae": a_, "n_points": int(len(wide)), "weight_scheme": tag,
                      "note": "leave-one-scheme-out 池化（诚实口径，无权重自选乐观性）"})
        print("   混合 %-20s 池化 RMSE %.6f  MAE %.6f（诚实口径）" % (tag, r_, a_))
    pd.DataFrame(arows).to_csv(OUT_A, index=False, encoding="utf-8-sig")

    # ---------- 3) 混合点预测 2024–2028 ----------
    print("\n" + "-" * 78)
    print("3) 混合点预测 2024–2028（= Σ w_k · 三模型点预测，点预测取自 R29 归档）")
    print("-" * 78)
    mix_pt = {ws: np.array([sum(W[ws][m] * pt[m][k] for m in MODELS) for k in range(N_FUT)])
              for ws in W}
    for ws in W:
        print("   %-20s %s | 2028 %.6f  等级 %s  margin %+.6f"
              % (ws, " ".join("%.4f" % x for x in mix_pt[ws]), mix_pt[ws][-1],
                 K.grade_of(mix_pt[ws][-1]), mix_pt[ws][-1] - 0.4))
    for m in MODELS:
        print("   [模型] %-12s %s | 2028 %.6f" % (m, " ".join("%.4f" % x for x in pt[m]), pt[m][-1]))

    rows = []
    for k, y in enumerate(FUT_YEARS):
        r = {"year": y}
        for m in MODELS:
            r["model_" + m] = round(float(pt[m][k]), 6)
        for ws in W:
            r["mix_" + ws] = round(float(mix_pt[ws][k]), 6)
        r["mix_invRMSE_grade"] = K.grade_of(mix_pt["invRMSE"][k])
        r["mix_equal_grade"] = K.grade_of(mix_pt["equal"][k])
        r["note"] = ("三模型列取自 %s（gm11_8ind / ngbm_8ind_gamma_train / "
                     "arima_011_8ind）；混合列 = 加权混合点值" % K.SOURCES["forecast"])
        rows.append(r)
    pd.DataFrame(rows).to_csv(OUT_F, index=False, encoding="utf-8-sig")

    # ---------- 4) bootstrap（混合区间与等级概率） ----------
    print("\n" + "-" * 78)
    print("4) bootstrap（B=%d, seed=%d, 块长=%d, NGBM 每重复重选 γ）"
          % (K.B, K.SEED, K.BLOCK_L))
    print("-" * 78)
    bs = {"raw_R29": K.get_bootstrap(esi, space="raw", first_fix="naive"),
          "logit_main": K.get_bootstrap(esi, space="logit", first_fix="reg")}
    for cal in CALIBERS:
        addcheck("bootstrap_n_valid_%s" % cal,
                 ";".join("%s=%d" % (m, bs[cal]["n_valid"][m]) for m in MODELS),
                 "口径 %s 的有效重复数（应为 2000）" % cal)
    r29r = pd.read_csv(os.path.join(DATA, "r29_2028_range.csv"))

    def r29val(rt, name, col):
        s = r29r[(r29r.row_type == rt) & (r29r.model_or_scheme == name)]
        return float(s[col].iloc[0]) if len(s) else float("nan")

    for m in MODELS:
        pool = bs["raw_R29"]["draws"][m]
        pool = pool[np.all(np.isfinite(pool), axis=1)]
        got = float(np.percentile(pool[:, -1], 97.5))
        exp = r29val("model", m, "ci_hi_97.5")
        addcheck("repro_r29_2028_hi_%s" % m, "%.6f" % got,
                 "raw_R29 口径 2028 上界；R29 归档 %.6f（应一致，Δ=%.2e）"
                 % (exp, got - exp))
        print("   [复现] %-12s raw_R29 2028 上界 %.6f vs R29 归档 %.6f" % (m, got, exp))

    grade_rows, mix_summary = [], {}
    for ws in W:
        for cal in CALIBERS:
            vals, counts, nreq = K.mixture_draws(bs[cal], W[ws])
            lo, hi, wid, probs, n = K.summarize_vals(vals, mix_pt[ws])
            mix_summary[(ws, cal)] = (lo, hi, probs, n, counts, vals)
            for k, y in enumerate(FUT_YEARS):
                grade_rows.append({
                    "target": "mixture", "caliber": cal, "weight_scheme": ws, "year": y,
                    "p_severe": probs[k][0], "p_medium": probs[k][1], "p_mild": probs[k][2],
                    "p_rel_safe": probs[k][3], "p_safe": probs[k][4],
                    "prob_sum": float(sum(probs[k])),
                    "modal_grade": GRADES[int(np.argmax(probs[k]))],
                    "p_modal": float(max(probs[k])),
                    "p_below_0.400": float(np.mean(vals[:, k] < 0.4)),
                    "p_below_0.200": float(np.mean(vals[:, k] < 0.2)),
                    "boot_mean": float(np.mean(vals[:, k])),
                    "lo_2.5": float(lo[k]), "hi_97.5": float(hi[k]),
                    "hi_exceeds_1": bool(hi[k] > 1.0), "lo_below_0": bool(lo[k] < 0.0),
                    "n_draws": int(n),
                    "note": "混合预测分布的加权抽样（N_MIX=%d，seed=%d）；口径 %s"
                            % (K.N_MIX, K.SEED_MIX, cal),
                })
    gdf = pd.DataFrame(grade_rows)
    gdf.to_csv(OUT_G, index=False, encoding="utf-8-sig")
    addcheck("grade_prob_sum_max_abs_dev", "%.3e" % float(np.abs(gdf["prob_sum"] - 1.0).max()),
             "全部（混合 × 权重方案 × 口径 × 年）五级概率和与 1 的最大偏差（应为 0）")

    # ---------- 5) 2028 汇总结论与敏感性 ----------
    print("\n" + "-" * 78)
    print("5) 2028 混合点值/区间/等级 与**权重敏感性**")
    print("-" * 78)
    srows = []

    def add_s2028(tag, ws, cal, ptv, lo, hi, probs, n, note):
        pv = float(ptv[-1] if np.ndim(ptv) else ptv)
        srows.append({
            "row_type": tag, "weight_scheme": ws, "caliber": cal,
            "point_2028": round(pv, 6), "grade_2028": K.grade_of(pv),
            "margin_vs_0.400": round(pv - 0.400, 6),
            "grade_at_1dp": K.grade_of(round(pv, 1)),
            "grade_at_2dp": K.grade_of(round(pv, 2)),
            "grade_at_3dp": K.grade_of(round(pv, 3)),
            "flips_grade_at_2dp": bool(K.grade_of(round(pv, 2)) != K.grade_of(pv)),
            "flips_grade_at_1dp": bool(K.grade_of(round(pv, 1)) != K.grade_of(pv)),
            "p_severe_2028": (probs[0] if probs else np.nan),
            "p_medium_2028": (probs[1] if probs else np.nan),
            "p_mild_2028": (probs[2] if probs else np.nan),
            "p_rel_safe_2028": (probs[3] if probs else np.nan),
            "p_safe_2028": (probs[4] if probs else np.nan),
            "modal_grade_2028": (GRADES[int(np.argmax(probs))] if probs else ""),
            "p_below_0.400_2028": (float(sum(probs[:2])) if probs else np.nan),
            "ci_lo_2.5_2028": (round(float(lo[-1]), 6) if lo is not None else np.nan),
            "ci_hi_97.5_2028": (round(float(hi[-1]), 6) if hi is not None else np.nan),
            "width95_2028": (round(float(hi[-1] - lo[-1]), 6) if lo is not None else np.nan),
            "hi_exceeds_1": (bool(hi[-1] > 1.0) if lo is not None else ""),
            "lo_below_0": (bool(lo[-1] < 0.0) if lo is not None else ""),
            "n_draws": n, "note": note,
        })

    for ws in W:
        for cal in CALIBERS:
            lo, hi, probs, n, counts, vals = mix_summary[(ws, cal)]
            add_s2028("mixture_weight_scheme", ws, cal, mix_pt[ws], lo, hi,
                      K.grade_probs(vals[:, -1]), n,
                      "混合预测分布加权抽样；权重方案 %s；口径 %s" % (ws, cal))
    # 单模型行（同口径，供对照）
    for m in MODELS:
        for cal in CALIBERS:
            pool = bs[cal]["draws"][m]
            pool = pool[np.all(np.isfinite(pool), axis=1)]
            lo = np.percentile(pool, 2.5, axis=0)
            hi = np.percentile(pool, 97.5, axis=0)
            add_s2028("model", m, cal, pt[m], lo, hi, K.grade_probs(pool[:, -1]), len(pool),
                      "单模型 %s；口径 %s" % (m, cal))
    # paired（诊断）
    for ws in [MAIN_WS, "equal"]:
        for cal in CALIBERS:
            pv = K.mixture_paired(bs[cal], W[ws])
            lo = np.percentile(pv, 2.5, axis=0)
            hi = np.percentile(pv, 97.5, axis=0)
            add_s2028("mixture_paired_diagnostic", ws, cal, mix_pt[ws], lo, hi,
                      K.grade_probs(pv[:, -1]), pv.shape[0],
                      "诊断行：逐重复先加权平均（同情景误差抵消），非标准 BMA")
    # LOSO 权重向量下的 2028（敏感性）
    loso_2028 = []
    for sch in SCHEME_ORDER:
        for tag, wl in (("invRMSE_LOSO", loso_inv[sch]),
                        ("stacking_LOSO", loso_wd[sch])):
            pv = float(sum(wl[m] * pt[m][-1] for m in MODELS))
            loso_2028.append((tag, sch, pv, K.grade_of(pv)))
            add_s2028("weight_sensitivity_LOSO", tag + "@" + sch, "point_only", pv, None, None,
                      None, 0, "只由其余四方案定权重的 2028 混合点值（诚实口径）")
    sdf = pd.DataFrame(srows)
    # 点值敏感性汇总（供正文）
    vals_2028 = {ws: float(mix_pt[ws][-1]) for ws in W}
    grades_2028 = {ws: K.grade_of(mix_pt[ws][-1]) for ws in W}
    span = max(vals_2028.values()) - min(vals_2028.values())
    all_mild = len(set(grades_2028.values())) == 1
    sens_note = ("权重方案变化时 2028 混合点值跨度 %.6f（%.4f–%.4f）；等级%s"
                 % (span, min(vals_2028.values()), max(vals_2028.values()),
                    ("全部相同（%s，**不翻转**）" % list(grades_2028.values())[0]) if all_mild
                    else "发生翻转：%s" % grades_2028))
    print("   %s" % sens_note)
    loso_min = min(x[2] for x in loso_2028)
    loso_max = max(x[2] for x in loso_2028)
    print("   LOSO 权重向量下 2028 混合点值范围 %.6f–%.6f，等级 %s"
          % (loso_min, loso_max, sorted(set(x[3] for x in loso_2028))))
    for ws in W:
        lo, hi, probs, n, counts, vals = mix_summary[(ws, "logit_main")]
        print("   [logit 口径] %-20s 2028 [%.4f, %.4f]  P(medium)=%.4f P(mild)=%.4f"
              % (ws, lo[-1], hi[-1], probs[-1][1], probs[-1][2]))
    for ws in W:
        lo, hi, probs, n, counts, vals = mix_summary[(ws, "raw_R29")]
        print("   [raw 口径]   %-20s 2028 [%.4f, %.4f]  hi>1: %s"
              % (ws, lo[-1], hi[-1], hi[-1] > 1.0))
    sdf.to_csv(OUT_2K, index=False, encoding="utf-8-sig")

    addcheck("mix_2028_equal_vs_r29_archive",
             round(float(mix_pt["equal"][-1]), 6),
             "等权混合 2028 点值；R29 归档 %.6f（应一致）" % r29val("model_averaged",
                                                                    "equal-weight mixture of 3 "
                                                                    "models (pooled draws)",
                                                                    "point_2028"))
    addcheck("mix_2028_invRMSE", round(float(mix_pt["invRMSE"][-1]), 6),
             "主口径（逆 RMSE 权重）混合 2028 点值")
    addcheck("mix_2028_invRMSE_grade", K.grade_of(mix_pt["invRMSE"][-1]),
             "主口径混合 2028 等级")
    addcheck("mix_2028_invRMSE_margin", round(float(mix_pt["invRMSE"][-1]) - 0.400, 6),
             "主口径混合 2028 距 0.400 阈值")
    addcheck("weight_sensitivity_2028_span", round(span, 6), sens_note)
    addcheck("weight_sensitivity_2028_grade_flip", bool(not all_mild),
             "权重方案变化是否导致 2028 等级翻转（%s）" % grades_2028)
    addcheck("weight_sensitivity_LOSO_2028_range",
             "%.6f–%.6f" % (loso_min, loso_max),
             "leave-one-scheme-out 权重向量下 2028 点值范围；等级 %s"
             % sorted(set(x[3] for x in loso_2028)))
    addcheck("mix_logit_2028_hi_le_1_ALL",
             bool(all(mix_summary[(ws, "logit_main")][1][-1] <= 1.0 for ws in W)),
             "logit 口径下全部权重方案的 2028 上界是否 <= 1")
    addcheck("mix_logit_lo_ge_0_ALL",
             bool(all(mix_summary[(ws, "logit_main")][0][-1] >= 0.0 for ws in W)),
             "logit 口径下全部权重方案的 2028 下界是否 >= 0")
    addcheck("mix_raw_2028_hi_exceeds_1_invRMSE",
             bool(mix_summary[(MAIN_WS, "raw_R29")][1][-1] > 1.0),
             "raw_R29 口径下主口径混合 2028 上界是否越界（旧问题是否在混合上复现）")
    addcheck("mix_counts_invRMSE_logit",
             ";".join("%s=%d" % (m, mix_summary[(MAIN_WS, "logit_main")][4][m]) for m in MODELS),
             "主口径混合抽样中各模型贡献的抽样数（N_MIX=%d）" % K.N_MIX)
    addcheck("mix_rmse_pooled_invRMSE",
             round(mixed_pred and rmse_mae(mixed_pred[(MAIN_WS, "pooled")], obs)[0], 6),
             "主口径混合池化样本外 RMSE（含权重自选乐观性）")
    addcheck("source_csv_md5_r32_validation", K.file_md5(os.path.join(DATA, "r32_validation_8ind.csv")),
             "输入：五方案样本外精度（权重依据）")
    addcheck("source_csv_md5_r32_validation_detail",
             K.file_md5(os.path.join(DATA, "r32_validation_8ind_detail.csv")),
             "输入：逐评估点预测（stacking 与混合精度）")
    addcheck("source_csv_md5_r29_forecast_8ind",
             K.file_md5(os.path.join(DATA, "r29_forecast_8ind.csv")), "输入：三模型点预测")
    addcheck("script", "run_r44_mixture.py", "生成脚本（新建，未改动任何既有脚本）")

    pd.DataFrame(checks).to_csv(OUT_C, index=False, encoding="utf-8-sig")
    print("\n写出：\n  %s\n  %s\n  %s\n  %s\n  %s\n  %s"
          % (OUT_W, OUT_F, OUT_A, OUT_G, OUT_2K, OUT_C))
    return 0


if __name__ == "__main__":
    sys.exit(main())