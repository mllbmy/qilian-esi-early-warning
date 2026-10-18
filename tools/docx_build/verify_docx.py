# -*- coding: utf-8 -*-
"""Verification of the submission Word manuscript: every count is measured."""
import collections
import io
import json
import os
import re
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
DOCX = sys.argv[1] if len(sys.argv) > 1 else \
    r"D:\比赛\论文\交付\2.0版本\论文_EN_2.0版本_投稿用.docx"
TEX = r"D:\比赛\论文\paper-code\manuscript.tex"
BIBTEX = r"D:\比赛\论文\paper-code\manuscript.bib"

R = {}
z = zipfile.ZipFile(DOCX)
docxml = z.read("word/document.xml").decode("utf-8")
R["docx_size"] = os.path.getsize(DOCX)
R["document_xml_chars"] = len(docxml)

import lxml.etree as ET
root = ET.fromstring(docxml.encode("utf-8"))

# ---- per-paragraph text (runs joined, so whole words stay searchable) -------
paras = []
for p in root.iter("{%s}p" % W_NS):
    txt = "".join(t.text or "" for t in p.iter("{%s}t" % W_NS))
    paras.append(txt)
body_text = "\n".join(paras)
math_text = "".join(t.text or "" for t in root.iter("{%s}t" % M_NS))

R["n_paragraphs"] = len(paras)
R["text_words"] = len([w for w in re.split(r"\s+", body_text)
                       if re.search(r"[A-Za-z0-9]", w)])
R["text_chars"] = len(body_text)

# ---- 2. structural counts ---------------------------------------------------
R["oMath"] = len(list(root.iter("{%s}oMath" % M_NS)))
R["oMathPara"] = len(list(root.iter("{%s}oMathPara" % M_NS)))
R["oMath_children_of_p"] = sum(
    1 for p in root.iter("{%s}p" % W_NS)
    for ch in p if ch.tag == "{%s}oMath" % M_NS)
R["w_tbl"] = len(list(root.iter("{%s}tbl" % W_NS)))
R["w_drawing"] = len(list(root.iter("{%s}drawing" % W_NS)))
R["blip"] = len(list(root.iter(
    "{http://schemas.openxmlformats.org/drawingml/2006/main}blip")))
media = [n for n in z.namelist() if n.startswith("word/media/")]
R["media_files"] = len(media)
R["media_bytes"] = sum(z.getinfo(n).file_size for n in media)

# ---- expected counts from the tex ------------------------------------------
tex = io.open(TEX, encoding="utf-8").read()
tex_nc = re.sub(r"(?<!\\)%.*", "", tex)
tbl_body = tex_nc[tex_nc.find("\\end{frontmatter}"):].split("\\end{document}")[0]
tex_tables = len(re.findall(r"\\begin\{table\}", tbl_body))
tex_figs = len(re.findall(r"\\begin\{figure\}", tbl_body))
tex_images = len(re.findall(r"\\includegraphics", tbl_body))
tex_eqs = len(re.findall(r"\\begin\{equation\}", tbl_body))
tex_cites = len(re.findall(r"\\cite[a-z]*\*?(?:\[[^\]]*\])*\{", tbl_body))
R["tex_tables"], R["tex_figs"], R["tex_images"], R["tex_eqs"] = \
    tex_tables, tex_figs, tex_images, tex_eqs
R["tex_cite_commands"] = tex_cites

R["missing_tables"] = tex_tables - R["w_tbl"] if tex_tables > R["w_tbl"] else 0
R["missing_figures"] = tex_figs - R["blip"] if tex_figs > R["blip"] else 0

# ---- 1. abstract / keywords -------------------------------------------------
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


ab = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", tex, re.S).group(1)
R["tex_abstract_words"] = wc(strip_latex(ab))
kw = re.search(r"\\begin\{keyword\}(.*?)\\end\{keyword\}", tex, re.S).group(1)
R["tex_keywords"] = [k.strip() for k in re.split(r"\\sep", kw) if k.strip()]
R["tex_keyword_count"] = len(R["tex_keywords"])
# abstract as it appears in the docx
ai = None
for i, t in enumerate(paras):
    if t.strip() == "Abstract":
        ai = i
        break
R["docx_abstract_words"] = wc(paras[ai + 1]) if ai is not None else -1
R["docx_keywords_line"] = next((t for t in paras if t.startswith("Keywords:")), "")
R["docx_keyword_count"] = len([k for k in
                               R["docx_keywords_line"].replace("Keywords:", "").split(";") if k.strip()])

# ---- 3. LaTeX residue -------------------------------------------------------
def hits(pat, text, flags=0):
    return len(re.findall(pat, text, flags))


R["residue"] = {}
for name, pat in [("\\cite", r"\\cite"), ("\\ref", r"\\ref"),
                  ("\\begin{", r"\\begin\{"), ("\\end{", r"\\end\{"),
                  ("\\label", r"\\label"), ("\\emph", r"\\emph"),
                  ("\\textbf", r"\\textbf"), ("\\includegraphics", r"\\includegraphics"),
                  ("[@", r"\[@"), ("{", r"[{}]"), ("$", r"\$"),
                  ("~", r"~"), ("&", r"&"), ("??", r"\?\?"),
                  ("[Author]", r"\[Author\]"), ("[email]", r"\[email\]"),
                  ("[Affiliation]", r"\[Affiliation\]")]:
    R["residue"][name] = hits(pat, body_text)
