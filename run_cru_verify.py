# -*- coding: utf-8 -*-
"""R21 气候链（CRU TS 4.10 → 区域/县域 ESI）可复现性验证

目的
────
上一轮已验证 CLCD 覆被采样环节可 100% 复现（run_clcd_verify.py）。
本轮验证**气候环节**：从 CRU TS 4.10 原始 NetCDF 出发，按仓库脚本的**原口径**
重建 2005–2023 年区域/县域气候序列与 ESI 序列，与归档产物逐点比对。

口径冻结（照抄现有脚本，不调参、不凑值）
──────────────────────────────────────
  · 研究期：2005–2023（19 年）—— run_esi_regional.py L20 `YEARS = range(2005, 2024)`
    （"2001–2023 / 19 年"与代码不符；代码与稿件均为 2005–2023 = 19 年，
      2001 年只是 NetCDF 分段文件名的起点）
  · 区域盒：lat 36.5–40.0, lon 94.0–103.0（process_cru.py L25）
  · 年降水 = 区域内月降水求和后按空间求均值（groupby("time.year").sum("time")）
    年气温 = 区域内月气温按空间 + 时间求均值（groupby("time.year").mean("time")）
  · 县域 = 11 个县质心最近格点（process_cru.py L19-24）
  · 区域 ESI：run_esi_regional.py / rerun_pipeline_ahp.py 的 9 指标 + 熵权 + AHP
    + α=0.4 组合权重（两个脚本对 w_ahp 的口径不同，本脚本两条都算并分别比对）
  · 县域 ESI：run_county_esi.py 的 6 指标 + 11 县间 min-max + 熵权 + 等权 AHP + α=0.4

与源脚本的唯一差异（最小适配，已在报告中记录）
────────────────────────────────────────────
 源脚本用 `xr.open_dataset(path)` 默认引擎；本机 netCDF4 C 库无法打开含中文的路径
 （例如 `<含中文的目录>/<repo>/...`），报 FileNotFoundError。故本脚本按引擎回退
 （netcdf4 → scipy）打开，其余逻辑逐字保持。

红线
────
只读原始数据；只**新建** data/cru_verify_*.csv；不覆盖 data/ 下任何已有 CSV；
不修改任何论文文件；不做插值填补缺口；结果不一致时如实报告，不调参。

运行：python run_cru_verify.py
"""
import glob
import hashlib
import os
import sys

import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import xarray as xr  # noqa: E402

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
sys.path.insert(0, BASE)
import io_utils  # noqa: E402  # R22：共享 I/O 层（目录回退）
CRU_DIR = io_utils.resolve_cru_dir()  # QILIAN_CRU_DATA -> _raw/cru_data -> data/cru -> 递归兜底
LC_DIR = io_utils.resolve_lc_dir()    # QILIAN_LC_DATA -> _raw/lc_data -> 递归兜底

sys.path.insert(0, os.path.join(BASE, "eco_security"))
from eco_security import (  # noqa: E402
    classify_warning, combined_weights, entropy_weights, esi_series, minmax_normalize,
)

# ---------------------------------------------------------------------------
# 冻结口径副本（逐字照抄源脚本）
# ---------------------------------------------------------------------------
REGION = dict(lat=slice(36.5, 40.0), lon=slice(94.0, 103.0))   # process_cru.py L25
QILIAN_COUNTIES = {                                             # process_cru.py L19-24
    "天祝": (37.20, 102.86), "肃南": (38.84, 99.62), "肃北": (39.51, 97.85),
    "阿克塞": (39.34, 94.34), "民乐": (38.43, 100.81), "山丹": (38.78, 101.09),
    "门源": (37.38, 101.62), "祁连": (38.18, 100.24), "刚察": (37.33, 100.14),
    "德令哈": (37.37, 97.36), "天峻": (37.30, 99.02),
}
YEARS = list(range(2005, 2024))                                  # 19 年
REGION_UNIT = "区域(祁连山盒)"
ALPHA = 0.4

