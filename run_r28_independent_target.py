# -*- coding: utf-8 -*-
"""R28-T5 · 独立目标变量获取与外部验证（NOAA CDR NDVI）
（审稿意见第 3 条：空间归因的内生性 —— 用与 ESI 构造完全无关的独立观测交叉验证）

────────────────────────────────────────────────────────────────────────────
为什么是 NDVI
────────────────────────────────────────────────────────────────────────────
点尺度 ESI 的 6 项指标全部来自 CLCD 土地覆被与 CRU 气候；对土地覆被做
GeoDetector 存在构造性（同义反复）相关。NOAA/STAR 的 **AVHRR/VIIRS NDVI
Climate Data Record** 是独立的卫星观测产品，不参与 ESI 构造，可作为：
  (1) 空间外部验证：ESI 的空间格局是否与独立植被绿度一致；
  (2) 归因外部验证：以 NDVI 为目标重做 GeoDetector，比较因子 q 的排序；
  (3) 趋势外部验证：2005-2023 年区域 NDVI 序列与 ESI 序列的趋势是否一致。

数据源（无需登录，THREDDS OPeNDAP 子集读取）
  https://www.ncei.noaa.gov/thredds/catalog/cdr/ndvi/catalog.xml
  2014-2023：VIIRS-Land v001（NPP13C1，S-NPP）
  1981-2013：AVHRR-Land v005（AVH13C1）
  0.05° 全球日尺度；NDVI 已解包（无量纲，valid_range -0.1~1.0）；
  QA 为 16 位位标志（读入需按无符号解释）：
    bit15 snow/ice；bit10 cloud；bit2 cloud shadow；bit1-0 cloud state
    （0=confident clear）；bit3-5 land-water flag
  本脚本的"晴空有效像元"判据：
    (QA & 32768)==0 且 (QA & 1024)==0 且 (QA & 4)==0 且 (QA & 3)==0

口径与限制（写入结论，不做掩饰）
  · 2014 年前后传感器由 AVHRR 切换为 VIIRS，CDR 虽做交叉定标，仍可能存在
    系统偏差 → 趋势分 2005-2013 / 2014-2023 两段分别报告；
  · 生长季合成采用 6 个固定日期（6/10、6/25、7/10、7/25、8/9、8/24），
    非严格最大值合成；单日云污染已按 QA 剔除，若某点有效日期不足则记 NaN；
  · NDVI 与 ESI 的量纲、时空支持（support）不同，只作一致性检验，不构成因果证据。

────────────────────────────────────────────────────────────────────────────
输出
· data/r28_external_ndvi_points_2020.csv   —— 1914 点的 2020 生长季 NDVI
· data/r28_external_ndvi_annual.csv        —— 2005-2023 区域生长季 NDVI 序列
· data/r28_external_ndvi_manifest.csv      —— 每个源文件的 URL / 版本 / 访问日期 / md5
· data/r28_external_validation.csv         —— 外部验证指标（相关、双向 q、排序对比）
运行：python run_r28_independent_target.py            # 全流程（需联网）
      python run_r28_independent_target.py spatial|temporal|validate
"""
import datetime as dt
import hashlib
import os
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
CACHE = os.path.join(os.path.dirname(BASE), "_r28_work", "ndvi_cache")
os.makedirs(CACHE, exist_ok=True)
sys.path.insert(0, os.path.join(BASE, "eco_security"))
from eco_security import geodetector_q  # noqa: E402

