# -*- coding: utf-8 -*-
"""Inspect runs (size / vertAlign / text) of Table 10's alpha column."""
import sys
import zipfile

import lxml.etree as ET

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
DOCX = r"D:\比赛\论文\交付\2.0版本\论文_EN_2.0版本_投稿用.docx"
root = ET.fromstring(zipfile.ZipFile(DOCX).read("word/document.xml"))
tbls = list(root.iter("{%s}tbl" % W))
t = tbls[9]  # Table 10
for ri, tr in enumerate(list(t.iter("{%s}tr" % W))[:4]):
    print("--- row", ri)
    for ci, tc in enumerate(tr.iter("{%s}tc" % W)):
        for p in tc.iter("{%s}p" % W):
            for r in p.iter("{%s}r" % W):
                txt = "".join(x.text or "" for x in r.iter("{%s}t" % W))
                sz = r.find("{%s}rPr/{%s}sz" % (W, W))
                va = r.find("{%s}rPr/{%s}vertAlign" % (W, W))
                sub = r.find("{%s}rPr/{%s}position" % (W, W))
                if txt:
                    print("   c%d %-22r sz=%s vertAlign=%s pos=%s" % (
                        ci, txt, sz.get("{%s}val" % W) if sz is not None else "-",
                        va.get("{%s}val" % W) if va is not None else "-",
                        sub.get("{%s}val" % W) if sub is not None else "-"))
        # also math content
        for mt in tc.iter("{%s}t" % ("http://schemas.openxmlformats.org/officeDocument/2006/math")):
            print("   c%d [MATH] %r" % (ci, mt.text))