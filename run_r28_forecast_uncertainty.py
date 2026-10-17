# -*- coding: utf-8 -*-
"""R28-T3 · 2024-2028 预测区间、等级概率与 0.394/0.400 阈值敏感性
（审稿意见第 2 条：不确定性报告不足）

────────────────────────────────────────────────────────────────────────────
正文现状
────────────────────────────────────────────────────────────────────────────
· 点预测：NGBM(γ=0.20) 由 0.446(2024) 降至 0.394(2028)；
· 区间：参数化 t 区间 σ·t(0.975, n-2)·√(1+1/n)，**半宽不随预测步长增大**
  （归档 results_forecast_ci.csv：2024 与 2028 半宽均为 0.0876），正文自承
  "5 年期预测的不确定性可能被低估"；
· 等级：只报单一等级，未报概率。

────────────────────────────────────────────────────────────────────────────
本脚本的区间构造（三条互相独立的依据，便于审稿人核对）
────────────────────────────────────────────────────────────────────────────
(A) Bootstrap（B=2000，seed 固定），把预测误差分解为两部分并分别/合并报告：
      · 参数不确定性 param_only_refit —— 残差重采样后**重估模型参数**；
      · 新息不确定性 innov_only_block —— 参数固定，未来冲击按长度 3 的移动块
        重采样并**沿预测步长累积**（随机游走式，故半宽随 h 增大）；
      · 总不确定性 total_iid_refit / total_block_refit —— 参数 + 累积新息；
      · param_plus_iid_nocum_refit —— 参数 + **不累积**新息（诊断：复现
        "半宽不随期增大"这一现象，说明归档区间隐含的正是该口径）；
      · ngbm_reselect_total_block —— 残差重采样后**同时重选 γ**，把 γ 的
        选择不确定性计入区间（仅 NGBM γ=0.20 一行）。
(B) 经验 h 步误差：直接取 T2 扩展窗口 rolling-origin 的**实际** h 步预测误差
    （`data/r28_rolling_origin_detail.csv`），报逐年/逐步 RMSE，作为"误差实际
    是否随期增大"的实证依据。
(C) 归档参数化 t 区间：原式复算，作对照。

────────────────────────────────────────────────────────────────────────────
数据来源（已入库；不新增下载，不覆盖已跟踪 CSV）
· data/qilian_climate.csv / data/qilian_landcover.csv / data/ahp_weights.csv
· data/results_esi_regional.csv、data/results_forecast_ci.csv（对照）
· data/r28_rolling_origin_detail.csv（T2 产出，经验 h 步误差）

输出（全部新文件）：
· data/r28_forecast_uncertainty.csv   —— 逐年×模型×区间依据
· data/r28_grade_probabilities.csv    —— 逐年×模型五级等级概率
· data/r28_threshold_sensitivity.csv  —— 2028 阈值扰动与舍入敏感性

运行：python run_r28_forecast_uncertainty.py
"""
import os
import sys
import warnings

import numpy as np
import pandas as pd
from scipy.stats import t as tdist

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
FUT_YEARS = list(range(2024, 2029))
N_FUT = 5
B = 2000
SEED = 20261017
BLOCK_L = 3
GAMMA_GRID = np.round(np.arange(0.05, 1.96, 0.05), 2)
GRADES = ["重警", "中警", "轻警", "较安全", "安全"]
THR = [0.2, 0.4, 0.6, 0.8]


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
    return esi_series(Xn, combined_weights(w_ahp, entropy_weights(Xn), ALPHA))


# ---------------------------------------------------------------------------
# 模型
# ---------------------------------------------------------------------------
def ngbm_core(x0, gamma, n_pred=N_FUT):
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
        fut = np.array([(1 - np.exp(-a)) * c * np.exp(-a * (len(x0) + k))
                        for k in range(1, n_pred + 1)])
        return fut, xh, (a, b)
    a, b = np.linalg.lstsq(np.column_stack([-z1, z1 ** gamma]), x0[1:], rcond=None)[0]
    if abs(a) < 1e-12:
        return None

    def X1(t):
        base = (x0[0] ** (1 - gamma) - b / a) * np.exp(-a * (1 - gamma) * t) + b / a
        if base <= 0:
            raise ValueError("negative base")
        return base ** (1.0 / (1.0 - gamma))

    xh = np.array([x0[0]] + [X1(k) - X1(k - 1) for k in range(1, len(x0))])
    fut = np.array([X1(len(x0) + k) - X1(len(x0) + k - 1) for k in range(1, n_pred + 1)])
    return fut, xh, (a, b)


