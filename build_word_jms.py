# -*- coding: utf-8 -*-
"""JMS 投稿版：从 manuscript.tex 生成
① 匿名主文档 Word（A4/单倍行距/10 pt/页码；图表置于正文之后）
② Title Page Word（作者/单位/邮箱/ORCID/致谢与资助/伦理声明）
③ 主文档纯文本校对稿（带行号）
数值与科学内容零改动：正文、公式、图表编号、参考文献条目均取自既有源文件。
"""
import io
import os
import re
import sys

from docx import Document
from docx.shared import Pt, Cm
from docx.oxml.ns import qn
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from word_style import (add_equation, make_three_line, heading_cn,
                        EQNORM_EN, EQ3, EQ4, EQ5, EQ6)

# 路径自解析：仓库克隆/解压到任意目录均可运行
BASE = os.path.dirname(os.path.abspath(__file__))
# 作者身份信息取自本地私有模块 author_local.py（已 .gitignore 排除）；缺失时用中性占位符
sys.path.insert(0, BASE)
try:
    from author_local import (AUTHOR_EN_DISPLAY as _AL_AUTHOR_EN_DISPLAY, AFFIL_EN as _AL_AFFIL,
                              CREDIT_EN as _AL_CREDIT_EN, EMAIL as _AL_EMAIL, ORCID as _AL_ORCID)
except ImportError:
    _AL_AUTHOR_EN_DISPLAY = "[Author] (Corresponding author)*"
    _AL_AFFIL = None
    _AL_CREDIT_EN = ("[Author]: Conceptualization, Methodology, Formal analysis, Data curation, "
                     "Visualization, Writing - original draft, Writing - review & editing.")
    _AL_EMAIL = None
    _AL_ORCID = "[ORCID]"
FIG = os.path.join(BASE, "figures")
OUTDIR = os.path.join(BASE, "out", "jms")
OUT = os.path.join(OUTDIR, "论文_EN_JMSv3_2026-09-23.docx")
OUT_TP = os.path.join(OUTDIR, "Title_Page_JMSv3_2026-09-23.docx")
OUT_TXT = os.path.join(OUTDIR, "论文_EN_JMSv3_2026-09-23.txt")
def _jmsread(fn):
    p = os.path.join(BASE, "jms", fn)
    return io.open(p, encoding="utf-8").read() if os.path.isfile(p) else ""


REFS_JMS = [l.strip() for l in _jmsread("refs_jms.txt").split("\n") if l.strip()]
KWS_JMS = _jmsread("keywords_jms.txt").strip()
DECL_JMS = _jmsread("declarations_jms.txt").strip()
GEO_JMS = _jmsread("study_area_geo.txt").strip()
LEFT = []


def rd(p):
    return io.open(p, encoding="utf-8", errors="replace").read() if os.path.isfile(p) else ""


TEX = rd(os.path.join(BASE, "manuscript.tex"))
# JMS：研究区须给经纬度 → 并入 Study Area 首段（仅加一句事实性范围，不改其他内容）
if "GEO_JMS" not in TEX and os.path.isfile(os.path.join(BASE, "jms", "study_area_geo.txt")):
    _geo = io.open(os.path.join(BASE, "jms", "study_area_geo.txt"), encoding="utf-8").read().strip()
    _si = TEX.index(r"\subsection{Study area")
    _p = TEX.index("\n", _si) + 1
    while TEX[_p:_p + 1] == "\n":
        _p += 1
    _e = TEX.index("\n", _p)
    TEX = TEX[:_e] + " " + _geo + TEX[_e:]
AUX = rd(os.path.join(BASE, "manuscript.aux"))
BBL = rd(os.path.join(BASE, "manuscript.bbl"))

BIB = {m.group(1): (m.group(4), m.group(3)) for m in re.finditer(
    r"\\bibcite\{([^}]+)\}\{\{(\d+)\}\{(\d{4})\}\{\{([^}]*)\}\}", AUX)}
# 声明段：由尾段统一输出，正文遍历遇到时必须跳过（否则 Word 里出现两组）
BACK_SECTIONS = ("Data availability", "CRediT authorship contribution statement",
                 "Declaration of competing interest", "Funding",
                 "Declaration of generative AI and AI-assisted technologies in the writing process")

REFS = {}
for m in re.finditer(r"\\newlabel\{([^}]+)\}\{\{([^}]+)\}", AUX):
    REFS.setdefault(m.group(1), m.group(2))
