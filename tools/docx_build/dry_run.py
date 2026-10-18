# -*- coding: utf-8 -*-
"""Dry run: build to a scratch path so the deliverable is never written by a test."""
import os
import sys

sys.path.insert(0, r"D:\比赛\论文\_r45_work\wb")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import docxbuild_lib as L

L.OUT = os.path.join(L.WORK, "_test_out.docx")
import build_docx as B

B.L.OUT = L.OUT
doc, biblio, numbering = B.build()
print("saved:", L.OUT, os.path.getsize(L.OUT), "bytes")
print("figures:", len(B.STATS["figures"]), "tables:", len(B.STATS["tables"]),
      "equations:", len(B.STATS["equations"]))
print("missing images:", B.STATS["images_missing"])
print("warnings:", B.STATS["warnings"][:25], "(%d)" % len(B.STATS["warnings"]))
print("unmapped commands:", B.STATS["unmapped_cmd"])
print("bib entries:", len(biblio.entries))
for t in B.STATS["tables"]:
    print("  table %2d cols=%d rows=%d hdr=%d widths=%s" %
          (t["n"], t["cols"], t["rows"], t["header_rows"], t["widths"]))
for f in B.STATS["figures"]:
    print("  fig %2d %s -> %s %.2fx%.2f cm" % (f["n"], f["file"], f["png"], f["w_cm"], f["h_cm"]))