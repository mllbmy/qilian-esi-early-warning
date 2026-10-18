# -*- coding: utf-8 -*-
"""Rasterise PDF pages to PNG for visual inspection.
Usage: python pdf2png.py <pdf> <outdir> [zoom] [pages...]"""
import os
import sys

import pymupdf

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
pdf, outdir = sys.argv[1], sys.argv[2]
zoom = float(sys.argv[3]) if len(sys.argv) > 3 else 2.0
want = [int(x) for x in sys.argv[4:]] if len(sys.argv) > 4 else None
os.makedirs(outdir, exist_ok=True)
d = pymupdf.open(pdf)
print("pages:", d.page_count)
for i, page in enumerate(d, 1):
    if want and i not in want:
        continue
    pm = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
    out = os.path.join(outdir, "p%02d.png" % i)
    pm.save(out)
    print("  wrote", out, pm.width, "x", pm.height)