# -*- coding: utf-8 -*-
"""并发下载 Copernicus DEM 90m 祁连山瓦片(N36..N40, E093..E103, 共 55 块)"""
import os
import time
import urllib.request
import concurrent.futures

# 路径自解析：仓库克隆/解压到任意目录均可运行
BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "data", "cop90")
os.makedirs(OUT, exist_ok=True)

lats = list(range(36, 41))   # N36..N40
lons = list(range(93, 104))  # E093..E103
tiles = [(la, lo) for la in lats for lo in lons]

def make_url(la, lo):
    t = f"Copernicus_DSM_COG_30_N{la:02d}_00_E{lo:03d}_00_DEM"
    return f"https://copernicus-dem-90m.s3.amazonaws.com/{t}/{t}.tif"

def download(args):
    la, lo = args
    p = os.path.join(OUT, f"N{la:02d}_E{lo:03d}.tif")
    if os.path.exists(p) and os.path.getsize(p) > 3_000_000:
        return f"N{la}/E{lo} cached"
    u = make_url(la, lo)
    for _ in range(3):
        try:
            urllib.request.urlretrieve(u, p)
            if os.path.getsize(p) > 3_000_000:
                return f"N{la}/E{lo} ok"
        except Exception as e:
            time.sleep(1.5)
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass
    return f"N{la}/E{lo} FAIL"

t0 = time.time()
n = 0
with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
    for r in ex.map(download, tiles):
        n += 1
        if n % 5 == 0 or "FAIL" in r or "cached" in r:
            print(f"[{n}/{len(tiles)}] {time.time()-t0:.0f}s {r}", flush=True)

ok = sum(1 for la, lo in tiles
         if os.path.exists(os.path.join(OUT, f"N{la:02d}_E{lo:03d}.tif"))
         and os.path.getsize(os.path.join(OUT, f"N{la:02d}_E{lo:03d}.tif")) > 3_000_000)
print(f"DONE {ok}/{len(tiles)} tiles in {time.time()-t0:.0f}s")