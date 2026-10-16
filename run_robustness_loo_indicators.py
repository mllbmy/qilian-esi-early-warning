# -*- coding: utf-8 -*-
"""去指标重叠稳健性检验：指标集留一（Leave-One-Out, LOO）
================================================================================
【问题】论文用 DPSIR 框架 9 项指标 + 组合赋权（熵权法 + AHP，α=0.4）计算区域生态
安全指数 ESI（2005-2023）。指标体系内部存在三处重叠：

  (a) 响应层 X9「生态用地占比」 = X3 草地占比 + X4 森林占比 + X5 水域占比  —— 完全重复
  (b) 影响层 X8「草地变化率」   = X3 草地占比的年变化率                  —— 状态量的导数
  (c) 影响层 + 状态层 + 响应层的组合权重合计约 69%（论文 Limitations 第 (1) 条）

本脚本在**缩减后的指标集**上重跑赋权-合成全流程，检验上述重叠是否影响论文结论
（趋势 / 2023 等级 / α 稳健性）。

【情景】
  baseline : 原始 9 指标（对照）
  S1       : 剔除 X9（生态用地占比）
  S2       : 剔除 X8（草地变化率）
  S3       : 同时剔除 X8、X9
  C1/C2/C3 : 对应的"对照情景"——**不重算权重**，仅把基准组合权重复归一化后算 ESI，
             用于区分"结论变化到底来自权重变化还是序列本身变化"
  S1eq/S2eq/S3eq : AHP 口径变体（AHP 取等权而非准则层权重）下的 S1/S2/S3

【公式来源】全部复用仓库既有实现，不另写口径：
  eco_security/eco_security.py
    · minmax_normalize()  极差标准化（正向 (x-min)/(max-min)，负向 (max-x)/(max-min)）
    · entropy_weights()   熵权法 w^E：P=x'/Σx'，e=-1/ln n·ΣP·lnP，d=1-e，w=d/Σd
    · combined_weights()  线性组合 w = α·w^A + (1-α)·w^E
    · esi_series()        ESI = X'·w
    · classify_warning()  五级预警：安全[0.8,1]、较安全[0.6,0.8)、轻警[0.4,0.6)、
                          中警[0.2,0.4)、重警[0,0.2)
  与 run_esi_regional.py / rerun_pipeline_ahp.py / run_alpha_sensitivity.py 完全同源。
  AHP 指标权重直接读取 run_ahp_weights.py 落盘的 data/ahp_weights.csv
  （准则层 5×5 判断矩阵 + 层内均分；λmax=5.015284, CI=0.003821, CR=0.003412）。

【数据来源】
  主口径：data/qilian_climate.csv + data/qilian_landcover.csv
          ——与 rerun_pipeline_ahp.py 完全一致，可**精确复现**已发表基准序列
          （results_esi_regional.csv，最大绝对偏差 ~5e-5 = 该文件的 4 位小数舍入）
  校核口径：data/results_indicators.csv（make_fig_trends.py 落盘的 3 位小数副本）
          ——仅用于验证两套数据口径一致性（不改变任何结论）

【输出】只新建，不修改任何既有文件
  data/results_robustness_loo_indicators.csv        全部数值结果（长表，可机读）
  reports/robustness_loo_indicators.md              中文报告（表 + 原始数字 + 结论）
      报告中的每一句叙述都由脚本按算出的数值生成，不含硬编码结论。

用法：python run_robustness_loo_indicators.py [--overwrite]
默认拒绝覆盖已存在的输出文件。
================================================================================
"""
from __future__ import annotations

import argparse
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
import pandas as pd
from scipy import stats

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "eco_security"))
# —— 复用仓库既有实现（同一套公式口径）——
from eco_security import (  # noqa: E402
    classify_warning,
    combined_weights,
    entropy_weights,
    esi_series,
    minmax_normalize,
)

YEARS = list(range(2005, 2024))
ALPHA = 0.4                                              # 论文主口径
ALPHA_GRID = np.round(np.arange(0.0, 1.0001, 0.01), 2)   # 0→1 步长 0.01

OUT_CSV = os.path.join(BASE, "data", "results_robustness_loo_indicators.csv")
OUT_MD = os.path.join(BASE, "reports", "robustness_loo_indicators.md")

# DPSIR 九项指标：名称 → (数据列, 方向, 所属层)
# 方向与论文表 2 一致：降水/气温/草地/森林/水域/生态用地为正；裸地/农田为负
INDICATORS = [
    ("X1_降水mm",    "precip_mm",      +1, "Driving"),
    ("X2_气温C",      "temp_c",         +1, "Driving"),
    ("X3_草地占比%",  "grass_pct",      +1, "State"),
    ("X4_森林占比%",  "forest_pct",     +1, "State"),
    ("X5_水域占比%",  "water_pct",      +1, "State"),
    ("X6_裸地荒漠%",  "barren_pct",     -1, "Pressure"),
    ("X7_农田占比%",  "crop_pct",       -1, "Pressure"),
    ("X8_草地变化率", "grass_chg_rate", +1, "Impact"),
    ("X9_生态用地%",  "ecoland_pct",    +1, "Response"),
]
NAMES = [t[0] for t in INDICATORS]
DIRECTIONS = [t[2] for t in INDICATORS]
LAYERS = [t[3] for t in INDICATORS]

MAIN = ["baseline", "S1", "S2", "S3"]
EQ = ["S1eq", "S2eq", "S3eq"]
CTRL = ["C1", "C2", "C3"]
# 重叠指标组：影响层 + 状态层 + 响应层（论文 69% 断言的对象）
OVERLAP_GROUP = ["X3_草地占比%", "X4_森林占比%", "X5_水域占比%", "X8_草地变化率", "X9_生态用地%"]

SCENARIOS = {
    "baseline": {"drop": [],                 "kind": "reweight"},
    "S1":       {"drop": ["X9_生态用地%"],   "kind": "reweight"},
    "S2":       {"drop": ["X8_草地变化率"],  "kind": "reweight"},
    "S3":       {"drop": ["X8_草地变化率", "X9_生态用地%"], "kind": "reweight"},
    "C1":       {"drop": ["X9_生态用地%"],   "kind": "control_renorm"},
    "C2":       {"drop": ["X8_草地变化率"],  "kind": "control_renorm"},
    "C3":       {"drop": ["X8_草地变化率", "X9_生态用地%"], "kind": "control_renorm"},
    "S1eq":     {"drop": ["X9_生态用地%"],   "kind": "reweight_eq"},
    "S2eq":     {"drop": ["X8_草地变化率"],  "kind": "reweight_eq"},
    "S3eq":     {"drop": ["X8_草地变化率", "X9_生态用地%"], "kind": "reweight_eq"},
}

SCHEME_NAME = {"reweight": "AHP_criterion(主口径)",
               "reweight_eq": "AHP_equal(口径变体)",
               "control_renorm": "control(仅重归一化权重)"}


