# -*- coding: utf-8 -*-
"""R28 · T2-附：区域气候口径敏感性（CRU TS 4.10）

背景
----
论文 §2.1 声明研究区为 36.0–40.5°N, 93.5–103.5°E（土地覆被亦按此盒裁剪），
但 process_cru.py L30 的区域气候盒为 36.5–40.0°N, 94.0–103.0°E（四边各缩 0.5°），
且 L64–77 用的是盒内格点**算术平均**（无 cos(lat) 面积权重）。

本脚本在**不改动任何既有文件**的前提下，比较四种区域气候口径：
  A  现状   ：36.5–40.0 / 94.0–103.0，算术平均（复现 process_cru.py 现有口径）
  B  声明域 ：36.0–40.5 / 93.5–103.5，算术平均
  C  声明域 ：36.0–40.5 / 93.5–103.5，cos(lat) 面积加权
  D  现状盒 ：36.5–40.0 / 94.0–103.0，cos(lat) 面积加权（用于分离"换盒"与"换权重"两种效应）
并各自重算 whi=α=0.4 的九指标 ESI 与五级预警，比较逐年差异。

输入（只读）：data/cru/cru_ts4.10.{2001.2010,2011.2020,2021.2025}.{pre,tmp}.dat.nc
              data/qilian_landcover.csv（五期覆被，线性插值到逐年）
              data/ahp_weights.csv
输出（新建）：data/r28_cru_box_sensitivity.csv

口径与 rerun_pipeline_ahp.py / run_esi_regional.py 一致：min–max 归一化（19 年极差）、
熵权、AHP 权重（α=0.4 线性组合）、ESI = X'·w、五级预警 [0.2,0.4,0.6,0.8]。
"""
import os
import sys
import glob
import numpy as np
import pandas as pd
import xarray as xr

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "eco_security"))
import io_utils                                    # noqa: E402
from eco_security import (minmax_normalize, entropy_weights,   # noqa: E402
                          combined_weights, esi_series, classify_warning)

DATA = io_utils.resolve_cru_dir()
YEARS = list(range(2005, 2024))
ALPHA = 0.4

BOXES = {
    "A_current_small_arith":  dict(lat=slice(36.5, 40.0), lon=slice(94.0, 103.0), weight="arith"),
    "B_declared_arith":       dict(lat=slice(36.0, 40.5), lon=slice(93.5, 103.5), weight="arith"),
    "C_declared_coslat":      dict(lat=slice(36.0, 40.5), lon=slice(93.5, 103.5), weight="coslat"),
    "D_current_coslat":       dict(lat=slice(36.5, 40.0), lon=slice(94.0, 103.0), weight="coslat"),
}
ORDER = ["A_current_small_arith", "B_declared_arith", "C_declared_coslat", "D_current_coslat"]


def annual_cube(var):
    """返回逐年、逐格点的年值 DataArray（pre=年降水总和；tmp=年均温）。"""
    pat = os.path.join(DATA, f"*{var}*.nc")
    files = [f for f in sorted(glob.glob(pat))
             if any(s in os.path.basename(f) for s in ("2001.2010", "2011.2020", "2021.2025"))]
    if not files:
        raise FileNotFoundError(f"未找到 {var} 的 CRU 分段文件于 {DATA}")
    parts = []
    for f in files:
        ds, _ = io_utils.open_netcdf(f)
        da = ds[var].sel(time=slice("2005-01", "2023-12"))
        # 只保留声明域（覆盖全部四种口径），减少内存
        da = da.sel(lat=slice(36.0, 40.5), lon=slice(93.5, 103.5))
        if var == "pre":
            ann = da.groupby("time.year").sum("time")       # 年降水 = 12 个月之和
        else:
            ann = da.groupby("time.year").mean("time")      # 年均温
        parts.append(ann.load())
        ds.close()
    out = xr.concat(parts, dim="year").sortby("year")
    return out.sel(year=YEARS)


def spatial_mean(da, box):
    sub = da.sel(lat=box["lat"], lon=box["lon"])
    if box["weight"] == "arith":
        return sub.mean(dim=["lat", "lon"])
    w = np.cos(np.deg2rad(sub["lat"]))
    return (sub * w).sum(dim="lat").sum(dim="lon") / (w.sum() * sub.sizes["lon"])


def build_esi(precip, temp, lc, ahp):
    # 指标命名与 data/ahp_weights.csv 完全一致（勿改，否则取权失败）
    indicators = {
        "X1_降水mm": (precip, +1), "X2_气温C": (temp, +1),
        "X3_草地占比%": (lc["grass_pct"], +1), "X4_森林占比%": (lc["forest_pct"], +1),
        "X5_水域占比%": (lc["water_pct"], +1),
        "X6_裸地荒漠%": (100 - lc["grass_pct"] - lc["forest_pct"] - lc["water_pct"] - lc["crop_pct"], -1),
        "X7_农田占比%": (lc["crop_pct"], -1),
        "X8_草地变化率": (lc["grass_pct"].pct_change().fillna(0) * 100, +1),
        "X9_生态用地%": (lc["grass_pct"] + lc["forest_pct"] + lc["water_pct"], +1),
    }
    names = list(indicators.keys())
    X = np.column_stack([indicators[n][0].values for n in names])
    directions = [indicators[n][1] for n in names]
    Xn = minmax_normalize(X, directions)
    w_ent = entropy_weights(Xn)
    w_ahp = ahp.set_index("indicator").loc[names, "ahp_weight"].values
    w = combined_weights(w_ahp, w_ent, ALPHA)
    esi = esi_series(Xn, w)
    return dict(X=X, Xn=Xn, names=names, w_ent=w_ent, w_ahp=w_ahp, w=w,
                esi=esi, level=classify_warning(esi))