amp_ctx = [t.strip()[:110] for t in paras if "&" in t]
R["amp_contexts"] = amp_ctx

# ---- 4. text-layer health ---------------------------------------------------
CTL = [0x15, 0x16, 0x1b, 0x1c, 0x1d, 0x1e, 0x1f]
R["control_chars"] = {hex(c): body_text.count(chr(c)) for c in CTL}
R["control_chars_total"] = sum(R["control_chars"].values())
R["whole_words"] = {w: len(re.findall(r"(?<![A-Za-z0-9-])" + re.escape(w) +
                                    r"(?![A-Za-z0-9-])", body_text))
                    for w in ["specification", "significant", "six-indicator",
                              "land-cover", "eight-indicator", "grassland"]}

# ---- 5. key values ----------------------------------------------------------
KEY = ["0.447", "0.225", "0.805", "0.39", "0.389", "0.222", "0.390",
       "In ESI", "Medium", "0.676", "0.478", "0.469", "0.448", "0.380", "0.485"]
R["key_values_text"] = {k: body_text.count(k) for k in KEY}
R["key_values_math"] = {k: math_text.count(k) for k in KEY}
R["key_values_total"] = {k: body_text.count(k) + math_text.count(k) for k in KEY}

# ---- citations --------------------------------------------------------------
bib_keys = re.findall(r"@\w+\s*\{\s*([^,]+),", io.open(BIBTEX, encoding="utf-8").read())
R["bib_keys"] = len([k for k in bib_keys])
R["ref_list_entries"] = len([t for t in paras if re.match(r"^[A-Z\[]", t.strip())
                             and re.search(r"\(\d{4}[a-z]?\)\.", t)])
# reference entries: count paragraphs between References heading and end
ri = next((i for i, t in enumerate(paras) if t.strip() == "References"), None)
R["references_heading_index"] = ri
R["entries_after_references"] = len([t for t in paras[ri + 1:] if t.strip()]) if ri is not None else 0
R["in_text_citations"] = len(re.findall(r"\([A-Z][^()]{2,80}?(?:19|20)\d{2}[a-z]?\)", body_text))
R["unresolved_citations"] = body_text.count("??") + hits(r"\\cite", body_text)

# ---- section / heading census ----------------------------------------------
heads = []
for p in root.iter("{%s}p" % W_NS):
    txt = "".join(t.text or "" for t in p.iter("{%s}t" % W_NS))
    bold = any(r.find("{%s}rPr/{%s}b" % (W_NS, W_NS)) is not None
               for r in p.iter("{%s}r" % W_NS))
    if bold and txt.strip() and len(txt) < 90:
        heads.append(txt.strip())
R["headings"] = heads

# ---- tables census ---------------------------------------------------------
tbl_info = []
for tbl in root.iter("{%s}tbl" % W_NS):
    rows = list(tbl.iter("{%s}tr" % W_NS))
    nr = len(rows)
    nc = max(len(list(r.iter("{%s}tc" % W_NS))) for r in rows) if rows else 0
    first = "".join(t.text or "" for t in rows[0].iter("{%s}t" % W_NS)) if rows else ""
    tbl_info.append((nc, nr, first[:70]))
R["tables"] = tbl_info

json.dump(R, io.open(r"D:\比赛\论文\_r45_work\wb\verify_result.json", "w",
                     encoding="utf-8"), indent=1, ensure_ascii=False)

# ---- report -----------------------------------------------------------------
print("=" * 78)
print("FILE:", DOCX)
print("size bytes        :", R["docx_size"])
print("paragraphs        :", R["n_paragraphs"], " text words:", R["text_words"],
      " text chars:", R["text_chars"])
print("oMath (m:oMath)   :", R["oMath"], " (direct children of w:p:",
      R["oMath_children_of_p"], ")  oMathPara:", R["oMathPara"])
print("w:tbl             :", R["w_tbl"], " tex tables:", R["tex_tables"],
      " missing:", R["missing_tables"])
print("images (a:blip)   :", R["blip"], " tex figures:", R["tex_figs"],
      " missing:", R["missing_figures"], " media files:", R["media_files"],
      " bytes:", R["media_bytes"])
print("equations in tex  :", R["tex_eqs"])
print("abstract words    : tex", R["tex_abstract_words"], "| docx", R["docx_abstract_words"],
      " (JMS limit 300)")
print("keywords          : tex", R["tex_keyword_count"], R["tex_keywords"], "| docx", R["docx_keyword_count"])
print("LaTeX residue     :", R["residue"])
print("& contexts        :", R["amp_contexts"])
print("control chars     :", R["control_chars"])
print("whole words       :", R["whole_words"])
print("key values text   :", R["key_values_text"])
print("key values math   :", {k: v for k, v in R["key_values_math"].items() if v})
print("key values total  :", R["key_values_total"])
print("ref entries       :", R["entries_after_references"], " (bib keys:", R["bib_keys"], ")")
print("in-text citations :", R["in_text_citations"], " unresolved:", R["unresolved_citations"])
print("cite commands tex :", R["tex_cite_commands"])
print("headings (%d):" % len(heads))
for h in heads:
    print("   ", h)
print("tables (cols,rows,first row):")
for c, r_, f in tbl_info:
    print("    %2d x %2d  %s" % (c, r_, f))