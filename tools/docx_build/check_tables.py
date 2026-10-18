# -*- coding: utf-8 -*-
"""Print every tabular column spec, the parsed column count, and each row's span sum."""
import io
import re
import sys

sys.path.insert(0, r"D:\比赛\论文\_r45_work\wb")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import docxbuild_lib as L

tex = L.strip_comments(L.read(L.TEX))
body = tex[tex.find("\\end{frontmatter}"):].split("\\end{document}")[0]
for i, m in enumerate(re.finditer(r"\\begin\{table\}.*?\\end\{table\}", body, re.S), 1):
    blk = m.group(0)
    lab = L._label_of(blk)
    j = blk.find("\\begin{tabular}")
    k = j + len("\\begin{tabular}")
    spec = ""
    if k < len(blk) and blk[k] == "{":
        spec, bs = L.find_group(blk, k)
    else:
        bs = k
    end = blk.find("\\end{tabular}")
    tbody = blk[bs:end]
    cols = L.parse_colspec(spec)
    rows, ncol = L.parse_tabular(spec, tbody)
    spans = []
    for cells, rules in rows:
        s = 0
        for c in cells:
            mm = re.match(r"\\multicolumn\{(\d+)\}", c.strip())
            s += int(mm.group(1)) if mm else 1
        spans.append(s)
    print("table %2d %-22s spec=%-30r ncol=%d colspec=%d rows=%d span_sums=%s rules=%s"
          % (i, lab, spec, ncol, len(cols), len(rows), sorted(set(spans)),
             [r[0] for r in rows[0][1]] if rows else []))