BBL_KEYS = re.findall(r"\\bibitem(?:\[[^\]]*\])?\{([^}]+)\}", BBL)

GREEK = {r"\alpha": "α", r"\beta": "β", r"\gamma": "γ", r"\delta": "δ", r"\Delta": "Δ",
         r"\sigma": "σ", r"\mu": "μ", r"\lambda": "λ", r"\theta": "θ", r"\pi": "π",
         r"\rho": "ρ", r"\tau": "τ", r"\phi": "φ", r"\omega": "ω", r"\Omega": "Ω",
         r"\times": "×", r"\pm": "±", r"\approx": "≈", r"\leq": "≤", r"\geq": "≥",
         r"\le": "≤", r"\ge": "≥", r"\sim": "∼", r"\circ": "°", r"\rightarrow": "→",
         r"\to": "→", r"\cdot": "·", r"\infty": "∞", r"\in": "∈", r"\sum": "Σ",
         r"\S": "§", r"\%": "%", r"\&": "&", r"\_": "_", r"\,": " ", r"\;": " ", r"\!": "",
         r"\ ": " ", r"\quad": " ", r"\qquad": " "}


_SUPMAP = str.maketrans("0123456789+-=()ni", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱ")
_SUPSET = set("⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱ")


def _sup(x):
    """斜率单位之类的内联上标：可映射则用 Unicode 上标，否则退回纯文本"""
    y = x.translate(_SUPMAP)
    return y if y and all(c in _SUPSET for c in y) else x


_HATMAP = {"a": "â", "b": "b̂", "e": "ê", "i": "î", "n": "n̂", "o": "ô", "u": "û", "x": "x̂", "y": "ŷ", "w": "ŵ", "z": "ẑ"}


def math2txt(m):
    m = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"\1/\2", m)
    m = re.sub(r"\\dfrac\{([^{}]*)\}\{([^{}]*)\}", r"\1/\2", m)
    for _ in range(2):
        m = re.sub(r"\\text\{([^{}]*)\}", r"\1", m)
        m = re.sub(r"\\mathrm\{([^{}]*)\}", r"\1", m)
        m = re.sub(r"\\emph\{([^{}]*)\}", r"\1", m)
    m = m.replace(r"^{\circ}", "°")
    m = re.sub(r"\^\{([^{}]*)\}", lambda x: _sup(x.group(1)), m)
    m = re.sub(r"_\{([^{}]*)\}", r"\1", m)
    m = re.sub(r"\^(\w)", lambda x: _sup(x.group(1)), m)
    m = re.sub(r"_(\w)", r"\1", m)
    m = re.sub(r"\\hat\s*\{?([a-zA-Z])\}?", lambda x: _HATMAP.get(x.group(1), x.group(1)), m)
    for k, v in GREEK.items():
        m = m.replace(k, v)
    m = m.replace("{", "").replace("}", "").replace("\\", "")
    return m


def cite(keys):
    """\\citep{a,b} -> (Author, Year; Author, Year)，同作者合并年份（elsarticle-harv 体例）"""
    order, by = [], {}
    for k in keys.split(","):
        k = k.strip()
        if not k:
            continue
        a, y = BIB.get(k, ("?", "?"))
        a = a.replace("~", " ")
        if a not in by:
            by[a] = []
            order.append(a)
        by[a].append(y)
    if not order:
        return ""
    # JMS：作者-年制，(Author Year)，年份前无逗号
    return "(" + "; ".join("%s %s" % (a, ", ".join(sorted(by[a]))) for a in order) + ")"