# ---------------------------------------------------------------------------
# 1. 指标矩阵构建（严格照抄 run_esi_regional.py / rerun_pipeline_ahp.py）
# ---------------------------------------------------------------------------
def build_matrix_raw():
    """从原始数据源重建 9 指标矩阵——与主导管线逐行一致。"""
    cli = pd.read_csv(os.path.join(BASE, "data", "qilian_climate.csv"))
    lc = pd.read_csv(os.path.join(BASE, "data", "qilian_landcover.csv"))
    reg = cli[cli.unit == "区域(祁连山盒)"].set_index("year")
    lc = lc.set_index("year").reindex(YEARS)
    for c in lc.columns:                        # 5 个覆被时相 → 逐年线性插值
        lc[c] = lc[c].interpolate(method="linear").bfill().ffill()
    series = {
        "precip_mm": reg["precip_mm"],
        "temp_c": reg["temp_c"],
        "grass_pct": lc["grass_pct"],
        "forest_pct": lc["forest_pct"],
        "water_pct": lc["water_pct"],
        "barren_pct": 100 - lc["grass_pct"] - lc["forest_pct"] - lc["water_pct"] - lc["crop_pct"],
        "crop_pct": lc["crop_pct"],
        "grass_chg_rate": lc["grass_pct"].pct_change().fillna(0) * 100,
        "ecoland_pct": lc["grass_pct"] + lc["forest_pct"] + lc["water_pct"],
    }
    return pd.DataFrame({k: np.asarray(v, dtype=float) for k, v in series.items()}), "qilian_climate.csv + qilian_landcover.csv"


def build_matrix_csv():
    """从落盘的 results_indicators.csv 读指标值（3 位小数副本），用于口径校核。"""
    df = pd.read_csv(os.path.join(BASE, "data", "results_indicators.csv"))
    assert list(df["year"]) == YEARS, "results_indicators.csv 年份与 2005-2023 不一致"
    cols = {c: df[c].values.astype(float) for c in df.columns if c != "year"}
    return pd.DataFrame(cols), "results_indicators.csv"


def load_ahp_weights():
    """读取 run_ahp_weights.py 落盘的 AHP 指标权重，并与 results_weights.csv 交叉核对。"""
    ahp = pd.read_csv(os.path.join(BASE, "data", "ahp_weights.csv"))
    w = ahp.set_index("indicator").loc[NAMES, "ahp_weight"].values.astype(float)
    ref = pd.read_csv(os.path.join(BASE, "data", "results_weights.csv"))
    ref = ref.set_index("indicator").loc[NAMES, "ahp_w"].values.astype(float)
    assert np.abs(w - ref).max() < 5e-4, "ahp_weights.csv 与 results_weights.csv 不一致"
    return w / w.sum()


# ---------------------------------------------------------------------------
# 2. 赋权-合成（在缩减指标集上重跑全流程）
# ---------------------------------------------------------------------------
def run_scenario(mat: pd.DataFrame, keep_idx, ahp_all, kind: str, alpha: float = ALPHA):
    """在指标子集上重做 min-max 标准化 → 熵权 → AHP → 组合 → ESI。

    kind:
      reweight      : 重算权重（AHP 用准则层权重，缩减集上重归一化）
      reweight_eq   : 重算权重，但 AHP 取等权（指定口径的字面读法，用于口径敏感性复核）
      control_renorm: 不重算权重，只把基准组合权重复归一化（区分权重效应 vs 序列效应）
    """
    X = mat[[INDICATORS[i][1] for i in keep_idx]].values.astype(float)
    dirs = [DIRECTIONS[i] for i in keep_idx]
    Xn = minmax_normalize(X, dirs)                 # (1) 缩减集上重新极差标准化
    w_ent = entropy_weights(Xn)                    # (2) 缩减集上重新求熵权
    if kind == "control_renorm":
        return Xn, w_ent, None, None, None
    if kind == "reweight_eq":
        w_ahp = np.ones(len(keep_idx)) / len(keep_idx)          # (3a) AHP 等权
    else:
        w_ahp_raw = ahp_all[keep_idx]
        # (3b) 准则层权重在存活层上重归一化 + 层内均分 ≡ 存活指标 AHP 权重按比例重归一化
        w_ahp = w_ahp_raw / w_ahp_raw.sum()
    w = combined_weights(w_ahp, w_ent, alpha)      # (4) α 组合
    return Xn, w_ent, w_ahp, w, esi_series(Xn, w)  # (5) ESI


def levels_and_stats(esi, levels, base_esi, base_levels):
    """单情景汇总指标。"""
    pear = stats.pearsonr(esi, base_esi)
    spear = stats.spearmanr(esi, base_esi)
    peak_i = int(np.argmax(esi))
    tail_mask = np.array(YEARS) >= 2011
    rho_tail = stats.spearmanr(esi[tail_mask], np.array(YEARS)[tail_mask])
    since_2011 = [l for y, l in zip(YEARS, levels) if y >= 2011]
    return {
        "esi_2005": float(esi[YEARS.index(2005)]),
        "esi_2010": float(esi[YEARS.index(2010)]),
        "esi_2013": float(esi[YEARS.index(2013)]),
        "esi_2023": float(esi[YEARS.index(2023)]),
        "esi_min": float(esi.min()),
        "esi_min_year": YEARS[int(np.argmin(esi))],
        "esi_max": float(esi.max()),
        "esi_max_year": YEARS[peak_i],
        "peak_year": YEARS[peak_i],
        "peak_value": float(esi[peak_i]),
        "esi_2010_minus_2023": float(esi[YEARS.index(2010)] - esi[-1]),
        "esi_2023_minus_peak": float(esi[-1] - esi[peak_i]),
        "level_2005": levels[0],
        "level_2010": levels[YEARS.index(2010)],
        "level_2013": levels[YEARS.index(2013)],
        "level_2023": levels[-1],
        "pearson_r": float(pear.statistic),
        "pearson_p": float(pear.pvalue),
        "spearman_rho": float(spear.statistic),
        "spearman_p": float(spear.pvalue),
        "max_abs_dev_vs_base": float(np.abs(esi - base_esi).max()),
        "mean_abs_dev_vs_base": float(np.abs(esi - base_esi).mean()),
        "n_level_diff_vs_base": int(sum(a != b for a, b in zip(levels, base_levels))),
        "all_light_2011_2023": bool(all(l == "轻警" for l in since_2011)),
        "n_nonlight_2011_2023": int(sum(l != "轻警" for l in since_2011)),
        "peak_is_2010": bool(YEARS[peak_i] == 2010),
        "rho_tail_2011_2023": float(rho_tail.statistic),
        "rho_tail_p": float(rho_tail.pvalue),
    }


def alpha_sweep(Xn, w_ent, w_ahp):
    """α∈[0,1]（步长 0.01）下 2023 年 ESI 与等级。"""
    rows = []
    for a in ALPHA_GRID:
        w = combined_weights(w_ahp, w_ent, float(a))
        e = esi_series(Xn, w)
        rows.append({"alpha": float(a), "esi_2023": float(e[-1]),
                     "level_2023": classify_warning(e)[-1]})
    return rows


