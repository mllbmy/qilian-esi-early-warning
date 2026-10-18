# -*- coding: utf-8 -*-
"""Dump the 5 display equations and the digit-mismatch detail."""
import collections
import io
import re
import sys

sys.path.insert(0, r"D:\比赛\论文\_r45_work\wb")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import omml

s = io.open(r"D:\比赛\论文\paper-code\manuscript.tex", encoding="utf-8").read()
s = re.sub(r"(?<!\\)%.*", "", s)
body = s.split(r"\begin{document}", 1)[1].split(r"\end{document}")[0]
disp = re.findall(r"\\begin\{equation\}(.*?)\\end\{equation\}", body, re.S)
inline = re.findall(r"(?<!\$)\$(?!\$)((?:\\.|[^$\\])+)\$(?!\$)", body)

print("=== DISPLAY EQUATIONS ===")
for k, d in enumerate(disp, 1):
    d = " ".join(d.split())
    print("--- eq %d ---" % k)
    print("LATEX:", d)
    print("TEXT :", repr(omml.omml_text(d, display=True)))
    print()

print("=== digit mismatch detail ===")
for kind, tex in ([("D", x) for x in disp] + [("i", x) for x in inline]):
    tex = " ".join(tex.split())
    try:
        txt = omml.omml_text(tex, display=(kind == "D"))
    except Exception as e:
        print("  CONV FAIL", tex, e); continue
    src = collections.Counter(c for c in re.sub(r"\\[A-Za-z]+", "", tex) if c.isdigit())
    out = collections.Counter(c for c in txt if c.isdigit())
    if src != out:
        print("  [%s] %s" % (kind, tex))
        print("      src=%s" % dict(src))
        print("      out=%s" % dict(out))