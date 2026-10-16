# -*- coding: utf-8 -*-
"""留一目标 GeoDetector（Leave-One-Out Target GeoDetector）——切断空间归因的机械相关

────────────────────────────────────────────────────────────────────────────
问题（R19 审稿意见）
────────────────────────────────────────────────────────────────────────────
论文以点尺度 ESI（1,914 个格网样本）为因变量报告 GeoDetector 因子探测 q：
裸地/退化 0.8024、草地 0.7077、降水 0.5060、气温 0.1697，并把这些因子称为
"外生驱动因子"。

但点尺度 ESI 的构成（见 run_county_geodetector.py 第 126-136 行 / 本脚本
`build_esi` 的 FULL_SPEC）本身就是这 6 项指标的组合：

    ESI = w · [ precip(+), temp(+), forest(+), grass(+), water(+), barren_neg(-) ]
    barren_neg = 1 - grass - forest - water     （点位为 3×3 邻域主导类的 one-hot）

因此 precip、temp、grass、barren 全部是 ESI 的**输入项**：q(precip)、q(temp)、
q(grass)、q(barren) 必然含有机械相关（mechanical correlation）成分，
并非外生因子对 ESI 的空间解释力。真正从未进入 ESI 构造的因子只有
高程（elev）与坡度（slope）。

────────────────────────────────────────────────────────────────────────────
方法
────────────────────────────────────────────────────────────────────────────
1) 留一目标（LOO target）：对 F ∈ {precip, temp, grass, barren} 各做一次——
   从 6 项指标集中剔除 F（剩 5 项）→ 重新 min-max 标准化 → 重算熵权 →
   AHP 等权（1/5）→ α = 0.4 线性组合 → 得到**剔除 F 后的 ESI**（记为 ESI_{-F}）；
   再以 ESI_{-F} 为因变量，把 F 按样本分位数离散为 4 个等样本层（F 为 one-hot
   0/1 时实际只有 2 层，与基准口径一致），计算 q(F) 与置换检验 p。
   此时 F 与目标在代数上不再共享同一列，机械相关被切断。

2) 严格外生对照：以**完整点 ESI** 为目标，计算 elev 与 slope 的 q 与 p。
   这两项从未进入 ESI 构造，"留一"为空操作，故 q_loo ≡ q_baseline。

3) 对照（基准）：以完整点 ESI 为目标，复算 4 个因子的 q，用于量化基准 q
   相对于 LOO q 被抬高了多少（Δ 与降幅）。

4) 稳健性变体 loo_strict：one-hot 土地覆被存在结构退化——若只删除 `grass`
   列，`barren_neg = 1 - grass - forest - water` 仍含 grass，机械相关未真正切断。
   故增加严格变体：删除 F 且同时把各派生复合项中 F 的成分替换掉/重定义。
   · F = grass：改用 barren_neg_strict = 1 - forest - water（不含 grass，仍 5 项）。
   · F = barren：先删除 barren_neg，并额外用 `barren_neg`（而非 `barren` one-hot）
     做分层，检验结果对因子定义口径的敏感性。

────────────────────────────────────────────────────────────────────────────
冻结的超参数（与正文 §4.5 及归档管线一致）
────────────────────────────────────────────────────────────────────────────
· 分层层数 K = 4（样本分位数等样本分层；one-hot 变量退化为 2 层）
· 置换次数 N_PERM = 999，p = (1 + #{q_perm ≥ q_obs}) / (999 + 1)
· 随机种子 SEED = 42；每个检验独立重置 default_rng(SEED)，结果与检验顺序无关
· 组合权重 α = 0.4（AHP 等权 + 熵权 线性组合），min-max 方向 +1/+1/+1/+1/+1/-1
· q = 1 - Σ_h N_h σ_h² / (N σ²)，调用 eco_security.geodetector_q

────────────────────────────────────────────────────────────────────────────
数据来源（全部为已入库文件，不新增外部下载、不修改任何既有文件）
────────────────────────────────────────────────────────────────────────────
· data/spatial_samples.csv        —— 1,914 点 precip/temp/grass/forest/water/barren/class
· data/spatial_esi_points.csv     —— 归档点尺度 ESI（仅用于校验本脚本重建值）
· data/_aux_terrain_points.csv    —— 1,914 点 elev/slope
· data/results_geodetector_pvalues.csv   —— 归档基准 q（对照，不覆盖）
· data/results_geodetector_exogenous.csv —— 归档外生 q（对照，不覆盖）

输出（全部为新文件）：
· data/results_geodetector_loo.csv

运行：python run_geodetector_loo.py
"""
import os
import sys

