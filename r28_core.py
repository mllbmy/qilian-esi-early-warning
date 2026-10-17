# -*- coding: utf-8 -*-
"""R28 · 去冗余 ESI 重构的共用内核（供 T2–T7 复用，单一真源）

本模块只做三件事：
  1) 按冻结口径装载区域 DPSIR 指标矩阵（气候按年、土地覆被按可切换插值方案）
  2) 按「存活指标集」重算 AHP 权重（准则层权重在存活层上重归一化 + 层内均分，
     与 `run_robustness_loo_indicators.py` 的 S1/S2/S3 口径一致）
  3) 组合权重 / ESI / 分级 / 逐年等级 / 障碍度 的统一实现

⚠ 口径与论文一致的地方（不得在本模块内擅改）：
  · 熵权与极差标准化直接调用 `eco_security/eco_security.py`
  · α = 0.4；五级阈值 [0.2, 0.4, 0.6, 0.8]
  · 指标方向见 LAYER_DIR
  · 基准复现校验：与 data/results_esi_regional.csv 的 max|Δ| 应在 1e-4 量级
    （该归档文件只有 4 位小数）

⚠ 本模块明确**修正**的一个口径问题：
  · 候选集里若同时保留恒等式两侧（X9 与其构成项；X6 与其构成项；X8 与 X3），
    熵权/标准化会把同一信息计入两次。见 DEREDUNDANT_SETS。
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
sys.path.insert(0, os.path.join(BASE, "eco_security"))
from eco_security import (  # noqa: E402
    classify_warning, combined_weights, entropy_weights, esi_series, minmax_normalize,
)

YEARS = list(range(2005, 2024))
ALPHA = 0.4
THRESHOLDS = [0.2, 0.4, 0.6, 0.8]

# ---- 指标 → DPSIR 层 / 方向 ----
LAYER = {
    "X1_降水mm": "Driving", "X2_气温C": "Driving",
    "X6_裸地荒漠%": "Pressure", "X7_农田占比%": "Pressure",
    "X3_草地占比%": "State", "X4_森林占比%": "State", "X5_水域占比%": "State",
    "X8_草地变化率": "Impact", "X9_生态用地%": "Response",
}
LAYER_DIR = {
    "X1_降水mm": +1, "X2_气温C": +1,
    "X3_草地占比%": +1, "X4_森林占比%": +1, "X5_水域占比%": +1,
    "X6_裸地荒漠%": -1, "X7_农田占比%": -1,
    "X8_草地变化率": +1, "X9_生态用地%": +1,
}
ALL9 = ["X1_降水mm", "X2_气温C", "X3_草地占比%", "X4_森林占比%", "X5_水域占比%",
        "X6_裸地荒漠%", "X7_农田占比%", "X8_草地变化率", "X9_生态用地%"]

# ---- 去冗余情景（单一真源；T2–T7 全部引用此处） ----
# 命名一律写清"删掉谁"，避免歧义（R19 的 S1/S2/S3 见 run_robustness_loo_indicators.py，
# 本文件不复用其标签以免与 R19 报告混淆）
DEREDUNDANT_SETS = {
    # 基准：论文现用 9 指标（对照）
    "baseline9": ALL9,
    # 删响应层恒等项 X9（= X3+X4+X5 的完全重复）
    "drop_X9": [n for n in ALL9 if n != "X9_生态用地%"],
    # 删影响层导数项 X8（= X3 的年变化率）
    "drop_X8": [n for n in ALL9 if n != "X8_草地变化率"],
    # 同时删 X9 与 X8（= R19 的 S3 口径，7 指标）
    "drop_X8_X9": [n for n in ALL9 if n not in ("X8_草地变化率", "X9_生态用地%")],
    # R28 主推「去冗余指标集」：再删恒等式残差项 X6（= 100−X3−X4−X5−X7；去均值后 ≈ −(X3−mean)）
    #   → 6 指标 {X1,X2,X3,X4,X5,X7}，全部线性无关（5 指标满分秩，X2 与其余不共线）
    "primary6": [n for n in ALL9 if n not in ("X6_裸地荒漠%", "X8_草地变化率", "X9_生态用地%")],
    # 替代组合（不明感的对照）：删掉全部状态层构成项与残差项，只保留 X8、X9
    #   → 5 指标 {X1,X2,X7,X8,X9}，用于检验"保留导数与和"这一选择的影响
    "substitute5": [n for n in ALL9 if n not in
                    ("X3_草地占比%", "X4_森林占比%", "X5_水域占比%", "X6_裸地荒漠%")],
}
PRIMARY = "primary6"
PRIMARY_KEEP = DEREDUNDANT_SETS[PRIMARY]


def _landcover(interp: str = "linear") -> pd.DataFrame:
    """区域土地覆被按 interp 方案展布到 2005–2023。

    interp ∈ {"linear", "cubic", "pchip", "observed"}
      · observed：只在实测年 [2005,2010,2015,2020,2023] 上取值（不外推/内插）
    """
    lc_raw = pd.read_csv(os.path.join(DATA, "qilian_landcover.csv"))
    if interp == "observed":
        return lc_raw.set_index("year").sort_index()
    lc = lc_raw.set_index("year").reindex(YEARS)
    method = {"linear": "linear", "cubic": "cubic", "pchip": "pchip"}[interp]
    for c in lc.columns:
        lc[c] = lc[c].interpolate(method=method).bfill().ffill()
    return lc


def build_indicators(interp: str = "linear", temp_direction: str = "positive",
                     years=None) -> pd.DataFrame:
    """返回 index=年份、columns=9 项指标的原始值矩阵。

    temp_direction ∈ {"positive", "negative", "excluded"}
    """
    if years is None:
        years = YEARS if interp != "observed" else [2005, 2010, 2015, 2020, 2023]
    cli = pd.read_csv(os.path.join(DATA, "qilian_climate.csv"))
    reg = cli[cli.unit == "区域(祁连山盒)"].set_index("year")
    lc = _landcover(interp)
    idx = [y for y in years if y in lc.index]
    lc = lc.loc[idx]
    reg = reg.loc[idx]
    df = pd.DataFrame(index=idx)
    df["X1_降水mm"] = reg["precip_mm"].values
    if temp_direction != "excluded":
        df["X2_气温C"] = reg["temp_c"].values
    df["X3_草地占比%"] = lc["grass_pct"].values
    df["X4_森林占比%"] = lc["forest_pct"].values
    df["X5_水域占比%"] = lc["water_pct"].values
    df["X6_裸地荒漠%"] = 100.0 - lc["grass_pct"] - lc["forest_pct"] - lc["water_pct"] - lc["crop_pct"]
    df["X7_农田占比%"] = lc["crop_pct"].values
    df["X8_草地变化率"] = (lc["grass_pct"].pct_change().fillna(0) * 100).values
    df["X9_生态用地%"] = (lc["grass_pct"] + lc["forest_pct"] + lc["water_pct"]).values
    return df


def ahp_weights_for(keep, temp_direction: str = "positive") -> np.ndarray:
    """按存活指标集重算 AHP 权重：准则层权重在存活层上重归一化 + 层内均分。

    与 `run_robustness_loo_indicators.py` 的 S1/S2/S3 口径一致（该口径下基准可精确复现）。
    """
    crit = pd.read_csv(os.path.join(DATA, "results_ahp_criteria.csv"))
    cw = dict(zip(crit["criterion"], crit["weight"]))
    if temp_direction == "excluded":
        cw = dict(cw)
    keep = list(keep)
    layers = {n: LAYER[n] for n in keep}
    live = sorted(set(layers.values()))
    tot = sum(cw[l] for l in live)
    out = np.empty(len(keep))
    for j, n in enumerate(keep):
        l = layers[n]
        cnt = sum(1 for m in keep if layers[m] == l)
        out[j] = (cw[l] / tot) / cnt
    return out


def directions_for(keep, temp_direction: str = "positive") -> np.ndarray:
    d = []
    for n in keep:
        v = LAYER_DIR[n]
        if n == "X2_气温C" and temp_direction == "negative":
            v = -1
        d.append(v)
    return np.array(d, dtype=float)


def compute(keep, interp: str = "linear", alpha: float = ALPHA,
            temp_direction: str = "positive", thresholds=None, years=None):
    """在指标集 keep 上重跑全链：标准化 → 熵权 → AHP → 组合 → ESI → 分级。

    返回 dict：years, raw, Xn, w_ent, w_ahp, w, esi, levels, thresholds
    """
    df = build_indicators(interp=interp, temp_direction=temp_direction, years=years)
    keep = [n for n in keep if n in df.columns]
    X = df[keep].values.astype(float)
    dirs = directions_for(keep, temp_direction)
    Xn = minmax_normalize(X, dirs)
    w_ent = entropy_weights(Xn)
    w_ahp = ahp_weights_for(keep, temp_direction)
    w = combined_weights(w_ahp, w_ent, alpha)
    esi = esi_series(Xn, w)
    thr = THRESHOLDS if thresholds is None else thresholds
    levels = classify_warning(esi, thr)
    return dict(years=list(df.index), raw=df, keep=keep, Xn=Xn, w_ent=w_ent,
                w_ahp=w_ahp, w=w, esi=esi, levels=levels, thresholds=thr,
                directions=dirs)


def obstacle_degree(Xn: np.ndarray, w: np.ndarray) -> np.ndarray:
    """障碍度 O_ij = (1 - x'_ij) * w_j，再按行归一化到 1（论文图 10 口径）。"""
    o = (1.0 - Xn) * w[None, :]
    s = o.sum(axis=1, keepdims=True)
    s[s == 0] = 1.0
    return o / s


def spearman(a, b):
    from scipy.stats import spearmanr
    r = spearmanr(a, b)
    return float(r.statistic), float(r.pvalue)


def pearson(a, b):
    from scipy.stats import pearsonr
    r = pearsonr(a, b)
    return float(r.statistic), float(r.pvalue)


def baseline_reference():
    """已发表的基准序列（data/results_esi_regional.csv，4 位小数）。"""
    b = pd.read_csv(os.path.join(DATA, "results_esi_regional.csv")).set_index("year")
    return b


def self_check(verbose=True):
    """复现校验：baseline9 应复现已发表基准序列与权重。"""
    r = compute(ALL9)
    b = baseline_reference()
    d = float(np.abs(r["esi"] - b.loc[YEARS, "esi"].values).max())
    lv_ok = bool(list(r["levels"]) == list(b.loc[YEARS, "warning"]))
    w_arch = pd.read_csv(os.path.join(DATA, "results_weights.csv")).set_index("indicator")
    dw = float(np.abs(r["w"] - w_arch.loc[r["keep"], "combined_w"].values).max())
    if verbose:
        print("[self_check] baseline9 vs results_esi_regional.csv  max|Δ| = %.3e；分级一致 = %s"
              % (d, lv_ok))
        print("[self_check] baseline9 vs results_weights.csv       max|Δ| = %.3e" % dw)
        print("[self_check] 熵权 =", np.round(r["w_ent"], 6))
        print("[self_check] 组合权 =", np.round(r["w"], 6))
    return dict(esi_max_abs_delta=d, levels_match=lv_ok, weight_max_abs_delta=dw)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    self_check()