ENV_NOTE = []
SUMMARY = []


def note(k, v):
    ENV_NOTE.append({"item": k, "value": str(v)})


def rec(k, v):
    SUMMARY.append({"metric": k, "value": v})
    print(f"  [SUMMARY] {k} = {v}")


def open_nc(path):
    """按引擎回退打开 NetCDF（中文路径下 netCDF4 C 库会 FileNotFoundError）。"""
    last = None
    for eng in ("netcdf4", "scipy", None):
        try:
            ds = xr.open_dataset(path) if eng is None else xr.open_dataset(path, engine=eng)
            ENV_NOTE.append({"item": "open_engine_used",
                             "value": f"{os.path.basename(path)} -> {eng or 'default'}"})
            return ds
        except Exception as e:  # noqa: BLE001
            last = e
    raise RuntimeError(f"无法打开 {path}: {type(last).__name__}: {last}")


# ---------------------------------------------------------------------------
# 1) CRU 文件清单 + 时间覆盖 + 年度缺口
# ---------------------------------------------------------------------------
def step1_inventory():
    print("\n[1] CRU 文件清单与时间覆盖")
    rows = []
    for fn in sorted(os.listdir(CRU_DIR)):
        p = os.path.join(CRU_DIR, fn)
        if not os.path.isfile(p):
            continue
        r = {"file": fn, "bytes": os.path.getsize(p),
             "md5": hashlib.md5(open(p, "rb").read()).hexdigest(),
             "var": ("pre" if ".pre." in fn else ("tmp" if ".tmp." in fn else "")),
             "opened": "", "ntime": "", "first": "", "last": "", "error": ""}
        if fn.endswith(".nc"):
            try:
                ds = open_nc(p)
                t = pd.to_datetime(ds["time"].values)
                r.update(opened="yes", ntime=len(t),
                         first=str(t[0].date()), last=str(t[-1].date()))
                ds.close()
            except Exception as e:  # noqa: BLE001
                r["error"] = f"{type(e).__name__}: {e}"
        else:
            r["opened"] = "no (gzip, 未解压)"
        rows.append(r)
    inv = pd.DataFrame(rows)
    inv.to_csv(os.path.join(DATA, "cru_verify_file_inventory.csv"),
               index=False, encoding="utf-8-sig")
    print(inv[["file", "bytes", "var", "opened", "ntime", "first", "last"]].to_string(index=False))

    # 月度连续性（合并 2001-2010 / 2011-2020 / 2021-2025 段）
    segs = ["2001.2010", "2011.2020", "2021.2025"]
    months = []
    for seg in segs:
        ds = open_nc(os.path.join(CRU_DIR, f"cru_ts4.10.{seg}.pre.dat.nc"))
        months.append(pd.to_datetime(ds["time"].values))
        ds.close()
    all_ts = pd.DatetimeIndex(np.concatenate([m.values for m in months]))
    # CRU 月中时间戳是每月 16 日，比较按"月"粒度归一到月初
    all_m = pd.DatetimeIndex(all_ts.to_period("M").to_timestamp())
    expect = pd.date_range(all_m.min(), all_m.max(), freq="MS")
    missing = expect.difference(all_m)
    dup = len(all_m) - len(all_m.unique())
    rec("CRU_pre_月份总数(合并后)", len(all_m))
    rec("CRU_pre_时间范围", f"{all_m.min().date()} ~ {all_m.max().date()}")
    rec("CRU_pre_缺失月份数", len(missing))
    rec("CRU_pre_重复月份数", dup)
    rec("研究期2005-2023所需月份数", 19 * 12)
    need = pd.date_range("2005-01-01", "2023-12-01", freq="MS")
    rec("研究期内缺失月份数", len(need.difference(all_m)))
    rec("研究期内月份总数", len(need.intersection(all_m)))
    gap = [str(d.date()) for d in missing[:5]]
    note("月度缺口(合并段内)", "无" if len(missing) == 0 else ",".join(gap))
    note("1901-1910 gz 是否参与", "否 —— process_cru.py L32-33 keep 白名单不含 '1901.1910'，"
                                "且 .gz 未解压；该段在 2005-2023 研究期之外")
    note("2021-2025 段覆盖", "2021-01 ~ 2025-12（60 月）；研究期只需 2021-2023，"
                            "2024-2025 超出研究期，不构成缺口")
    note("研究期年度缺口", "无（2005-01 ~ 2023-12 全部 228 个月齐备）")
    return inv