def tex2txt(s):
    s = re.sub(r"\\label\{[^}]*\}", "", s)
    s = re.sub(r"\\citep\{([^}]*)\}", lambda m: cite(m.group(1)), s)
    s = re.sub(r"\\citet\{([^}]*)\}", lambda m: cite(m.group(1)), s)
    s = re.sub(r"\\cite\{([^}]*)\}", lambda m: cite(m.group(1)), s)
    s = re.sub(r"\\eqref\{([^}]*)\}", lambda m: "(" + REFS.get(m.group(1), "?") + ")", s)
    s = re.sub(r"\\ref\{([^}]*)\}", lambda m: REFS.get(m.group(1), "?"), s)
    s = re.sub(r"\$([^$]*)\$", lambda m: math2txt(m.group(1)), s)
    s = re.sub(r"\\multirow\{\d+\}\{[^}]*\}\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\\multicolumn\{\d+\}\{[^}]*\}\{([^{}]*)\}", r"\1", s)
    for cmd in ("\\textbf", "\\textit", "\\emph", "\\texttt", "\\textsuperscript",
                "\\noindent", "\\centering", "\\small", "\\footnotesize", "\\url",
                "\\href", "\\text", "\\mathrm"):
        s = s.replace(cmd, "")
    s = re.sub(r"\\vspace\{[^}]*\}", "", s)
    s = re.sub(r"\\setlength\{[^}]*\}\{[^}]*\}", "", s)
    s = re.sub(r"\\begin\{[^}]*\}\[?[^\]]*\]?", "", s)
    s = re.sub(r"\\end\{[^}]*\}", "", s)
    s = s.replace("---", "—").replace("--", "–").replace("``", "“").replace("''", "”")
    for _k, _v in (("\\,", " "), ("\\;", " "), ("\\ ", " "), ("\\quad", " "),
                   ("\\qquad", " "), ("\\%", "%"), ("\\&", "&"), ("\\_", "_")):
        s = s.replace(_k, _v)
    # elsarticle-harv 的 .bbl 用 \bibinfo{域}{值} + \DOIprefix\doi{...}
    for _ in range(3):
        s = re.sub(r"\\bibinfo\{[^}]*\}\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}", r"\1", s)
        s = re.sub(r"\\bibfield\{[^}]*\}\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}", r"\1", s)
    s = s.replace("\\DOIprefix", "doi: ").replace("\\newblock", " ")
    s = re.sub(r"\\doi\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\\[a-zA-Z]+\*?", "", s)
    s = s.replace("{", "").replace("}", "")
    s = s.replace("~", " ").replace(r"\%", "%").replace(r"\&", "&")
    s = re.sub(r"\s+", " ", s).strip()
    _bad = re.findall(r"\\[a-zA-Z]*|\$|\{|\}", s)
    if _bad:
        LEFT.append((s[:90], sorted(set(_bad))))
    return s


# ---------------- 版式（与 build_word_cn.py 完全一致） ----------------
doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
normal = doc.styles["Normal"]
normal.font.name = "Times New Roman"
normal.font.size = Pt(10)          # JMS：10 pt
normal.paragraph_format.line_spacing = 1.0   # JMS：单倍行距
normal.paragraph_format.space_after = Pt(0)
normal._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")


def set_cn(run):
    run._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), "宋体")


def h1(text):
    return heading_cn(doc, text, 11)


def h2(text):
    return heading_cn(doc, text, 10.5)


def para(text, size=10, bold=False, align=None, indent=True):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.font.size = Pt(size)
    r.bold = bold
    set_cn(r)
    if align is not None:
        p.alignment = align
    if indent and align is None:
        p.paragraph_format.first_line_indent = Pt(size * 2)
    p.paragraph_format.line_spacing = 1.0     # JMS：单倍行距
    p.paragraph_format.space_after = Pt(2)
    return p


def _embed_path(img, w_cm):
    """主文档内嵌图：按 400 dpi × 实际宽度降采样。
    JMS 的 600 dpi 图件要求由独立 TIFF 文件满足；主文档需服从投稿系统单文件 ≤20 MB 上限。"""
    from PIL import Image
    src = os.path.join(FIG, img)
    if not os.path.isfile(src):
        return src
    target = round(w_cm / 2.54 * 400)
    im = Image.open(src).convert("RGB")
    if im.size[0] > target:
        im = im.resize((target, max(1, round(im.size[1] * target / im.size[0]))), Image.LANCZOS)
    d = os.path.join(OUTDIR, "_embed")
    os.makedirs(d, exist_ok=True)
    out = os.path.join(d, os.path.splitext(img)[0] + "_%dpx.png" % target)
    # 缓存键含源图 mtime：源图更新（重出图/换字体）后自动重建，杜绝旧缓存复用（Qoder R10 复跑发现）
    if not os.path.isfile(out) or os.path.getmtime(out) < os.path.getmtime(src):
        im.save(out, format="PNG", optimize=True)
    return out


def fig(img, caption, w=14.5):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(_embed_path(img, w), width=Cm(w))
    cp = doc.add_paragraph()
    cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = cp.add_run(caption)
    r.font.size = Pt(9.5)
    r.bold = True
    set_cn(r)
    return cp


def _vcenter_content(t):
    from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
    for row in t.rows:
        for cell in row.cells:
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            for p in cell.paragraphs:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER


