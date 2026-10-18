# -*- coding: utf-8 -*-
"""Locate residue contexts in the built docx."""
import re
import sys
import zipfile

import lxml.etree as ET

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
DOCX = r"D:\比赛\论文\交付\2.0版本\论文_EN_2.0版本_投稿用.docx"
z = zipfile.ZipFile(DOCX)
root = ET.fromstring(z.read("word/document.xml"))
paras = []
for p in root.iter("{%s}p" % W_NS):
    paras.append("".join(t.text or "" for t in p.iter("{%s}t" % W_NS)))
for target in ["$", "[Author]", "[email]", "[Affiliation]", "[ORCID]", "\\"]:
    print("=== %r ===" % target)
    n = 0
    for t in paras:
        if target in t:
            n += 1
            print("   ...%s..." % t.strip()[:180])
    print("   paragraphs with it:", n)