# -*- coding: utf-8 -*-
"""R28 · T4 —— 年均温方向敏感性（审稿意见第 7 条）

把 X2_年均温的方向由正（+1，当前口径）改为负（−1）或从指标集中剔除，重跑 ESI 与等级：
  pos   : 气温 +（论文现用口径，对照）
  neg   : 气温 −（升温被视为压力）
  drop  : 气温不参与（剔除该指标，AHP 准则层在存活层上重归一化）

对 6 套指标集（baseline9 / drop_X9 / drop_X8 / drop_X8_X9 / primary6 / substitute5）分别执行。

输出
  data/r28_temperature_direction.csv   逐情景 × 方向 × 逐年 ESI/等级 + 汇总对比

运行：python run_r28_t4_temperature.py
"""
import os
import sys

import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
OUT = os.path.join(DATA, "r28_temperature_direction.csv")
import r28_core as C  # noqa: E402

SCEN = ["baseline9", "drop_X9", "drop_X8", "drop_X8_X9", C.PRIMARY, "substitute5"]
MODES = ["pos", "neg", "drop"]
MODE_DIR = {"pos": "positive", "neg": "negative", "drop": "excluded"}


def main():
    rows = []
    for s in SCEN:
        keep = C.DEREDUNDANT_SETS[s]
        res = {m: C.compute(keep, temp_direction=MODE_DIR[m]) for m in MODES}
        # 若 drop 模式把 X2 剔除，则 keep 列表里 X2 会被 compute 过滤吗？不会——
        # build_indicators 在 excluded 下不生成 X2 列，compute 会过滤掉它。
        ref = res["pos"]
        for m in MODES:
            r = res[m]
            for y, e, g in zip(r["years"], r["esi"], r["levels"]):
                j = r["years"].index(y)
                rows.append(dict(
                    scope="series", scenario=s, temp_mode=m, year=int(y),
                    esi=round(float(e), 6), grade=g,
                    esi_pos=round(float(ref["esi"][j]), 6), grade_pos=ref["levels"][j],
                    delta=round(float(e - ref["esi"][j]), 6),
                    level_changed=bool(g != ref["levels"][j]),
                    n_indicators=len(r["keep"]),
                    keep="|".join(r["keep"]),
                    temp_entropy_w=(round(float(r["w_ent"][r["keep"].index("X2_气温C")]), 6)
                                    if "X2_气温C" in r["keep"] else np.nan),
                    temp_combined_w=(round(float(r["w"][r["keep"].index("X2_气温C")]), 6)
                                     if "X2_气温C" in r["keep"] else np.nan),
                    temp_direction=(int(r["directions"][r["keep"].index("X2_气温C")])
                                    if "X2_气温C" in r["keep"] else (0 if m == "drop" else -1)),
                    note=""))
        for m in ["neg", "drop"]:
            r = res[m]
            d = r["esi"] - ref["esi"]
            sp = C.spearman(r["esi"], ref["esi"])
            pr = C.pearson(r["esi"], ref["esi"])
            n_chg = int(sum(1 for a, b in zip(r["levels"], ref["levels"]) if a != b))
            from collections import Counter
            cnt = Counter(r["levels"])
            rows.append(dict(
                scope="summary", scenario=s, temp_mode=m, year=np.nan,
                esi=round(float(r["esi"][-1]), 6), grade=r["levels"][-1],
                esi_pos=round(float(ref["esi"][-1]), 6), grade_pos=ref["levels"][-1],
                delta=round(float(r["esi"][-1] - ref["esi"][-1]), 6),
                level_changed=(r["levels"][-1] != ref["levels"][-1]),
                n_indicators=len(r["keep"]), keep="|".join(r["keep"]),
                temp_entropy_w=(round(float(r["w_ent"][r["keep"].index("X2_气温C")]), 6)
                                if "X2_气温C" in r["keep"] else np.nan),
                temp_combined_w=(round(float(r["w"][r["keep"].index("X2_气温C")]), 6)
                                 if "X2_气温C" in r["keep"] else np.nan),
                max_abs_delta=round(float(np.abs(d).max()), 6),
                mean_abs_delta=round(float(np.abs(d).mean()), 6),
                pearson_r=round(pr[0], 6), spearman_rho=round(sp[0], 6),
                spearman_p=round(sp[1], 4),
                n_grade_changed=n_chg,
                grade_counts="|".join("%s:%d" % (k, v) for k, v in sorted(cnt.items())),
                peak_year=int(r["years"][int(np.argmax(r["esi"]))]),
                peak_year_pos=int(ref["years"][int(np.argmax(ref["esi"]))]),
                note=("温度方向=%s；与当前口径(pos)逐指标共同项一致，仅 X2 方向/在否不同" % m)))
    df = pd.DataFrame(rows)
    df.to_csv(OUT, index=False, encoding="utf-8-sig")

    print("=" * 100)
    print("T4 温度方向敏感性汇总（对各情景；对照 = 气温 + 口径）")
    print("=" * 100)
    sm = df[df.scope == "summary"][
        ["scenario", "temp_mode", "n_indicators", "temp_direction", "temp_combined_w",
         "max_abs_delta", "mean_abs_delta", "pearson_r", "spearman_rho", "n_grade_changed",
         "esi", "grade", "grade_pos", "peak_year", "peak_year_pos"]]
    print(sm.to_string(index=False))
    print("\n逐情景·逐方向的等级年数分布")
    for s in SCEN:
        for m in MODES:
            sub = df[(df.scope == "series") & (df.scenario == s) & (df.temp_mode == m)]
            if len(sub) == 0:
                continue
            from collections import Counter
            print("  %-14s %-4s 等级分布=%s  ESI2023=%.4f  峰值年=%d"
                  % (s, m, dict(Counter(sub["grade"])), sub["esi"].values[-1],
                     int(sub["year"].values[int(np.argmax(sub["esi"].values))])))
    print("\n已写出 data/%s（%d 行）" % (os.path.basename(OUT), len(df)))
    return 0


if __name__ == "__main__":
    sys.exit(main())