def table(headers, rows, caption, note=None):
    para(caption, 10.5, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, indent=False)
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, htxt in enumerate(headers):
        c = t.rows[0].cells[i]
        c.paragraphs[0].add_run(htxt).bold = True
        c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        c.paragraphs[0].runs[0].font.size = Pt(9)
        set_cn(c.paragraphs[0].runs[0])
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            if i < len(cells):
                r = cells[i].paragraphs[0].add_run(str(v))
                r.font.size = Pt(9)
                set_cn(r)
    make_three_line(t)
    _vcenter_content(t)
    if note:
        para(note, 9, align=WD_ALIGN_PARAGRAPH.CENTER, indent=False)
    return t


def eq(name, num):
    b = {"weight": EQ3, "norm": EQNORM_EN, "esi": EQ4, "gm": EQ5, "q": EQ6}[name]
    return add_equation(doc, b(), num)


EQ_OF = {"eq:weight": ("weight", 1), "eq:norm": ("norm", 2), "eq:esi": ("esi", 3),
         "eq:gm": ("gm", 4), "eq:q": ("q", 5)}

# ---------------- 题头 ----------------
title = re.search(r"\\title\{(.*?)\}\s*\n", TEX, re.S).group(1)
author = re.search(r"\\author\[[^\]]*\]\{(.*)$", TEX, re.M).group(1)
# manuscript.tex 的公开版本作者块为占位符 → 优先使用本地私有模块的真实值
email = _AL_EMAIL or re.search(r"\\ead\{(.*?)\}", TEX).group(1)
affil = _AL_AFFIL or re.search(r"\\affiliation\[[^\]]*\]\{organization=\{(.*?)\}\}", TEX, re.S).group(1)
abstract = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", TEX, re.S).group(1)
kws = re.search(r"\\begin\{keyword\}(.*?)\\end\{keyword\}", TEX, re.S).group(1)

# JMS：主文档用于同行评审，不得出现作者姓名与单位 → 只保留题名
para(tex2txt(title), 14, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, indent=False)
doc.add_paragraph()
h1("Abstract")
para(tex2txt(abstract))
para("Keywords: " + KWS_JMS, 10, bold=True, indent=False)
doc.add_paragraph()

# ---------------- 正文扫描 ----------------
lines = TEX.split("\n")
start = next(i for i, l in enumerate(lines) if l.strip().startswith("\\end{frontmatter}")) + 1
i = start
sec_n = sub_n = fig_n = tab_n = 0
hl_items = []
buf = []
stats = {"para": 0, "fig": 0, "tab": 0, "eq": 0}
fig_q, tab_q = [], []          # JMS：图表统一置于正文之后


def flush():
    global buf
    if buf:
        t = tex2txt(" ".join(buf))
        if t:
            para(t)
            stats["para"] += 1
        buf = []


def block_end(j, env):
    while j < len(lines) and not lines[j].strip().startswith("\\end{%s}" % env):
        j += 1
    return j


