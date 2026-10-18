# -*- coding: utf-8 -*-
"""Structural reconnaissance of commands that need special handling."""
import collections
import io
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
TEX = r"D:\比赛\论文\paper-code\manuscript.tex"
s = io.open(TEX, encoding="utf-8").read()
s = re.sub(r"(?<!\\)%.*", "", s)

print("=== footnote-family commands ===")
for m in re.finditer(r"\\(footnote[a-z]*)", s):
    print("  ", m.group(1), "at", m.start())
print("  real \\footnote{} count:",
      len(re.findall(r"\\footnote\{", s)))
print("  \\footnotesize count:", len(re.findall(r"\\footnotesize", s)))

print("\n=== every backslash command, with counts ===")
cmds = collections.Counter(re.findall(r"\\([A-Za-z]+)", s))
for k, v in sorted(cmds.items(), key=lambda x: (-x[1], x[0])):
    print("  %-24s %d" % (k, v))

print("\n=== non-alphabetic escapes ===")
esc = collections.Counter(re.findall(r"\\([^A-Za-z])", s))
print("  ", dict(esc))

print("\n=== multicolumn / cmidrule context ===")
for m in re.finditer(r"\\multicolumn", s):
    print("  ", s[m.start():m.start() + 120].replace("\n", " "))
for m in re.finditer(r"\\cmidrule", s):
    print("  ", s[m.start():m.start() + 80].replace("\n", " "))

print("\n=== textsuperscript ===")
for m in re.finditer(r"\\textsuperscript", s):
    print("  ", s[m.start():m.start() + 90].replace("\n", " "))