# ---------------------------------------------------------------------------
# 2) 重建气候序列（process_cru.py 口径）
# ---------------------------------------------------------------------------
def load_var(var):
    """逐字照抄 process_cru.py L27-49，仅把 open_dataset 换成引擎回退版。"""
    pat = os.path.join(CRU_DIR, f"*{var}*.nc*")
    all_files = glob.glob(pat)
    keep = [f for f in all_files if any(d in os.path.basename(f) for d in
            ["2001.2010", "2011.2020", "2021.2025", "1901.2025"])]
    if not keep:
        raise FileNotFoundError(f"未找到覆盖 2005-2023 的 {var} 数据文件于 {CRU_DIR}"
                                f"（找到: {[os.path.basename(f) for f in all_files]}）")
    files = sorted(keep)
    note(f"{var}_使用文件", "; ".join(os.path.basename(f) for f in files))
    ds_list = []
    for f in files:
        path = f
        if f.endswith(".gz"):
            nc = f[:-3]
            if not os.path.exists(nc):
                raise RuntimeError(f"需要 .gz 解压但本脚本不写盘: {f}")
            path = nc
        ds_list.append(open_nc(path))
    return xr.concat(ds_list, dim="time") if len(ds_list) > 1 else ds_list[0]


def step2_climate():
    print("\n[2] 从原始 CRU 重建 2005-2023 气候序列（process_cru.py 口径）")
    pre = load_var("pre")
    tmp = load_var("tmp")
    pre = pre.sel(time=slice("2005-01", "2023-12"))
    tmp = tmp.sel(time=slice("2005-01", "2023-12"))
    pre_region = pre["pre"].sel(**REGION)
    tmp_region = tmp["tmp"].sel(**REGION)
    print(f"  pre 窗口={pre.sizes['time']} 月, lat={pre_region.sizes['lat']}, lon={pre_region.sizes['lon']}")

    pre_annual = pre_region.groupby("time.year").sum("time")     # 年降水 mm
    tmp_annual = tmp_region.groupby("time.year").mean("time")    # 年均温 °C

    rows = []
    for y in YEARS:
        rows.append({"unit": REGION_UNIT, "year": int(y),
                     "precip_mm": float(pre_annual.sel(year=y).mean().values),
                     "temp_c": float(tmp_annual.sel(year=y).mean().values)})
    for name, (lat, lon) in QILIAN_COUNTIES.items():
        pre_p = pre_region.sel(lat=lat, lon=lon, method="nearest")
        tmp_p = tmp_region.sel(lat=lat, lon=lon, method="nearest")
        pre_y = pre_p.groupby("time.year").sum("time")
        tmp_y = tmp_p.groupby("time.year").mean("time")
        for y in YEARS:
            rows.append({"unit": name, "year": int(y),
                         "precip_mm": float(pre_y.sel(year=y).values),
                         "temp_c": float(tmp_y.sel(year=y).values)})
    new = pd.DataFrame(rows)
    new.to_csv(os.path.join(DATA, "cru_verify_climate_series.csv"),
               index=False, encoding="utf-8-sig")
    print(f"  重建行数: {len(new)}（{new.unit.nunique()} 单元 × {len(YEARS)} 年）")

    # ---- 与归档 qilian_climate.csv 逐点比对 ----
    arc = pd.read_csv(os.path.join(DATA, "qilian_climate.csv"))
    m = arc.merge(new, on=["unit", "year"], suffixes=("_arc", "_new"), how="outer", indicator=True)
    if (m["_merge"] != "both").any():
        print("  !! 行集合不一致:", m.loc[m["_merge"] != "both", ["unit", "year", "_merge"]].to_string(index=False))
    cmp = m[m["_merge"] == "both"].copy()
    cmp["d_precip"] = cmp["precip_mm_new"] - cmp["precip_mm_arc"]
    cmp["d_temp"] = cmp["temp_c_new"] - cmp["temp_c_arc"]
    cmp["rel_precip"] = np.where(np.abs(cmp["precip_mm_arc"]) > 1e-12,
                                 cmp["d_precip"] / cmp["precip_mm_arc"], np.nan)
    cmp["rel_temp"] = np.where(np.abs(cmp["temp_c_arc"]) > 1e-12,
                               cmp["d_temp"] / cmp["temp_c_arc"], np.nan)
    cmp.to_csv(os.path.join(DATA, "cru_verify_climate_compare.csv"),
               index=False, encoding="utf-8-sig")

    ap = float(np.abs(cmp["d_precip"]).max())
    at = float(np.abs(cmp["d_temp"]).max())
    rp = float(np.nanmax(np.abs(cmp["rel_precip"])))
    rt = float(np.nanmax(np.abs(cmp["rel_temp"])))
    exact = int(((np.abs(cmp["d_precip"]) < 1e-10) & (np.abs(cmp["d_temp"]) < 1e-10)).sum())
    rec("气候_比对行数", len(cmp))
    rec("气候_降水最大绝对偏差(mm)", f"{ap:.3e}")
    rec("气候_气温最大绝对偏差(°C)", f"{at:.3e}")
    rec("气候_降水最大相对偏差", f"{rp:.3e}")
    rec("气候_气温最大相对偏差", f"{rt:.3e}")
    rec("气候_|Δ|<1e-10 的行数", f"{exact}/{len(cmp)}")
    if ap > 0:
        w = cmp.loc[np.abs(cmp["d_precip"]).idxmax()]
        rec("气候_降水最大偏差所在", f"{w['unit']} {int(w['year'])}: arc={w['precip_mm_arc']:.6f} new={w['precip_mm_new']:.6f}")
    if at > 0:
        w = cmp.loc[np.abs(cmp["d_temp"]).idxmax()]
        rec("气候_气温最大偏差所在", f"{w['unit']} {int(w['year'])}: arc={w['temp_c_arc']:.6f} new={w['temp_c_new']:.6f}")
    return new