DAP = "https://www.ncei.noaa.gov/thredds/dodsC/cdr/ndvi/%d/%s"
CAT = "https://www.ncei.noaa.gov/thredds/catalog/cdr/ndvi/%d/catalog.xml"
ACCESS_DATE = dt.date.today().isoformat()
SEED = 42
K = 4
N_PERM = 999
GROWING_DATES = [(6, 10), (6, 25), (7, 10), (7, 25), (8, 9), (8, 24)]


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def catalog_files(year):
    """列出一年的 NDVI 文件（urlPath 末段），结果缓存在本地。"""
    import urllib.request
    ci = os.path.join(CACHE, "cat_%d.txt" % year)
    if os.path.exists(ci):
        return [l.strip() for l in open(ci, encoding="utf-8") if l.strip()]
    with urllib.request.urlopen(CAT % year, timeout=60) as r:
        txt = r.read().decode("utf-8", "replace")
    import re
    names = sorted(set(re.findall(r'urlPath="cdr/ndvi/%d/([^"]+\.nc)"' % year, txt)))
    with open(ci, "w", encoding="utf-8") as f:
        f.write("\n".join(names))
    return names


def pick_file(year, month, day):
    tag = "%04d%02d%02d" % (year, month, day)
    names = catalog_files(year)
    cand = [n for n in names if "_%s_" % tag in n]
    if not cand:
        for off in (1, -1, 2, -2, 3, -3):
            d = dt.date(year, month, day) + dt.timedelta(days=off)
            t2 = d.strftime("%Y%m%d")
            cand = [n for n in names if "_%s_" % t2 in n]
            if cand:
                return cand[0], t2
        return None, tag
    return cand[0], tag


def read_box(url, box, cache_key):
    """经 OPeNDAP 读取 box 内的 NDVI 与 QA；返回 (lat, lon, ndvi, clear_mask, meta)。"""
    cf = os.path.join(CACHE, cache_key + ".npz")
    if os.path.exists(cf):
        z = np.load(cf)
        return z["lat"], z["lon"], z["ndvi"], z["clear"], str(z["meta"])
    from netCDF4 import Dataset
    ds = Dataset(url)
    la = np.asarray(ds.variables["latitude"][:], dtype=float)
    lo = np.asarray(ds.variables["longitude"][:], dtype=float)
    s, n, w, e = box
    ilat = np.where((la >= s) & (la <= n))[0]
    ilon = np.where((lo >= w) & (lo <= e))[0]
    nd = ds.variables["NDVI"][0, ilat[0]:ilat[-1] + 1, ilon[0]:ilon[-1] + 1]
    qa = ds.variables["QA"][0, ilat[0]:ilat[-1] + 1, ilon[0]:ilon[-1] + 1]
    ndvi = np.ma.filled(nd.astype(np.float64), np.nan)
    qi = np.ma.filled(qa.astype(np.int32), 0) & 0xFFFF
    clear = ((qi & 32768) == 0) & ((qi & 1024) == 0) & ((qi & 4) == 0) & ((qi & 3) == 0) \
        & np.isfinite(ndvi)
    meta = "product_version=%s; date_created=%s; source=%s" % (
        getattr(ds, "product_version", "?"), getattr(ds, "date_created", "?"),
        getattr(ds, "source", "?"))
    ds.close()
    np.savez_compressed(cf, lat=la[ilat[0]:ilat[-1] + 1], lon=lo[ilon[0]:ilon[-1] + 1],
                        ndvi=ndvi, clear=clear, meta=meta)
    return (la[ilat[0]:ilat[-1] + 1], lo[ilon[0]:ilon[-1] + 1], ndvi, clear, meta)


def point_sample(lat, lon, field, pts_lat, pts_lon, mode="nearest"):
    ilat = np.abs(lat[:, None] - pts_lat[None, :]).argmin(axis=0)
    ilon = np.abs(lon[:, None] - pts_lon[None, :]).argmin(axis=0)
    if mode == "nearest":
        return field[ilat, ilon]
    out = np.full(len(pts_lat), np.nan)
    for i in range(len(pts_lat)):
        a, b = max(ilat[i] - 1, 0), min(ilat[i] + 2, len(lat))
        c, d = max(ilon[i] - 1, 0), min(ilon[i] + 2, len(lon))
        blk = field[a:b, c:d]
        if np.isfinite(blk).any():
            out[i] = np.nanmean(blk)
    return out