import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
sys.path.insert(0, os.path.join(BASE, "eco_security"))
from eco_security import (  # noqa: E402
    minmax_normalize, entropy_weights, combined_weights, esi_series, geodetector_q,
)

K = 4           # 分位数分层数
N_PERM = 999    # 置换次数
SEED = 42       # 随机种子（每个检验独立重置）
ALPHA = 0.4     # AHP 权重占比
ARCHIVED_SAMPLES = "spatial_samples.csv"
ARCHIVED_ESI = "spatial_esi_points.csv"
ARCHIVED_TERRAIN = "_aux_terrain_points.csv"
OUT_CSV = "results_geodetector_loo.csv"

# 完整点尺度 ESI 的指标构成（严格照抄 run_county_geodetector.py 的口径）
#   (指标名, 取值列, 方向)
FULL_SPEC = [
    ("precip", "precip", +1),
    ("temp", "temp", +1),
    ("forest", "forest", +1),
    ("grass", "grass", +1),
    ("water", "water", +1),
    ("barren_neg", "_barren_neg", -1),
]
# 论文报告的 4 个点尺度因子 -> 其在 ESI 指标集中的对应列
FACTOR_TO_SPEC = {"precip": "precip", "temp": "temp",
                  "grass": "grass", "barren": "barren_neg"}
FACTOR_COLUMN = {"precip": "precip", "temp": "temp",
                 "grass": "grass", "barren": "barren"}


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------
def add_derived(df):
    """补齐派生列：barren_neg = 1 - grass - forest - water（点位 one-hot 版本）。"""
    df = df.copy()
    df["_barren_neg"] = (1 - df["grass"] - df["forest"] - df["water"]).clip(lower=0)
    return df


def build_esi(df, spec, alpha=ALPHA):
    """按 spec 构造 ESI：min-max → 熵权 → AHP 等权 → α 组合 → 加权求和。

    返回 (esi, weights_entropy, weights_combined, Xn)
    """
    X = df[[col for _, col, _ in spec]].values.astype(float)
    dirs = [d for _, _, d in spec]
    Xn = minmax_normalize(X, dirs)
    w_ent = entropy_weights(Xn)
    w_ahp = np.ones(len(spec)) / len(spec)
    w = combined_weights(w_ahp, w_ent, alpha)
    return esi_series(Xn, w), w_ent, w, Xn


def discretize(v, k=K):
    """样本分位数等样本分层（与 run_geodetector_pvalues.py 完全一致）。"""
    qs = np.quantile(v, np.linspace(0, 1, k + 1)[1:-1])
    return np.digitize(v, qs)


def detect(x, y, seed=SEED, n_perm=N_PERM):
    """返回 (q, p, 实际层数)。x 为连续因子，y 为因变量。"""
    strata = discretize(x)
    n_levels = int(len(np.unique(strata)))
    q = geodetector_q(y, strata)
    rng = np.random.default_rng(seed)
    cnt = 0
    for _ in range(n_perm):
        if geodetector_q(y, rng.permutation(strata)) >= q:
            cnt += 1
    return q, (1.0 + cnt) / (n_perm + 1.0), n_levels


