# -*- coding: utf-8 -*-
"""Inventory every math snippet in manuscript.tex (inline $...$, display equation,
\\[...\\]) so the LaTeX->OMML converter can be sized against the real vocabulary."""
import collections
import io
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
TEX = r"D:\比赛\论文\paper-code\manuscript.tex"
s = io.open(TEX, encoding="utf-8").read()

# drop comments
s = re.sub(r"(?<!\\)%.*", "", s)
body = s.split(r"\begin{document}", 1)[1] if r"\begin{document}" in s else s
body = body.split(r"\end{document}")[0]

disp = re.findall(r"\\begin\{equation\}(.*?)\\end\{equation\}", body, re.S)
brack = re.findall(r"\\\[(.*?)\\\]", body, re.S)
inline = re.findall(r"(?<!\$)\$(?!\$)((?:\\.|[^$\\])+)\$(?!\$)", body)

print("display equations: %d ; \\[..\\]: %d ; inline: %d" % (len(disp), len(brack), len(inline)))
print("\n--- display ---")
for d in disp:
    print("  " + " ".join(d.split())[:160])
for d in brack:
    print("  [..] " + " ".join(d.split())[:160])

c = collections.Counter(" ".join(x.split()) for x in inline)
print("\n--- distinct inline snippets: %d ---" % len(c))
for k, v in sorted(c.items(), key=lambda x: (-x[1], x[0])):
    print("  %3d  %s" % (v, k))

# command vocabulary
cmds = collections.Counter(re.findall(r"\\[a-zA-Z]+", " ".join(inline + disp + brack)))
print("\n--- command vocabulary ---")
print("  " + ", ".join("%s(%d)" % (k, v) for k, v in sorted(cmds.items(), key=lambda x: -x[1])))
print("\n--- raw chars beyond ASCII ---")
non = collections.Counter(ch for ch in " ".join(inline + disp + brack) if ord(ch) > 127)
print("  ", dict(non))