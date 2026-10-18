# -*- coding: utf-8 -*-
"""Convert every math snippet in manuscript.tex through omml.py and verify that
no character content was lost."""
import collections
import io
import re
import sys

sys.path.insert(0, r"D:\比赛\论文\_r45_work\wb")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import omml

TEX = r"D:\比赛\论文\paper-code\manuscript.tex"
s = io.open(TEX, encoding="utf-8").read()
s = re.sub(r"(?<!\\)%.*", "", s)
body = s.split(r"\begin{document}", 1)[1].split(r"\end{document}")[0]

disp = re.findall(r"\\begin\{equation\}(.*?)\\end\{equation\}", body, re.S)
inline = re.findall(r"(?<!\$)\$(?!\$)((?:\\.|[^$\\])+)\$(?!\$)", body)

snippets = []
for d in disp:
    snippets.append(("DISPLAY", " ".join(d.split())))
for x in inline:
    snippets.append(("inline", " ".join(x.split())))

print("total snippets: %d (display %d, inline %d)" % (len(snippets), len(disp), len(inline)))

fails = []
rows = []
for kind, tex in snippets:
    try:
        body_xml = omml.to_omml_body(tex, display=(kind == "DISPLAY"))
        txt = omml.omml_text(tex, display=(kind == "DISPLAY"))
        omml.omml_element(tex, display=(kind == "DISPLAY"))   # exercise parse_xml too
    except Exception as ex:
        fails.append((kind, tex, "%s: %s" % (type(ex).__name__, ex)))
        continue
    rows.append((kind, tex, txt, body_xml))

print("\n=== FAILURES: %d ===" % len(fails))
for k, t, e in fails:
    print("  [%s] %-50s %s" % (k, t, e))

# ---- content preservation: literal digits must survive exactly -------------
bad_digits = []
for kind, tex, txt, _ in rows:
    src_digits = collections.Counter(re.sub(r"\\[A-Za-z]+", "", tex))
    src_digits = collections.Counter(c for c in re.sub(r"\\[A-Za-z]+", "", tex) if c.isdigit())
    out_digits = collections.Counter(c for c in txt if c.isdigit())
    if src_digits != out_digits:
        bad_digits.append((tex, dict(src_digits), dict(out_digits)))
print("\n=== DIGIT MISMATCH: %d ===" % len(bad_digits))
for tex, a, b in bad_digits:
    print("  %-50s src=%s out=%s" % (tex, a, b))

# ---- distinct snippets, LaTeX -> rendered text -----------------------------
seen = set()
uniq = []
for kind, tex, txt, _ in rows:
    if tex in seen:
        continue
    seen.add(tex)
    uniq.append((kind, tex, txt))
print("\n=== DISTINCT CONVERSIONS: %d ===" % len(uniq))
for kind, tex, txt in sorted(uniq, key=lambda r: (r[0], r[1])):
    flag = "  " if kind == "inline" else "D "
    print("%s%-46s -> %s" % (flag, tex, txt))

# ---- symbol coverage -------------------------------------------------------
for sym in ["\u2265", "\u2264", "\u00b1", "\u00d7", "\u00b0", "\u03b1", "\u03b3",
            "\u03c1", "\u03bb", "\u03c3", "\u0394", "\u2208", "\u223c",
            "\u2192", "\u2261", "\u2211", "\u0302"]:
    n = sum(txt.count(sym) for _, _, txt, _ in rows)
    print("symbol %r appears %d times in converted output" % (sym, n))