def loo_esi(df, spec, drop_name, strict=False):
    """构造剔除 drop_name 后的点尺度 ESI。

    strict=True 时，从派生项中一并剔除 drop_name 的成分：
      · drop_name == 'grass'  → barren_neg_strict = 1 - forest - water
    """
    spec2 = [s for s in spec if s[0] != drop_name]
    if strict and drop_name == "grass":
        spec2 = [(n, ("_barren_neg_strict" if n == "barren_neg" else c), d)
                 for n, c, d in spec2]
    df2 = df.copy()
    if strict:
        df2["_barren_neg_strict"] = (1 - df2["forest"] - df2["water"]).clip(lower=0)
    esi, w_ent, w, _ = build_esi(df2, spec2)
    return esi, spec2, w_ent, w


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main():
    smp = add_derived(pd.read_csv(os.path.join(DATA, ARCHIVED_SAMPLES)))
    esp = pd.read_csv(os.path.join(DATA, ARCHIVED_ESI))
    ter = pd.read_csv(os.path.join(DATA, ARCHIVED_TERRAIN))
    df = smp.merge(esp[["lat", "lon", "esi"]], on=["lat", "lon"], how="inner")
    df = df.merge(ter[["lat", "lon", "elev", "slope"]], on=["lat", "lon"], how="inner")
    n = len(df)
    print("=" * 78)
    print("留一目标 GeoDetector（K=%d, N_per=%d, seed=%d, alpha=%.1f）" % (K, N_PERM, SEED, ALPHA))
    print("=" * 78)
    print("点位：samples %d + esi %d + terrain %d → 合并 %d"
          % (len(smp), len(esp), len(ter), n))
    if n != 1914:
        print("警告：合并后样本数 %d ≠ 1914，请检查点位文件一致性。" % n)

    # ---------- 0) 管线校验：完整 ESI 必须复现归档 spatial_esi_points.csv ----------
    esi_full, w_ent_full, w_full, _ = build_esi(df, FULL_SPEC)
    maxdiff = float(np.abs(esi_full - df["esi"].values).max())
    corr_full = float(np.corrcoef(esi_full, df["esi"].values)[0, 1])
    print("\n[校验] 本脚本重建完整 ESI vs 归档 spatial_esi_points.csv：")
    print("       最大绝对偏差 = %.3e，Pearson r = %.10f" % (maxdiff, corr_full))
    if maxdiff > 1e-9:
        print("       !! 重建失败，后续结果不可信，请先排查指标口径。")
    print("       熵权   =", np.round(w_ent_full, 6))
    print("       组合权重 =", np.round(w_full, 6))

    # 因变量统一用重建值（与归档值在 1e-16 量级一致，便于最小化与权重自洽）
    y_full = esi_full

    rows = []

    # ---------- 1) 对照：以完整 ESI 为目标的基准 q ----------
    print("\n" + "-" * 78)
    print("1) 基准（对照）：目标 = 完整点尺度 ESI（含全部 6 项指标）")
    print("-" * 78)
    base = {}
    for fac in ["precip", "temp", "grass", "barren"]:
        q, p, lv = detect(df[FACTOR_COLUMN[fac]].values, y_full)
        base[fac] = (q, p)
        print("   %-8s q = %.6f  p = %.4f  (分层 %d 层)" % (fac, q, p, lv))

    # ---------- 2) 留一目标 LOO ----------
    print("\n" + "-" * 78)
    print("2) 留一目标（LOO）：目标 = 剔除 F 后的 ESI，q(F) 与目标不再共享 F")
    print("-" * 78)
    loo = {}
    for fac in ["precip", "temp", "grass", "barren"]:
        drop = FACTOR_TO_SPEC[fac]
        esi_loo, spec_loo, w_e_loo, w_loo = loo_esi(df, FULL_SPEC, drop, strict=False)
        q, p, lv = detect(df[FACTOR_COLUMN[fac]].values, esi_loo)
        loo[fac] = (q, p)
        r = float(np.corrcoef(esi_full, esi_loo)[0, 1])
        print("   %-8s 剔除 %-11s 剩余 %d 项 %s"
              % (fac, drop, len(spec_loo), [s[0] for s in spec_loo]))
        print("            q_loo = %.6f  p = %.4f  (分层 %d 层)  corr(ESI_full, ESI_loo) = %.4f"
              % (q, p, lv, r))
        del w_e_loo, w_loo

    # ---------- 3) 严格外生对照：elev / slope ----------
    print("\n" + "-" * 78)
    print("3) 严格外生对照：elev / slope（从未进入 ESI 构造，目标是完整 ESI）")
    print("-" * 78)
    exo = {}
    for fac in ["elev", "slope"]:
        q, p, lv = detect(df[fac].values, y_full)
        exo[fac] = (q, p)
        print("   %-8s q = %.6f  p = %.4f  (分层 %d 层)" % (fac, q, p, lv))

    # ---------- 4) 稳健性：loo_strict（切断派生项内的 F 成分） ----------
    print("\n" + "-" * 78)
    print("4) 稳健性 loo_strict：同时切断派生复合项内的 F 成分")
    print("-" * 78)
    strict = {}
    # F = grass：barren_neg 重定义为 1 - forest - water（不含 grass）
    esi_s, spec_s, _, _ = loo_esi(df, FULL_SPEC, "grass", strict=True)
    q, p, lv = detect(df["grass"].values, esi_s)
    strict["grass"] = (q, p)
    print("   grass  剩 %s" % [s[0] for s in spec_s])
    print("          q_strict = %.6f  p = %.4f  (分层 %d 层)"
          "  corr(ESI_full, ESI_strict) = %.4f"
          % (q, p, lv, float(np.corrcoef(esi_full, esi_s)[0, 1])))
    # F = barren：改用 barren_neg 作为分层口径（barren one-hot 与 barren_neg 有 81 点差异）
    esi_b, spec_b, _, _ = loo_esi(df, FULL_SPEC, "barren_neg", strict=False)
    q_bn, p_bn, lv_bn = detect(df["_barren_neg"].values, esi_b)
    q_bh, p_bh, lv_bh = detect(df["barren"].values, esi_b)
    strict["barren"] = (q_bh, p_bh)
    print("   barren  剩 %s" % [s[0] for s in spec_b])
    print("          分层口径 barren(one-hot)      : q = %.6f  p = %.4f  (分层 %d 层)"
          % (q_bh, p_bh, lv_bh))
    print("          分层口径 barren_neg(ESI 输入) : q = %.6f  p = %.4f  (分层 %d 层)"
          % (q_bn, p_bn, lv_bn))

    # ---------- 5) 汇总表 ----------
    def add(factor, variant, qb, ql, pb, pl, note):
        delta = ql - qb
        drop_pct = (delta / qb * 100.0) if qb > 0 else np.nan
        rows.append({
            "factor": factor, "variant": variant,
            "q_baseline": round(qb, 6), "q_loo": round(ql, 6),
            "delta_q": round(delta, 6), "drop_pct": round(drop_pct, 2),
            "p_baseline": round(pb, 4), "p_loo": round(pl, 4), "note": note,
        })

    for fac, zh in [("precip", "降水"), ("temp", "气温"),
                    ("grass", "草地"), ("barren", "裸地/退化")]:
        add(fac, "loo_primary", base[fac][0], loo[fac][0], base[fac][1], loo[fac][1],
            "目标=剔除%s后的 ESI（剩 5 项），分层口径与基准相同的 %s 列"
            % (zh, FACTOR_COLUMN[fac]))
    for fac, zh in [("elev", "高程"), ("slope", "坡度")]:
        add(fac, "exogenous", exo[fac][0], exo[fac][0], exo[fac][1], exo[fac][1],
            "严格外生：%s 从未进入 ESI 构造，LOO 为空操作，q_loo=q_baseline，目标是完整 ESI" % zh)
    add("grass", "loo_strict", base["grass"][0], strict["grass"][0],
        base["grass"][1], strict["grass"][1],
        "严格变体：剔除 grass 且 barren_neg 重定义为 1-forest-water，彻底不含 grass")
    add("barren", "loo_strict", base["barren"][0], strict["barren"][0],
        base["barren"][1], strict["barren"][1],
        "严格变体：剔除 barren_neg 后仍用 barren(one-hot) 分层，检验结构化残差")

    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(DATA, OUT_CSV), index=False, encoding="utf-8-sig")

    print("\n" + "=" * 78)
    print("汇总表（已写出 data/%s）" % OUT_CSV)
    print("=" * 78)
    print(out.to_string(index=False))

    # ---------- 6) 结论性判定 ----------
    print("\n" + "-" * 78)
    print("结论性判定（p < 0.05 记为显著）")
    print("-" * 78)
    for fac in ["precip", "temp", "grass", "barren", "elev", "slope"]:
        q_l = loo.get(fac, exo.get(fac))[0]
        p_l = loo.get(fac, exo.get(fac))[1]
        sig = "显著" if p_l < 0.05 else "不显著"
        print("   %-8s 切断后 q = %.4f  p = %.4f  → %s" % (fac, q_l, p_l, sig))
    rank = sorted(["precip", "temp", "grass", "barren"],
                  key=lambda f: -loo[f][0])
    print("   切断机械相关后 4 因子 q 排序（降序）:", " > ".join(rank),
          "  → 最强因子：%s" % rank[0])
    print("\n已写出: data/%s（新文件，未覆盖任何既有结果）" % OUT_CSV)
    return 0


if __name__ == "__main__":
    sys.exit(main())