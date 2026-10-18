# -*- coding: utf-8 -*-
"""Exact final figures for the report (boundary-aware numeric counts)."""
import re
import sys
import zipfile

import lxml.etree as ET

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
DOCX = r"D:\比赛\论文\交付\2.0版本\论文_EN_2.0版本_投稿用.docx"
root = ET.fromstring(zipfile.ZipFile(DOCX).read("word/document.xml"))
txt = "\n".join("".join(t.text or "" for t in p.iter("{%s}t" % W))
                for p in root.iter("{%s}p" % W))
mt = "".join(t.text or "" for t in root.iter("{%s}t" % M))
allt = txt + "\n" + mt


def exact(v):
    return len(re.findall(r"(?<![\d.])" + re.escape(v) + r"(?![\d])", allt))


print("boundary-exact numeric/token counts (text + math):")
for v in ["0.447", "0.225", "0.805", "0.39", "0.389", "0.390", "0.222",
          "0.448", "0.485", "0.380", "0.676", "0.478", "0.469", "0.368"]:
    print("   %-8s %d" % (v, exact(v)))
print("   %-8s %d" % ("In ESI", exact("In ESI")))
print("   %-8s %d" % ("Medium", exact("Medium")))
print("   %-8s %d" % ("Mild", exact("Mild")))
print()
print("degree glyphs: U+00B0 =", allt.count("\u00b0"),
      " U+2218(∘) =", allt.count("\u2218"))
print("en dash U+2013 =", allt.count("\u2013"), " em dash U+2014 =", allt.count("\u2014"))
print("minus sign U+2212 =", allt.count("\u2212"), " hyphen-minus =", allt.count("-"))
print()
tbls = list(root.iter("{%s}tbl" % W))
print("table census (cols x rows, header first cell):")
for i, t in enumerate(tbls, 1):
    rows = list(t.iter("{%s}tr" % W))
    nc = max(len(list(r.iter("{%s}tc" % W))) for r in rows)
    first = "".join(x.text or "" for x in rows[0].iter("{%s}t" % W))
    print("   T%-3d %d x %d  %s" % (i, nc, len(rows), first[:56]))
print()
caps = [t for t in txt.split("\n") if re.match(r"^(Table|Figure) ", t)]
print("caption labels:", len(caps))
print("display-equation numbers present:",
      [n for n in range(1, 8) if re.search(r"\(%d\)" % n, txt)])
print("drawing/anchor:", len(list(root.iter("{%s}drawing" % W))),
      "inline:", len(list(root.iter(
          "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}inline"))))
print("sections after References:",
      [t for t in txt.split("\n") if t.strip() in
       ("Data availability", "CRediT authorship contribution statement",
        "Declaration of competing interest", "Funding",
        "Declaration of generative AI and AI-assisted technologies in the writing process",
        "References")])