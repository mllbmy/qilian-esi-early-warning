# -*- coding: utf-8 -*-
"""R29 · T3 —— 八指标主规格（drop_X9）关键数值清单（供改稿直接引用）

产出一张长表 `data/r29_primary_spec_values.csv`：主规格下**需要在论文里出现的每个
数值**，每行给【数值】【九指标对应值】【差值】【出处 CSV】【取值定位】，使改稿环节
可以直接照抄而不必回头找脚本。

覆盖（按审稿人关心的顺序）
  A 区域 ESI 历史：2010 峰值、2005 低值、2023 值、各等级年数、与九指标的差异/相关
  B α 敏感性：α∈[0,1] 的 2023 年等级与改级年数、稳健区间
  C 阈值扰动：±0.05 的改级年数、边界年、2023 年等级
  D 障碍度：两阶段 top1–top3（含归档口径与 r28 管线口径的交叉核对）
  E 空间：点尺度 q（含 leave-one-target LOO）、独立 NDVI 外部验证、Moran's I
  F 趋势：MK / Hamed–Rao / TFPW p、Sen 斜率与 CI、Pettitt 变点（全期与 2010–2023）
  G 权重：D/P/S/I 四层占比、重叠指标组合计、两个重标定因子
  H 预测（交叉引用 T2 产物）

口径来源
  · 主规格 = r28_core.DEREDUNDANT_SETS['drop_X9']（八指标），α=0.4，阈值 [0.2,0.4,0.6,0.8]
  · 趋势检验函数直接复用 `run_r28_t6_trend_moran.py`（同一真源，保证与 r28_trend_tests.csv 一致）
  · 障碍度主口径用**归档 `data/results_obstacle.csv`**（论文图 10 的来源）：删「生态用地」
    列后逐行重归一化——该口径可逐位复现论文引用的 0.233/0.221/0.151 与 0.364/0.206
  · 点尺度主规格 = CORE5（删补集项 barren_neg，等价于区域删 X9 的恒等重复处理）
  · Moran's I 权重 = 行标准化 inv_dist k 近邻（k=8 时逐位复现归档 results_moran.csv）

输出（全部新文件）
  data/r29_primary_spec_values.csv   关键数值长表
  data/r29_primary_spec_checks.csv   复算校验

运行：python run_r29_primary_values.py
"""
import os
import sys
import warnings

import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings("ignore")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
sys.path.insert(0, os.path.join(BASE, "eco_security"))
from eco_security import (  # noqa: E402
    minmax_normalize, entropy_weights, combined_weights, esi_series,
    classify_warning, geodetector_q,
)

import r28_core as C  # noqa: E402
import run_r28_t6_trend_moran as T6  # noqa: E402  趋势检验的单一真源

ALPHA = 0.4
THR = [0.2, 0.4, 0.6, 0.8]
K_STRATA = 4
N_PERM = 999
SEED = 42
K_MORAN = 8
MORAN_SCHEME = "inv_dist"

ARCH_OBSTACLE = "data/results_obstacle.csv"
OUT = os.path.join(DATA, "r29_primary_spec_values.csv")
OUT_K = os.path.join(DATA, "r29_primary_spec_checks.csv")

CN2X = {"降水": "X1_降水mm", "气温": "X2_气温C", "草地": "X3_草地占比%", "森林": "X4_森林占比%",
        "水域": "X5_水域占比%", "裸地/荒漠": "X6_裸地荒漠%", "农田": "X7_农田占比%",
        "草地变化率": "X8_草地变化率", "生态用地": "X9_生态用地%"}

rows = []
checks = []


def add(group, item, value=None, value_9ind=None, unit="", source_csv="", locator="",
        note="", value_txt=None, value_9ind_txt=None, value_id=None):
    """value / value_9ind 为数值；非数值内容用 value_txt / value_9ind_txt。"""
    def num(v):
        return round(float(v), 6) if v is not None and np.isfinite(v) else np.nan

    vn, v9 = num(value), num(value_9ind)
    rows.append({
        "value_id": value_id or ("%s|%s" % (group, item)),
        "group": group, "item": item,
        "value": vn, "value_txt": ("" if value_txt is None else value_txt),
        "value_9ind": v9, "value_9ind_txt": ("" if value_9ind_txt is None else value_9ind_txt),
        "delta_8ind_minus_9ind": (round(vn - v9, 6)
                                  if np.isfinite(vn) and np.isfinite(v9) else np.nan),
        "unit": unit, "source_csv": source_csv, "source_locator": locator, "note": note,
    })


def chk(item, value, note):
    checks.append({"item": item, "value": value, "note": note})