def main():
    print("CRU 目录:", DATA)
    pre_cube = annual_cube("pre")
    tmp_cube = annual_cube("tmp")
    print("年降水 cube:", dict(pre_cube.sizes), "| 年均温 cube:", dict(tmp_cube.sizes))

    lc = pd.read_csv(os.path.join(BASE, "data", "qilian_landcover.csv")).set_index("year").reindex(YEARS)
    for c in lc.columns:
        lc[c] = lc[c].interpolate(method="linear").bfill().ffill()
    ahp = pd.read_csv(os.path.join(BASE, "data", "ahp_weights.csv"))

    res = {}
    for tag in ORDER:
        box = BOXES[tag]
        pr = spatial_mean(pre_cube, box)
        tp = spatial_mean(tmp_cube, box)
        r = build_esi(pr, tp, lc, ahp)
        r["precip"] = pr.values
        r["temp"] = tp.values
        res[tag] = r
        print(f"[{tag}] 降水 2005-2023 均值 {np.mean(pr.values):.3f} mm | "
              f"气温均值 {np.mean(tp.values):.4f} °C | ESI_2023 {r['esi'][-1]:.4f} | "
              f"轻警年数 {sum(1 for l in r['level'] if l=='轻警')}")

    # ---- 逐年表 ----
    rows = []
    for i, y in enumerate(YEARS):
        row = {"year": y}
        for tag in ORDER:
            row[f"precip_{tag}"] = round(float(res[tag]["precip"][i]), 4)
            row[f"temp_{tag}"] = round(float(res[tag]["temp"][i]), 4)
            row[f"esi_{tag}"] = round(float(res[tag]["esi"][i]), 4)
            row[f"level_{tag}"] = res[tag]["level"][i]
        rows.append(row)
    df = pd.DataFrame(rows)
    out = os.path.join(BASE, "data", "r28_cru_box_sensitivity.csv")
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print("\n已写出:", out)

    # ---- 差异汇总 ----
    def cmp(a, b, label):
        dp = res[b]["precip"] - res[a]["precip"]
        dt = res[b]["temp"] - res[a]["temp"]
        de = res[b]["esi"] - res[a]["esi"]
        dl = [x != yv for x, yv in zip(res[a]["level"], res[b]["level"])]
        print(f"\n{label}")
        print(f"  降水 Δ: max|Δ|={np.abs(dp).max():.3f} mm (年 {YEARS[int(np.abs(dp).argmax())]}), "
              f"均值差={dp.mean():+.3f} mm, 极差 {np.abs(dp).max()/res[a]['precip'].mean()*100:.2f}%")
        print(f"  气温 Δ: max|Δ|={np.abs(dt).max():.4f} °C (年 {YEARS[int(np.abs(dt).argmax())]}), "
              f"均值差={dt.mean():+.4f} °C")
        print(f"  ESI  Δ: max|Δ|={np.abs(de).max():.4f} (年 {YEARS[int(np.abs(de).argmax())]}), "
              f"均值差={de.mean():+.4f}, ESI_2023 {res[a]['esi'][-1]:.4f} → {res[b]['esi'][-1]:.4f}")
        print(f"  预警等级改变年数: {sum(dl)}/19" +
              ("" if not any(dl) else " → " + ", ".join(f"{YEARS[i]}:{res[a]['level'][i]}→{res[b]['level'][i]}"
                                                        for i, v in enumerate(dl) if v)))
        return dict(label=label, precip_maxabs=float(np.abs(dp).max()),
                    precip_meandiff=float(dp.mean()), temp_maxabs=float(np.abs(dt).max()),
                    temp_meandiff=float(dt.mean()), esi_maxabs=float(np.abs(de).max()),
                    esi_meandiff=float(de.mean()), grade_changes=int(sum(dl)))

    summary = [
        cmp("A_current_small_arith", "B_declared_arith", "① 换盒（小盒算术 → 声明域算术）"),
        cmp("A_current_small_arith", "C_declared_coslat", "② 现状 → 声明域 + cos(lat) 加权"),
        cmp("B_declared_arith", "C_declared_coslat", "③ 只换权重（声明域：算术 → cos(lat)）"),
        cmp("A_current_small_arith", "D_current_coslat", "④ 只换权重（小盒：算术 → cos(lat)）"),
    ]
    print("\n=== 归一化后 X1/X2 的变化（对 ESI 的直接作用）===")
    for a, b in [("A_current_small_arith", "B_declared_arith"),
                 ("A_current_small_arith", "C_declared_coslat")]:
        d = res[b]["Xn"][:, :2] - res[a]["Xn"][:, :2]
        print(f"  {a} → {b}: max|ΔX1'|={np.abs(d[:,0]).max():.4f}, max|ΔX2'|={np.abs(d[:,1]).max():.4f}")
    print("\n=== 权重表（各口径）===")
    for tag in ORDER:
        print(f"  {tag:24s} " + " ".join(f"{v:.4f}" for v in res[tag]["w"]))
    return summary


if __name__ == "__main__":
    main()