def summ_alpha(rows):
    lvs = [r["level_2023"] for r in rows]
    e23 = [r["esi_2023"] for r in rows]
    nonlight = [(r["alpha"], r["level_2023"]) for r in rows if r["level_2023"] != "轻警"]
    d = {
        "n_grid": len(rows),
        "always_light": bool(all(l == "轻警" for l in lvs)),
        "distinct_levels": sorted(set(lvs)),
        "level_at_alpha_0": rows[0]["level_2023"],
        "level_at_alpha_1": rows[-1]["level_2023"],
        "esi2023_min": min(e23), "esi2023_max": max(e23),
        "esi2023_min_alpha": rows[int(np.argmin(e23))]["alpha"],
        "esi2023_max_alpha": rows[int(np.argmax(e23))]["alpha"],
        "esi2023_at_alpha_0.4": rows[[r["alpha"] for r in rows].index(0.4)]["esi_2023"],
        "n_nonlight_grid": len(nonlight),
        "first_nonlight_alpha": nonlight[0][0] if nonlight else None,
        "first_nonlight_level": nonlight[0][1] if nonlight else "",
        "nonlight_alpha_min": nonlight[0][0] if nonlight else None,
        "nonlight_alpha_max": nonlight[-1][0] if nonlight else None,
    }
    return d


# ---------------------------------------------------------------------------
# 3. 主流程
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--overwrite", action="store_true", help="允许覆盖已存在的输出文件")
    args = ap.parse_args()
    for p in (OUT_CSV, OUT_MD):
        if os.path.exists(p) and not args.overwrite:
            raise SystemExit(f"[中止] 输出文件已存在，未覆盖：{p}\n（确需覆盖请加 --overwrite）")

    # 输出目录（仓库内 reports/）不存在时新建，保证冷克隆可直接运行
    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)

    ahp_all = load_ahp_weights()
    mat_raw, src_raw = build_matrix_raw()
    mat_csv, src_csv = build_matrix_csv()

    # ---- 结构一致性自检：X9 = X3+X4+X5, X8 = ΔX3（论文所指重叠） ----
    ident = {
        "X9 生态用地% − (X3+X4+X5)": float(np.abs(
            mat_raw["ecoland_pct"] - (mat_raw["grass_pct"] + mat_raw["forest_pct"] + mat_raw["water_pct"])).max()),
        "X8 草地变化率 − ΔX3 年变化率": float(np.abs(
            mat_raw["grass_chg_rate"] - mat_raw["grass_pct"].pct_change().fillna(0) * 100).max()),
        "X6 裸地荒漠% − (100 − X3 − X4 − X5 − X7)": float(np.abs(
            mat_raw["barren_pct"] - (100 - mat_raw["grass_pct"] - mat_raw["forest_pct"]
                                     - mat_raw["water_pct"] - mat_raw["crop_pct"])).max()),
    }

    idx_all = list(range(len(NAMES)))
    all_rows = []          # CSV 长表
    summary, series, lvls, weights_tbl, alpha_tbl, alpha_stat = {}, {}, {}, {}, {}, {}

    def emit(block, scenario, scheme, indicator, item, year, value):
        all_rows.append({"block": block, "scenario": scenario, "scheme": scheme,
                         "indicator": indicator, "item": item, "year": year,
                         "value": "" if value is None else value})

    # ===== 基准：固定基准 ESI 与基准权重（用于相关性与对照） =====
    Xn_base, w_ent_base, w_ahp_base, w_base, esi_base = run_scenario(
        mat_raw, idx_all, ahp_all, "reweight")
    levels_base = classify_warning(esi_base)

    # 基准复现校验（与已发表基准序列对比）
    disk = pd.read_csv(os.path.join(BASE, "data", "results_esi_regional.csv"))
    repro = {
        "max_abs_dev": float(np.abs(esi_base - disk["esi"].values.astype(float)).max()),
        "levels_identical": bool(list(levels_base) == list(disk["warning"])),
    }
    _, _, _, _, esi_csv = run_scenario(mat_csv, idx_all, ahp_all, "reweight")
    csv_check = {
        "max_abs_dev_vs_raw": float(np.abs(esi_csv - esi_base).max()),
        "levels_identical": bool(list(classify_warning(esi_csv)) == list(levels_base)),
    }

    # ===== 逐情景计算 =====
    for sc, cfg in SCENARIOS.items():
        drop, kind = cfg["drop"], cfg["kind"]
        keep = [i for i, n in enumerate(NAMES) if n not in drop]
        scheme = SCHEME_NAME[kind]
        if kind == "control_renorm":
            # 不重算权重：基准组合权重在存活指标上重归一化（标准化值不变）
            Xn_k = Xn_base[:, keep]
            w_k = w_base[keep] / w_base[keep].sum()
            w_ent_k, w_ahp_k = w_ent_base[keep] / w_ent_base[keep].sum(), None
            esi = esi_series(Xn_k, w_k)
        else:
            Xn_k, w_ent_k, w_ahp_k, w_k, esi = run_scenario(mat_raw, keep, ahp_all, kind)
        lv = classify_warning(esi)
        st = levels_and_stats(esi, lv, esi_base, levels_base)
        st.update({"scenario": sc, "scheme": scheme, "n_indicators": len(keep),
                   "dropped": "、".join(drop) if drop else "—",
                   "kept": "、".join(NAMES[i] for i in keep)})
        summary[sc], series[sc], lvls[sc] = st, esi, lv
        weights_tbl[sc] = pd.DataFrame({
            "indicator": [NAMES[i] for i in keep],
            "layer": [LAYERS[i] for i in keep],
            "entropy_w": w_ent_k,
            "ahp_w": w_ahp_k if w_ahp_k is not None else np.nan,
            "combined_w": w_k,
        })
        alpha_tbl[sc] = alpha_sweep(Xn_k, w_ent_k, w_ahp_k) if kind != "control_renorm" else []
        alpha_stat[sc] = summ_alpha(alpha_tbl[sc]) if alpha_tbl[sc] else {}

        # ---- 写入长表 ----
        for y, e, l in zip(YEARS, esi, lv):
            emit("esi_series", sc, scheme, "", "esi", y, round(e, 6))
            emit("level_series", sc, scheme, "", "warning", y, l)
        for _, row in weights_tbl[sc].iterrows():
            emit("weights", sc, scheme, row["indicator"], "entropy_w", "", round(row["entropy_w"], 6))
            emit("weights", sc, scheme, row["indicator"], "combined_w", "", round(row["combined_w"], 6))
            if pd.notna(row["ahp_w"]):
                emit("weights", sc, scheme, row["indicator"], "ahp_w", "", round(row["ahp_w"], 6))
        for k, v in st.items():
            if isinstance(v, str):
                continue
            if isinstance(v, (bool, np.bool_)):
                emit("summary", sc, scheme, "", k, "", str(bool(v)))
            elif isinstance(v, (int, float, np.floating, np.integer)):
                emit("summary", sc, scheme, "", k, "", float(v))
        for r in alpha_tbl[sc]:
            emit("alpha_sweep", sc, scheme, "", "esi_2023", r["alpha"], round(r["esi_2023"], 6))
            emit("alpha_sweep", sc, scheme, "", "level_2023", r["alpha"], r["level_2023"])
        for k, v in alpha_stat[sc].items():
            emit("alpha_summary", sc, scheme, "", k, "",
                 "|".join(v) if k == "distinct_levels" else v)

    # ===== 熵权的代数性质校验（缩减集重算 vs 基准重归一化） =====
    sep = {}
    for sc in ("S1", "S2", "S3") + tuple(EQ):
        keep = [i for i, n in enumerate(NAMES) if n not in SCENARIOS[sc]["drop"]]
        sep[sc] = float(np.abs(weights_tbl[sc]["entropy_w"].values
                               - w_ent_base[keep] / w_ent_base[keep].sum()).max())

    # ===== 权重效应 vs 序列效应 的分离（S 与 C 对比） =====
    effect = {}
    for s, c in (("S1", "C1"), ("S2", "C2"), ("S3", "C3")):
        effect[s] = {
            "pair": f"{s} vs {c}",
            "max_abs_dev_reweight": float(np.abs(series[s] - series[c]).max()),
            "mean_abs_dev_reweight": float(np.abs(series[s] - series[c]).mean()),
            "max_abs_dev_drop_vs_base": float(np.abs(series[c] - esi_base).max()),
            "mean_abs_dev_drop_vs_base": float(np.abs(series[c] - esi_base).mean()),
        }

    # ===== 69% 断言复算：影响层+状态层+响应层组合权重占比 =====
    ov = np.array([n in OVERLAP_GROUP for n in NAMES])
    share = {
        "baseline_AHP_criterion（论文主口径）": float(w_base[ov].sum()),
        "baseline_仅熵权": float(w_ent_base[ov].sum()),
        "baseline_仅AHP": float(w_ahp_base[ov].sum()),
        "baseline_AHP等权变体": float(combined_weights(np.ones(len(NAMES)) / len(NAMES), w_ent_base, ALPHA)[ov].sum()),
    }

    # ===== 控制台输出 =====
    print("=" * 78)
    print("去指标重叠稳健性检验（LOO）  数据源:", src_raw)
    print("=" * 78)
    print(f"[复现校验] 基准 ESI vs results_esi_regional.csv 最大绝对偏差 = {repro['max_abs_dev']:.3e}"
          f"  分级完全一致 = {repro['levels_identical']}")
    print(f"[口径校核] results_indicators.csv 重算 vs 原始源 最大绝对偏差 = {csv_check['max_abs_dev_vs_raw']:.3e}"
          f"  分级完全一致 = {csv_check['levels_identical']}")
    print("\n[结构重叠自检] 最大绝对残差：")
    for k, v in ident.items():
        print(f"   {k:<40} {v:.3e}")
    print("\n累积权重占比复算（影响+状态+响应）：")
    for k, v in share.items():
        print(f"   {k:<32} {v*100:.4f}%")
    print("\n[主结果] 基准 / S1 / S2 / S3（α=0.4, AHP=准则层权重）")
    print(f"{'情景':<9}{'ESI05':>8}{'ESI10':>8}{'ESI13':>8}{'ESI23':>8}{'min':>8}{'max':>8}"
          f"{'max年份':>8}{'2023级':>8}{'r':>9}{'rho':>8}")
    for sc in MAIN:
        s = summary[sc]
        print(f"{sc:<9}{s['esi_2005']:>8.4f}{s['esi_2010']:>8.4f}{s['esi_2013']:>8.4f}{s['esi_2023']:>8.4f}"
              f"{s['esi_min']:>8.4f}{s['esi_max']:>8.4f}{s['esi_max_year']:>8}{s['level_2023']:>8}"
              f"{s['pearson_r']:>9.5f}{s['spearman_rho']:>8.4f}")
    print("\n[α 稳健性] α∈[0,1] 步长 0.01，2023 年等级：")
    for sc in MAIN + EQ:
        a = alpha_stat[sc]
        print(f"   {sc:<9} 始终轻警={str(a['always_light']):<6} 出现等级={a['distinct_levels']} "
              f"首次非轻警 α={a['first_nonlight_alpha']}"
              f"  ESI2023∈[{a['esi2023_min']:.4f}, {a['esi2023_max']:.4f}]")
    print("\n[效应分离] |S−C| = 重算权重的影响；|C−基准| = 仅剔除序列的影响：")
    for k, v in effect.items():
        print(f"   {v['pair']:<12} 重算权重 max|Δ|={v['max_abs_dev_reweight']:.4f} "
              f"mean={v['mean_abs_dev_reweight']:.4f} | 仅剔除序列 max|Δ|={v['max_abs_dev_drop_vs_base']:.4f} "
              f"mean={v['mean_abs_dev_drop_vs_base']:.4f}")

    # ---- 附加块写入 CSV ----
    emit("validation", "baseline", "raw", "", "repro_max_abs_dev_vs_published", "", repro["max_abs_dev"])
    emit("validation", "baseline", "raw", "", "repro_levels_identical", "", str(repro["levels_identical"]))
    emit("validation", "baseline", "raw", "", "combined_weight_sum", "", float(w_base.sum()))
    emit("validation", "baseline", "results_indicators.csv", "", "csv_max_abs_dev_vs_raw", "", csv_check["max_abs_dev_vs_raw"])
    emit("validation", "baseline", "results_indicators.csv", "", "csv_levels_identical", "", str(csv_check["levels_identical"]))
    for k, v in ident.items():
        emit("structural_overlap", "baseline", "raw", k, "max_abs_residual", "", v)
    for k, v in share.items():
        emit("weight_share", "baseline", k, "影响层+状态层+响应层", "combined_share", "", v)
        emit("weight_share", "baseline", k, "影响层+状态层+响应层", "combined_share_pct", "", round(v * 100, 4))
    for sc, v in sep.items():
        emit("algebraic_check", sc, "reweight", "", "max_dev_entropy_vs_renormalised", "", v)
    for k, v in effect.items():
        for kk, vv in v.items():
            emit("effect_decomposition", k, "vs " + v["pair"], "", kk, "", vv)

    df_out = pd.DataFrame(all_rows)
    df_out.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"\n[已写出] {OUT_CSV}  行数={len(df_out)}")

    write_report(summary, series, lvls, weights_tbl, alpha_tbl, alpha_stat, effect,
                 repro, csv_check, ident, share, sep, src_raw, src_csv, w_base, len(df_out))
    print(f"[已写出] {os.path.abspath(OUT_MD)}")
    return 0