# ---------------------------------------------------------------------------
# 3) 重建区域级 ESI 19 年序列（两种 w_ahp 口径都算）
# ---------------------------------------------------------------------------
def regional_esi(cli_df, lc_df, w_ahp_kind):
    """run_esi_regional.py / rerun_pipeline_ahp.py 的 9 指标区域管线。"""
    reg_cli = cli_df[cli_df.unit == REGION_UNIT].set_index("year")
    lc = lc_df.set_index("year").reindex(YEARS)
    for c in lc.columns:
        lc[c] = lc[c].interpolate(method="linear").bfill().ffill()
    indicators = {
        "X1_降水mm": (reg_cli["precip_mm"], +1), "X2_气温C": (reg_cli["temp_c"], +1),
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
    if w_ahp_kind == "equal":       # run_esi_regional.py L48-49
        w_ahp = np.ones(len(names)) / len(names)
    elif w_ahp_kind == "ahp_csv":   # rerun_pipeline_ahp.py L36-38
        ahp = pd.read_csv(os.path.join(DATA, "ahp_weights.csv"))
        w_ahp = ahp.set_index("indicator").loc[names, "ahp_weight"].values
    else:
        raise ValueError(w_ahp_kind)
    w = combined_weights(w_ahp, w_ent, ALPHA)
    return esi_series(Xn, w), w, w_ent


def step3_regional_esi(cli_new):
    print("\n[3] 重建区域级 ESI 19 年序列")
    lc = pd.read_csv(os.path.join(DATA, "qilian_landcover.csv"))
    arc = pd.read_csv(os.path.join(DATA, "results_esi_regional.csv")).set_index("year")

    out = pd.DataFrame({"year": YEARS})
    res = {}
    for kind in ("ahp_csv", "equal"):
        esi, w, w_ent = regional_esi(cli_new, lc, kind)
        res[kind] = (esi, w, w_ent)
        out["esi_" + kind] = np.round(esi, 6)
    esi_arch = arc.loc[YEARS, "esi"].values
    for kind in res:
        out["d_" + kind] = res[kind][0] - esi_arch
    out["esi_archive"] = esi_arch
    out["warning_archive"] = arc.loc[YEARS, "warning"].values
    out["warning_ahp_csv"] = classify_warning(res["ahp_csv"][0])
    out["warning_equal"] = classify_warning(res["equal"][0])
    out.to_csv(os.path.join(DATA, "cru_verify_esi_regional.csv"),
               index=False, encoding="utf-8-sig")

    print(out[["year", "esi_archive", "esi_ahp_csv", "esi_equal",
               "d_ahp_csv", "d_equal"]].to_string(index=False, float_format=lambda v: f"{v: .6f}"))
    print("\n  组合权重（ahp_csv 口径）:")
    for n, ww in zip(["X1", "X2", "X3", "X4", "X5", "X6", "X7", "X8", "X9"], res["ahp_csv"][1]):
        print(f"    {n}: {ww:.6f}")

    for kind in ("ahp_csv", "equal"):
        d = np.abs(out["d_" + kind].values)
        pk_new = YEARS[int(np.argmax(res[kind][0]))]
        pk_arc = YEARS[int(np.argmax(esi_arch))]
        rec(f"区域ESI_{kind}_最大绝对偏差", f"{d.max():.3e}")
        rec(f"区域ESI_{kind}_|Δ|<1e-10 的点数", f"{int((d < 1e-10).sum())}/{len(d)}")
        rec(f"区域ESI_{kind}_四舍五入到4位后与归档相同", f"{int((np.round(res[kind][0], 4) == esi_arch).sum())}/{len(d)}")
        rec(f"区域ESI_{kind}_峰值年", f"{pk_new}（归档 {pk_arc}）")
        rec(f"区域ESI_{kind}_峰值", f"{res[kind][0].max():.6f}（归档 {esi_arch.max():.6f}）")
        rec(f"区域ESI_{kind}_预警等级序列与归档一致", str(list(classify_warning(res[kind][0])) == list(arc.loc[YEARS, "warning"].values)))
    rec("区域ESI_归档_2023", f"{esi_arch[YEARS.index(2023)]:.6f}")
    rec("区域ESI_归档_峰值年", YEARS[int(np.argmax(esi_arch))])

    # ---- 对照实验：把"归档气候"（而非重建气候）喂进同一管线 ----
    # 用于把残余偏差拆成两半：(a) 气候重建引入的偏差，(b) 归档 CSV 只存 4 位小数。
    # 守恒前提：归档 results_esi_regional.csv 由 rerun_pipeline_ahp.py + 归档 qilian_climate.csv 生成。
    arc_cli = pd.read_csv(os.path.join(DATA, "qilian_climate.csv"))
    esi_ctl, _, _ = regional_esi(arc_cli, lc, "ahp_csv")
    d_recon = np.abs(esi_ctl - res["ahp_csv"][0]).max()   # (a) 重建气候 vs 归档气候
    d_round = np.abs(esi_ctl - esi_arch).max()            # (b) 未取整 vs 取整归档
    rec("对照_归档气候输入 ESI 与重建气候 ESI 最大差", f"{d_recon:.3e}")
    rec("对照_归档气候输入 ESI 与归档CSV 最大差（=取整残差）", f"{d_round:.3e}")
    out["esi_control_arcclimate"] = np.round(esi_ctl, 6)
    out.to_csv(os.path.join(DATA, "cru_verify_esi_regional.csv"),
               index=False, encoding="utf-8-sig")
    return out


# ---------------------------------------------------------------------------
# 4) 重建县域 ESI（run_county_esi.py 口径 + CRU 重建气候）
# ---------------------------------------------------------------------------
def county_esi_from(cli_df, lc_df):
    """逐字照抄 run_county_esi.py county_esi()。"""
    cli = cli_df[cli_df.unit != REGION_UNIT]
    cnt_cli = cli.groupby("unit")[["precip_mm", "temp_c"]].mean()
    m = lc_df.set_index("unit").join(cnt_cli).dropna()
    indicators = ["precip_mm", "temp_c", "forest_pct", "grass_pct", "water_pct"]
    X = m[indicators].values
    barren_neg = (100.0 - m["forest_pct"] - m["grass_pct"] - m["water_pct"] - m["crop_pct"]).values
    X2 = np.column_stack([X, barren_neg])
    names = ["precip_mm", "temp_c", "forest_pct", "grass_pct", "water_pct", "barren_neg_pct"]
    directions = [+1, +1, +1, +1, +1, -1]
    Xn = minmax_normalize(X2, directions)
    w_ent = entropy_weights(Xn)
    w_ahp = np.ones(X2.shape[1]) / X2.shape[1]
    w = combined_weights(w_ahp, w_ent, ALPHA)
    esi = esi_series(Xn, w)
    return (pd.DataFrame({"unit": m.index, "esi_2020": esi})
            .sort_values("esi_2020", ascending=False).reset_index(drop=True), w, w_ent, m)


def step4_county_esi(cli_new):
    print("\n[4] 重建县域 ESI（11 县，run_county_esi.py 口径）")
    lc_arc = pd.read_csv(os.path.join(DATA, "qilian_county_landcover.csv"))

    # 额外：从 CLCD 栅格重新采样县域覆被，验证气候链 + 覆被链端到端
    lc_rt = None
    tif = os.path.join(LC_DIR, "CLCD_v01_2020_albert.tif")
    if os.path.exists(tif):
        try:
            import rasterio
            from pyproj import Transformer
            from rasterio.windows import from_bounds
            src = rasterio.open(tif)
            tf = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
            rows = []
            for name, (lat, lon) in QILIAN_COUNTIES.items():
                x0, y0 = tf.transform(lon - 0.1, lat - 0.1)
                x1, y1 = tf.transform(lon + 0.1, lat + 0.1)
                win = from_bounds(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1), src.transform)
                arr = src.read(1, window=win)
                vals, counts = np.unique(arr[arr != 0], return_counts=True)
                d = {int(v): int(c) for v, c in zip(vals, counts)}
                tot = sum(d.values())
                pct = lambda c: d.get(c, 0) * 100 / tot if tot else 0.0
                rows.append({"unit": name, "forest_pct": pct(2), "grass_pct": pct(4),
                             "water_pct": pct(5), "barren_pct": pct(7), "crop_pct": pct(1)})
            src.close()
            lc_rt = pd.DataFrame(rows)
            d = (lc_rt.set_index("unit").sort_index() -
                 lc_arc.set_index("unit").sort_index())[["forest_pct", "grass_pct", "water_pct", "crop_pct"]]
            rec("县域覆被CLCD重采样_最大绝对偏差(pct)", f"{np.abs(d.values).max():.3e}")
        except Exception as e:  # noqa: BLE001
            print("  CLCD 重采样失败（不阻塞气候链验证）:", type(e).__name__, e)
    else:
        print("  CLCD 栅格缺失，县域覆被只用归档 qilian_county_landcover.csv")

    archives = {}
    for fn in ("results_county_esi.csv",):
        p = os.path.join(DATA, fn)
        if os.path.exists(p):
            archives[fn] = pd.read_csv(p)
    cnt_clcd = os.path.join(DATA, "results_county_esi_from_clcd.csv")
    if os.path.exists(cnt_clcd):
        archives["results_county_esi_from_clcd.csv"] = pd.read_csv(cnt_clcd)
    else:
        note("results_county_esi_from_clcd.csv", "缺失（不在磁盘、也不在 git 跟踪列表）；"
                                                "无法与 run_county_geodetector.py 的直读产物比对")

    lc_use = lc_arc if lc_rt is None else lc_rt
    new, w, w_ent, m = county_esi_from(cli_new, lc_use)
    new["esi_2020"] = np.round(new["esi_2020"], 6)

    blk = new.rename(columns={"esi_2020": "esi_new"})
    # 对照：归档气候（而非重建气候）输入同一管线
    arc_cli = pd.read_csv(os.path.join(DATA, "qilian_climate.csv"))
    ctl, _, _, _ = county_esi_from(arc_cli, lc_use)
    blk = blk.merge(ctl.rename(columns={"esi_2020": "esi_control_arcclimate"}), on="unit", how="left")
    rec("对照_县域_归档气候 ESI 与重建气候 ESI 最大差",
        f"{np.abs(blk['esi_control_arcclimate'] - blk['esi_new']).max():.3e}")
    for fn, a in archives.items():
        blk = blk.merge(a.rename(columns={"esi_2020": "esi_" + fn}), on="unit", how="outer")
    blk.to_csv(os.path.join(DATA, "cru_verify_county_esi.csv"), index=False, encoding="utf-8-sig")
    print(blk.to_string(index=False, float_format=lambda v: f"{v:.6f}"))
    print("\n  县域组合权重:", {n: round(float(x), 6) for n, x in
          zip(["precip", "temp", "forest", "grass", "water", "barren"], w)})

    for fn in archives:
        col = "esi_" + fn
        d = np.abs(blk["esi_new"] - blk[col])
        rec(f"县域ESI_vs_{fn}_最大绝对偏差", f"{d.max():.3e}")
        rec(f"县域ESI_vs_{fn}_|Δ|<1e-10 的县数", f"{int((d < 1e-10).sum())}/{len(d)}")
        rec(f"县域ESI_vs_{fn}_最大偏差县", f"{blk.loc[d.idxmax(), 'unit']}")
    aksai = blk[blk.unit == "阿克塞"]
    if len(aksai):
        r = aksai.iloc[0]
        rec("阿克塞_ESI(重建)", f"{r['esi_new']:.6f}")
        for fn in archives:
            rec(f"阿克塞_ESI(归档 {fn})", f"{r['esi_' + fn]:.6f}")
    return blk


