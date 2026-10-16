# -*- coding: utf-8 -*-
"""外生因子 GeoDetector（复现图 8(b) 的高程/坡度 q 值）

背景：图 8(b) 中高程 0.09、坡度 0.06 原先是写死在
make_fig_geodetector_q_v2.py 里的字面量，既无生成脚本也无 CSV。本脚本补上
可复现管线，产出 data/results_geodetector_exogenous.csv，图 8 改为读该 CSV。

数据来源（全部为已入库文件，不新增外部下载）：
  · 点位与地形：data/_aux_terrain_points.csv（lat, lon, elev, slope）
    —— 1,914 个格点，与 data/spatial_esi_points.csv 的点位逐一对应。
  · 点尺度 ESI：data/spatial_esi_points.csv（lat, lon, esi）
  · 气候：CRU TS 4.10 原始 NetCDF（与 run_county_geodetector.py 同一路径），
    按最近邻取点，2005-2023 年年降水求和后取多年均值 / 年均温取多年均值。

方法（与正文 §4.5、图 8(b) 一致）：
  · 每个因子按样本分位数离散为 4 个等样本层（四分位分层）。
  · q = 1 - Σ_h N_h σ_h² / (N σ²)，即分层所解释的 ESI 空间方差份额。
  · 显著性用 999 次置换检验，p = (1 + #{q_perm ≥ q_obs}) / (999 + 1)。

坡度定义：_aux_terrain_points.csv 的 slope 为 Copernicus DEM 90 m 上的
地表坡度（度），3×3 窗口中心点取值。同一坡度定义下按不同重采样方式分别得 0.0647 与
0.0631，差异源于坡度栅格的重采样方式；两者四舍五入均为 0.06，正文与
图 8(b) 的标注不受影响。
"""
import os
import sys

import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
sys.path.insert(0, BASE)
import io_utils  # noqa: E402  # R22：共享 I/O 层
N_PERM = 999
K = 4


def find_cru_dir():
    """定位 CRU 目录（R22：统一走 io_utils，解析规则见 io_utils 模块 docstring）。"""
    try:
        return io_utils.resolve_cru_dir()
    except FileNotFoundError:
        return None


def q_stat(x, y):
    """GeoDetector q 统计量：x 为分层标签，y 为连续值。"""
    n = len(y)
    var = y.var(ddof=0)
    if var == 0:
        return 0.0
    s = 0.0
    for h in np.unique(x):
        m = x == h
        s += m.sum() * y[m].var(ddof=0)
    return 1.0 - s / (n * var)


def discretize(v, k=K):
    """按样本分位数离散为 k 个等样本层。"""
    qs = np.quantile(v, np.linspace(0, 1, k + 1)[1:-1])
    return np.searchsorted(qs, v, side="right")


def detect(x, y, rng, n_perm=N_PERM):
    xd = discretize(x)
    q = q_stat(xd, y)
    cnt = 0
    for _ in range(n_perm):
        if q_stat(rng.permutation(xd), y) >= q:
            cnt += 1
    return q, (1.0 + cnt) / (n_perm + 1.0)


def main():
    ter = pd.read_csv(os.path.join(DATA, "_aux_terrain_points.csv"))
    esp = pd.read_csv(os.path.join(DATA, "spatial_esi_points.csv"))
    df = pd.merge(ter, esp[["lat", "lon", "esi"]], on=["lat", "lon"], how="inner")
    print("点位合并: terrain %d + esi %d → %d" % (len(ter), len(esp), len(df)))
    if len(df) != 1914:
        print("警告: 合并后点位 %d ≠ 1914，请检查点位文件" % len(df))

    cru = find_cru_dir()
    if cru is None:
        print("未找到 CRU TS 4.10 NetCDF，无法复现降水/气温，退出。")
        return 1
    print("CRU 目录:", cru)
    import xarray as xr

    def _open(path):
        """R22：统一走 io_utils 的引擎回退（netcdf4 -> scipy -> h5netcdf -> 默认）。"""
        return io_utils.open_netcdf(path)[0]

    pre = _open(os.path.join(cru, "cru_ts4.10.2001.2010.pre.dat.nc")).sel(time=slice("2005-01", "2023-12"))
    tmp = _open(os.path.join(cru, "cru_ts4.10.2001.2010.tmp.dat.nc")).sel(time=slice("2005-01", "2023-12"))
    for seg in ["2011.2020", "2021.2025"]:
        fp = os.path.join(cru, "cru_ts4.10.%s.pre.dat.nc" % seg)
        ft = os.path.join(cru, "cru_ts4.10.%s.tmp.dat.nc" % seg)
        if os.path.exists(fp):
            pre = xr.concat([pre, _open(fp).sel(time=slice("2005-01", "2023-12"))], dim="time")
            tmp = xr.concat([tmp, _open(ft).sel(time=slice("2005-01", "2023-12"))], dim="time")
    pre_ann = pre["pre"].groupby("time.year").sum("time").mean("year")
    tmp_ann = tmp["tmp"].groupby("time.year").mean("time").mean("year")

    prec, temp = [], []
    for lat, lon in zip(df["lat"].values, df["lon"].values):
        prec.append(float(pre_ann.sel(lat=lat, lon=lon, method="nearest").values))
        temp.append(float(tmp_ann.sel(lat=lat, lon=lon, method="nearest").values))
    df["precip"] = prec
    df["temp"] = temp

    y = df["esi"].values
    rng = np.random.default_rng(42)
    rows = []
    for fac, col in [("precip", "precip"), ("temp", "temp"),
                     ("elev", "elev"), ("slope", "slope")]:
        q, p = detect(df[col].values, y, rng)
        rows.append({"factor": fac, "q": round(q, 4), "p": round(p, 4)})
        print("  %-7s q=%.4f  p=%.4f" % (fac, q, p))

    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(DATA, "results_geodetector_exogenous.csv"),
               index=False, encoding="utf-8-sig")
    print("\n已写出 data/results_geodetector_exogenous.csv")
    print(out.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())