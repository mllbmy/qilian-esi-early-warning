# -*- coding: utf-8 -*-
"""Print the manuscript abstract word count using the same rule the R45 abstract
patcher uses (strip LaTeX, keep math content, count tokens containing [A-Za-z0-9]).

Usage: python abstract_words.py [path/to/manuscript.tex]
Prints: ABSTRACT_WORDS=<n>
"""
import io
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TEX = sys.argv[1] if len(sys.argv) > 1 else r"D:\比赛\论文\paper-code\manuscript.tex"


def strip_latex(t):
    t = re.sub(r"(?<!\\)%.*", "", t)
    t = re.sub(r"\\citep?\{[^}]*\}", " ", t)
    t = re.sub(r"\\ref\{[^}]*\}", " ", t)
    t = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?", " ", t)
    t = t.replace("~", " ").replace("---", "\u2014").replace("--", "\u2013")
    t = t.replace("\\%", "%").replace("\\&", "&").replace("\\_", "_")
    t = re.sub(r"[$\\{}]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def wc(t):
    return len([x for x in re.split(r"\s+", t) if re.search(r"[A-Za-z0-9]", x)])


s = io.open(TEX, encoding="utf-8").read()
m = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", s, re.S)
if not m:
    print("ABSTRACT_WORDS=-1")
    sys.exit(0)
body = m.group(1)
print("ABSTRACT_WORDS=%d" % wc(strip_latex(body)))
print("ABSTRACT_HEAD=%s" % strip_latex(body)[:60])