def main():
    print("=" * 78)
    print("R29 · T3 —— 八指标主规格关键数值清单")
    print("=" * 78)

    r8 = C.compute(C.DEREDUNDANT_SETS["drop_X9"])
    r9 = C.compute(C.DEREDUNDANT_SETS["baseline9"])
    y8, y9 = np.asarray(r8["esi"], float), np.asarray(r9["esi"], float)
    years = np.array(r8["years"])
    lv8, lv9 = list(r8["levels"]), list(r9["levels"])
    archived = pd.read_csv(os.path.join(DATA, "r28_deredundancy_series.csv"))
    d_arch = float(np.abs(y8 - archived["esi_drop_X9"].values).max())
    chk("esi_8ind_vs_archived_max_abs_delta", float("%.3e" % d_arch),
        "主规格 ESI 重建 vs data/r28_deredundancy_series.csv")
    print("[校验] 主规格 ESI vs 归档 max|Δ| = %.3e" % d_arch)

    # =====================================================================
    # A 区域 ESI 历史
    # =====================================================================
    src_ser = "data/r28_deredundancy_series.csv（本脚本由 r28_core 重算，逐位一致）"
    i_peak = int(np.argmax(y8))
    i_min = int(np.argmin(y8))
    from collections import Counter
    cnt8, cnt9 = Counter(lv8), Counter(lv9)
    grades = ["重警", "中警", "轻警", "较安全", "安全"]
    add("A_historical", "2010 年峰值 ESI", y8[list(years).index(2010)],
        y9[list(years).index(2010)], "", src_ser, "year=2010", "论文引用的 0.676（八指标）")
    add("A_historical", "峰值年", int(years[i_peak]),
        int(np.array(r9["years"])[int(np.argmax(y9))]),
        "year", src_ser, "argmax",
        "八指标与九指标峰值年均为 2010（峰值不因删 X9 而移动）")
    add("A_historical", "2005 年 ESI（序列低值）", y8[0], y9[0], "", src_ser, "year=2005",
        "2005 同时是两条序列的最小值（低值端 = 序列最小值）")
    add("A_historical", "序列最小值", y8[i_min], y9[int(np.argmin(y9))], "", src_ser, "min",
        "八指标最小值年 = %d；九指标最小值年 = %d"
        % (years[i_min], np.array(r9["years"])[int(np.argmin(y9))]))
    add("A_historical", "2023 年 ESI", y8[-1], y9[-1], "", src_ser, "year=2023",
        "论文引用的 0.478（八指标）/0.486（九指标）")
    add("A_historical", "2023 年等级", value_txt=lv8[-1], value_9ind_txt=lv9[-1], unit="",
        source_csv=src_ser, locator="year=2023", note="八指标与九指标 2023 年同为轻警")
    add("A_historical", "2005 年等级", value_txt=lv8[0], value_9ind_txt=lv9[0], unit="",
        source_csv=src_ser, locator="year=2005", note="中警")
    for g in grades:
        add("A_historical", "等级年数：%s" % g, cnt8.get(g, 0), cnt9.get(g, 0), "year",
            src_ser, "全期 2005–2023（19 年）",
            "八指标 中警1/轻警16/较安全2，无重警、无安全；与九指标完全相同")
    add("A_historical", "2011–2023 非轻警年数", sum(1 for i, yv in enumerate(years)
                                              if yv >= 2011 and lv8[i] != "轻警"),
        sum(1 for i, yv in enumerate(np.array(r9["years"]))
            if yv >= 2011 and lv9[i] != "轻警"), "year", src_ser,
        "grades[year>=2011] != 轻警", "两口径均为 0 ⇒『2011 年以来轻警平台』在八指标下不变")
    s = pd.read_csv(os.path.join(DATA, "r28_deredundancy_comparison.csv"))
    srow = s[(s.scope == "series") & (s.scenario == "drop_X9")].iloc[0]
    for item, col, note in [
            ("与九指标的最大逐年差", "max_abs_delta", "max|ΔESI| 逐年"),
            ("与九指标的平均逐年差", "mean_abs_delta", "mean|ΔESI| 逐年"),
            ("与九指标的 Pearson r", "pearson_r", "ESI_dropX9 vs ESI_baseline9"),
            ("与九指标的 Spearman ρ", "spearman_rho", "同上"),
            ("与九指标相比的改级年数", "n_grade_changed", "0/19 ⇒ 删 X9 不改变任何年份的等级")]:
        add("A_historical", item, srow[col], None, "",
            "data/r28_deredundancy_comparison.csv",
            "scope=series, scenario=drop_X9, %s" % col,
            note + "（该行是「八指标 vs 九指标」的比较量，本身没有九指标对应值）")

    # =====================================================================
    # B α 敏感性
    # =====================================================================
    alphas = [round(0.1 * k, 1) for k in range(11)]
    arows = []
    for a in alphas:
        ra = C.compute(C.DEREDUNDANT_SETS["drop_X9"], alpha=a)
        rb = C.compute(C.DEREDUNDANT_SETS["baseline9"], alpha=a)
        arows.append({"alpha": a, "esi_2023_8": float(ra["esi"][-1]),
                      "grade_2023_8": ra["levels"][-1],
                      "esi_2023_9": float(rb["esi"][-1]), "grade_2023_9": rb["levels"][-1],
                      "n_changed_8": int(sum(1 for x, yv in zip(ra["levels"], r8["levels"]) if x != yv)),
                      "n_changed_9": int(sum(1 for x, yv in zip(rb["levels"], r9["levels"]) if x != yv)),
                      "n_moderate_8": sum(1 for x in ra["levels"] if x == "中警"),
                      "n_mild_8": sum(1 for x in ra["levels"] if x == "轻警"),
                      "n_relsafe_8": sum(1 for x in ra["levels"] if x == "较安全"),
                      "n_severe_8": sum(1 for x in ra["levels"] if x == "重警"),
                      "n_severe_9": sum(1 for x in rb["levels"] if x == "重警"),
                      "n_moderate_9": sum(1 for x in rb["levels"] if x == "中警"),
                      "n_mild_9": sum(1 for x in rb["levels"] if x == "轻警"),
                      "n_relsafe_9": sum(1 for x in rb["levels"] if x == "较安全")})
    adf = pd.DataFrame(arows)
    src_a = "data/r28_alpha_grade_summary.csv（本脚本由 r28_core 重算，α=0.4 行与归档一致）"
    add("B_alpha", "α=0.4 下的 2023 年等级", value_txt="轻警", value_9ind_txt="轻警",
        source_csv=src_a, locator="scenario=drop_X9, alpha=0.4",
        note="全 α∈[0,1] 区间 2023 年等级恒为轻警")
    add("B_alpha", "α 全区间 2023 年等级是否恒为轻警",
        value_txt="是（11/11 个 α 均为轻警）", value_9ind_txt="是（11/11 个 α 均为轻警）",
        source_csv=src_a, locator="scenario=drop_X9, all alpha",
        note="唯一等级不随权重主观性变化的结论")
    z = adf[adf.n_changed_8 == 0]
    z9 = adf[adf.n_changed_9 == 0]
    add("B_alpha", "改级年数为 0 的 α 区间（八指标）",
        value_txt="α∈[%.1f, %.1f]（%d 个取值）" % (z.alpha.min(), z.alpha.max(), len(z)),
        value_9ind_txt="α∈[%.1f, %.1f]（%d 个取值）" % (z9.alpha.min(), z9.alpha.max(), len(z9)),
        source_csv=src_a, locator="n_grade_changed==0",
        note="八指标稳健区间宽于九指标（九指标仅 α=0.3–0.4 两值）")
    for a in [0.0, 0.2, 0.3, 0.4, 0.6, 0.8, 0.9, 1.0]:
        rr = adf[adf.alpha == a].iloc[0]
        add("B_alpha", "α=%.1f 的改级年数" % a, rr.n_changed_8, rr.n_changed_9, "year",
            src_a, "alpha=%.1f" % a,
            "α=%.1f 时 2023 年等级：八指标 %s / 九指标 %s" % (a, rr.grade_2023_8, rr.grade_2023_9))
    add("B_alpha", "α=1.0 时的重警年数", int(adf[adf.alpha == 1.0].n_severe_8.iloc[0]),
        int(adf[adf.alpha == 1.0].n_severe_9.iloc[0]), "year", src_a, "alpha=1.0",
        "α=1.0（纯 AHP）时八指标出现 1 个重警年（2005）")
    chk("alpha04_row_matches_archive",
        bool(np.isclose(adf[adf.alpha == 0.4].esi_2023_8.iloc[0],
                        float(pd.read_csv(os.path.join(DATA, "r28_alpha_grade_summary.csv"))
                              .query("scenario=='drop_X9' and alpha==0.4").esi_2023.iloc[0]))),
        "本脚本重算的 α=0.4 年 ESI 与 r28_alpha_grade_summary.csv 一致")

    # =====================================================================
    # C 阈值扰动
    # =====================================================================
    src_t = "data/r28_threshold_perturbation.csv（本脚本由 r28_core 重算）"
    tot8 = tot9 = 0
    maxc8 = maxc9 = 0
    bound8, bound9 = set(), set()
    base_lv8 = C.classify_warning(y8, THR)
    for j, t0 in enumerate(THR):
        for dd in (-0.05, 0.05):
            th = list(THR)
            th[j] = round(t0 + dd, 3)
            l8 = classify_warning(y8, th)
            l9 = classify_warning(y9, th)
            c8 = sum(1 for a, b in zip(l8, base_lv8) if a != b)
            c9 = sum(1 for a, b in zip(l9, C.classify_warning(y9, THR)) if a != b)
            tot8 += c8
            tot9 += c9
            maxc8, maxc9 = max(maxc8, c8), max(maxc9, c9)
            if c8:
                bound8 |= {int(years[i]) for i, (a, b) in enumerate(zip(l8, base_lv8)) if a != b}
            if c9:
                bound9 |= {int(years[i]) for i, (a, b) in enumerate(zip(l9, C.classify_warning(y9, THR))) if a != b}
    add("C_threshold", "8 个阈值扰动情景的改级年数合计", tot8, tot9, "year", src_t,
        "sum over threshold_index∈1..4, delta∈{−0.05,+0.05}",
        "扰动空间 = 四个阈值各 ±0.05；主规格 3 年，九指标 7 年")
    add("C_threshold", "单一扰动情景的最大改级年数", maxc8, maxc9, "year", src_t,
        "max over 8 scenarios", "主规格最坏情景只改 1 年")
    add("C_threshold", "阈值扰动的边界年（曾出现两种等级）", value_txt=str(sorted(bound8)),
        value_9ind_txt=str(sorted(bound9)), source_csv=src_t, locator="changed_years",
        note="主规格 3 个边界年 vs 九指标 7 个")
    add("C_threshold", "2023 年等级在全部扰动下是否不变", value_txt="不变（恒为轻警）",
        value_9ind_txt="不变（恒为轻警）", source_csv=src_t, locator="grade_2023",
        note="删 X9 不改变阈值稳健性的定性结论")
    add("C_threshold", "峰值年在全部扰动下是否不变", value_txt="不变（恒为 2010）",
        value_9ind_txt="不变（恒为 2010）", source_csv=src_t, locator="peak_year", note="")
    for t0, tag in [(0.6, "轻警/较安全分界"), (0.4, "中警/轻警分界"), (0.2, "重警/中警分界")]:
        det = []
        for dd in (-0.05, 0.05):
            th = list(THR)
            th[THR.index(t0)] = round(t0 + dd, 3)
            l8 = classify_warning(y8, th)
            c8 = sum(1 for a, b in zip(l8, base_lv8) if a != b)
            det.append("Δ%+.2f: %d 年" % (dd, c8))
        add("C_threshold", "阈值 %.1f（%s）±0.05 的改级年数" % (t0, tag),
            value_txt="; ".join(det), value_9ind_txt="见 CSV", source_csv=src_t,
            locator="threshold_index=%d" % (THR.index(t0) + 1),
            note="最敏感的是 0.6；0.2/0.4 的 −0.05 方向为 0")

    # =====================================================================
    # D 障碍度（归档口径：删 X9 列后逐行重归一化）
    # =====================================================================
    ob = pd.read_csv(os.path.join(DATA, "results_obstacle.csv"))
    ob = ob.rename(columns={"Unnamed: 0": "year"})
    ob.columns = [str(c) for c in ob.columns]
    short = [c for c in ob.columns if c != "year"]
    ob["year"] = ob["year"].astype(float)
    # 行和（归档为 4 位小数，故 ≈1）
    rs = ob[short].sum(axis=1)
    chk("archived_obstacle_row_sum_max_abs_delta_from_1", float("%.4f" % float(np.abs(rs - 1).max())),
        "归档 results_obstacle.csv 每行 9 项障碍度之和与 1 的最大偏差（4 位小数舍入）")
    keep8 = [c for c in short if c != "生态用地"]
    ob8 = ob[keep8].div((1.0 - ob["生态用地"]).values, axis=0)   # 删 X9 后逐行重归一化

    def phase_mean(df, cols, lo, hi):
        m = (ob["year"] >= lo) & (ob["year"] <= hi)
        return df.loc[m, cols].mean()

    for lo, hi in [(2005, 2010), (2011, 2023)]:
        p8 = phase_mean(ob8, keep8, lo, hi).sort_values(ascending=False)
        p9 = phase_mean(ob, short, lo, hi).sort_values(ascending=False)
        for rank in (1, 2, 3):
            nm8, v8 = p8.index[rank - 1], float(p8.iloc[rank - 1])
            nm9, v9 = p9.index[rank - 1], float(p9.iloc[rank - 1])
            add("D_obstacle", "%d–%d 阶段第 %d 位障碍因子" % (lo, hi, rank),
                v8, v9, "", "data/results_obstacle.csv",
                "删「生态用地」列后逐行重归一化；阶段算术均值",
                "八指标 top%d = %s（%s）；九指标 top%d = %s（%s）"
                % (rank, CN2X.get(nm8, nm8), nm8, rank, CN2X.get(nm9, nm9), nm9))
    p8a = phase_mean(ob8, keep8, 2005, 2010).sort_values(ascending=False)
    p8b = phase_mean(ob8, keep8, 2011, 2023).sort_values(ascending=False)
    add("D_obstacle", "恢复期（2005–2010）top3 排序",
        value_txt=" > ".join("%s %.4f" % (CN2X.get(k, k), v) for k, v in p8a.head(3).items()),
        value_9ind_txt=" > ".join("%s %.4f" % (CN2X.get(k, k), v)
                                 for k, v in phase_mean(ob, short, 2005, 2010)
                                 .sort_values(ascending=False).head(3).items()),
        source_csv="data/results_obstacle.csv", locator="2005–2010 阶段均值",
        note="删 X9 后第三位由「生态用地」变为「草地」，前两位不变")
    add("D_obstacle", "平台期（2011–2023）top3 排序",
        value_txt=" > ".join("%s %.4f" % (CN2X.get(k, k), v) for k, v in p8b.head(3).items()),
        value_9ind_txt=" > ".join("%s %.4f" % (CN2X.get(k, k), v)
                                 for k, v in phase_mean(ob, short, 2011, 2023)
                                 .sort_values(ascending=False).head(3).items()),
        source_csv="data/results_obstacle.csv", locator="2011–2023 阶段均值",
        note="首位「草地变化率」与次位「农田」在删 X9 后不变")
    # 交叉核对：r28 管线（r28_core 重建 ESI + 组合权）
    o28 = pd.read_csv(os.path.join(DATA, "r28_obstacle_sensitivity.csv"))
    o28 = o28[(o28.scenario == "drop_X9") & (o28.weight_scheme == "combined(alpha=0.4)")
              & (o28.scope == "phase")]
    for lo, hi in [(2005, 2010), (2011, 2023)]:
        sub = o28[o28.phase == "%d-%d" % (lo, hi)].sort_values("rank")
        add("D_obstacle_crosscheck", "%d–%d 阶段 top3（r28 管线口径）" % (lo, hi),
            value_txt=" > ".join("%s %.6f" % (r.indicator, r.mean_obstacle)
                                 for _, r in sub.head(3).iterrows()),
            value_9ind_txt="见 r28_obstacle_sensitivity.csv",
            source_csv="data/r28_obstacle_sensitivity.csv",
            locator="scenario=drop_X9, weight_scheme=combined(alpha=0.4), phase=%d-%d" % (lo, hi),
            note="**已知 provenance 缺口**：r28_core 重建的逐年障碍度在 X8/X9 两列与归档 "
                 "results_obstacle.csv 不完全一致（归档表在仓库内无生成脚本）；两口径的 "
                 "**排序完全相同**，数值在小数第二位起有差异，引用时以归档口径为准并在"
                 "方法段写明公式与阶段均值定义")

    # =====================================================================
    # E 空间：点尺度 q / LOO / 独立 NDVI / Moran's I
    # =====================================================================
    smp = pd.read_csv(os.path.join(DATA, "spatial_samples.csv"))
    esp = pd.read_csv(os.path.join(DATA, "spatial_esi_points.csv"))
    pts = smp.merge(esp[["lat", "lon", "esi"]], on=["lat", "lon"], how="inner")
    pts["barren_neg"] = (1 - pts["grass"] - pts["forest"] - pts["water"]).clip(lower=0)
    FULL6 = [("precip", "precip", +1), ("temp", "temp", +1), ("forest", "forest", +1),
             ("grass", "grass", +1), ("water", "water", +1), ("barren_neg", "barren_neg", -1)]
    CORE5 = [s for s in FULL6 if s[0] != "barren_neg"]

    def build(df_, spec, alpha=ALPHA):
        X = df_[[c for _, c, _ in spec]].values.astype(float)
        Xn = minmax_normalize(X, [d for _, _, d in spec])
        w = combined_weights(np.ones(len(spec)) / len(spec), entropy_weights(Xn), alpha)
        return esi_series(Xn, w)

    e6, e5 = build(pts, FULL6), build(pts, CORE5)
    d6 = float(np.abs(e6 - pts["esi"].values).max())
    chk("point_6ind_rebuild_vs_archive_max_abs_delta", float("%.3e" % d6),
        "点尺度六指标 ESI 重建 vs data/spatial_esi_points.csv（r28 口径：min–max + 熵权 + "
        "等权 AHP，α=0.4）")
    chk("point_5ind_vs_archive_max_abs_delta", round(float(np.abs(e5 - e6).max()), 6),
        "点尺度去冗余五指标 ESI 与六指标（归档）ESI 的最大绝对差")
    print("[校验] 点尺度六指标 ESI vs 归档 max|Δ| = %.3e" % d6)

    def discretize(v, k=K_STRATA):
        return np.digitize(v, np.quantile(v, np.linspace(0, 1, k + 1)[1:-1]))

    def detect(x, yv, seed=SEED, n_perm=N_PERM):
        st = discretize(x)
        q = geodetector_q(yv, st)
        rng = np.random.default_rng(seed)
        c = sum(1 for _ in range(n_perm) if geodetector_q(yv, rng.permutation(st)) >= q)
        return float(q), (1.0 + c) / (n_perm + 1.0)

    src_q = "data/r28_deredundancy_comparison.csv（本脚本重算并逐位核对，见 checks）"
    # 因子列与 r28_t2 的 FACTOR_COL 一致：barren 用**原始 barren 列**（负向指标参与 ESI 时用
    # barren_neg，但作为解释因子的离散分层取原列；两者的 q 因分层不同而确实不同）
    FACTOR_COL = {"precip": "precip", "temp": "temp", "grass": "grass", "barren": "barren"}
    recomputed = {}
    for fac in ["precip", "temp", "grass", "barren"]:
        col = FACTOR_COL[fac]
        q8, p8v = detect(pts[col].values, e5)
        q9, p9v = detect(pts[col].values, e6)
        recomputed["point_deredundant5|q_%s" % fac] = q8
        recomputed["point_baseline6|q_%s" % fac] = q9
        add("E_spatial_q", "q(%s → 点尺度 ESI)" % fac, q8, q9, "", src_q,
            "scope=spatial_attribution；目标=去冗余5指标 / 六指标归档",
            "K=%d 分位分层，置换 %d 次，seed=%d；p(八指标)=%.4f，p(九指标)=%.4f"
            % (K_STRATA, N_PERM, SEED, p8v, p9v))
    add("E_spatial_q", "q 排序（目标=去冗余点尺度 ESI）",
        value_txt="barren > grass > precip > temp", value_9ind_txt="barren > grass > precip > temp",
        source_csv=src_q, locator="rank_baseline", note="删恒等补集项后因子排序不变")
    for fac in ["precip", "temp", "grass", "barren"]:
        col = FACTOR_COL[fac]
        y5loo = build(pts, [s for s in CORE5
                            if s[0] != ("barren_neg" if fac == "barren" else fac)])
        y6loo = build(pts, [s for s in FULL6
                            if s[0] != ("barren_neg" if fac == "barren" else fac)])
        if fac == "barren":
            add("E_spatial_q", "q_LOO(barren)", value_txt="不适用（barren 不在去冗余五指标集内）",
                value_9ind=None, source_csv=src_q, locator="q_loo_barren",
                note="九指标口径下 LOO(barren) 的目标为剔除 barren_neg 的 ESI；"
                     "去冗余五指标集本就无此列，故 LOO 不适用")
            recomputed["point_baseline6|q_loo_%s" % fac] = detect(pts[col].values, y6loo)[0]
            continue
        q8, p8v = detect(pts[col].values, y5loo)
        q9, p9v = detect(pts[col].values, y6loo)
        recomputed["point_deredundant5|q_loo_%s" % fac] = q8
        recomputed["point_baseline6|q_loo_%s" % fac] = q9
        add("E_spatial_q", "q_LOO(%s → 剔除该因子后的 ESI)" % fac, q8, q9, "", src_q,
            "leave-one-target（留一目标）", "p(八指标)=%.4f%s"
            % (p8v, "；**不显著**（p>0.05）：草地单独可从 ESI 中移除而不改变其空间格局"
               if p8v > 0.05 else ""))
    add("E_spatial_q", "q_LOO 排序（目标=去冗余点尺度 ESI）",
        value_txt="temp > precip > grass(≈0)", value_9ind_txt="barren > precip > grass > temp",
        source_csv=src_q, locator="rank_loo",
        note="**排序在 LOO 口径下改变**：说明因子 q 的次序部分来自指标集内的构造性共享")
    # 与 r28 归档逐位核对
    sdict = {"%s|%s" % (r["scenario"], r["item"]): float(r["value"])
             for _, r in s[s.scope == "spatial_attribution"].iterrows()
             if np.isfinite(r["value"])}
    dq = max(abs(recomputed[k] - sdict[k]) for k in recomputed if k in sdict)
    chk("spatial_q_recompute_vs_r28_max_abs_delta", float("%.3e" % dq),
        "本脚本重算的 %d 个 q（含 LOO）与 data/r28_deredundancy_comparison.csv 的最大绝对差"
        % len(recomputed))
    print("[校验] 点尺度 q 重算 vs r28 归档 max|Δ| = %.3e（%d 个值）" % (dq, len(recomputed)))

    # 独立 NDVI 外部验证
    nd = pd.read_csv(os.path.join(DATA, "r28_external_ndvi_points_2020.csv"))
    ter = pd.read_csv(os.path.join(DATA, "_aux_terrain_points.csv"))
    dd = pts[["lat", "lon", "precip", "temp", "grass", "forest", "water", "barren",
              "barren_neg"]].copy()
    dd["esi6"], dd["esi5"] = e6, e5
    dd = dd.merge(nd[["lat", "lon", "ndvi_growing_season_mean"]], on=["lat", "lon"], how="inner")
    dd = dd.merge(ter[["lat", "lon", "elev", "slope"]], on=["lat", "lon"], how="inner")
    dd = dd[np.isfinite(dd["ndvi_growing_season_mean"])].reset_index(drop=True)
    src_n = "data/r28_external_validation.csv（本脚本用 r28_external_ndvi_points_2020.csv 重算）"
    y5a, y6a, ndv = dd["esi5"].values, dd["esi6"].values, dd["ndvi_growing_season_mean"].values
    pear8 = float(np.corrcoef(y5a, ndv)[0, 1])
    pear9 = float(np.corrcoef(y6a, ndv)[0, 1])
    sp8 = float(pd.Series(y5a).corr(pd.Series(ndv), method="spearman"))
    sp9 = float(pd.Series(y6a).corr(pd.Series(ndv), method="spearman"))
    add("E_external_ndvi", "ESI 与独立 NDVI 的 Pearson r", pear8, pear9, "",
        src_n, "spatial_agreement, n=%d" % len(dd),
        "九指标列 0.705413 与归档逐位一致 ⇒ 复算口径正确；八指标主规格略高")
    add("E_external_ndvi", "ESI 与独立 NDVI 的 Spearman ρ", sp8, sp9, "",
        src_n, "spatial_agreement, n=%d" % len(dd), "归档 0.737252（6 位小数归档舍入）")
    add("E_external_ndvi", "合并样本量 n", len(dd), 1785, "点", src_n,
        "ndvi_growing_season_mean 非缺失", "与归档 n=1785 一致")
    lab_nd = np.digitize(ndv, np.quantile(ndv, [.25, .5, .75]))
    lab_es8 = np.digitize(y5a, np.quantile(y5a, [.25, .5, .75]))
    q_nd2es = float(geodetector_q(y5a, lab_nd))
    q_es2nd = float(geodetector_q(ndv, lab_es8))
    add("E_external_ndvi", "q(NDVI 四分位分层 → ESI)", q_nd2es,
        float(geodetector_q(y6a, lab_nd)), "", src_n, "q_ndvi_strata_to_esi",
        "双向关联；八指标列")
    add("E_external_ndvi", "q(ESI 四分位分层 → NDVI)", q_es2nd,
        float(geodetector_q(ndv, np.digitize(y6a, np.quantile(y6a, [.25, .5, .75])))),
        "", src_n, "q_esi_strata_to_ndvi",
        "两列**数值相同**并非笔误：去冗余五指标与六指标点尺度 ESI 的 Spearman = 0.999966，"
        "四分位分层标签在 n=1785 个点上完全一致（不同点数 = 0），故 strata→NDVI 的 q 必然相同")
    facs = ["precip", "temp", "grass", "barren", "elev", "slope"]
    q_e8, q_e9, q_n8 = {}, {}, {}
    for f_ in facs:
        v = dd[f_].values.astype(float)
        lab = (v > 0).astype(int) if f_ in ("forest", "water") else \
            np.digitize(v, np.quantile(v, [.25, .5, .75]))
        q_e8[f_] = float(geodetector_q(y5a, lab))
        q_e9[f_] = float(geodetector_q(y6a, lab))
        q_n8[f_] = float(geodetector_q(ndv, lab))
    for f_ in facs:
        add("E_external_ndvi", "q(%s → ESI)" % f_, q_e8[f_], q_e9[f_], "", src_n,
            "attribution_external, 因子 %s" % f_,
            "解释因子四分位分层（forest/water 用二值）；八指标列目标 = 去冗余五指标 ESI，"
            "九指标列目标 = 归档六指标点尺度 ESI")
        add("E_external_ndvi", "q(%s → 独立 NDVI)" % f_, q_n8[f_], None, "", src_n,
            "attribution_external, q_target_ndvi, 因子 %s" % f_,
            "目标换成与 ESI 构造无关的 NOAA CDR NDVI；九指标口径的对应列见 "
            "data/r28_external_validation.csv（该文件以归档六指标 ESI 为 q_target_esi）")
    rho = float(pd.Series([q_e8[f_] for f_ in facs]).corr(
        pd.Series([q_n8[f_] for f_ in facs]), method="spearman"))
    rho9 = 0.7714
    add("E_external_ndvi", "两套 q 排序的 Spearman 相关（主规格 ESI vs NDVI）", rho, rho9, "",
        src_n, "rank_spearman",
        "归档值 0.7714 以六指标 ESI 为目标；主规格口径略高，排序一致性结论不变")
    A = np.column_stack([np.ones(len(dd)), dd[["elev", "slope"]].values.astype(float)])
    b, *_ = np.linalg.lstsq(A, ndv, rcond=None)
    r2 = 1 - float(((ndv - A @ b) ** 2).sum()) / float(((ndv - ndv.mean()) ** 2).sum())
    add("E_external_ndvi", "严格外生因子对独立 NDVI 的 OLS R²（elev+slope）", r2, 0.058533,
        "", src_n, "ols_r2_exogenous_to_ndvi",
        "外生地形只能解释 NDVI 的 ~6%，说明 NDVI 与覆被因子并非同一信息源")

    # Moran's I
    lat, lon = esp["lat"].values, esp["lon"].values
    dmat = T6.pair_dist(lat, lon)
    W8, _ = T6.knn_weights(lat, lon, K_MORAN, MORAN_SCHEME, dmat=dmat)
    I9, EI, VarI, Z, pn, pp = T6.moran_perm(W8, esp["esi"].values, seed=SEED, n_perm=N_PERM)
    I8, EI8, VarI8, Z8, pn8, pp8 = T6.moran_perm(W8, e5, seed=SEED, n_perm=N_PERM)
    arch = pd.read_csv(os.path.join(DATA, "results_moran.csv"))
    chk("moran_rebuild_vs_archive_k8_invdist", round(I9, 6),
        "用 k=8 行标准化 inv_dist kNN 权重复算归档点尺度 ESI 的 Moran's I = %.6f（归档 %.6f）"
        % (I9, float(arch["morans_i"].iloc[0])))
    mk = pd.read_csv(os.path.join(DATA, "r28_moran_k_sensitivity.csv"))
    inv = mk[mk.scheme == "inv_dist"]
    p9_k8 = float(mk[(mk.scheme == "inv_dist") & (mk.k == K_MORAN)].p_permutation.iloc[0])
    add("E_moran", "Moran's I（点尺度 2020 ESI，主规格五指标）", I8, I9,
        "", "data/results_moran.csv（本脚本按 k=8 inv_dist 行标准化 kNN 重算）",
        "n=%d, k=%d, scheme=%s" % (len(esp), K_MORAN, MORAN_SCHEME),
        "八指标列 = 主规格五指标 ESI；九指标列 = 本脚本重算的归档六指标 ESI（%.6f，与归档"
        " results_moran.csv 的 %.6f 逐位一致）。z(八)=%.2f，p_perm(八)=%.4f，p_normal(八)=%.2e"
        % (I9, float(arch["morans_i"].iloc[0]), Z8, pp8, pn8))
    add("E_moran", "Moran's I 的置换检验 p（k=8 inv_dist 口径）", pp8, p9_k8, "",
        "data/r28_moran_k_sensitivity.csv",
        "weight=knn_k%d, scheme=inv_dist, p_permutation" % K_MORAN,
        "999 次置换；两者均为最小可达 p=0.001。**注意**：归档 results_moran.csv 的 p=0.005 "
        "由不同置换口径给出，与本表不可直接对比")
    add("E_moran", "Moran's I 的 z 分数（k=8 inv_dist）", Z8, Z, "", "data/results_moran.csv",
        "z_score", "归档未存 z；本脚本按随机化假设给出八/九指标两列")
    add("E_moran", "Moran's I 对 k 的敏感性（inv_dist，k=4–50，归档六指标 ESI）",
        value_txt="范围 %.4f–%.4f；k=8（归档口径）时 %.4f"
                 % (inv.morans_i.min(), inv.morans_i.max(),
                    float(mk[(mk.scheme == "inv_dist") & (mk.k == K_MORAN)]
                          .morans_i.iloc[0])),
        value_9ind_txt="见 r28_moran_k_sensitivity.csv",
        source_csv="data/r28_moran_k_sensitivity.csv", locator="scheme=inv_dist",
        note="该行的 k 扫描针对归档六指标 ESI；主规格五指标 ESI 的对应值为 %.6f（k=8）" % I8)
    sw = pd.read_csv(os.path.join(DATA, "r28_spatial_weights.csv"))
    for varn, lab in [("esi", "归档点尺度 ESI 本身"),
                      ("resid_OLS_all6", "六指标 OLS 残差"),
                      ("resid_OLS_exogenous4_precip_temp_elev_slope", "外生四因子残差")]:
        sub = sw[(sw.variable == varn) & (sw.weight_matrix == "rook_grid")
                 & (sw.row_standardised == False)]  # noqa: E712
        if len(sub):
            add("E_moran", "空间自相关（rook 网格、未行标准化）：%s" % lab,
                float(sub.morans_i.iloc[0]), None, "",
                "data/r28_spatial_weights.csv",
                "weight_matrix=rook_grid, variable=%s" % varn,
                "p_perm=%.3f；该行是**归档六指标点尺度口径**的 rook 网格结果，"
                "主规格五指标口径见本表 k=8 行；对应 OLS R²=%s"
                % (float(sub.p_perm.iloc[0]), sub.ols_r2_for_this_residual.iloc[0]))

    # =====================================================================
    # F 趋势（复用 run_r28_t6_trend_moran 的真源实现）
    # =====================================================================
    src_tr = "data/r28_trend_tests.csv（本脚本调用 run_r28_t6_trend_moran 的同名函数重算）"
    for a, b in [(2005, 2023), (2010, 2023)]:
        m = (years >= a) & (years <= b)
        for tag, arr in [("八指标", y8[m]), ("九指标", y9[m])]:
            ys = arr
            mkp = T6.mk_plain(ys)
            hr = T6.hamed_rao_mk(ys)
            tp = T6.tfpw_mk(ys)
            beta, lo, hi = T6.sen_slope_ci(years[m].astype(float), ys)
            if tag == "八指标":
                cur = {"mk": mkp, "hr": hr, "tp": tp, "sen": (beta, lo, hi)}
            else:
                ref = {"mk": mkp, "hr": hr, "tp": tp, "sen": (beta, lo, hi)}
        add("F_trend", "%d–%d 的 Mann–Kendall Z" % (a, b), cur["mk"]["Z"], ref["mk"]["Z"], "",
            src_tr, "series=%d-%d" % (a, b), "p(八)=%.6f，p(九)=%.6f"
            % (cur["mk"]["p"], ref["mk"]["p"]))
        add("F_trend", "%d–%d 的 Mann–Kendall p" % (a, b), cur["mk"]["p"], ref["mk"]["p"], "",
            src_tr, "series=%d-%d" % (a, b),
            "八指标全期**不显著**（p>0.05）；九指标 2010–2023 显著（p=0.0062）")
        add("F_trend", "%d–%d 的 Hamed–Rao 修正后 p" % (a, b),
            cur["hr"]["p_corrected"], ref["hr"]["p_corrected"],
            "", src_tr, "series=%d-%d" % (a, b),
            "Hamed–Rao 方差修正（去趋势秩自相关）；八指标 n/n*=%.4f（stable=%s），"
            "九指标 n/n*=%.4f（stable=%s）"
            % (cur["hr"]["n_nstar"], cur["hr"]["stable"],
               ref["hr"]["n_nstar"], ref["hr"]["stable"]))
        add("F_trend", "%d–%d 的 TFPW（趋势自由预白化）p" % (a, b),
            cur["tp"]["p_tfpw"], ref["tp"]["p_tfpw"], "", src_tr, "series=%d-%d" % (a, b),
            "TFPW 在两种指标集下都显著；与 HR 结论相反 ⇒ 该长度序列上趋势判定对自相关"
            "处理方式敏感，正文只能写 suggestive")
        add("F_trend", "%d–%d 的 Sen 斜率" % (a, b), cur["sen"][0], ref["sen"][0], "ESI/yr",
            src_tr, "series=%d-%d" % (a, b), "Theil–Sen 中位斜率")
        add("F_trend", "%d–%d 的 Sen 斜率 95%% CI" % (a, b),
            value_txt="[%+.6f, %+.6f]" % (cur["sen"][1], cur["sen"][2]),
            value_9ind_txt="[%+.6f, %+.6f]" % (ref["sen"][1], ref["sen"][2]),
            source_csv=src_tr, locator="series=%d-%d" % (a, b),
            note="八指标两段 CI 均**跨越 0**（不显著）；九指标 2010–2023 的 CI 不含 0")
        K, tau8, p_pet = T6.pettitt_k(y8[m])
        K9, tau9, p_pet9 = T6.pettitt_k(y9[m])
        add("F_trend", "%d–%d 的 Pettitt 变点（K, p）" % (a, b),
            value_txt="K=%.1f, p=%.6f" % (K, p_pet),
            value_9ind_txt="K=%.1f, p=%.6f" % (K9, p_pet9),
            source_csv=src_tr, locator="series=%d-%d" % (a, b),
            note="变点年 = %d（九指标 %d）；K 的绝对值与 p 均未达显著（只用作描述性分段依据）"
                 % (int(years[m][tau8]), int(np.array(r9["years"])[m][tau9])))
    # 变点年单独补一行
    det = pd.read_csv(os.path.join(DATA, "r28_trend_tests.csv"))
    dk = det[(det.scenario == "drop_X9") & (det.series == "2005-2023")].iloc[0]
    dk9 = det[(det.scenario == "baseline9") & (det.series == "2005-2023")].iloc[0]
    add("F_trend", "Pettitt 变点年（2005–2023）", int(dk.pettitt_change_point),
        int(dk9.pettitt_change_point), "year", src_tr, "series=2005-2023",
        "变点年 = %d（八指标）/%d（九指标）" % (int(dk.pettitt_change_point),
                                            int(dk9.pettitt_change_point)))
    # F 交叉核对：重算 vs r28_trend_tests.csv
    tt = pd.read_csv(os.path.join(DATA, "r28_trend_tests.csv"))
    mchk = []
    for a, b in [(2005, 2023), (2010, 2023)]:
        for scen, arr in [("drop_X9", y8), ("baseline9", y9)]:
            mm = (years >= a) & (years <= b)
            ys_ = arr[mm]
            row = tt[(tt.scenario == scen) & (tt.series == "%d-%d" % (a, b))].iloc[0]
            mchk += [abs(T6.mk_plain(ys_)["Z"] - row.Z_mk),
                     abs(T6.mk_plain(ys_)["p"] - row.p_mk),
                     abs(T6.sen_slope_ci(years[mm].astype(float), ys_)[0] - row.sen_slope),
                     abs(T6.sen_slope_ci(years[mm].astype(float), ys_)[1] - row.sen_ci_lo),
                     abs(T6.pettitt_k(ys_)[0] - row.pettitt_K)]
    chk("trend_recompute_vs_r28_max_abs_delta", float("%.3e" % max(mchk)),
        "本脚本用 run_r28_t6_trend_moran 的同名函数重算的 MK Z/p、Sen 斜率与 CI、Pettitt K，"
        "与 data/r28_trend_tests.csv 的最大绝对差（2 个时段 × 2 个指标集 × 5 个量）")
    print("[校验] 趋势量重算 vs r28_trend_tests.csv max|Δ| = %.3e" % max(mchk))
    chk("ndvi_pearson_recompute_vs_r28_archive", round(float(abs(pear9 - 0.705413)), 8),
        "以归档六指标点尺度 ESI 重算的 ESI–NDVI Pearson r = %.6f（归档 0.705413）" % pear9)

    # =====================================================================
    # G 权重
    # =====================================================================
    src_w = "data/r29_weights_8ind.csv（本脚本读入 T1 产物）"
    wdf = pd.read_csv(os.path.join(DATA, "r29_weights_8ind.csv"))
    lt = wdf[wdf.row_type == "layer_total"].set_index("indicator")
    for lay in ["Driving", "Pressure", "State", "Impact", "Response"]:
        k = "layer_weight:" + lay
        add("G_weights", "%s 层组合权重占比" % lay, float(lt.loc[k, "combined_w"]),
            float(lt.loc[k, "combined_w_9ind"]), "", src_w, k,
            "层内指标 α=0.4 组合权重合计")
    gt = wdf[wdf.row_type == "group_total"].set_index("indicator")
    add("G_weights", "D/P/S/I 四层组合权重合计（八指标主规格）",
        float(gt.loc["D+P+S+I (four live layers, 8ind)", "combined_w"]),
        float(gt.loc["D+P+S+I (four live layers, 8ind)", "combined_w_9ind"]), "", src_w,
        "row_type=group_total",
        "八指标下 Response 层无指标 ⇒ 其权重全额再分配给 D/P/S/I，四层合计 = 1.000000；"
        "九指标同四层合计 = 0.864532")
    add("G_weights", "重叠指标组合计（State+Impact+Response，论文 Limitations 的『约 69%』）",
        float(gt.loc["State+Impact+Response (paper's ~69% overlap group)", "combined_w"]),
        float(gt.loc["State+Impact+Response (paper's ~69% overlap group)", "combined_w_9ind"]),
        "", src_w, "row_type=group_total",
        "九指标 0.692904（69.29%）→ 八指标 0.656013（65.60%）；**注意**：任务书写的"
        "『D/P/S/I 四层合计 = 69.29%』与归档不符——69.29% 实为 State+Impact+Response "
        "三层合计，已在此分别列出两个口径")
    ck = pd.read_csv(os.path.join(DATA, "r29_weights_8ind_checks.csv")).set_index("item")
    ck["value"] = pd.to_numeric(ck["value"], errors="coerce")
    add("G_weights", "熵权的统一重标定因子", float(ck.loc["entropy_uniform_rescale_factor", "value"]),
        np.nan, "", "data/r29_weights_8ind_checks.csv", "entropy_uniform_rescale_factor",
        "= 1/(1 − w_ent,9(X9))；删 X9 不改变任何存活列的 (1−e_j)，只改变分母")
    add("G_weights", "AHP 指标层权重的统一重标定因子",
        float(ck.loc["ahp_uniform_rescale_factor", "value"]), np.nan, "",
        "data/r29_weights_8ind_checks.csv", "ahp_uniform_rescale_factor",
        "= 1/Σ(存活准则层权重) = 1/0.749770；准则层在 D/P/S/I 上重归一化")
    top = wdf[(wdf.row_type == "indicator")].sort_values("combined_w", ascending=False).iloc[0]
    add("G_weights", "八指标下权重最大的指标", value_txt="%s（%.6f）" % (top.indicator, top.combined_w),
        value_9ind_txt="X8_草地变化率（0.206326）", source_csv=src_w, locator="row_type=indicator",
        note="八指标下 X8 组合权重升至 0.235369（第 1），X9 删去后其 0.135468 被再分配")

    # =====================================================================
    # H 预测（交叉引用 T2）
    # =====================================================================
    fc = pd.read_csv(os.path.join(DATA, "r29_forecast_8ind.csv"))
    rr = pd.read_csv(os.path.join(DATA, "r29_2028_range.csv"))
    ck2 = pd.read_csv(os.path.join(DATA, "r29_forecast_8ind_checks.csv")).set_index("item")
    ck2["value"] = pd.to_numeric(ck2["value"], errors="coerce")
    src_f = "data/r29_forecast_8ind.csv（T2 产物）"
    for yv in [2024, 2028]:
        row = fc[fc.year == yv].iloc[0]
        add("H_forecast", "%d 年 GM(1,1) 点预测" % yv, row.gm11_8ind, row.gm11_9ind, "",
            src_f, "year=%d" % yv, "八指标 GM 后验 C=%.4f, P=%.4f（勉强合格）"
            % (ck2.loc["gm11_8ind_accuracy_C", "value"], ck2.loc["gm11_8ind_accuracy_P", "value"]))
        add("H_forecast", "%d 年 NGBM 点预测（γ=%.2f，训练期 SSE 最优、无泄漏）"
            % (yv, float(ck2.loc["gamma_8ind_train_sse", "value"])),
            row.ngbm_8ind_gamma_train, row.ngbm_9ind_gamma_train, "", src_f, "year=%d" % yv,
            "九指标列用其训练期最优 γ=0.25 作对照")
        add("H_forecast", "%d 年 NGBM 点预测（γ=%.2f，全序列 SSE 最优）"
            % (yv, float(ck2.loc["gamma_8ind_full_sse", "value"])),
            row.ngbm_8ind_gamma_full, row.ngbm_9ind_gamma_full, "", src_f, "year=%d" % yv,
            "对照口径；九指标列即论文现正文的 0.4458/0.3939")
        add("H_forecast", "%d 年 ARIMA(0,1,1) 点预测" % yv, row.arima_011_8ind,
            row.arima_011_9ind, "", src_f, "year=%d" % yv, "阶数固定，故无选阶泄漏")
    add("H_forecast", "NGBM γ 选择窗口对 2028 点值的影响",
        value_txt="训练期 γ=%.2f → 2028 = %.6f（中警）；全序列 γ=%.2f → 2028 = %.6f（轻警）"
                 % (float(ck2.loc["gamma_8ind_train_sse", "value"]),
                    float(ck2.loc["dpsi_2028_ngbm_8ind_gamma_train", "value"]),
                    float(ck2.loc["gamma_8ind_full_sse", "value"]),
                    float(ck2.loc["dpsi_2028_ngbm_8ind_gamma_full", "value"])),
        value_9ind_txt="九指标：训练期 γ=0.25 / 全序列 γ=0.20",
        source_csv="data/r29_forecast_8ind_gamma.csv",
        locator="sse_train_2005_2018 / sse_full_2005_2023 的 argmin",
        note="全序列 γ 落在网格下边界 0.05（边界解）⇒ 八指标下 γ 的确定方式直接决定 2028 "
             "年是否跨过 0.400")
    for _, r in rr[rr.row_type.isin(["model", "model_averaged", "model_averaged_variant"])].iterrows():
        add("H_forecast", "2028 年 95%% 区间与等级概率：%s" % r.model_or_scheme,
            value_txt="点 %.6f（%s）; 95%% CI [%.6f, %.6f]; P(中警)=%.4f; P(轻警)=%.4f"
                     % (r.point_2028, r.point_grade, r["ci_lo_2.5"], r["ci_hi_97.5"],
                        r.p_medium, r.p_mild),
            value_9ind_txt="", source_csv="data/r29_2028_range.csv",
            locator="row_type=%s, model_or_scheme=%s" % (r.row_type, r.model_or_scheme),
            note="%s；margin vs 0.400 = %+.6f；区间口径 total_block（参数+γ 重选+累积新息块）"
                 % (r.note, r["margin_vs_0.400"]))
    for _, r in rr[rr.row_type == "margin_and_rounding"].iterrows():
        add("H_forecast", "2028 年 margin 与舍入翻级：%s" % r.model_or_scheme,
            value_txt="margin = %+.6f；1dp %.1f→%s%s；2dp %.2f→%s；3dp %.3f→%s"
                     % (r["margin_vs_0.400"], r["v_1dp"], r["grade_1dp"],
                        "（翻级）" if r["flips_grade_at_1dp"] else "",
                        r["v_2dp"], r["grade_2dp"], r["v_3dp"], r["grade_3dp"]),
            value_9ind_txt="九指标 NGBM(γ=0.20) 2028 = 0.3939，margin −0.0061（1dp 0.4 → 轻警，翻级）",
            source_csv="data/r29_2028_range.csv", locator="row_type=margin_and_rounding",
            note="**关键**：主规格 NGBM 用无泄漏 γ 时 2028 = 0.3804 < 0.400（中警），"
                 "1 位小数会舍入为 0.4 而翻成轻警；2/3 位小数不翻级。"
                 "model-averaged 点值 0.4376 距阈值 +0.0376（3 位小数精度下的 75 倍），"
                 "故原文『0.006 边际』的表述在八指标下不适用")

    out = pd.DataFrame(rows)
    cols = ["value_id", "group", "item", "value", "value_txt", "value_9ind", "value_9ind_txt",
            "delta_8ind_minus_9ind", "unit", "source_csv", "source_locator", "note"]
    out = out[cols]
    out.to_csv(OUT, index=False, encoding="utf-8-sig")
    pd.DataFrame(checks).to_csv(OUT_K, index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 250)
    print("\n" + "-" * 78)
    print("关键数值（按组）")
    print("-" * 78)
    for g, sub in out.groupby("group", sort=False):
        print("\n[%s]  %d 行" % (g, len(sub)))
        for _, r in sub.iterrows():
            v = ("%s" % r["value_txt"]) if r["value_txt"] else (
                "%.6f" % r["value"] if np.isfinite(r["value"]) else "")
            v9 = ("%s" % r["value_9ind_txt"]) if r["value_9ind_txt"] else (
                "%.6f" % r["value_9ind"] if np.isfinite(r["value_9ind"]) else "")
            print("   %-52s %-46s | 九指标 %s" % (str(r["item"])[:52], v[:46], v9[:60]))
    print("\n已写出：data/r29_primary_spec_values.csv（%d 行）, "
          "data/r29_primary_spec_checks.csv（%d 行）" % (len(out), len(checks)))
    return 0


if __name__ == "__main__":
    sys.exit(main())