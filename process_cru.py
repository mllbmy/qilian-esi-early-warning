# -*- coding: utf-8 -*-
"""CRU TS 4.10 气候数据处理：祁连山国家公园县域指标提取（2005-2023）
输入：paper-code/data/cru/ 下的 pre/tmp .nc.gz（1901-2025 完整序列，或 2001-2025 十年段）
输出：paper-code/data/qilian_climate.csv（区域/县域逐年年降水、年均温）
"""
import os, glob, gzip, shutil
import numpy as np
import pandas as pd
import xarray as xr

DATA = os.environ.get("QILIAN_CRU_DATA", os.path.join(os.path.dirname(os.path.abspath(__file__)), "_raw", "cru_data"))  # ASCII 路径（netCDF4 C 库不支持中文路径）
# 路径自解析：仓库克隆/解压到任意目录均可运行
BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "data", "qilian_climate.csv")

# 祁连山国家公园范围（初步：县域质心近似，边界数据到位后精化）
# 甘肃侧: 天祝(37.20,102.86) 肃南(38.84,99.62) 肃北(39.51,97.85) 阿克塞(39.34,94.34) 民乐(38.43,100.81) 山丹(38.78,101.09)
# 青海侧: 门源(37.38,101.62) 祁连(38.18,100.24) 刚察(37.33,100.14) 德令哈(37.37,97.36) 天峻(37.30,99.02)
QILIAN_COUNTIES = {
    "天祝": (37.20, 102.86), "肃南": (38.84, 99.62), "肃北": (39.51, 97.85),
    "阿克塞": (39.34, 94.34), "民乐": (38.43, 100.81), "山丹": (38.78, 101.09),
    "门源": (37.38, 101.62), "祁连": (38.18, 100.24), "刚察": (37.33, 100.14),
    "德令哈": (37.37, 97.36), "天峻": (37.30, 99.02),
}
REGION = dict(lat=slice(36.5, 40.0), lon=slice(94.0, 103.0))  # 区域盒

def load_var(var):
    """找到覆盖 2005-2023 的 pre/tmp 数据文件（.nc 或 .nc.gz），返回合并数据集。"""
    pat = os.path.join(DATA, f"*{var}*.nc*")
    all_files = glob.glob(pat)
    # 只保留覆盖研究期的十年段（或完整序列）
    keep = [f for f in all_files if any(d in os.path.basename(f) for d in
            ["2001.2010", "2011.2020", "2021.2025", "1901.2025"])]
    if not keep:
        raise FileNotFoundError(f"未找到覆盖 2005-2023 的 {var} 数据文件于 {DATA}（找到: {[os.path.basename(f) for f in all_files]}）")
    files = sorted(keep)
    ds_list = []
    for f in files:
        if f.endswith(".gz"):
            nc = f[:-3]
            if not os.path.exists(nc):
                with gzip.open(f, "rb") as fi, open(nc, "wb") as fo:
                    shutil.copyfileobj(fi, fo)
            path = nc
        else:
            path = f
        ds_list.append(xr.open_dataset(path))
    ds = xr.concat(ds_list, dim="time") if len(ds_list) > 1 else ds_list[0]
    return ds, "1901.2025" in os.path.basename(files[0])

def main():
    pre, pre_full = load_var("pre")
    tmp, tmp_full = load_var("tmp")
    print(f"降水: {len(pre.time)} 月 {pre.time[0].dt.strftime('%Y-%m').item()} ~ {pre.time[-1].dt.strftime('%Y-%m').item()}")
    print(f"气温: {len(tmp.time)} 月 {tmp.time[0].dt.strftime('%Y-%m').item()} ~ {tmp.time[-1].dt.strftime('%Y-%m').item()}")

    pre = pre.sel(time=slice("2005-01", "2023-12"))
    tmp = tmp.sel(time=slice("2005-01", "2023-12"))
    pre_region = pre["pre"].sel(**REGION)
    tmp_region = tmp["tmp"].sel(**REGION)

    years = pd.date_range("2005", "2023", freq="YS").year
    rows = []
    # 区域均值
    pre_annual = pre_region.groupby("time.year").mean(dim=["lat", "lon"]).sum(dim="time")  # 年均降水(mm/年)（月均值×12近似→用sum更准）
    # 注意：groupby.sum 在时间维求和需正确写法
    pre_annual = pre_region.groupby("time.year").sum("time")  # 每年12个月降水求和
    tmp_annual = tmp_region.groupby("time.year").mean("time")  # 年均温
    for y in years:
        rows.append({"unit": "区域(祁连山盒)", "year": int(y),
                     "precip_mm": float(pre_annual.sel(year=y).mean().values),
                     "temp_c": float(tmp_annual.sel(year=y).mean().values)})
    # 县域质心点
    for name, (lat, lon) in QILIAN_COUNTIES.items():
        pre_p = pre_region.sel(lat=lat, lon=lon, method="nearest")
        tmp_p = tmp_region.sel(lat=lat, lon=lon, method="nearest")
        pre_y = pre_p.groupby("time.year").sum("time")
        tmp_y = tmp_p.groupby("time.year").mean("time")
        for y in years:
            rows.append({"unit": name, "year": int(y),
                         "precip_mm": float(pre_y.sel(year=y).values),
                         "temp_c": float(tmp_y.sel(year=y).values)})
    df = pd.DataFrame(rows)
    df.to_csv(OUT, index=False, encoding="utf-8-sig")
    print("已保存:", OUT)
    print(df[df.unit == "区域(祁连山盒)"].head(6).to_string(index=False))
    print("县域数:", df.unit.nunique() - 1, "| 总行数:", len(df))

if __name__ == "__main__":
    main()