def ngbm_pick_gamma(x0):
    best = None
    for g in GAMMA_GRID:
        try:
            r = ngbm_core(x0, g, n_pred=1)
        except Exception:
            continue
        if r is None or not np.all(np.isfinite(r[1])):
            continue
        sse = float(np.sum((x0[1:] - r[1][1:]) ** 2))
        if best is None or sse < best[0]:
            best = (sse, float(g))
    return None if best is None else best[1]


def fp_ngbm(series, gamma=0.20, reselect=False, n_pred=N_FUT):
    g = ngbm_pick_gamma(series) if reselect else gamma
    if g is None:
        return None
    try:
        r = ngbm_core(series, g, n_pred=n_pred)
    except Exception:
        return None
    if r is None:
        return None
    fut, xh, (a, b) = r
    if not np.all(np.isfinite(fut)) or not np.all(np.isfinite(xh)):
        return None
    return fut, xh, "gamma=%.2f (a=%.6f, b=%.6f)" % (g, a, b)


def fp_gm(series, n_pred=N_FUT):
    fut, fit, C, P = gm11_forecast(np.asarray(series, float), n_pred=n_pred)
    return np.asarray(fut, float), np.asarray(fit, float), "C=%.4f P=%.4f" % (C, P)


def fp_arima(series, order=(0, 1, 1), n_pred=N_FUT):
    from statsmodels.tsa.arima.model import ARIMA
    m = ARIMA(np.asarray(series, float), order=order).fit()
    fit = np.asarray(m.fittedvalues, float)
    if len(fit) == len(series) - 1:
        fit = np.concatenate([[series[0]], fit])
    return np.asarray(m.forecast(n_pred), float), fit, "order=%s" % (order,)


MODELS = {
    "NGBM_g0.20": lambda s: fp_ngbm(s, gamma=0.20),
    "NGBM_g0.25": lambda s: fp_ngbm(s, gamma=0.25),
    "NGBM_g0.10": lambda s: fp_ngbm(s, gamma=0.10),
    "GM(1,1)": fp_gm,
    "ARIMA(0,1,1)": fp_arima,
}
# 说明：NGBM 的 γ 重选不确定性由 bootstrap 的 gamma_mode 列表达
# （model="NGBM_g0.20" 的 fixed_gamma 与 reselect_each_replicate 两组），
# 不再单列一个 NGBM_reselect 模型，避免同一模型出现两套重复行。


# ---------------------------------------------------------------------------
# bootstrap：一次重采样 → 一个重估参数 → 多种区间口径
# ---------------------------------------------------------------------------
def draw_block(r, n, L, rng):
    """从中心化残差 r 中抽取长度 n 的移动块样本（保留局部自相关）。"""
    if len(r) <= L:
        return rng.choice(r, size=n, replace=True)
    starts = rng.integers(0, len(r) - L + 1, size=int(np.ceil(n / L)))
    return np.concatenate([r[s:s + L] for s in starts])[:n]


def bootstrap_paths(series, fp, reselect=False, B=B, seed=SEED):
    """返回 dict：{'param_only','innov_only_block','total_iid','total_block',
                    'param_plus_iid_nocum','ngbm_reselect_total_block'} → (B,5)"""
    base = fp(series)
    if base is None:
        return None
    fut0 = np.asarray(base[0], float)
    fit0 = np.asarray(base[1], float)
    rc = np.asarray(series, float) - fit0
    n = len(series)
    rng = np.random.default_rng(seed)
    out = {k: np.full((B, N_FUT), np.nan) for k in
           ["param_only", "innov_only_block", "total_iid", "total_block",
            "param_plus_iid_nocum"]}
    for b in range(B):
        y = fit0 + rng.choice(rc, size=n, replace=True)
        r = fp_ngbm(y, reselect=True) if reselect else fp(y)
        if r is None or not np.all(np.isfinite(r[0])):
            continue
        p = np.asarray(r[0], float)
        e_iid = rng.choice(rc - rc.mean(), size=N_FUT, replace=True)
        e_blk = draw_block(rc - rc.mean(), N_FUT, BLOCK_L, rng)
        cum_iid = np.cumsum(e_iid)
        cum_blk = np.cumsum(e_blk)
        out["param_only"][b] = p
        out["total_iid"][b] = p + cum_iid
        out["total_block"][b] = p + cum_blk
        out["param_plus_iid_nocum"][b] = p + e_iid
        out["innov_only_block"][b] = fut0 + cum_blk
    return out