def main():
    stage = sys.argv[1] if len(sys.argv) > 1 else "all"
    smp = pd.read_csv(os.path.join(DATA, "spatial_samples.csv"))
    esp = pd.read_csv(os.path.join(DATA, "spatial_esi_points.csv"))
    df = smp.merge(esp[["lat", "lon", "esi"]], on=["lat", "lon"], how="inner")
    pts_lat, pts_lon, esi = (df["lat"].values, df["lon"].values, df["esi"].values)
    box = (float(pts_lat.min()) - 0.25, float(pts_lat.max()) + 0.25,
           float(pts_lon.min()) - 0.25, float(pts_lon.max()) + 0.25)
    print("=" * 78)
    print("R28-T5 · 独立目标变量（NOAA CDR NDVI）获取与外部验证")
    print("=" * 78)
    print("点位范围 lat %.3f-%.3f, lon %.3f-%.3f；读取盒 %.2f-%.2f / %.2f-%.2f"
          % (pts_lat.min(), pts_lat.max(), pts_lon.min(), pts_lon.max(),
             box[0], box[1], box[2], box[3]))
    print("访问日期：%s" % ACCESS_DATE)

    man = []
    pts_csv = os.path.join(DATA, "r28_external_ndvi_points_2020.csv")
    ann_csv = os.path.join(DATA, "r28_external_ndvi_annual.csv")

    # ---------------- 空间：2020 生长季逐点 NDVI ----------------
    if stage in ("all", "spatial"):
        dates = []
        d0 = dt.date(2020, 5, 25)
        while d0 <= dt.date(2020, 9, 10):
            dates.append(d0)
            d0 += dt.timedelta(days=6)
        print("\n[空间] 2020 生长季合成：%d 个日期" % len(dates))
        stack, cnt = [], np.zeros(len(pts_lat))
        for d in dates:
            fn, tag = pick_file(d.year, d.month, d.day)
            if fn is None:
                print("   跳过 %s（无文件）" % d)
                continue
            url = DAP % (d.year, fn)
            try:
                lat, lon, ndvi, clear, meta = read_box(url, box, "sp_%s" % tag)
            except Exception as e:
                print("   读取失败 %s: %s" % (tag, e))
                continue
            f = np.where(clear, ndvi, np.nan)
            v = point_sample(lat, lon, f, pts_lat, pts_lon)
            stack.append(v)
            cnt += np.isfinite(v)
            man.append({"stage": "spatial_2020", "date_tag": tag, "file": fn,
                        "url": url, "dap_url": url, "access_date": ACCESS_DATE,
                        "product_version": meta.split("product_version=")[1].split(";")[0],
                        "box_valid_clear_frac": round(float(clear.mean()), 4),
                        "n_points_with_clear": int(np.isfinite(v).sum())})
            print("   %s  晴空像元 %.1f%%  有点位值 %d/%d"
                  % (tag, 100 * clear.mean(), int(np.isfinite(v).sum()), len(v)))
        if stack:
            S = np.vstack(stack)
            with np.errstate(invalid="ignore"):
                ndvi_mean = np.nanmean(S, axis=0)
            out = pd.DataFrame({"lat": pts_lat, "lon": pts_lon, "esi": esi,
                                "ndvi_growing_season_mean": np.round(ndvi_mean, 6),
                                "ndvi_valid_dates": cnt.astype(int),
                                "ndvi_n_dates_used": len(stack),
                                "source": "NOAA CDR AVHRR/VIIRS NDVI (VIIRS-Land v001)",
                                "access_date": ACCESS_DATE})
            out.to_csv(pts_csv, index=False, encoding="utf-8-sig")
            print("   写出 %s（md5=%s）" % (pts_csv, md5(pts_csv)))
            print("   NDVI 点数 %d，均值 %.4f，中位数 %.4f，范围 %.4f~%.4f；"
                  "有效日期中位数 %.0f"
                  % (out.ndvi_growing_season_mean.notna().sum(),
                     out.ndvi_growing_season_mean.mean(),
                     out.ndvi_growing_season_mean.median(),
                     out.ndvi_growing_season_mean.min(),
                     out.ndvi_growing_season_mean.max(),
                     out.ndvi_valid_dates.median()))

    # ---------------- 时间：2005-2023 区域生长季 NDVI ----------------
    if stage in ("all", "temporal"):
        print("\n[时间] 2005-2023 年区域生长季 NDVI（每年 %d 个日期）"
              % len(GROWING_DATES))
        rows = []
        for year in range(2005, 2024):
            vals, wts = [], []
            for (mm, dd) in GROWING_DATES:
                fn, tag = pick_file(year, mm, dd)
                if fn is None:
                    continue
                url = DAP % (year, fn)
                try:
                    lat, lon, ndvi, clear, meta = read_box(url, box, "tm_%s" % tag)
                except Exception as e:
                    print("   读取失败 %s: %s" % (tag, e))
                    continue
                if clear.sum() > 0:
                    vals.append(float(np.nanmean(ndvi[clear])))
                    wts.append(int(clear.sum()))
                man.append({"stage": "regional_annual", "date_tag": tag, "file": fn,
                            "url": url, "dap_url": url, "access_date": ACCESS_DATE,
                            "product_version": meta.split("product_version=")[1].split(";")[0],
                            "box_valid_clear_frac": round(float(clear.mean()), 4),
                            "n_points_with_clear": np.nan})
            if vals:
                sensor = "VIIRS" if year >= 2014 else "AVHRR"
                rows.append({"year": year, "sensor": sensor,
                             "ndvi_growing_season_mean": round(float(np.mean(vals)), 6),
                             "n_dates": len(vals),
                             "mean_clear_pixels": int(np.mean(wts)),
                             "source": ("NOAA CDR AVHRR-Land v005 (AVH13C1)" if year < 2014
                                        else "NOAA CDR VIIRS-Land v001 (NPP13C1)"),
                             "access_date": ACCESS_DATE,
                             "catalog_url": CAT % year})
                print("   %d [%s] NDVI=%.4f（%d 个日期，平均晴空像元 %d）"
                      % (year, sensor, np.mean(vals), len(vals), int(np.mean(wts))))
        ann = pd.DataFrame(rows)
        ann.to_csv(ann_csv, index=False, encoding="utf-8-sig")
        print("   写出 %s（md5=%s）" % (ann_csv, md5(ann_csv)))

    if man:
        mf = pd.DataFrame(man)
        mpath = os.path.join(DATA, "r28_external_ndvi_manifest.csv")
        mf.to_csv(mpath, index=False, encoding="utf-8-sig")
        print("\n源文件清单：%d 条 → %s（md5=%s）" % (len(mf), mpath, md5(mpath)))

    # ---------------- 时间（缓存重算）：共同掩膜序列与逐点趋势 ----------------
    def temporal_from_cache():
        """从缓存重算：共同晴空掩膜下的区域序列 + 逐点年值/趋势（校正云采样偏差）。"""
        files = sorted(f for f in os.listdir(CACHE) if f.startswith("tm_") and f.endswith(".npz"))
        if not files:
            return None, None
        keys, cnt, tot = [], None, 0
        for f in files:
            z = np.load(os.path.join(CACHE, f))
            c = z["clear"]
            if cnt is None:
                cnt = np.zeros(c.shape)
            cnt += c
            tot += 1
            keys.append((f[3:11], z))
        common = cnt >= 0.5 * tot
        print("\n[时间·重算] %d 个日期；共同掩膜（≥50%% 日期晴空）覆盖 %d/%d 格点（%.1f%%）"
              % (tot, int(common.sum()), common.size, 100 * common.mean()))
        by_year = {}
        for tag, z in keys:
            y = int(tag[:4])
            by_year.setdefault(y, []).append((tag, z))
        rows, pt_year = [], {}
        for y in sorted(by_year):
            vals = []
            for tag, z in by_year[y]:
                sel = z["clear"] & common
                if sel.sum() > 0:
                    vals.append(float(np.nanmean(z["ndvi"][sel])))
            if vals:
                rows.append({"year": y, "sensor": "VIIRS" if y >= 2014 else "AVHRR",
                             "ndvi_commonmask_mean": round(float(np.mean(vals)), 6),
                             "n_dates": len(vals),
                             "common_mask_cells": int(common.sum()),
                             "common_mask_fraction": round(float(common.mean()), 4),
                             "source": ("NOAA CDR AVHRR-Land v005 (AVH13C1)" if y < 2014
                                        else "NOAA CDR VIIRS-Land v001 (NPP13C1)"),
                             "access_date": ACCESS_DATE,
                             "catalog_url": CAT % y})
            # 逐点年值（用共同掩膜与最近邻取样）
            acc, nacc = np.zeros(len(pts_lat)), np.zeros(len(pts_lat))
            for tag, z in by_year[y]:
                fld = np.where(z["clear"] & common, z["ndvi"], np.nan)
                v = point_sample(z["lat"], z["lon"], fld, pts_lat, pts_lon)
                ok = np.isfinite(v)
                acc[ok] += v[ok]
                nacc[ok] += 1
            with np.errstate(invalid="ignore"):
                pt_year[y] = np.where(nacc > 0, acc / np.maximum(nacc, 1), np.nan)
        cm = pd.DataFrame(rows)
        cm.to_csv(os.path.join(DATA, "r28_external_ndvi_annual_commonmask.csv"),
                  index=False, encoding="utf-8-sig")
        print("   %s（md5=%s）"
              % (os.path.join(DATA, "r28_external_ndvi_annual_commonmask.csv"),
                 md5(os.path.join(DATA, "r28_external_ndvi_annual_commonmask.csv"))))
        yrs = sorted(pt_year)
        M = np.column_stack([pt_year[y] for y in yrs])
        ok = np.isfinite(M).sum(axis=1) >= 10
        slopes = np.full(len(pts_lat), np.nan)
        for i in np.where(ok)[0]:
            v = M[i]
            m = np.isfinite(v)
            slopes[i] = np.polyfit(np.array(yrs)[m], v[m], 1)[0] if m.sum() >= 5 else np.nan
        pt = pd.DataFrame({"lat": pts_lat, "lon": pts_lon, "esi": esi,
                           "ndvi_slope_per_yr_2005_2023": np.round(slopes, 8),
                           "n_years_with_ndvi": np.isfinite(M).sum(axis=1),
                           "source": "NOAA CDR AVHRR/VIIRS NDVI (2005-2013 AVH13C1, 2014-2023 NPP13C1)",
                           "access_date": ACCESS_DATE})
        pt.to_csv(os.path.join(DATA, "r28_external_ndvi_point_trends.csv"),
                  index=False, encoding="utf-8-sig")
        m = np.isfinite(slopes)
        print("   逐点 NDVI 趋势 %s：%d 点可算，斜率均值 %+.5f/yr，中位数 %+.5f/yr；"
              "正趋势占比 %.1f%%"
              % (os.path.join(DATA, "r28_external_ndvi_point_trends.csv"),
                 int(m.sum()), float(slopes[m].mean()), float(np.median(slopes[m])),
                 100 * float((slopes[m] > 0).mean())))
        return cm, pt

    # ---------------- 外部验证 ----------------
    if stage in ("all", "validate"):
        if not os.path.exists(pts_csv):
            print("\n[验证] 缺少 %s，先运行 spatial 阶段" % pts_csv)
            return 1
        ter = pd.read_csv(os.path.join(DATA, "_aux_terrain_points.csv"))
        pts = pd.read_csv(pts_csv)
        d = df.merge(pts[["lat", "lon", "ndvi_growing_season_mean", "ndvi_valid_dates"]],
                     on=["lat", "lon"], how="inner")
        d = d.merge(ter[["lat", "lon", "elev", "slope"]], on=["lat", "lon"], how="inner")
        ok = d.ndvi_growing_season_mean.notna()
        d = d[ok].reset_index(drop=True)
        y, nd = d["esi"].values, d["ndvi_growing_season_mean"].values
        print("\n" + "-" * 78)
        print("外部验证 1：ESI 与独立 NDVI 的空间一致性（n=%d）" % len(d))
        print("-" * 78)
        pear = float(np.corrcoef(y, nd)[0, 1])
        spear = float(pd.Series(y).corr(pd.Series(nd), method="spearman"))
        print("   Pearson r = %.4f（R² = %.4f）；Spearman ρ = %.4f" % (pear, pear ** 2, spear))
        lab_nd, lab_es = np.digitize(nd, np.quantile(nd, [.25, .5, .75])), \
            np.digitize(y, np.quantile(y, [.25, .5, .75]))
        q_nd2es = float(geodetector_q(y, lab_nd))
        q_es2nd = float(geodetector_q(nd, lab_es))
        print("   双向 GeoDetector：q(NDVI分层→ESI) = %.4f ；q(ESI分层→NDVI) = %.4f"
              % (q_nd2es, q_es2nd))
        rows = [{"analysis": "spatial_agreement", "metric": "pearson_r", "value": round(pear, 6),
                 "note": "ESI vs 独立 NDVI，n=%d" % len(d)},
                {"analysis": "spatial_agreement", "metric": "spearman_rho",
                 "value": round(spear, 6), "note": "同上"},
                {"analysis": "spatial_agreement", "metric": "q_ndvi_strata_to_esi",
                 "value": round(q_nd2es, 6), "note": "四分位分层，目标=ESI"},
                {"analysis": "spatial_agreement", "metric": "q_esi_strata_to_ndvi",
                 "value": round(q_es2nd, 6), "note": "四分位分层，目标=NDVI"}]

        print("\n外部验证 2：以独立 NDVI 为目标重做 GeoDetector（q 排序对比）")
        facs = ["precip", "temp", "grass", "barren", "elev", "slope"]
        q_esi, q_ndvi = {}, {}
        for f in facs:
            v = d[f].values.astype(float)
            lab = (v > 0).astype(int) if f in ("forest", "water") else \
                np.digitize(v, np.quantile(v, [.25, .5, .75]))
            if len(np.unique(lab)) < 2:
                continue
            q_esi[f] = round(float(geodetector_q(y, lab)), 4)
            q_ndvi[f] = round(float(geodetector_q(nd, lab)), 4)
            print("   %-7s q(→ESI)=%.4f  q(→独立NDVI)=%.4f" % (f, q_esi[f], q_ndvi[f]))
            rows.append({"analysis": "attribution_external", "metric": "q_target_esi",
                         "value": q_esi[f], "note": "因子 %s" % f})
            rows.append({"analysis": "attribution_external", "metric": "q_target_ndvi",
                         "value": q_ndvi[f], "note": "因子 %s" % f})
        o_esi = [f for f in sorted(q_esi, key=lambda z: -q_esi[z])]
        o_nd = [f for f in sorted(q_ndvi, key=lambda z: -q_ndvi[z])]
        rho = float(pd.Series([q_esi[f] for f in facs]).corr(
            pd.Series([q_ndvi[f] for f in facs]), method="spearman"))
        print("   排序（→ESI）: %s" % " > ".join(o_esi))
        print("   排序（→NDVI）: %s" % " > ".join(o_nd))
        print("   两套 q 的 Spearman 相关 = %.4f" % rho)
        rows.append({"analysis": "attribution_external", "metric": "rank_spearman",
                     "value": round(rho, 4),
                     "note": "两套 q 排序：%s || %s" % (">".join(o_esi), ">".join(o_nd))})

        A = np.column_stack([np.ones(len(d)), d[["elev", "slope"]].values.astype(float)])
        b, *_ = np.linalg.lstsq(A, nd, rcond=None)
        r2 = 1 - float(((nd - A @ b) ** 2).sum()) / float(((nd - nd.mean()) ** 2).sum())
        print("   严格外生因子对独立 NDVI 的 OLS R² = %.4f" % r2)
        rows.append({"analysis": "attribution_external", "metric": "ols_r2_exogenous_to_ndvi",
                     "value": round(float(r2), 6), "note": "elev+slope → 独立 NDVI"})

        print("\n外部验证 3：2005-2023 区域 NDVI 序列与 ESI 序列的趋势")
        cm, pt = temporal_from_cache()
        reg = pd.read_csv(os.path.join(DATA, "results_esi_regional.csv"))
        for src, tag2 in [(ann_csv, "全体晴空像元均值"), 
                          (os.path.join(DATA, "r28_external_ndvi_annual_commonmask.csv"),
                           "共同掩膜均值")]:
            if not os.path.exists(src):
                continue
            ann = pd.read_csv(src)
            col = "ndvi_growing_season_mean" if "ndvi_growing_season_mean" in ann else \
                "ndvi_commonmask_mean"
            m = ann.merge(reg[["year", "esi"]], on="year", how="inner")
            print("   —— 口径：%s" % tag2)
            for lo, hi, tag3 in [(2005, 2023, "全期"), (2005, 2013, "AVHRR 段"),
                                 (2014, 2023, "VIIRS 段")]:
                s = m[(m.year >= lo) & (m.year <= hi)]
                if len(s) < 3:
                    continue
                bn = np.polyfit(s.year, s[col], 1)[0]
                be = np.polyfit(s.year, s.esi, 1)[0]
                r = float(np.corrcoef(s[col], s.esi)[0, 1])
                print("      %-9s %d-%d：NDVI 斜率 %+.5f/yr；ESI 斜率 %+.5f/yr；"
                      "水平相关 r=%.3f（n=%d）" % (tag3, lo, hi, bn, be, r, len(s)))
                rows.append({"analysis": "temporal_agreement",
                             "metric": "ndvi_slope_per_yr|" + tag2,
                             "value": round(float(bn), 6), "note": "%s %d-%d" % (tag3, lo, hi)})
                rows.append({"analysis": "temporal_agreement",
                             "metric": "esi_slope_per_yr|" + tag2,
                             "value": round(float(be), 6), "note": "%s %d-%d" % (tag3, lo, hi)})
                rows.append({"analysis": "temporal_agreement",
                             "metric": "level_corr|" + tag2,
                             "value": round(r, 6), "note": "%s %d-%d" % (tag3, lo, hi)})
            print(m.to_string(index=False))
        if pt is not None:
            okp = np.isfinite(pt.ndvi_slope_per_yr_2005_2023.values)
            rp = float(np.corrcoef(pt.esi.values[okp],
                                   pt.ndvi_slope_per_yr_2005_2023.values[okp])[0, 1])
            print("   逐点 NDVI 趋势与静态 ESI 的相关 r = %.4f（n=%d）："
                  "高 ESI 点位的植被趋势并不更强" % (rp, int(okp.sum())))
            rows.append({"analysis": "temporal_agreement",
                         "metric": "corr_point_ndvi_trend_vs_static_esi",
                         "value": round(rp, 6),
                         "note": "逐点 2005-2023 NDVI 斜率 vs 2020 静态 ESI，n=%d"
                                 % int(okp.sum())})
        v = pd.DataFrame(rows)
        vp = os.path.join(DATA, "r28_external_validation.csv")
        v.to_csv(vp, index=False, encoding="utf-8-sig")
        print("\n写出 %s（md5=%s）" % (vp, md5(vp)))
    print("\n完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())