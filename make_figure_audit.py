
# -*- coding: utf-8 -*-
"""make_figure_audit.py —— 生成 figures/JMS_figure_audit.tsv —— 用 pymupdf 逐 span 实测（不靠 fontsize 参数推断）。

判定（JMS 指南 §5.7 / §6）：
  画布宽 16.00 ± 0.02 cm；含字母/数字/digit/Greek 的 span 字号 ∈ [8.0, 9.0] pt；
  全部 span 的字体名含 "Times"（不允许 STIX/Arial/DejaVu 回退）。
"""
import os
import re
import sys

import pymupdf

BASE = os.path.dirname(os.path.abspath(__file__))   # paper-code/
FIGS = [
    (1,  "fig1_study_area.pdf"),
    (2,  "fig_dpsir_framework.pdf"),
    (3,  "fig_indicator_trends.pdf"),
    (4,  "fig3_esi_timeseries.pdf"),
    (5,  "fig_weights.pdf"),
    (6,  "fig4_alpha_sensitivity.pdf"),
    (7,  "fig_spatial_maps.pdf"),
    (8,  "fig_geodetector_q.pdf"),
    (9,  "fig_interaction.pdf"),
    (10, "fig_obstacle.pdf"),
]
WORD = re.compile(r"[0-9A-Za-z\u0370-\u03ff]")
rows = []
fails = 0
for num, fn in FIGS:
    p = os.path.join(BASE, "figures", fn)
    doc = pymupdf.open(p)
    pg = doc[0]
    w_cm = pg.rect.width / 72 * 2.54
    sizes, fonts = [], set()
    for b in pg.get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            for s in ln.get("spans", []):
                t = s["text"].strip()
                if not t or not WORD.search(t):
                    continue
                sizes.append(s["size"])
                fonts.add(s["font"])
    doc.close()
    mn = min(sizes) if sizes else 0.0
    mx = max(sizes) if sizes else 0.0
    fstr = ";".join(sorted(fonts))
    ok_w = abs(w_cm - 16.0) <= 0.02
    ok_s = bool(sizes) and mn >= 8.0 - 1e-6 and mx <= 9.0 + 1e-6
    ok_f = all("Times" in f for f in fonts)
    verdict = "PASS" if (ok_w and ok_s and ok_f) else "FAIL"
    if verdict == "FAIL":
        fails += 1
    rows.append((fn, "%.2f" % w_cm, "%.2f" % mn, "%.2f" % mx, fstr,
                 "%.2f" % (os.path.getsize(p) / 1048576.0), verdict))

out = os.path.join(BASE, "figures", "JMS_figure_audit.tsv")
with open(out, "w", encoding="utf-8", newline="\n") as f:
    f.write("file\tcanvas_cm\tmin_pt\tmax_pt\tfonts\tsize_mb\tverdict\n")
    for r in rows:
        f.write("\t".join(r) + "\n")
print(open(out, encoding="utf-8").read())
print("FAIL:", fails)
sys.exit(1 if fails else 0)