# -*- coding: utf-8 -*-
"""共享 I/O 层：原始数据目录解析 + NetCDF 引擎回退读取。

R22 加固新增（作者显式授权修改 .py 与新增说明文件）。
本模块**只做路径与读取层面的适配**，不涉及任何算法、权重、口径、数值逻辑。

一、为什么需要「引擎回退」
    本机（Windows）xarray 默认走 netCDF4/HDF5 的 C 库，而该 C 库在
    **含非 ASCII（中文）字符的路径**下会抛
        FileNotFoundError: [Errno 2] No such file or directory: '...\\比赛\\...'
    文件其实存在。CRU TS 4.10 是 NetCDF3 classic 格式，scipy 引擎（纯 Python 实现，
    不使用 C 库）可以正常打开。因此统一按
        netcdf4 -> scipy -> h5netcdf -> xarray 默认
    的顺序回退。**找到的第一个可用引擎即返回**；全部失败才抛错，并把各引擎的
    原始异常一并列出，便于审稿人定位。

二、为什么需要「目录回退」
    历史脚本默认 `_raw/cru_data`（本机不存在）。为满足「按 README 默认参数直接
    运行即可成功，无需手动设环境变量」，统一按下列优先级解析：

    CRU:  QILIAN_CRU_DATA（显式环境变量，最高优先）
          -> <repo>/_raw/cru_data      （若存在且含 cru_ts4.10.2001.2010.pre.dat.nc）
          -> <repo>/data/cru           （仓库实际位置）
          -> 在 <repo> 下递归搜索该文件名
    CLCD: QILIAN_LC_DATA
          -> <repo>/_raw/lc_data       （CLCD_v01_YYYY_albert.tif）
          -> 在 <repo> 下递归搜索

    解析结果是「含所需数据的目录」，因此显式设了环境变量但路径写错时会自动继续
    回退，而不是直接崩掉。
"""
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

__all__ = [
    "REPO_ROOT", "resolve_cru_dir", "resolve_lc_dir",
    "open_netcdf", "cru_file", "clcd_file",
]

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))

# CRU 段文件名（覆盖研究期 2005-2023 的三段）
CRU_SEGMENTS = ("2001.2010", "2011.2020", "2021.2025")
CRU_PROBE = "cru_ts4.10.2001.2010.pre.dat.nc"


def _first_existing_dir(cands, probe):
    """返回第一个「存在且含 probe 文件」的候选目录。"""
    for c in cands:
        if not c:
            continue
        try:
            if os.path.isfile(os.path.join(c, probe)):
                return os.path.abspath(c)
        except OSError:
            continue
    return None


def _search_under(root, probe, max_depth=4):
    """在 root 下有限深度搜索含 probe 的目录（兜底，避免硬编码失败）。"""
    root = os.path.abspath(root)
    base_depth = root.rstrip(os.sep).count(os.sep)
    for dirpath, dirnames, filenames in os.walk(root):
        if dirpath.count(os.sep) - base_depth >= max_depth:
            dirnames[:] = []
            continue
        # 跳过体积巨大或无关的目录
        dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__", "out", "figures")]
        if probe in filenames:
            return dirpath
    return None


def resolve_cru_dir(required=None, verbose=True):
    """解析 CRU TS 4.10 目录。见模块 docstring 的优先级说明。"""
    probe = required or CRU_PROBE
    cands = [os.environ.get("QILIAN_CRU_DATA"),
             os.path.join(REPO_ROOT, "_raw", "cru_data"),
             os.path.join(REPO_ROOT, "data", "cru")]
    d = _first_existing_dir(cands, probe)
    if d is None:
        d = _search_under(REPO_ROOT, probe)
    if d is None:
        tried = " | ".join([c for c in cands if c])
        raise FileNotFoundError(
            "未找到 CRU TS 4.10 数据（缺少 %s）。\n已尝试: %s\n"
            "请设置环境变量 QILIAN_CRU_DATA 指向含该文件的目录。" % (probe, tried))
    if verbose:
        src = "QILIAN_CRU_DATA" if os.environ.get("QILIAN_CRU_DATA") and \
            os.path.abspath(os.environ["QILIAN_CRU_DATA"]) == d else "默认回退"
        print("[io_utils] CRU 目录 = %s  (%s)" % (d, src))
    return d


def resolve_lc_dir(year=2020, verbose=True):
    """解析 CLCD 栅格目录（默认探测 CLCD_v01_2020_albert.tif）。"""
    probe = "CLCD_v01_%d_albert.tif" % year
    cands = [os.environ.get("QILIAN_LC_DATA"),
             os.path.join(REPO_ROOT, "_raw", "lc_data")]
    d = _first_existing_dir(cands, probe)
    if d is None:
        d = _search_under(REPO_ROOT, probe)
    if d is None:
        raise FileNotFoundError(
            "未找到 CLCD 栅格（缺少 %s）。\n请设置环境变量 QILIAN_LC_DATA 指向含该文件的目录。"
            % probe)
    if verbose:
        src = "QILIAN_LC_DATA" if os.environ.get("QILIAN_LC_DATA") and \
            os.path.abspath(os.environ["QILIAN_LC_DATA"]) == d else "默认回退"
        print("[io_utils] CLCD 目录 = %s  (%s)" % (d, src))
    return d


def open_netcdf(path, engines=("netcdf4", "scipy", "h5netcdf", None)):
    """按引擎回退打开 NetCDF。

    中文路径下 netCDF4 C 库会 FileNotFoundError；CRU 为 NetCDF3，scipy 引擎可用。
    返回 (dataset, engine_name)。全部失败时抛 RuntimeError 并附各引擎的原始异常。
    """
    import xarray as xr

    errors = []
    for eng in engines:
        try:
            ds = xr.open_dataset(path) if eng is None else xr.open_dataset(path, engine=eng)
            return ds, (eng or "default")
        except Exception as exc:  # noqa: BLE001
            errors.append("%s -> %s: %s" % (eng or "default", type(exc).__name__, exc))
    raise RuntimeError(
        "无法打开 NetCDF 文件: %s\n各引擎尝试结果:\n  " % path + "\n  ".join(errors))


def cru_file(cru_dir, var, seg):
    """CRU 段文件路径。var ∈ {'pre','tmp'}；seg ∈ CRU_SEGMENTS。"""
    return os.path.join(cru_dir, "cru_ts4.10.%s.%s.dat.nc" % (seg, var))


def clcd_file(lc_dir, year):
    return os.path.join(lc_dir, "CLCD_v01_%d_albert.tif" % year)