# -*- coding: utf-8 -*-
import io
import re
import sys

sys.path.insert(0, r"D:\比赛\论文\_r45_work\wb")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import docxbuild_lib as L

tex = L.strip_comments(L.read(L.TEX))
body = tex[tex.find("\\end{frontmatter}"):].split("\\end{document}")[0]
blocks = list(re.finditer(r"\\begin\{table\}.*?\\end\{table\}", body, re.S))
blk = blocks[10].group(0)
print(blk[:2500])
print("\n---- parsed rows ----")
j = blk.find("\\begin{tabular}")
k = j + len("\\begin{tabular}")
spec, bs = L.find_group(blk, k)
end = blk.find("\\end{tabular}")
rows, ncol = L.parse_tabular(spec, blk[bs:end])
for cells, rules in rows:
    span = 0
    for c in cells:
        mm = re.match(r"\\multicolumn\{(\d+)\}", c.strip())
        span += int(mm.group(1)) if mm else 1
    print("  span=%d ncell=%d rules=%s cells=%s" % (span, len(cells), [r[0] for r in rules],
                                                    [c[:40] for c in cells]))