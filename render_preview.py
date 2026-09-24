# -*- coding: utf-8 -*-
"""把英文 PDF 指定页渲染为 PNG，便于直接目检排版（R4 美化轮验证用）。
优先 pymupdf；缺失时回退 pdftoppm；再缺失则报告。"""
import os
import shutil
import subprocess
import sys

# 路径自解析：仓库克隆/解压到任意目录均可运行
BASE = os.path.dirname(os.path.abspath(__file__))
PDF = os.path.join(BASE, "manuscript.pdf")
OUT = os.path.join(BASE, "out", "preview")
PAGES = [int(a) for a in sys.argv[1:]] or [11, 12, 13, 14]

os.makedirs(OUT, exist_ok=True)

try:
    import fitz  # pymupdf
except ImportError:
    fitz = None

if fitz is not None:
    doc = fitz.open(PDF)
    print("pymupdf: %d 页" % doc.page_count)
    for p in PAGES:
        if p < 1 or p > doc.page_count:
            continue
        pix = doc[p - 1].get_pixmap(dpi=130)
        fp = os.path.join(OUT, "page%02d.png" % p)
        pix.save(fp)
        print("  saved", fp, pix.width, "x", pix.height)
else:
    exe = shutil.which("pdftoppm")
    if not exe:
        print("NO_RENDERER: 既无 pymupdf 也无 pdftoppm")
        raise SystemExit(2)
    for p in PAGES:
        subprocess.run([exe, "-r", "130", "-f", str(p), "-l", str(p), "-png",
                        PDF, os.path.join(OUT, "page%02d" % p)], check=False)
    print("pdftoppm 渲染完成 ->", OUT)