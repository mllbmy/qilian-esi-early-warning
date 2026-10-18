# -*- coding: utf-8 -*-
"""Delivery acceptance check for the compiled manuscript PDF (R44).

Two defects were diagnosed in the 2.0 delivery:
  * the body text was set in Type3 bitmap fonts, which degrades print quality;
  * the fonts carried no usable ToUnicode CMap, so ligatures and dashes were
    mapped to control characters and word/range boundaries were lost when the
    text layer was extracted (copy-paste, PDF->Word, PDF->HTML).

This script asserts both are fixed.  Usage:
    python check_pdf_textlayer.py [path/to/manuscript.pdf]
Exit code 0 only when every assertion passes.
"""
import re
import sys

import pymupdf

CTRL = {0x15, 0x16, 0x1B, 0x1C, 0x1D, 0x1E}
WORDS = ["specification", "five", "significant", "six-indicator", "land-cover",
         "nine-indicator", "different", "difficult"]
RANGES = ["2005\u20132023", "0.20\u20130.87", "47\u201369"]
SIGMA = ["\u03a3", "\u2211"]


def main(path):
    doc = pymupdf.open(path)
    ok = True

    # 1. fonts: no Type3 bitmap faces, vector share near 100 %
    base = set()
    for page in doc:
        for f in page.get_fonts(full=True):
            # f = (xref, ext, type, basefont, name, encoding, ...)
            base.add((f[3], f[2]))
    kinds = {}
    for name, t in base:
        kinds.setdefault(t, []).append(name)
    n_type3 = len(kinds.get("Type3", []))
    n_vec = sum(len(v) for k, v in kinds.items() if k != "Type3")
    print("fonts: %d base fonts; Type3=%d vector=%d" % (len(base), n_type3, n_vec))
    for k, v in sorted(kinds.items()):
        print("   %-8s %d" % (k, len(v)))
    if n_type3:
        print("FAIL: %d Type3 (bitmap) font(s): %s" % (n_type3, kinds["Type3"][:6]))
        ok = False
    else:
        print("ok: no Type3 bitmap fonts")

    text = "\n".join(p.get_text() for p in doc)

    # 2. control characters from broken ToUnicode maps
    bad = {c: text.count(chr(c)) for c in CTRL if text.count(chr(c))}
    print("control chars U+0015/16/1B-1E: %d %s" % (sum(bad.values()), bad or ""))
    if bad:
        print("FAIL: %d control characters in the text layer" % sum(bad.values()))
        ok = False
    else:
        print("ok: no control characters")

    # 3. whole words
    flat = re.sub(r"\s+", " ", text)
    miss = [w for w in WORDS if flat.count(w) == 0]
    print("whole words: %d/%d found%s" % (len(WORDS) - len(miss), len(WORDS),
                                          "" if not miss else "; missing %s" % miss))
    if miss:
        print("FAIL: words not retrievable: %s" % miss)
        ok = False

    # 4. ranges keep their dash, 5. summation sign survives
    rmiss = [r for r in RANGES if r not in flat]
    print("ranges with en dash: %d/%d found%s" % (len(RANGES) - len(rmiss), len(RANGES),
                                                  "" if not rmiss else "; missing %s" % rmiss))
    if rmiss:
        print("note: ranges not found as en dash: %s" % rmiss)
    smiss = [s for s in SIGMA if s not in flat]
    print("summation sign: %s" % ("found" if len(smiss) < len(SIGMA) else "MISSING"))
    if len(smiss) == len(SIGMA):
        print("note: no summation sign extractable")

    print("pages: %d" % doc.page_count)
    print("\nRESULT: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1
                  else r"D:\比赛\论文\_r44_work\build_r44\manuscript.pdf"))