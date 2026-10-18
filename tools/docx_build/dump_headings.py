# -*- coding: utf-8 -*-
"""Dump the numbered section headings (by run size) from the built docx."""
import re
import sys
import zipfile

import lxml.etree as ET

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
DOCX = sys.argv[1] if len(sys.argv) > 1 else \
    r"D:\比赛\论文\交付\2.0版本\论文_EN_2.0版本_投稿用.docx"
root = ET.fromstring(zipfile.ZipFile(DOCX).read("word/document.xml"))
n = 0
for p in root.iter("{%s}p" % W):
    txt = "".join(t.text or "" for t in p.iter("{%s}t" % W))
    sizes = set()
    for r in p.iter("{%s}r" % W):
        sz = r.find("{%s}rPr/{%s}sz" % (W, W))
        if sz is not None:
            sizes.add(int(sz.get("{%s}val" % W)) / 2.0)
    if not txt.strip():
        continue
    if sizes and max(sizes) >= 11 and len(txt) < 95:
        n += 1
        print("%5.1fpt  %s" % (max(sizes), txt.strip()))
print("--- total sized headings:", n)