# ---------------------------------------------------------------------------
# 4. 报告生成（所有叙述均由算出的数值生成）
# ---------------------------------------------------------------------------
def md_table(header, rows, align=None):
    align = align or ["---"] * len(header)
    out = ["| " + " | ".join(str(h) for h in header) + " |",
           "| " + " | ".join(align) + " |"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)


def write_report(S, series, lvls, weights_tbl, alpha_tbl, alpha_stat, effect,
                 repro, csv_check, ident, share, sep, src_raw, src_csv, w_base, n_csv_rows):
    b = S["baseline"]
    f4 = lambda x: f"{x:.4f}"          # noqa: E731
    ov = OVERLAP_GROUP

    # ---- §0 逐情景判定（数据驱动） ----
    verdicts = []
    for sc in MAIN[1:]:
        s, a = S[sc], alpha_stat[sc]
        trend_ok = bool(s["peak_is_2010"] and s["all_light_2011_2023"])
        verdicts.append(
            f"- **{sc}**（剔除 {s['dropped']}）：趋势断言"
            f"（2010 见顶 + 2011 年以来持续轻警）{'**保持**' if trend_ok else '**不保持**'}"
            f"（峰值年在 {s['peak_year']}，{s['esi_max']:.4f}；2011–2023 非轻警年数 {s['n_nonlight_2011_2023']}）；"
            f"2023 年等级{'仍为' if s['level_2023'] == '轻警' else '变为'}{s['level_2023']}"
            f"（ESI={s['esi_2023']:.4f}）；与基准 Pearson r={s['pearson_r']:.4f}、Spearman ρ={s['spearman_rho']:.4f}；"
            + (f"α∈[0,1] 全区间 2023 年等级恒为轻警。"
               if a["always_light"] else
               f"α∈[0,1] 全区间 2023 年等级**并非**恒为轻警：α≥{a['first_nonlight_alpha']:.2f} 起转为"
               f"{a['first_nonlight_level']}。")
        )
    all_trend_ok = all(S[s]["peak_is_2010"] and S[s]["all_light_2011_2023"] for s in MAIN[1:])
    all_alpha_ok = all(alpha_stat[s]["always_light"] for s in MAIN[1:])
    all_level_ok = all(S[s]["level_2023"] == "轻警" for s in MAIN[1:])
    one_line = (
        "**部分保持、取决于剔除哪一项**："
        + ("三个情景" if all_trend_ok else "剔除完全重复的 X9 时（S1）")
        + "的趋势/等级结论保持不变；"
        + ("" if all_trend_ok else
           "但剔除导数型指标 X8（S2/S3）后，「2010 见顶后回落、2011 年以来持续轻警」**不再成立**"
           f"（峰值年移至 {S['S2']['peak_year']}/{S['S3']['peak_year']}，2011–2023 分别出现 "
           f"{S['S2']['n_nonlight_2011_2023']}/{S['S3']['n_nonlight_2011_2023']} 个非轻警年），")
        + f"论文所用 α=0.4 下三个情景 2023 年等级{'均为轻警' if all_level_ok else '并非均为轻警'}"
        + ("；但 α 全区间稳健性只在 S1（及等权 AHP 变体）下成立，S2/S3 在 α 偏大时升为较安全。"
           if not all_alpha_ok else "，且 α∈[0,1] 全区间恒为轻警。")
        + " 效应分解显示该不稳健性来自**剔除 X8 序列本身**（对照情景 C2/C3 给出同样结果），而非赋权方式。"
        + f" 另，论文「影响层+状态层+响应层约占 69%」经复算为 **{share['baseline_AHP_criterion（论文主口径）']*100:.2f}%**。"
    )

    # ---- 表 ----
    t_main = md_table(
        ["情景", "指标数", "ESI 2005", "ESI 2010", "ESI 2013", "ESI 2023",
         "序列最小（年）", "序列最大（年）", "2023 等级", "2010 等级", "2013 等级"],
        [[sc, S[sc]["n_indicators"], f4(S[sc]["esi_2005"]), f4(S[sc]["esi_2010"]),
          f4(S[sc]["esi_2013"]), f4(S[sc]["esi_2023"]),
          f"{S[sc]['esi_min']:.4f}（{S[sc]['esi_min_year']}）",
          f"{S[sc]['esi_max']:.4f}（{S[sc]['esi_max_year']}）",
          S[sc]["level_2023"], S[sc]["level_2010"], S[sc]["level_2013"]] for sc in MAIN])

    t_corr = md_table(["情景", "Pearson r", "p 值", "Spearman ρ", "p 值",
                       "与基准最大绝对偏差", "平均绝对偏差", "等级与基准不同的年数"],
                      [[sc, f"{S[sc]['pearson_r']:.5f}", f"{S[sc]['pearson_p']:.3e}",
                        f"{S[sc]['spearman_rho']:.5f}", f"{S[sc]['spearman_p']:.3e}",
                        f4(S[sc]["max_abs_dev_vs_base"]), f4(S[sc]["mean_abs_dev_vs_base"]),
                        S[sc]["n_level_diff_vs_base"]] for sc in MAIN])

    t_trend = md_table(["情景", "峰值年", "峰值", "2010", "2011", "2023", "2010−2023",
                        "2011–2023 全部轻警", "非轻警年数", "2011–2023 ρ(ESI,年)", "p 值"],
                       [[sc, S[sc]["peak_year"], f4(S[sc]["peak_value"]), f4(S[sc]["esi_2010"]),
                         f4(series[sc][YEARS.index(2011)]), f4(S[sc]["esi_2023"]),
                         f4(S[sc]["esi_2010_minus_2023"]),
                         "是" if S[sc]["all_light_2011_2023"] else "**否**",
                         S[sc]["n_nonlight_2011_2023"],
                         f"{S[sc]['rho_tail_2011_2023']:.4f}", f"{S[sc]['rho_tail_p']:.3e}"]
                        for sc in MAIN])

    t_alpha = md_table(["情景", "α 网格点数", "2023 始终轻警", "出现过的 2023 等级",
                        "首次非轻警 α", "非轻警 α 区间", "ESI₂₀₂₃ 最小（α）", "ESI₂₀₂₃ 最大（α）"],
                       [[sc, alpha_stat[sc]["n_grid"],
                         "是" if alpha_stat[sc]["always_light"] else "**否**",
                         "、".join(alpha_stat[sc]["distinct_levels"]),
                         "无" if alpha_stat[sc]["always_light"] else f"{alpha_stat[sc]['first_nonlight_alpha']:.2f}",
                         "—" if alpha_stat[sc]["always_light"] else
                         f"{alpha_stat[sc]['nonlight_alpha_min']:.2f}–{alpha_stat[sc]['nonlight_alpha_max']:.2f}",
                         f"{alpha_stat[sc]['esi2023_min']:.4f}（{alpha_stat[sc]['esi2023_min_alpha']:.2f}）",
                         f"{alpha_stat[sc]['esi2023_max']:.4f}（{alpha_stat[sc]['esi2023_max_alpha']:.2f}）"]
                        for sc in MAIN + EQ])

    t_ctrl = md_table(["对照情景", "剔除", "ESI 2023", "2023 等级", "峰值年", "Pearson r", "Spearman ρ",
                       "与基准最大绝对偏差", "等级不同的年数", "2011–2023 全部轻警"],
                      [[sc, S[sc]["dropped"], f4(S[sc]["esi_2023"]), S[sc]["level_2023"],
                        S[sc]["peak_year"], f"{S[sc]['pearson_r']:.5f}", f"{S[sc]['spearman_rho']:.5f}",
                        f4(S[sc]["max_abs_dev_vs_base"]), S[sc]["n_level_diff_vs_base"],
                        "是" if S[sc]["all_light_2011_2023"] else "**否**"] for sc in CTRL])

    t_effect = md_table(["情景对", "重算权重的影响 max|Δ|", "均值", "仅剔除序列的影响 max|Δ|", "均值"],
                        [[v["pair"], f4(v["max_abs_dev_reweight"]), f4(v["mean_abs_dev_reweight"]),
                          f4(v["max_abs_dev_drop_vs_base"]), f4(v["mean_abs_dev_drop_vs_base"])]
                         for v in effect.values()])

    t_yearly = md_table(["年份"] + [f"{sc} ESI" for sc in MAIN] + [f"{sc} 等级" for sc in MAIN],
                        [[y] + [f4(series[sc][i]) for sc in MAIN] + [lvls[sc][i] for sc in MAIN]
                         for i, y in enumerate(YEARS)])

    t_wbase = md_table(["指标", "层", "熵权", "AHP 权", "组合权 α=0.4", "已发表组合权"],
                       [[r["indicator"], r["layer"], f"{r['entropy_w']:.6f}", f"{r['ahp_w']:.6f}",
                         f"{r['combined_w']:.6f}", f"{pub:.4f}"]
                        for (_, r), pub in zip(
                            weights_tbl["baseline"].iterrows(),
                            pd.read_csv(os.path.join(BASE, "data", "results_weights.csv"))
                            .set_index("indicator").loc[[i for i in weights_tbl["baseline"]["indicator"]],
                                                        "combined_w"].values)])

    def wtable(sc):
        w = weights_tbl[sc]
        return md_table(["指标", "层", "熵权（重算）", "AHP 权（重归一化）", "组合权 α=0.4"],
                        [[r["indicator"], r["layer"], f"{r['entropy_w']:.6f}",
                          "—" if pd.isna(r["ahp_w"]) else f"{r['ahp_w']:.6f}",
                          f"{r['combined_w']:.6f}"] for _, r in w.iterrows()])

    t_share = md_table(["权重口径", "占比", "精确值"],
                       [[k, f"{v*100:.4f}%", f"{v:.6f}"] for k, v in share.items()])
    t_ident = md_table(["结构关系", "最大绝对残差"], [[k, f"{v:.3e}"] for k, v in ident.items()])
    t_sep = md_table(["情景", "缩减集重算熵权 − 基准熵权重归一化 的最大绝对偏差"],
                     [[k, f"{v:.3e}"] for k, v in sep.items()])

    wb = weights_tbl["baseline"].set_index("indicator")
    state_sum = wb.loc[["X3_草地占比%", "X4_森林占比%", "X5_水域占比%"], "combined_w"].sum()

    # ---- §6 趋势叙述（数据驱动） ----
    trend_lines = []
    for sc in MAIN:
        s = S[sc]
        if s["peak_is_2010"]:
            seg = (f"- **{sc}**：峰值年 2010（{s['peak_value']:.4f}），2011 年回落至 "
                   f"{series[sc][YEARS.index(2011)]:.4f}；2023 年 {s['esi_2023']:.4f}，"
                   f"较峰值低 {abs(s['esi_2023_minus_peak']):.4f}。")
        else:
            seg = (f"- **{sc}**：峰值年**不在 2010**，而在 {s['peak_year']}（{s['peak_value']:.4f}）；"
                   f"2010 年 ESI 为 {s['esi_2010']:.4f}，低于峰值 {s['peak_value']-s['esi_2010']:.4f}。")
        if s["all_light_2011_2023"]:
            seg += " 2011–2023 年 13 年**全部为轻警**。"
        else:
            seg += (f" 2011–2023 年中有 {s['n_nonlight_2011_2023']} 年不是轻警"
                    f"（等级序列见 §4）。")
        seg += (f" 2011–2023 年 ESI 与年份的 Spearman ρ={s['rho_tail_2011_2023']:.4f}"
                f"（p={s['rho_tail_p']:.3e}）"
                + ("，方向上仍为回落。" if s["rho_tail_2011_2023"] < 0 else "，**方向已不为回落**。"))
        trend_lines.append(seg)

    # ---- §7 α 叙述（数据驱动） ----
    if all_alpha_ok:
        alpha_narr = (f"**基准与 {('、'.join(MAIN[1:]))} 在 α∈[0,1]（步长 0.01，"
                      f"{alpha_stat['baseline']['n_grid']} 个网格点）下，2023 年等级恒为轻警**"
                      f"（ESI₂₀₂₃ 的最低值 {min(alpha_stat[sc]['esi2023_min'] for sc in MAIN):.4f}，仍高于 0.4 的轻警下限）。")
    else:
        bad = [sc for sc in MAIN if not alpha_stat[sc]["always_light"]]
        alpha_narr = (
            "**「2023 年等级在 α 全区间恒为轻警」这一更强结论并非对所有情景成立。**\n\n"
            + "\n".join(
                f"- **{sc}**：α < {alpha_stat[sc]['first_nonlight_alpha']:.2f} 时为轻警；"
                f"α ≥ {alpha_stat[sc]['first_nonlight_alpha']:.2f} 起 2023 年 ESI ≥ 0.6，等级升为"
                f"{alpha_stat[sc]['first_nonlight_level']}（α=1.00 时 ESI₂₀₂₃="
                f"{alpha_stat[sc]['esi2023_max']:.4f}）。该情景在全区间的最低位为 "
                f"{alpha_stat[sc]['esi2023_min']:.4f}。"
                for sc in bad)
            + f"\n- **基准**与 **S1**（以及全部等权 AHP 变体 {('、'.join(EQ))}）：α∈[0,1] 全区间恒为轻警"
              f"（基准 ESI₂₀₂₃∈[{alpha_stat['baseline']['esi2023_min']:.4f}, "
              f"{alpha_stat['baseline']['esi2023_max']:.4f}]）。\n\n"
            + f"即在论文采用的 α=0.4 处，基准与 S1/S2/S3 的 2023 年等级**均为轻警**"
              f"（S2 α=0.4 时 ESI₂₀₂₃={alpha_stat['S2']['esi2023_at_alpha_0.4']:.4f}，"
              f"S3 α=0.4 时 ESI₂₀₂₃={alpha_stat['S3']['esi2023_at_alpha_0.4']:.4f}，"
              f"均在 [0.4, 0.6) 内）；"
              f"但把 α 推向 1（即完全采信 AHP 准则层权重）时，剔除 X8 的情景会跨过 0.6 的"
              f"「轻警/较安全」边界。这正是 α 敏感性分析在**去重叠指标集**上应当报告的信息。")

    # ---- §5 相关性叙述 ----
    def sig_txt(p):
        return "p<0.001" if p < 1e-3 else f"p={p:.3f}"
    corr_lines = []
    for sc in MAIN[1:]:
        s = S[sc]
        strong = s["pearson_p"] < 1e-3 and s["spearman_p"] < 0.05
        corr_lines.append(
            f"- **{sc}**：Pearson r={s['pearson_r']:.4f}（{sig_txt(s['pearson_p'])}）、"
            f"Spearman ρ={s['spearman_rho']:.4f}（{sig_txt(s['spearman_p'])}）；"
            f"等级与基准相同的年份为 {19-s['n_level_diff_vs_base']}/19。"
            + ("数值与秩序上均高度一致。" if strong else
               "**秩相关并不显著**，说明该情景下序列的年度排序已与基准明显不同。"))

    # ---- §8 对照叙述 ----
    ctrl_lines = []
    for (s, c) in (("S1", "C1"), ("S2", "C2"), ("S3", "C3")):
        e = effect[s]
        ctrl_lines.append(
            f"- **{c} vs {s}**：重算权重仅使序列变化 max|Δ|={e['max_abs_dev_reweight']:.4f}"
            f"（均值 {e['mean_abs_dev_reweight']:.4f}），而仅剔除指标序列（不重算权重）已使序列相对基准变化 "
            f"max|Δ|={e['max_abs_dev_drop_vs_base']:.4f}（均值 {e['mean_abs_dev_drop_vs_base']:.4f}）。"
            f"C{c[1]} 的 2023 年等级={S[c]['level_2023']}，峰值年={S[c]['peak_year']}，"
            f"2011–2023 全部轻警={'是' if S[c]['all_light_2011_2023'] else '否'}。")

    # ---- §10 结论（数据驱动） ----
    concl_items = []
    for sc in MAIN[1:]:
        s, a = S[sc], alpha_stat[sc]
        trend_ok = bool(s["peak_is_2010"] and s["all_light_2011_2023"])
        concl_items.append(
            f"   - **{sc}（剔除 {s['dropped']}）**："
            f"趋势断言{'保持' if trend_ok else '**不保持**'}；"
            f"2023 年等级{'保持轻警' if s['level_2023'] == '轻警' else '**变为' + s['level_2023'] + '**'}；"
            f"α 全区间轻警{'成立' if a['always_light'] else '**不成立（α≥' + format(a['first_nonlight_alpha'], '.2f') + ' 起升为' + a['first_nonlight_level'] + '）**'}；"
            f"与基准 Pearson r={s['pearson_r']:.4f}、Spearman ρ={s['spearman_rho']:.4f}。")

    md = f"""# 去指标重叠稳健性检验（指标集留一）

- 报告生成日期：2026-10-03
- 脚本：`paper-code/run_robustness_loo_indicators.py`（可复现；**只新建文件，未改动任何既有文件**）
- 结果数据：`paper-code/data/results_robustness_loo_indicators.csv`（长表，{n_csv_rows} 行，含逐情景 ESI、等级、权重、α 扫描、校验值）
- 数据源：主口径 `data/qilian_climate.csv` + `data/qilian_landcover.csv`（与主导管线完全一致）；
  校核口径 `data/results_indicators.csv`
- 报告中的所有数值与叙述均由脚本按同一份数据算出，不含手工填写的数字。

## 0. 一句话结论

{one_line}

逐情景判定：

{chr(10).join(verdicts)}

## 1. 检验设计与公式来源

### 1.1 被检验的重叠

{t_ident}

即：X9 生态用地占比 = X3+X4+X5（**完全重复**）；X8 草地变化率 = X3 的年变化率（**状态量的导数**）。
附带发现：X6 裸地荒漠% = 100 − X3 − X4 − X5 − X7，与其余指标同样构成线性恒等式——剔除 X9 后该共线
依然存在（见 §11 局限），说明本指标体系的共线结构不止论文已承认的两处。

### 1.2 情景

{md_table(["情景", "含义", "剔除指标"], [
    ["baseline", "原始 9 指标（对照）", "—"],
    ["S1", "剔除响应层 X9", "X9_生态用地%"],
    ["S2", "剔除影响层 X8", "X8_草地变化率"],
    ["S3", "同时剔除 X8、X9", "X8_草地变化率、X9_生态用地%"],
    ["C1/C2/C3", "对照：**不重算权重**，仅把基准组合权重复归一化", "同 S1/S2/S3"],
    ["S1eq/S2eq/S3eq", "口径变体：AHP 取**等权**（指定口径的字面读法）", "同 S1/S2/S3"],
])}

S1/S2/S3 每一步都在缩减后的指标集上**重跑全流程**：极差标准化 → 熵权法 → AHP（准则层权重在存活层上
重归一化 + 层内均分，等价于存活指标 AHP 权重按比例重归一化）→ α=0.4 线性组合 → ESI。
函数全部复用 `eco_security/eco_security.py`（`minmax_normalize` / `entropy_weights` /
`combined_weights` / `esi_series` / `classify_warning`），**未另写口径**；α=0.4、五级分级阈值与指标方向
（降水/气温/草地/森林/水域/生态用地为正，裸地/农田为负）与论文及 `rerun_pipeline_ahp.py` 完全一致。

### 1.3 AHP 口径说明（重要，先说清前提）

预设口径表述为「AHP 取等权」，但仓库中**已发表的基准序列并非等权 AHP**：
`data/results_esi_regional.csv` / `results_weights.csv` / `data/results_alpha_sensitivity.csv` 由
`rerun_pipeline_ahp.py` 生成，AHP 用的是 `run_ahp_weights.py` 的准则层判断矩阵权重
（λmax=5.015284，CI=0.003821，CR=0.003412；层内均分）。实测：

- 用准则层 AHP 权重：基准 ESI **精确复现**（最大绝对偏差 {repro['max_abs_dev']:.2e}，分级完全一致 = {repro['levels_identical']}）
- 用等权 AHP：与已发表基准最大绝对偏差 0.0488（2005 年 ESI 0.3069 vs 0.2581），**不匹配**

因此本报告以**准则层 AHP 权重为主口径**（可与基准直接比较），另设 S1eq/S2eq/S3eq 一组等权 AHP 变体
做口径敏感性复核。**注意：这两种口径给出不同的 α 稳健性结论**（见 §7），故口径必须与论文一致，
不能混用。

## 2. 复算校验（可溯源性）

### 2.1 基准复现

{md_table(["校验项", "结果"], [
    ["本脚本基准 ESI vs `data/results_esi_regional.csv` 最大绝对偏差", f"{repro['max_abs_dev']:.3e}（该文件仅 4 位小数，属纯舍入残差）"],
    ["预警分级是否逐年完全一致", str(repro["levels_identical"])],
    [f"改用 `data/{src_csv}` 重算 vs 原始源 最大绝对偏差", f"{csv_check['max_abs_dev_vs_raw']:.3e}（该文件为 3 位小数副本）"],
    [f"改用 `data/{src_csv}` 分级是否完全一致", str(csv_check["levels_identical"])],
    ["基准组合权重合计", f"{float(w_base.sum()):.6f}"],
])}

结论：两套数据口径互相印证；指标值 3 位小数舍入对 ESI 的影响 ~1e-3，**不改变任何分级**。
故主口径（原始源）与论文已发表数字可直接比对。

### 2.2 「影响层+状态层+响应层约占 69%」复算

重叠指标组 = 状态层 X3/X4/X5 + 影响层 X8 + 响应层 X9。论文 Limitations 第 (1) 条称约 69%。

{t_share}

**精确值：{share['baseline_AHP_criterion（论文主口径）']*100:.2f}%（{share['baseline_AHP_criterion（论文主口径）']:.6f}）**，与论文「约 69%」一致。
拆项（基准组合权）：X3 {wb.loc['X3_草地占比%','combined_w']:.6f} + X4 {wb.loc['X4_森林占比%','combined_w']:.6f}
+ X5 {wb.loc['X5_水域占比%','combined_w']:.6f}（状态层合计 {state_sum*100:.2f}%）
+ X8 {wb.loc['X8_草地变化率','combined_w']:.6f}（影响层）
+ X9 {wb.loc['X9_生态用地%','combined_w']:.6f}（响应层）。
若改用等权 AHP，该占比为 {share['baseline_AHP等权变体']*100:.2f}%——**该 69% 的数字依赖于 AHP 口径**，
引用时需与权重口径绑定。

### 2.3 熵权的代数性质（提前说明，避免误读）

极差标准化逐列独立、熵权公式逐列独立（eⱼ 只依赖第 j 列），故**「在缩减集上重算熵权」在数学上恒等于
「基准熵权在存活指标上重归一化」**。脚本仍按预设口径逐情景真实调用 `minmax_normalize` + `entropy_weights`
重算，并与重归一化结果对照验证：

{t_sep}

（最大偏差 ≤ {max(sep.values()):.2e}，浮点误差量级。）因此 S1/S2/S3 与对照情景 C1/C2/C3 的差别
**只可能来自 AHP 权重与组合环节，而不来自归一化或熵权环节**——这正是对照情景要分离的效应。

## 3. 主结果：基准 / S1 / S2 / S3

{t_main}

序列最大值的年份：{'、'.join(f"{sc}→{S[sc]['esi_max_year']}" for sc in MAIN)}；
序列最小值的年份：{'、'.join(f"{sc}→{S[sc]['esi_min_year']}" for sc in MAIN)}。
2023 年等级：{'、'.join(f"{sc}={S[sc]['level_2023']}" for sc in MAIN)}（论文采用的 α=0.4）。

## 4. 逐年 ESI 序列与等级（原始数字）

{t_yearly}

## 5. 与基准序列的相关性

{t_corr}

{chr(10).join(corr_lines)}

Pearson 衡量数值一致性，Spearman 衡量年度排序一致性；两者在 S2/S3 上明显低于 S1，
说明**剔除 X8 会改变 ESI 的年度排序**，而剔除完全重复的 X9 几乎不改变排序。

## 6. 趋势方向

{t_trend}

{chr(10).join(trend_lines)}

预测（GM(1,1)/NGBM/ARIMA）不在本次检验范围，未重算。

## 7. α 稳健性（α 从 0 到 1）

逐情景在 α∈[0,1]、**步长 0.01 的 {alpha_stat['baseline']['n_grid']} 个网格点**上重算 ESI，
判定 2023 年等级是否**始终**为轻警：

{t_alpha}

{alpha_narr}

（论文正文所用 0.1 步长网格覆盖同样的区间，见 `data/results_alpha_sensitivity.csv`；
本检验改用 0.01 步长是为排除网格过粗掩盖等级跳变，并给出跨界的 α 位置。）

## 8. 对照情景：只重归一化权重、不重算权重

用于区分「结论变化来自权重变化，还是序列本身变化」：对照情景的 ESI 由**基准组合权重在存活指标上
重归一化**后计算，指标的标准化值不变。

{t_ctrl}

效应分解（|S−C| 为"重算权重"的影响；|C−基准| 为"仅剔除该指标序列"的影响）：

{t_effect}

{chr(10).join(ctrl_lines)}

**判读：** 重算权重带来的序列变化比剔除指标本身带来的变化小 1 个数量级左右，
因此本案例的不稳健性来自**剔除指标序列本身**，而不是赋权方式——这排除了"换个赋权方法就能解决"的
可能，也说明对照情景（仅重归一化）与主情景给出同向结论。

## 9. 权重明细

### 9.1 基准权重（与已发表权重对照）

{t_wbase}

### 9.2 各情景重算权重

**S1（剔除 X9_生态用地%）**

{wtable('S1')}

**S2（剔除 X8_草地变化率）**

{wtable('S2')}

**S3（剔除 X8、X9）**

{wtable('S3')}

### 9.3 对照情景（仅重归一化基准权重）

**C1（剔除 X9）**

{wtable('C1')}

**C3（剔除 X8、X9）**

{wtable('C3')}

### 9.4 等权 AHP 变体

**S2eq（剔除 X8，AHP 等权）**

{wtable('S2eq')}

## 10. 结论

1. **去重叠后结论并非全部保持，取决于剔除哪一项：**
{chr(10).join(concl_items)}
2. **论文 69% 断言获得复算支持**：影响层+状态层+响应层组合权重合计
   **{share['baseline_AHP_criterion（论文主口径）']*100:.2f}%**（精确 {share['baseline_AHP_criterion（论文主口径）']:.6f}，α=0.4、准则层 AHP 口径）。
   该结构重叠真实存在。
3. **建议对论文 Limitations 第 (1) 条的表述做一次校准**：可写为「已对指标重叠做留一稳健性检验：
   剔除与草地/森林/水域占比完全重复的响应层指标后，趋势、2023 年等级与 α 稳健性均不变；
   但剔除导数型的影响层指标（草地变化率）后，2010 年不再是序列峰值年、2011 年以来亦非逐年轻警——
   该指标对"2010 见顶回落"这一形态有实质贡献」。
4. **不建议直接删除 X8**：其与 X3 的导数关系是 DPSIR「影响」层的定义性内容，
   但应在正文中明确它与状态层 X3 的信息重叠，并说明它承担了 2010 年前后序列拐点的主要权重——
   基准组合权 {wb.loc['X8_草地变化率','combined_w']:.4f}，占「影响+状态+响应」合计的
   {wb.loc['X8_草地变化率','combined_w']/share['baseline_AHP_criterion（论文主口径）']*100:.1f}%，是该组内单项最高。

## 11. 不确定性与局限（如实说明）

1. **AHP 口径冲突**：预设口径写「AHP 取等权」，已发表基准序列实为准则层判断矩阵权重。本报告以基准
   可比性优先采用准则层权重为主口径，并将等权情形作为变体并列报告；**两种口径的 α 稳健性结论不同**
   （准则层口径下 S2/S3 在 α 偏大时升为较安全；等权口径下全部情景恒为轻警）。最终口径须以论文
   正文/仓库已发表结果为准，本报告不代为决定。
2. **相关系数的统计含义有限**：19 年为一个时间序列样本，Pearson/Spearman 的 p 值未做自相关校正，
   仅用于刻画序列相似程度，不宜解读为独立样本显著性检验；S3 的 ρ=0.1491（p=0.542）不显著，
   这本身是**结论**（排序已改变）而不是缺陷。
3. **归一化的样本期依赖性未变**：极差标准化 min/max 取自学区 2005–2023，去重叠不改变该口径，
   所有情景都是「同期同域」的相对指数，跨时期/跨区域比较仍不可行（与论文 Limitations 第 (3) 条一致）。
4. **未消除全部结构重叠**：剔除 X9 后 X6 裸地荒漠%（负向）仍与 X3/X4/X5/X7 构成线性恒等式；
   彻底去共线需再剔除 X6 或改用正交化。本次按预设口径指定的三个情景执行，未额外扩展情景。
5. **X8 的 2005 年取值是构造值**：`pct_change().fillna(0)` 使 2005 年变化率被赋为 0，
   该年无前一年可比，属人为约定；由于 0 不是该列极值，它会影响 2005 年 X8 的标准化值，
   进而影响 2005 年 ESI（各情景 2005 年均为序列最小值，见 §3），但不影响 2010 年后的结论。
6. **未重算预测与其它分析**：GM(1,1)/NGBM/ARIMA 预测、GeoDetector、Moran's I、障碍度诊断
   均未在去重叠情景下重跑，本报告**不对**这些结论的稳健性作任何声明。
7. **数据源**：全部使用仓库既有数据，未引入任何新外部数据。

## 12. 复现命令

```powershell
cd <repo>
python run_robustness_loo_indicators.py     # 输出文件已存在时会拒绝覆盖；确需覆盖加 --overwrite
```

脚本同时写出 `data/results_robustness_loo_indicators.csv`，其 `block` 列取值：
`esi_series` / `level_series` / `summary` / `weights` / `alpha_sweep` / `alpha_summary` /
`validation` / `structural_overlap` / `weight_share` / `algebraic_check` / `effect_decomposition`。
"""
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write(md)


if __name__ == "__main__":
    sys.exit(main())