while i < len(lines):
    ln = lines[i].strip()
    if not ln or ln.startswith("%"):
        flush()
        i += 1
        continue
    m = re.match(r"\\section\{(.+)\}$", ln)
    if m:
        flush()
        sec_n += 1
        sub_n = 0
        h1("%d  %s" % (sec_n, tex2txt(m.group(1))))
        i += 1
        continue
    m = re.match(r"\\subsection\{(.+)\}$", ln)
    if m:
        flush()
        sub_n += 1
        h2("%d.%d  %s" % (sec_n, sub_n, tex2txt(m.group(1))))
        i += 1
        continue
    m = re.match(r"\\section\*\{(.+)\}$", ln)
    if m:
        flush()
        _name = tex2txt(m.group(1))
        if _name in BACK_SECTIONS:        # 尾段统一输出，避免正文遍历重复一遍
            i += 1
            while i < len(lines) and not re.match(
                    r"\\(section\*|bibliographystyle|end\{document\})", lines[i].strip()):
                i += 1
            continue
        h1(_name)
        i += 1
        continue
    if ln.startswith("\\begin{table}"):
        flush()
        j = block_end(i, "table")
        body = "\n".join(lines[i:j + 1])
        cap = re.search(r"\\caption\{(.*?)\}\s*\n", body, re.S)
        tab_n += 1
        rows_all = re.findall(r"^[^%\n]*?&[^\n]*$", re.sub(r"\\midrule", "@@MID@@",
                                                            re.sub(r"\\toprule", "@@TOP@@",
                                                                   re.sub(r"\\bottomrule", "@@BOT@@", body))),
                              re.M)
        raw = re.sub(r"\\bottomrule", "\n@@BOT@@", re.sub(r"\\midrule", "\n@@MID@@",
                      re.sub(r"\\toprule", "\n@@TOP@@", body)))
        seg = raw.split("@@MID@@")
        pre = seg[0].split("@@TOP@@")[-1] if "@@TOP@@" in seg[0] else seg[0]
        post = seg[1].split("@@BOT@@")[0] if len(seg) > 1 else ""
        def cells(txt):
            out = []
            for line in txt.split("\n"):
                s = line.strip().rstrip("\\").strip()
                if "&" in s:
                    out.append([tex2txt(c) for c in s.split("&")])
            return out
        hdr = cells(pre)
        bodyrows = [r for r in cells(post) if any(x for x in r)]
        note = None
        mn = re.search(r"\{\\footnotesize(.*?)\}", body, re.S)
        if mn:
            note = tex2txt(mn.group(1))
        tab_q.append((hdr[0] if hdr else [], bodyrows, "Table %d.  %s" % (tab_n, tex2txt(cap.group(1))), note))
        stats["tab"] += 1
        i = j + 1
        continue
    if ln.startswith("\\begin{figure}"):
        flush()
        j = block_end(i, "figure")
        body = "\n".join(lines[i:j + 1])
        img = re.search(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", body)
        w = re.search(r"width=([\d.]+)\\linewidth", body)
        cap = re.search(r"\\caption\{(.*?)\}\s*\n", body, re.S)
        stem = os.path.splitext(os.path.basename(img.group(1)))[0] + ".png"
        fig_n += 1
        frac = float(w.group(1)) if w else 0.9
        _cap_txt = tex2txt(cap.group(1))
        if fig_n == 1:   # R10 方案③：图1 已删除位置示意图，图注注明主图底图来源
            _cap_txt += "  Base map: Copernicus DEM 90 m; Natural Earth 1:50m province boundaries."
        if "framework" in stem:      # 框架图按 JMS 上限 16 cm 放置，保证图内 8–9 pt 印刷字号
            _w = 16.0
        else:
            _w = round(frac * 16.0, 1)
        fig_q.append((stem, "Figure %d.  %s" % (fig_n, _cap_txt), _w))
        stats["fig"] += 1
        i = j + 1
        continue
    if ln.startswith("\\begin{equation}"):
        flush()
        j = block_end(i, "equation")
        body = "\n".join(lines[i:j + 1])
        lab = re.search(r"\\label\{([^}]+)\}", body)
        nm, num = EQ_OF.get(lab.group(1), (None, None))
        if nm:
            eq(nm, num)
            stats["eq"] += 1
        i = j + 1
        continue
    if ln.startswith("\\begin{enumerate}"):
        flush()
        j = block_end(i, "enumerate")
        body = "\n".join(lines[i:j + 1])
        items = [tex2txt(x) for x in re.findall(r"\\item\s*(.*?)(?=\\item|\\end\{enumerate\})", body, re.S)]
        items = [x for x in items if x]
        if items:
            para(" ".join("(%d) %s" % (k, t) for k, t in enumerate(items, 1)))
            stats["para"] += 1
        i = j + 1
        continue
    if ln.startswith("\\begin{itemize}"):
        flush()
        j = block_end(i, "itemize")
        body = "\n".join(lines[i:j + 1])
        items = [tex2txt(x) for x in re.findall(r"\\item\s*(.*?)(?=\\item|\\end\{itemize\})", body, re.S)]
        hl_items.extend([x for x in items if x])
        i = j + 1
        continue
    if ln.startswith(("\\bibliographystyle", "\\bibliography", "\\end{document}",
                      "\\label{", "\\vspace", "\\setlength")):
        i += 1
        continue
    buf.append(ln)
    i += 1
flush()

# ---------------- 尾段（镜像 CN Word 顺序） ----------------
doc.add_paragraph()
# JMS 不要求 Highlights（提交件仅 Title Page + Main document + Cover letter）
doc.add_paragraph()
# —— JMS 必含四类声明（置于参考文献之前）——
_parts = [x.strip() for x in re.split(r"\n\s*\n", DECL_JMS) if x.strip()]
for _i in range(0, len(_parts) - 1, 2):
    h1(_parts[_i])
    para(_parts[_i + 1])
    stats["para"] += 1
doc.add_paragraph()
# —— 参考文献（JMS 体例 19 条，字母序，无序号）——
h1("References")
refs = list(REFS_JMS)
for r in refs:
    _p = para(r, 10, indent=False)
    _p.paragraph_format.left_indent = Pt(18)
    _p.paragraph_format.first_line_indent = Pt(-18)
# —— 图（含图注，置于正文之后）——
doc.add_paragraph()
h1("Figures")
for _stem, _cap, _w in fig_q:
    fig(_stem, _cap, w=min(16.0, max(14.0, _w)))
# —— 表（置于图之后）——
doc.add_paragraph()
h1("Tables")
for _hdr, _rows, _cap, _note in tab_q:
    table(_hdr, _rows, _cap, _note)

def add_page_numbers(d):
    """JMS：要求页码（自动页码域）"""
    from docx.oxml import OxmlElement
    for s in d.sections:
        p = s.footer.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run()
        run.font.size = Pt(10)
        f1 = OxmlElement("w:fldChar"); f1.set(qn("w:fldCharType"), "begin")
        it = OxmlElement("w:instrText"); it.set(qn("xml:space"), "preserve"); it.text = "PAGE"
        f2 = OxmlElement("w:fldChar"); f2.set(qn("w:fldCharType"), "end")
        run._r.append(f1); run._r.append(it); run._r.append(f2)


add_page_numbers(doc)
os.makedirs(OUTDIR, exist_ok=True)
doc.save(OUT)

# ---- 主文档纯文本校对稿（带行号，供审阅与 Qoder 复核）----
txt = []
for i, p in enumerate(doc.paragraphs, 1):
    t = p.text.strip()
    if t:
        txt.append("%4d  %s" % (i, t))
for t in doc.tables:
    for row in t.rows:
        txt.append("      [表] " + " | ".join(c.text.strip() for c in row.cells))
io.open(OUT_TXT, "w", encoding="utf-8", newline="\n").write("\n".join(txt) + "\n")

# ---- Title Page（作者信息只出现在此）----
tp = Document()
_s = tp.sections[0]
_s.page_width, _s.page_height = Cm(21.0), Cm(29.7)
_st = tp.styles["Normal"]
_st.font.name = "Times New Roman"
_st.paragraph_format.line_spacing = 1.0


def tpara(text, size=12, bold=False, align=WD_ALIGN_PARAGRAPH.LEFT):
    p = tp.add_paragraph()
    r = p.add_run(text)
    r.font.size = Pt(size)
    r.bold = bold
    set_cn(r)
    p.alignment = align
    p.paragraph_format.line_spacing = 1.0
    return p


tpara(tex2txt(title), 14, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
tpara(_AL_AUTHOR_EN_DISPLAY, 12, align=WD_ALIGN_PARAGRAPH.CENTER)
tpara(tex2txt(affil), 11, align=WD_ALIGN_PARAGRAPH.CENTER)
tpara("Email: " + email, 11, align=WD_ALIGN_PARAGRAPH.CENTER)
tpara("ORCID: " + _AL_ORCID, 11, align=WD_ALIGN_PARAGRAPH.CENTER)
tpara("*Corresponding author", 10, align=WD_ALIGN_PARAGRAPH.CENTER)
tp.add_paragraph()
tpara("Acknowledgements", 12, bold=True)
tpara("This study received no specific grant from any funding agency in the public, "
      "commercial, or not-for-profit sectors.")
tp.add_paragraph()
tpara("Author contribution", 12, bold=True)
tpara(_AL_CREDIT_EN)
tp.add_paragraph()
tpara("Ethics Declaration", 12, bold=True)
tpara("This study did not involve human participants or animals. All datasets used are openly "
      "available, and the research was conducted in accordance with the ethical standards of the journal.")
add_page_numbers(tp)
tp.save(OUT_TP)

print("OK:", OUT)
print("OK:", OUT_TP)
print("OK:", OUT_TXT)
print("段落 %d | 图 %d | 表 %d | 公式 %d | 参考文献 %d"
      % (stats["para"], stats["fig"], stats["tab"], stats["eq"], len(refs)))
if LEFT:
    print("[警告] 仍有 %d 处 LaTeX 残留：" % len(LEFT))
    for _s, _b in LEFT[:8]:
        print("   ", _b, _s)
else:
    print("LaTeX 残留检查：干净")
unknown = sorted({k.strip() for m in re.findall(r"\\cite[pt]?\{([^}]*)\}", TEX)
                  for k in m.split(",") if k.strip() and k.strip() not in BIB})
print("未映射引用键:", unknown if unknown else "无")
sys.exit(1 if (LEFT or unknown) else 0)