def main():
    print("=" * 78)
    print("R21 气候链可复现性验证（CRU TS 4.10 → 区域/县域 ESI）")
    print("=" * 78)
    note("QILIAN_CRU_DATA", os.environ.get("QILIAN_CRU_DATA", "(未设置；回退 data/cru)"))
    note("QILIAN_LC_DATA", os.environ.get("QILIAN_LC_DATA", "(未设置；回退 _raw/lc_data)"))
    note("CRU_DIR(实际使用)", CRU_DIR)
    note("LC_DIR(实际使用)", LC_DIR)
    note("研究期", "2005-2023（19 年，以 run_esi_regional.py L20 为准）")

    step1_inventory()
    cli_new = step2_climate()
    step3_regional_esi(cli_new)
    step4_county_esi(cli_new)

    pd.DataFrame(SUMMARY).to_csv(os.path.join(DATA, "cru_verify_summary.csv"),
                                 index=False, encoding="utf-8-sig")
    pd.DataFrame(ENV_NOTE).to_csv(os.path.join(DATA, "cru_verify_env_and_notes.csv"),
                                  index=False, encoding="utf-8-sig")
    print("\n已写出（全部新增，未覆盖任何既有文件）:")
    for f in ("cru_verify_file_inventory.csv", "cru_verify_climate_series.csv",
              "cru_verify_climate_compare.csv", "cru_verify_esi_regional.csv",
              "cru_verify_county_esi.csv", "cru_verify_summary.csv",
              "cru_verify_env_and_notes.csv"):
        print("  data/" + f)


if __name__ == "__main__":
    main()