def pctl(a, q):
    return np.nanpercentile(a, q, axis=0)


def grade_index(v):
    return sum(1 for t in THR if v >= t)


# ---------------------------------------------------------------------------
def main():
    esi = build_esi()
    arch = pd.read_csv(os.path.join(DATA, "results_esi_regional.csv"))
    arch_ci = pd.read_csv(os.path.join(DATA, "results_forecast_ci.csv"))
    print("=" * 78)
    print("R28-T3 · 2024-2028 预测区间 / 等级概率 / 阈值敏感性")
    print("=" * 78)
    print("[校验] 重建 ESI vs 归档 max|Δ| = %.3e" % np.abs(esi - arch["esi"].values).max())

    # ---------- 1) 点预测 ----------
    print("\n" + "-" * 78)
    print("1) 点预测（origin=2023，全部 19 年可用）")
    print("-" * 78)
    point = {}
    for name, fp in MODELS.items():
        r = fp(esi)
        if r is None:
            continue
        point[name] = r
        print("   %-14s 2024=%.6f ... 2028=%.6f 斜率=%+.5f/yr  %s"
              % (name, r[0][0], r[0][-1], np.polyfit(range(N_FUT), r[0], 1)[0], r[2]))

    fut_n, fit_n, info_n = point["NGBM_g0.20"]
    resid_n = esi - fit_n
    n = len(esi)
    sigma = float(np.std(resid_n, ddof=2))
    tcrit = float(tdist.ppf(0.975, max(n - 2, 1)))
    half = tcrit * sigma * np.sqrt(1 + 1 / n)
    print("\n   归档参数化 t 区间：σ=%.6f, t=%.4f, 半宽=%.6f（恒定）" % (sigma, tcrit, half))
    print("   复算 2024: %.4f~%.4f ；2028: %.4f~%.4f（归档 %.4f~%.4f / %.4f~%.4f）"
          % (fut_n[0] - half, fut_n[0] + half, fut_n[4] - half, fut_n[4] + half,
             arch_ci.loc[0, "ci_lo"], arch_ci.loc[0, "ci_hi"],
             arch_ci.loc[4, "ci_lo"], arch_ci.loc[4, "ci_hi"]))

    # 残差结构诊断
    from statsmodels.stats.diagnostic import acorr_ljungbox
    lb = acorr_ljungbox(resid_n, lags=[1, 2, 3], return_df=True)
    ac = [float(np.corrcoef(resid_n[:-k], resid_n[k:])[0, 1]) for k in (1, 2, 3)]
    print("   残差诊断（NGBM γ=0.20 全序列）：sd=%.4f，lag1-3 自相关 = %s"
          % (sigma, np.round(ac, 3)))
    print("   Ljung-Box p(lag1,2,3) = %s（>0.05 表示不拒绝白噪声）"
          % np.round(lb["lb_pvalue"].values, 3))
    print("   ESI 一阶差分 sd = %.6f；ESI 全序列 sd = %.6f"
          % (float(np.std(np.diff(esi), ddof=1)), float(np.std(esi, ddof=1))))

    # 平稳性诊断：决定"新息是否累积"这一口径选择
    from statsmodels.tsa.stattools import adfuller, kpss
    adf_lvl = adfuller(esi, autolag="AIC")
    adf_dif = adfuller(np.diff(esi), autolag="AIC")
    kp_lvl = kpss(esi, regression="c", nlags="auto")
    print("   平稳性：ADF 水平 p=%.4f（%s）；ADF 一阶差分 p=%.4f（%s）"
          % (adf_lvl[1], "拒绝单位根" if adf_lvl[1] < 0.05 else "不拒绝单位根",
             adf_dif[1], "拒绝单位根" if adf_dif[1] < 0.05 else "不拒绝单位根"))
    print("           KPSS 水平统计量 %.4f p=%.4f（%s）"
          % (kp_lvl[0], kp_lvl[1],
             "拒绝平稳" if kp_lvl[1] < 0.05 else "不拒绝平稳"))
    print("   解读：残差为白噪声（Ljung-Box 不拒绝），故『新息逐步累积』的随机游走式")
    print("         区间（total_iid/total_block）属**上界**；『新息不累积』口径")
    print("         （param_plus_iid_nocum）属确定性趋势模型的**下界**；")
    print("         实证多步误差（empirical_rolling_origin）为无模型假设的直接估计。")

    # ---------- 2) bootstrap 区间 ----------
    print("\n" + "-" * 78)
    print("2) Bootstrap 预测区间（B=%d，seed=%d，块长=%d）" % (B, SEED, BLOCK_L))
    print("-" * 78)
    paths = {}
    rows = []
    runs = []
    for name, fp in MODELS.items():
        if name not in point:
            continue
        if name == "NGBM_g0.20":
            runs.append((name, fp, True, "reselect_each_replicate"))
            runs.append((name, fp, False, "fixed_gamma"))
        else:
            runs.append((name, fp, False, "not_applicable"))
    for name, fp, reselect, gmode in runs:
        pset = bootstrap_paths(esi, fp, reselect=reselect)
        if pset is None:
            continue
        for method, p in pset.items():
            if p is None or not np.any(np.isfinite(p)):
                continue
            paths[(name, method, gmode)] = p
            lo95, hi95 = pctl(p, 2.5), pctl(p, 97.5)
            lo90, hi90 = pctl(p, 5), pctl(p, 95)
            for i, y in enumerate(FUT_YEARS):
                rows.append({
                    "model": name, "uncertainty_basis": "bootstrap",
                    "method": method, "gamma_mode": gmode, "year": y,
                    "point_forecast": round(float(point[name][0][i]), 6),
                    "boot_mean": round(float(np.nanmean(p[:, i])), 6),
                    "boot_sd": round(float(np.nanstd(p[:, i], ddof=1)), 6),
                    "boot_p2.5": round(float(lo95[i]), 6),
                    "boot_p5": round(float(lo90[i]), 6),
                    "boot_p50": round(float(pctl(p, 50)[i]), 6),
                    "boot_p95": round(float(hi90[i]), 6),
                    "boot_p97.5": round(float(hi95[i]), 6),
                    "width95": round(float(hi95[i] - lo95[i]), 6),
                    "width90": round(float(hi90[i] - lo90[i]), 6),
                    "n_boot_valid": int(np.sum(np.isfinite(p[:, i]))),
                })

    # 归档参数化 t 区间 + 经验 h 步误差
    for i, y in enumerate(FUT_YEARS):
        rows.append({
            "model": "NGBM_g0.20", "uncertainty_basis": "archived_param_t",
            "method": "param_t_const_halfwidth", "gamma_mode": "not_applicable", "year": y,
            "point_forecast": round(float(fut_n[i]), 6),
            "boot_mean": np.nan, "boot_sd": np.nan,
            "boot_p2.5": round(float(fut_n[i] - half), 6),
            "boot_p5": np.nan, "boot_p50": round(float(fut_n[i]), 6),
            "boot_p95": np.nan, "boot_p97.5": round(float(fut_n[i] + half), 6),
            "width95": round(float(2 * half), 6), "width90": np.nan,
            "n_boot_valid": 0,
        })

    det_path = os.path.join(DATA, "r28_rolling_origin_detail.csv")
    if os.path.exists(det_path):
        det = pd.read_csv(det_path)
        det = det[det.scheme == "rolling_5step_from2013"]
        for m, m_key in [("GM(1,1)", "GM(1,1)"), ("NGBM", "NGBM_g0.20"),
                         ("ARIMA", "ARIMA(0,1,1)")]:
            for ty in FUT_YEARS:
                sub = det[(det.model == m) & (det.target_year == (ty - 10))]
                # rolling_5step_from2013 的 origin=2013 起，target=origin+h；用 h 对齐
            # 按 horizon 汇总：报每个 h 的经验 RMSE（跨 origin）
            for h in range(1, 6):
                sub = det[(det.model == m) & (det.horizon == h)]
                sub = sub[np.isfinite(sub.err)]
                if len(sub) == 0:
                    continue
                rows.append({
                    "model": m_key, "uncertainty_basis": "empirical_rolling_origin",
                    "method": "hstep_rmse_origin2013_2018",
                    "gamma_mode": "not_applicable", "year": FUT_YEARS[h - 1],
                    "point_forecast": np.nan, "boot_mean": np.nan,
                    "boot_sd": round(float(np.sqrt(np.mean(sub.err ** 2))), 6),
                    "boot_p2.5": np.nan, "boot_p5": np.nan, "boot_p50": np.nan,
                    "boot_p95": np.nan, "boot_p97.5": np.nan,
                    "width95": round(float(2 * 1.96 * np.sqrt(np.mean(sub.err ** 2))), 6),
                    "width90": np.nan, "n_boot_valid": int(len(sub)),
                })

    unc = pd.DataFrame(rows)
    unc.to_csv(os.path.join(DATA, "r28_forecast_uncertainty.csv"),
               index=False, encoding="utf-8-sig")

    print("\n   NGBM γ=0.20 各口径 95% 区间（逐口径看半宽是否随期增大）：")
    for method in ["param_only", "innov_only_block", "param_plus_iid_nocum",
                   "total_iid", "total_block"]:
        for gmode in ["reselect_each_replicate", "fixed_gamma"]:
            sub = unc[(unc.model == "NGBM_g0.20") & (unc.method == method)
                      & (unc.gamma_mode == gmode)]
            if len(sub) == 0:
                continue
            w = sub.sort_values("year").width95.values
            print("     %-22s %-24s 半宽 %s  增幅 %.3f"
                  % (method, gmode, np.round(w, 4).tolist(), w[-1] / w[0]))
    w = unc[(unc.model == "NGBM_g0.20") & (unc.method == "param_t_const_halfwidth")]
    print("     %-30s 半宽 %s  增幅 %.3f"
          % ("archived_param_t", np.round(w.sort_values("year").width95.values, 4).tolist(), 1.0))
    emp = unc[(unc.model == "NGBM_g0.20")
              & (unc.uncertainty_basis == "empirical_rolling_origin")]
    print("     经验 h 步 RMSE（rolling-origin，NGBM）：%s"
          % np.round(emp.sort_values("year").boot_sd.values, 4).tolist())
    print("\n   区间宽度对照（NGBM γ=0.20，2024 → 2028）：")
    for method, gmode, lab in [
            ("param_t_const_halfwidth", "not_applicable", "归档参数化 t（宽度恒定）"),
            ("param_only", "fixed_gamma", "bootstrap 仅参数不确定性（γ 固定）"),
            ("param_only", "reselect_each_replicate", "bootstrap 参数+γ 重选"),
            ("param_plus_iid_nocum", "fixed_gamma", "参数 + 不累积新息（下界）"),
            ("total_iid", "fixed_gamma", "参数 + 累积新息 i.i.d."),
            ("total_block", "fixed_gamma", "参数 + 累积新息 块重采样"),
            ("total_block", "reselect_each_replicate", "参数+γ 重选 + 累积新息块（主口径）")]:
        sub = unc[(unc.model == "NGBM_g0.20") & (unc.method == method)
                  & (unc.gamma_mode == gmode)].sort_values("year")
        if len(sub) == 0:
            continue
        w = sub.width95.values
        print("     %-40s %.4f → %.4f （×%.2f）" % (lab, w[0], w[-1], w[-1] / w[0]))
    empsd = emp.sort_values("year").boot_sd.values
    print("     %-34s %.4f → %.4f （×%.2f）"
          % ("经验 h 步误差（1.96σ 近似）", 3.92 * empsd[0], 3.92 * empsd[-1],
             empsd[-1] / empsd[0]))
    archw = 2 * half
    print("   → 归档区间在各期均窄于经验口径；2028 年 %.4f vs %.4f（经验/归档 ≈ %.2f 倍）"
          % (archw, 3.92 * empsd[-1], 3.92 * empsd[-1] / archw))
    print("   total_block 95% 区间（主口径=γ 重选）:")
    for name in MODELS:
        sub = unc[(unc.model == name) & (unc.method == "total_block")
                  & (unc.gamma_mode != "fixed_gamma")]
        if len(sub) == 0:
            sub = unc[(unc.model == name) & (unc.method == "total_block")]
        if len(sub) == 0:
            continue
        print("     %-14s " % name + " | ".join(
            "%d %.4f~%.4f" % (r.year, r["boot_p2.5"], r["boot_p97.5"])
            for _, r in sub.sort_values("year").iterrows()))

    # ---------- 3) 等级概率 ----------
    print("\n" + "-" * 78)
    print("3) 蒙特卡洛等级概率（主口径 total_block；param_only 作对照）")
    print("-" * 78)
    grows = []
    for name in MODELS:
        if name not in point:
            continue
        for method in ["total_block", "param_only"]:
            for gmode in (["reselect_each_replicate", "fixed_gamma"]
                          if name == "NGBM_g0.20" else ["not_applicable"]):
                p = paths.get((name, method, gmode))
                if p is None:
                    continue
                for i, y in enumerate(FUT_YEARS):
                    v = p[:, i]
                    v = v[np.isfinite(v)]
                    if len(v) == 0:
                        continue
                    lv = np.array([grade_index(x) for x in v])
                    probs = [float(np.mean(lv == k)) for k in range(5)]
                    modal = int(np.argmax(probs))
                    grows.append({
                        "model": name, "method": method, "gamma_mode": gmode, "year": y,
                        "p_severe": round(probs[0], 6), "p_medium": round(probs[1], 6),
                        "p_mild": round(probs[2], 6), "p_rel_safe": round(probs[3], 6),
                        "p_safe": round(probs[4], 6),
                        "modal_grade": GRADES[modal], "p_modal": round(probs[modal], 6),
                        "p_below_0.400": round(float(np.mean(v < 0.400)), 6),
                        "p_below_0.200": round(float(np.mean(v < 0.200)), 6),
                        "p_ge_0.600": round(float(np.mean(v >= 0.600)), 6),
                        "n_boot_valid": int(len(v)),
                        "boot_mean": round(float(np.mean(v)), 6),
                        "boot_p2.5": round(float(np.percentile(v, 2.5)), 6),
                        "boot_p97.5": round(float(np.percentile(v, 97.5)), 6),
                    })
    gp = pd.DataFrame(grows)
    gp.to_csv(os.path.join(DATA, "r28_grade_probabilities.csv"),
              index=False, encoding="utf-8-sig")
    for name in ["NGBM_g0.20", "GM(1,1)", "ARIMA(0,1,1)"]:
        for gmode in (["reselect_each_replicate", "fixed_gamma"]
                      if name == "NGBM_g0.20" else ["not_applicable"]):
            sub = gp[(gp.model == name) & (gp.method == "total_block")
                     & (gp.gamma_mode == gmode)].sort_values("year")
            if len(sub) == 0:
                continue
            print("   %s（主口径，γ 模式=%s）:" % (name, gmode))
            for _, r in sub.iterrows():
                print("     %d  重警 %.3f 中警 %.3f 轻警 %.3f 较安全 %.3f 安全 %.3f | "
                      "众数 %-4s P=%.3f | P(ESI<0.400)=%.3f"
                      % (r.year, r.p_severe, r.p_medium, r.p_mild, r.p_rel_safe, r.p_safe,
                         r.modal_grade, r.p_modal, r["p_below_0.400"]))
    print("   仅参数不确定性口径（param_only，γ 重选）2028：")
    for name in ["NGBM_g0.20", "GM(1,1)", "ARIMA(0,1,1)"]:
        sub = gp[(gp.model == name) & (gp.method == "param_only") & (gp.year == 2028)]
        sub = sub[sub.gamma_mode.isin(["reselect_each_replicate", "not_applicable"])]
        if len(sub):
            r = sub.iloc[0]
            print("     %-14s 中警 %.3f 轻警 %.3f P(ESI<0.400)=%.3f"
                  % (name, r.p_medium, r.p_mild, r["p_below_0.400"]))
    print("   γ 口径对照（2028，total_block）：")
    for name in ["NGBM_g0.10", "NGBM_g0.20", "NGBM_g0.25"]:
        sub = gp[(gp.model == name) & (gp.method == "total_block") & (gp.year == 2028)]
        sub = sub[sub.gamma_mode.isin(["reselect_each_replicate", "not_applicable"])]
        if len(sub):
            r = sub.iloc[0]
            print("     %-14s 中警概率 %.3f  轻警概率 %.3f  P(ESI<0.400)=%.3f  众数=%s"
                  % (name, r.p_medium, r.p_mild, r["p_below_0.400"], r.modal_grade))

    # ---------- 4) 2028 阈值/舍入敏感性 ----------
    print("\n" + "-" * 78)
    print("4) 2028 点预测的精度、阈值与舍入敏感性")
    print("-" * 78)
    f2028 = float(fut_n[4])
    print("   NGBM(γ=0.20) 2028 = %.6f（正文 0.394，归档 0.3939）" % f2028)
    print("   距 0.400 阈值 = %+.6f" % (f2028 - 0.400))
    p_main = paths[("NGBM_g0.20", "total_block", "reselect_each_replicate")][:, 4]
    p_main = p_main[np.isfinite(p_main)]
    p_fix = paths[("NGBM_g0.20", "total_block", "fixed_gamma")][:, 4]
    p_fix = p_fix[np.isfinite(p_fix)]
    print("   γ 模式对照（2028，total_block）：P(ESI<0.400) = %.4f（γ 每重复重选）"
          " vs %.4f（γ 固定 0.20）" % (float(np.mean(p_main < 0.4)),
                                      float(np.mean(p_fix < 0.4))))
    rows = []
    for thr in np.round(np.arange(0.380, 0.4201, 0.005), 3):
        rows.append({
            "model": "NGBM_g0.20", "year": 2028, "kind": "threshold_shift",
            "value": float(thr),
            "p_below": round(float(np.mean(p_main < thr)), 6),
            "grade_if_below": GRADES[grade_index(thr - 1e-12)],
            "note": "阈值 0.400 平移 %+.3f" % (thr - 0.400),
        })
    rnd_note = {3: "→ 中警", 2: "→ 中警", 1: "→ 轻警（等级翻转）"}
    for d in [6, 4, 3, 2, 1]:
        v = round(f2028, d)
        rows.append({
            "model": "NGBM_g0.20", "year": 2028, "kind": "rounding",
            "value": float(v),
            "p_below": round(float(np.mean(np.round(p_main, d) < 0.4)), 6),
            "grade_if_below": GRADES[grade_index(v)],
            "note": "保留 %d 位小数：%.*f，等级=%s %s"
                    % (d, d, v, GRADES[grade_index(v)], rnd_note.get(d, "")),
        })
    for name in ["NGBM_g0.20", "GM(1,1)", "ARIMA(0,1,1)"]:
        p = paths.get((name, "total_block", "reselect_each_replicate"))
        if p is None:
            p = paths.get((name, "total_block", "not_applicable"))
        if p is None:
            continue
        v = p[:, 4]
        v = v[np.isfinite(v)]
        for thr in [0.395, 0.400, 0.405]:
            rows.append({
                "model": name, "year": 2028, "kind": "p_below_threshold",
                "value": thr,
                "p_below": round(float(np.mean(v < thr)), 6),
                "grade_if_below": GRADES[grade_index(thr - 1e-12)],
                "note": "同一 bootstrap 路径在阈值 %.3f 下的 P(ESI<thr)" % thr,
            })
    for thr in [0.395, 0.400, 0.405]:
        rows.append({
            "model": "NGBM_g0.20", "year": 2028, "kind": "p_below_threshold_gamma_fixed",
            "value": thr, "p_below": round(float(np.mean(p_fix < thr)), 6),
            "grade_if_below": GRADES[grade_index(thr - 1e-12)],
            "note": "γ 固定为 0.20（不含 γ 选择不确定性）时阈值 %.3f 的 P(ESI<thr)" % thr,
        })
    ts = pd.DataFrame(rows)
    ts.to_csv(os.path.join(DATA, "r28_threshold_sensitivity.csv"),
              index=False, encoding="utf-8-sig")
    print("\n   阈值平移（NGBM γ=0.20，2028）：",
          ", ".join("%.3f:%.3f" % (r.value, r.p_below)
                    for _, r in ts[ts.kind == "threshold_shift"].iterrows()))
    print("   P(ESI<0.400) 主口径：")
    for name in ["NGBM_g0.20", "GM(1,1)", "ARIMA(0,1,1)"]:
        q = ts[(ts.model == name) & (ts.kind == "p_below_threshold") & (ts.value == 0.400)]
        if len(q):
            print("     %-14s %.4f" % (name, q.iloc[0].p_below))
    print("   舍入敏感性：")
    for _, r in ts[ts.kind == "rounding"].sort_values("value", ascending=False).iterrows():
        print("     %s" % r.note)

    # ---------- 5) GM 与 NGBM 分歧 ----------
    print("\n" + "-" * 78)
    print("5) GM(1,1) 与 NGBM 的分歧：水平、斜率、γ 依赖与可分辨性")
    print("-" * 78)
    fg = point["GM(1,1)"][0]
    sg = float(np.polyfit(range(N_FUT), fg, 1)[0])
    sn = float(np.polyfit(range(N_FUT), fut_n, 1)[0])
    print("   GM(1,1)    2024=%.4f 2028=%.4f 斜率=%+.5f/yr  %s" % (fg[0], fg[-1], sg, point["GM(1,1)"][2]))
    print("   NGBM γ=0.20 2024=%.4f 2028=%.4f 斜率=%+.5f/yr  %s"
          % (fut_n[0], fut_n[-1], sn, info_n))
    print("   → 两者**同向下降**；GM 斜率仅为 NGBM 的 %.2f 倍，GM 全程 >0.49，"
          % (abs(sg) / abs(sn)))
    print("     NGBM 于 2028 降到 0.40 阈值附近。『GM 上升 vs NGBM 下降』的对立"
          "表述与数值不符。")
    print("   γ 决定 NGBM 斜率（同一结构，全序列拟合）：")
    for gv in [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40]:
        r = fp_ngbm(esi, gamma=gv)
        if r is None:
            continue
        print("     γ=%.2f 2028=%.4f 斜率=%+.5f/yr" % (
            gv, r[0][-1], np.polyfit(range(N_FUT), r[0], 1)[0]))

    rng = np.random.default_rng(SEED + 1)
    rc = resid_n - resid_n.mean()
    ng, gm, diffs = [], [], []
    for b in range(B):
        y = fit_n + rng.choice(rc, size=n, replace=True)
        rn = fp_ngbm(y, gamma=0.20)
        rg = fp_gm(y)
        if rn is None or rg is None:
            continue
        ng.append(float(rn[0][-1]))
        gm.append(float(rg[0][-1]))
        diffs.append(float(rn[0][-1] - rg[0][-1]))
    diffs = np.array(diffs)
    ng = np.array(ng)
    gm = np.array(gm)
    print("\n   配对 bootstrap（同一残差重采样序列重估两模型，有效 n=%d）：" % len(diffs))
    print("     NGBM_2028 均值 %.4f（95%%: %.4f~%.4f）"
          % (ng.mean(), np.percentile(ng, 2.5), np.percentile(ng, 97.5)))
    print("     GM_2028   均值 %.4f（95%%: %.4f~%.4f）"
          % (gm.mean(), np.percentile(gm, 2.5), np.percentile(gm, 97.5)))
    print("     P(NGBM_2028 < GM_2028) = %.4f；Δ(GM-NGBM) 均值 %+.4f（95%%: %+.4f~%+.4f）"
          % (float(np.mean(diffs < 0)), float(np.mean(-diffs)),
             float(np.percentile(-diffs, 2.5)), float(np.percentile(-diffs, 97.5))))
    print("     P(GM_2028<0.400)=%.4f ； P(NGBM_2028<0.400)=%.4f"
          % (float(np.mean(gm < 0.4)), float(np.mean(ng < 0.4))))

    # ---------- 6) no-intervention scenario ----------
    print("\n" + "-" * 78)
    print("6) 'no-intervention scenario'（N0）的可操作定义——本脚本实际执行的假设")
    print("-" * 78)
    for line in [
        "(a) 模型参数冻结：NGBM 的 (a, b, γ) 取 2005-2023 全序列估计值（γ=0.20）；",
        "    预测 origin = 2023 年末，参数只用到 2023 年及以前的数据；",
        "(b) 指标赋权冻结：9 项指标的熵权与 AHP 组合权重（α=0.4）取 2005-2023；",
        "(c) 归一化区间冻结：min-max 上下界取 2005-2023 观测范围；",
        "(d) 无额外干预：不假设退牧还草、草地恢复、耕地调控等新增工程，",
        "    也不额外注入超出 2005-2023 记录的新增退化或气候强迫；",
        "(e) 数据生成机制不变：CLCD 五期线性插值口径与 CRU 气候波动结构不变。",
        "性质：这是**条件趋势外推**，不是无干预的因果反事实。ESI 为 min-max 相对",
        "指数，其量纲随研究时段与样本范围而变，0.394 只在 2005-2023 口径内可比。",
    ]:
        print("   " + line)

    print("\n已写出：data/r28_forecast_uncertainty.csv, data/r28_grade_probabilities.csv,")
    print("        data/r28_threshold_sensitivity.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())