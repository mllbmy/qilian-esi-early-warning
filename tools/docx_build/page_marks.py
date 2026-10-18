# -*- coding: utf-8 -*-
"""Report which page holds which landmark, then rasterise the chosen pages."""
import os
import re
import sys

import pymupdf

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PDF = r"D:\比赛\论文\_r45_work\wb\submission_word.pdf"
OUT = r"D:\比赛\论文\_r45_work\wb\png2"
os.makedirs(OUT, exist_ok=True)
d = pymupdf.open(PDF)
print("pages:", d.page_count)
marks = {}
for i, page in enumerate(d, 1):
    t = page.get_text()
    tags = []
    for pat, name in [(r"Abstract", "abstract"), (r"Keywords:", "keywords"),
                      (r"Table 1:", "Tab1"), (r"Table 2:", "Tab2"),
                      (r"Table 10:", "Tab10"), (r"Table A\.14:", "TabA14"),
                      (r"Figure 1:", "Fig1"), (r"Figure 10:", "Fig10"),
                      (r"^References", "Refs"), (r"References\s*$", "RefsEnd"),
                      (r"Appendix A", "AppA"), (r"Photo|Acknowledg", "x")]:
        if re.search(pat, t, re.M):
            tags.append(name)
    if t.count("=") and re.search(r"\(1\)", t):
        tags.append("eqnum")
    marks[i] = tags
    print("  p%02d %s" % (i, ",".join(tags)))