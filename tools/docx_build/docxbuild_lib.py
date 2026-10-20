# -*- coding: utf-8 -*-
"""Build the JMS submission Word manuscript from the LaTeX source.

Text     -> ordinary Word paragraphs (never text boxes or images)
Math     -> real OMML equations (m:oMath), editable in Word's equation editor
Tables   -> real Word tables (w:tbl), one per LaTeX table environment
Figures  -> embedded images (the PDFs named by \\includegraphics, rasterised)
Refs     -> parsed from manuscript.bbl (elsarticle-harv), author-year in text

Nothing scientific is altered: every number, symbol, citation and scope statement
is carried over from the source files.  Only formatting is converted.
"""
import copy
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import omml
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

BASE = r"D:\比赛\论文"
PKG = os.path.join(BASE, "paper-code")
TEX = os.path.join(PKG, "manuscript.tex")
BBL = os.path.join(PKG, "manuscript.bbl")
FIGD = os.path.join(PKG, "figures")
OUT = os.path.join(BASE, "交付", "2.1版本", "论文_EN_2.1版本_投稿用.docx")
WORK = os.path.join(BASE, "paper-code", "tools", "docx_build", "_work")
IMGDIR = os.path.join(WORK, "img")
TEXTW = 16.0                      # cm of usable text width (A4, 2.5 cm margins)
BODY_PT = 10.0
TABLE_PT = 8.0
NOTE_PT = 7.0

# --------------------------------------------------------------------------- #
# author identity (real values; the tex author block is a public-repo placeholder)
# --------------------------------------------------------------------------- #
sys.path.insert(0, PKG)
from author_local import (AFFIL_EN, AUTHOR_EN, AUTHOR_EN_DISPLAY, CREDIT_EN,
                          EMAIL, ORCID)


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #
def read(p):
    return io.open(p, encoding="utf-8").read()


def strip_comments(s):
    out = []
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c == "\\" and i + 1 < n:
            out.append(s[i:i + 2]); i += 2; continue
        if c == "%":
            while i < n and s[i] != "\n":
                i += 1
            continue
        out.append(c); i += 1
    return "".join(out)


def norm_ws(s):
    """Collapse source line wrapping, keeping control escapes intact."""
    s = re.sub(r"[ \t]*\n[ \t]*", " ", s)
    return re.sub(r"[ \t]{2,}", " ", s).strip()


# --------------------------------------------------------------------------- #
# inline LaTeX -> pieces
#   ('text', str, style)  |  ('math', latex)  |  ('scr', 'sup'|'sub', text)
#   style = {'i':bool,'b':bool,'mono':bool,'sup':bool,'sub':bool}
# --------------------------------------------------------------------------- #
STYLE0 = {"i": False, "b": False, "mono": False, "sup": False, "sub": False}


def st(**kw):
    d = dict(STYLE0)
    d.update(kw)
    return d


SIZE_CMDS = {"small", "footnotesize", "scriptsize", "tiny", "normalsize",
             "large", "Large", "LARGE", "huge", "Huge"}
DROP_CMDS = SIZE_CMDS | {"centering", "noindent", "protect", "toprule",
                         "midrule", "bottomrule", "hline", "vspace",
                         "setlength", "tabcolsep", "linewidth", "label",
                         "nonumber", "appendix", "bibliographystyle",
                         "addlinespace", "raggedright", "sloppy", "ignorespaces",
                         "unskip", "relax", "leavevmode"}
SIMPLE_ESC = {"%": "%", "&": "&", "_": "_", "#": "#", "$": "$", "{": "{",
              "}": "}", " ": " ", ",": " ", ";": " ", ":": " ", "!": ""}
CMD_CHAR = {"%": "%", "&": "&", "_": "_", "#": "#", "$": "$",
            "{": "{", "}": "}", " ": " ", ",": " ", ";": " ", ":": " ",
            "-": "", "!": ""}


def find_group(s, i):
    """s[i] must be '{'; return (content, index_after)."""
    assert s[i] == "{"
    depth = 0
    j = i
    while j < len(s):
        if s[j] == "\\":
            j += 2; continue
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
        j += 1
    raise ValueError("unbalanced braces: %r" % s[i:i + 60])


def parse_inline(s, style=None, ctx=None, stats=None):
    """Convert a LaTeX text fragment into a flat list of pieces."""
    style = style or STYLE0
    if stats is None:
        stats = {}
    out = []
    i, n = 0, len(s)

    def add_text(t):
        if t:
            out.append(("text", t, style))

    while i < n:
        c = s[i]
        if c == "\\":
            if i + 1 >= n:
                break
            nxt = s[i + 1]
            if nxt in CMD_CHAR:                       # \% \& \_ \{ \} \, \  \-
                add_text(CMD_CHAR[nxt]); i += 2; continue
            if nxt == "\\":                            # line break -> space
                add_text(" "); i += 2; continue
            m = re.match(r"\\([A-Za-z]+)", s[i:])
            if not m:
                i += 2; continue
            cmd = m.group(1)
            i += len(cmd) + 1
            if cmd in ("emph", "textit", "itshape", "textsl"):
                arg, i = _arg_or_word(s, i)
                out.extend(parse_inline(arg, st(i=True, b=style["b"],
                                                mono=style["mono"]), ctx, stats))
                continue
            if cmd in ("textbf", "bfseries", "bf"):
                arg, i = _arg_or_word(s, i)
                out.extend(parse_inline(arg, st(b=True, i=style["i"],
                                                mono=style["mono"]), ctx, stats))
                continue
            if cmd in ("texttt", "tt", "url", "path", "nolinkurl"):
                arg, i = _arg_or_word(s, i)
                out.extend(parse_inline(arg, st(mono=True), ctx, stats))
                continue
            if cmd in ("textrm", "textnormal", "text", "mathrm", "mbox",
                       "hbox", "textup", "mbox"):
                arg, i = _arg_or_word(s, i)
                out.extend(parse_inline(arg, style, ctx, stats))
                continue
            if cmd in ("textsuperscript", "textsuperscript"):
                arg, i = _arg_or_word(s, i)
                out.extend(parse_inline(arg, st(sup=True), ctx, stats))
                continue
            if cmd == "textsubscript":
                arg, i = _arg_or_word(s, i)
                out.extend(parse_inline(arg, st(sub=True), ctx, stats))
                continue
            if cmd in ("citep", "cite", "citealp", "citep", "citeauthor",
                       "citeyear", "citeyearpar", "citet", "citealt", "cite"):
                keys, i = _cite_keys(s, i)
                out.append(("cite", cmd, keys, None))
                continue
            if cmd == "citet":
                keys, i = _cite_keys(s, i)
                out.append(("cite", "citet", keys, None))
                continue
            if cmd in ("ref", "eqref", "autoref", "subref", "pageref", "nameref"):
                arg, i = _arg_or_word(s, i)
                out.append(("ref", arg.strip()))
                continue
            if cmd in ("href",):
                first, i = _arg_or_word(s, i)
                second, i = _arg_or_word(s, i)
                out.extend(parse_inline(second or first, style, ctx, stats))
                continue
            if cmd in ("doi",):
                arg, i = _arg_or_word(s, i)
                add_text(arg)
                continue
            if cmd in ("SI", "qty"):
                arg, i = _arg_or_word(s, i)
                add_text(arg)
                continue
            if cmd in ("label", "index", "footnote", "protect"):
                if i < n and s[i] == "{":
                    _, i = find_group(s, i)
                continue
            if cmd in DROP_CMDS:
                if i < n and s[i] == "{":
                    _, i = find_group(s, i)
                continue
            if cmd == "begin" or cmd == "end":
                if i < n and s[i] == "{":
                    _, i = find_group(s, i)
                continue
            if cmd in ("quad", "qquad", "enspace", "space"):
                add_text(" ")
                continue
            if cmd in ("newline", "linebreak", "clearpage", "newpage", "par"):
                add_text(" ")
                continue
            if cmd in ("sep",):
                add_text("; ")
                continue
            if cmd in ("copyright",):
                add_text("\u00a9")
                continue
            if cmd in ("textendash",):
                add_text("\u2013"); continue
            if cmd in ("textemdash",):
                add_text("\u2014"); continue
            if cmd in ("ldots", "dots"):
                add_text("\u2026"); continue
            # a bare command inside text: keep its spelling so nothing vanishes
            stats[cmd] = stats.get(cmd, 0) + 1
            add_text(cmd)
            continue
        if c == "$":
            j = i + 1
            while j < n:
                if s[j] == "\\":
                    j += 2; continue
                if s[j] == "$":
                    break
                j += 1
            latex = s[i + 1:j]
            out.append(("math", latex))
            i = j + 1
            continue
        if c == "{":
            content, i = find_group(s, i)
            if content.strip() == ",":
                add_text(",")
            else:
                out.extend(parse_inline(content, style, ctx, stats))
            continue
        if c == "}":
            i += 1; continue
        if c == "~":
            add_text(" "); i += 1; continue
        if s.startswith("---", i):
            add_text("\u2014"); i += 3; continue
        if s.startswith("--", i):
            add_text("\u2013"); i += 2; continue
        if c in "&":
            add_text("&"); i += 1; continue
        add_text(c); i += 1
    return _merge_text(out)


def _merge_text(pieces):
    """Coalesce adjacent text pieces that share a style (one run per word/sentence)."""
    merged = []
    for p in pieces:
        if (p[0] == "text" and merged and merged[-1][0] == "text"
                and merged[-1][2] == p[2]):
            merged[-1] = ("text", merged[-1][1] + p[1], p[2])
        else:
            merged.append(p)
    return merged


def _arg_or_word(s, i):
    if i < len(s) and s[i] == "{":
        return find_group(s, i)
    m = re.match(r"\s*([A-Za-z])", s[i:])
    if m:
        return m.group(1), i + m.end()
    return "", i


def _cite_keys(s, i):
    m = re.match(r"\s*(?:\[[^\]]*\])*\s*\{([^}]*)\}", s[i:])
    if not m:
        return [], i
    return [k.strip() for k in m.group(1).split(",") if k.strip()], i + m.end()


# --------------------------------------------------------------------------- #
# numbering maps
# --------------------------------------------------------------------------- #
class Numbering:
    def __init__(self):
        self.label = {}          # label -> display text
        self.fig = {}            # label -> int
        self.tab = {}
        self.sec = {}
        self.by_pos = {}         # match start -> heading number text
        self.cur_letter = None   # appendix letter while inside \appendix
        self.n_fig = 0
        self.n_tab = 0
        self.n_sec = 0
        self.n_app = 0
        self.n_sub = 0
        self.in_appendix = False


def assign_numbers(body):
    """Walk the body once and assign figure/table/section numbers."""
    num = Numbering()
    toks = SPECIAL.finditer(body)
    for m in toks:
        t = m.group(0)
        if t.startswith("\\appendix"):
            num.in_appendix = True
        elif t.startswith("\\section"):
            starred = t.startswith("\\section*")
            if starred:
                num.n_sub = 0
            else:
                if num.in_appendix:
                    num.n_app += 1
                    letter = chr(ord("A") + num.n_app - 1)
                    num.cur_letter = letter
                    num.cur_sec = "Appendix " + letter
                    num.sub_prefix = letter
                else:
                    num.n_sec += 1
                    num.cur_sec = str(num.n_sec)
                    num.sub_prefix = str(num.n_sec)
                num.n_sub = 0
            lab = _label_of(t) or _label_after(body, m.end())
            if lab and not starred:
                num.label[lab] = num.cur_sec
            num.by_pos[m.start()] = "" if starred else num.cur_sec
        elif t.startswith("\\subsection"):
            num.n_sub += 1
            parent = getattr(num, "sub_prefix", "1")
            txt = "%s.%d" % (parent, num.n_sub)
            lab = _label_of(t) or _label_after(body, m.end())
            if lab:
                num.label[lab] = txt
            num.by_pos[m.start()] = txt
        elif t.startswith("\\begin{figure}"):
            num.n_fig += 1
            lab = _label_of(t)
            if lab:
                num.fig[lab] = num.n_fig
                num.label[lab] = ("%s.%d" % (num.cur_letter, num.n_fig)
                                  if num.in_appendix else str(num.n_fig))
        elif t.startswith("\\begin{table}"):
            num.n_tab += 1
            lab = _label_of(t)
            if lab:
                num.tab[lab] = num.n_tab
                num.label[lab] = ("%s.%d" % (num.cur_letter, num.n_tab)
                                  if num.in_appendix else str(num.n_tab))
    return num


def _label_after(body, end, window=400):
    """Sectioning commands carry their \\label on the following line."""
    m = re.match(r"[\s]*\\label\{([^}]*)\}", body[end:end + window])
    return m.group(1) if m else None


def _label_of(block):
    m = re.search(r"\\label\{([^}]*)\}", block)
    return m.group(1) if m else None


# --------------------------------------------------------------------------- #
# bibliography (from manuscript.bbl)
# --------------------------------------------------------------------------- #
class Bib:
    def __init__(self, bbl_text):
        self.entries = []        # (key, label, pieces)
        self.label = {}          # key -> in-text author-year label
        self.order = []          # keys in reference-list order
        self._parse(bbl_text)

    def _parse(self, s):
        s = strip_comments(s)
        chunks = re.split(r"\\bibitem", s)[1:]
        for ch in chunks:
            m = re.match(r"\s*(?:\[(?P<opt>.*?)\])?\s*\{(?P<key>[^}]*)\}(?P<body>.*)", ch, re.S)
            if not m:
                continue
            key = m.group("key").strip()
            opt = m.group("opt") or ""
            body = m.group("body")
            body = body.split("\\end{thebibliography}")[0]
            self.label[key] = self._label_from_opt(opt, key)
            self.order.append(key)
            self.entries.append((key, self.label[key], self._render_entry(body)))

    @staticmethod
    def _label_from_opt(opt, key):
        opt = opt.strip()
        if not opt:
            return key
        m = re.match(r"^(.*?)\((\d{4}[a-z]?)\)", opt, re.S)
        if m:
            name = clean_bib_text(m.group(1)).strip()
            year = m.group(2)
            return ("%s %s" % (name, year)).strip()
        return clean_bib_text(opt).strip()

    def _render_entry(self, body):
        body = re.sub(r"\\newblock", " ", body)
        body = re.sub(r"\\bibinfo\{[^}]*\}\{", "", body)     # keep the value
        body = body.replace("\\DOIprefix", "doi:")
        body = body.replace("\\URLprefix", "URL: ")
        body = body.replace("\\Pubmedprefix", "pmid: ")
        body = body.replace("\\ArXivprefix", "arXiv: ")
        body = re.sub(r"\\(?:bibfnamefont|bibnamefont|emph|textit|path)\b", "", body)
        body = re.sub(r"\\(?:url|href|doi)\{([^{}]*)\}", r"\1", body)
        body = body.replace("\\&", "&").replace("\\%", "%").replace("\\_", "_")
        body = re.sub(r"\s+", " ", body).strip()
        return parse_inline(body)

    def cite(self, keys, cmd="citep"):
        labs = [self.label.get(k, k) for k in keys]
        if cmd == "citet" and labs:
            return labs[0]
        return "(" + "; ".join(labs) + ")"


def clean_bib_text(t):
    t = re.sub(r"\\[A-Za-z]+\*?", "", t)
    t = t.replace("{", "").replace("}", "")
    t = t.replace("~", " ").replace("\\&", "&")
    t = re.sub(r"\s+", " ", t)
    return t


# --------------------------------------------------------------------------- #
# table parsing
# --------------------------------------------------------------------------- #
def split_cells(row):
    """Split a tabular row on & at brace depth 0."""
    cells, depth, cur, i = [], 0, [], 0
    while i < len(row):
        ch = row[i]
        if ch == "\\":
            cur.append(row[i:i + 2]); i += 2; continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        if ch == "&" and depth == 0:
            cells.append("".join(cur)); cur = []; i += 1; continue
        cur.append(ch); i += 1
    cells.append("".join(cur))
    return [c.strip() for c in cells]


SENT_RE = re.compile(r"\[\[M:([a-z]+)(?::([0-9\-]*))?\]\]")


def _mark_rules(body):
    body = body.replace("\\toprule", "[[M:top]]")
    body = body.replace("\\bottomrule", "[[M:bot]]")
    body = body.replace("\\midrule", "[[M:mid]]")
    return re.sub(r"\\cmidrule(?:\([^)]*\))?\{([^}]*)\}",
                  lambda m: "[[M:cmid:%s]]" % m.group(1), body)


def _classify(m):
    kind = m.group(1)
    return (kind, m.group(2))


def parse_tabular(spec, body):
    """Return (rows, ncol); rows = [(cells, [(rule_kind, arg), ...]), ...].

    A rule that sits before a row's content belongs to the *previous* row (that
    is what LaTeX means by a rule between two rows)."""
    ncol = len(parse_colspec(spec))
    body = _mark_rules(body)
    parts = re.split(r"(?<!\\)\\\\", body)
    rows = []
    for part in parts:
        ms = list(SENT_RE.finditer(part))
        starts = {m.start(): m for m in ms}
        content = SENT_RE.sub("", part)
        first_content = None
        i = 0
        while i < len(part):
            if part[i].isspace():
                i += 1; continue
            if i in starts:
                i = starts[i].end(); continue
            first_content = i
            break
        if content.strip():
            leading = [m for m in ms if first_content is not None and m.start() < first_content]
            trailing = [m for m in ms if not (first_content is not None and m.start() < first_content)]
            if rows:
                rows[-1][1].extend(_classify(m) for m in leading)
            rows.append((split_cells(content), [_classify(m) for m in trailing]))
        else:
            if rows:
                rows[-1][1].extend(_classify(m) for m in ms)
    return rows, ncol


def parse_colspec(spec):
    """Return list of (align, width_cm_or_None)."""
    cols, i = [], 0
    while i < len(spec):
        c = spec[i]
        if c in "lcr":
            cols.append((c, None)); i += 1; continue
        if c in "pmb":
            m = re.match(r"[pmb]\{([\d.]+)\\?(?:cm|mm|pt|textwidth)\}", spec[i:])
            if m:
                v = float(m.group(1))
                if "mm" in m.group(0):
                    v /= 10.0
                elif "pt" in m.group(0):
                    v = v * 2.54 / 72.0
                elif "textwidth" in m.group(0):
                    v = v * TEXTW
                cols.append((c, v))
                i += m.end(); continue
            i += 1; continue
        if c == "@":
            if i + 1 < len(spec) and spec[i + 1] == "{":
                _, i = find_group(spec, i + 1)
                continue
            i += 1; continue
        i += 1
    return cols


def column_widths(cols, ncol):
    """Distribute the 16 cm text width over the columns."""
    fixed = sum(w for _, w in cols if w)
    flex = [k for k, (a, w) in enumerate(cols) if not w]
    if not flex:
        total = fixed or 1.0
        return [TEXTW * w / total for _, w in cols]
    avail = max(TEXTW - fixed, 1.0)
    return [w if w else avail / len(flex) for _, w in cols]


# --------------------------------------------------------------------------- #
# OMML emission
# --------------------------------------------------------------------------- #
def adopt_bases(pieces):
    """km$^2$ / mm$^{-1}$: pull the preceding character in as the equation base."""
    out = list(pieces)
    for k, p in enumerate(out):
        if p[0] != "math":
            continue
        m = re.match(r"^\s*([\^_])(.*)$", p[1], re.S)
        if not m:
            continue
        kind = "sup" if m.group(1) == "^" else "sub"
        rest = m.group(2)
        j = k - 1
        while j >= 0 and out[j][0] == "text" and out[j][1] == "":
            j -= 1
        if j >= 0 and out[j][0] == "text" and out[j][1] and not out[j][1][-1].isspace():
            ch = out[j][1][-1]
            out[j] = ("text", out[j][1][:-1], out[j][2])
            esc = {"%": "\\%", "#": "\\#", "&": "\\&", "_": "\\_", "$": "\\$",
                   "{": "\\{", "}": "\\}", "~": "\\~{}", "^": "\\^{}"}.get(ch, ch)
            out[k] = ("math", esc + m.group(1) + rest)
        else:
            try:
                txt = omml.omml_text(rest)
            except Exception:
                txt = re.sub(r"[{}$]", "", rest)
            out[k] = ("scr", kind, txt)
    return out


def emit_pieces(par, pieces, size=BODY_PT, base_style=None):
    """Append pieces to a paragraph in order."""
    for p in pieces:
        if p[0] == "text":
            _, txt, style = p
            if not txt:
                continue
            r = par.add_run(txt)
            r.font.size = Pt(size)
            r.italic = bool(style["i"])
            r.bold = bool(style["b"])
            if style["mono"]:
                r.font.name = "Courier New"
            if style["sup"]:
                r.font.superscript = True
            if style["sub"]:
                r.font.subscript = True
        elif p[0] == "math":
            par._p.append(omml.omml_element(p[1]))
        elif p[0] == "scr":
            r = par.add_run(p[2])
            r.font.size = Pt(size)
            if p[1] == "sup":
                r.font.superscript = True
            else:
                r.font.subscript = True


def resolve_refs(pieces, biblio, numbering, warnings):
    """Resolve ('ref', label) and ('cite', ...) into text pieces."""
    out = []
    for p in pieces:
        if p[0] == "ref":
            lab = p[1]
            if lab in numbering.label:
                out.append(("text", numbering.label[lab], STYLE0))
            else:
                warnings.append("unresolved \\ref{%s}" % lab)
                out.append(("text", "??", STYLE0))
        elif p[0] == "cite":
            out.append(("text", biblio.cite(p[2], p[1]), STYLE0))
        else:
            out.append(p)
    return out


SPECIAL = re.compile(
    r"\\begin\{figure\}.*?\\end\{figure\}"
    r"|\\begin\{table\}.*?\\end\{table\}"
    r"|\\begin\{equation\}.*?\\end\{equation\}"
    r"|\\begin\{enumerate\}.*?\\end\{enumerate\}"
    r"|\\section\*?\{.*?\}"
    r"|\\subsection\*?\{.*?\}"
    r"|\\appendix\b"
    r"|\\bibliography\{[^}]*\}",
    re.S)

def scrub_metadata(doc, title=""):
    """Remove author-identifying and tool-identifying document properties.

    Word stores the creator/last editor in docProps/core.xml and some of this
    leaks into the exported PDF; for a double-blind submission the file must not
    carry a name (or 'python-docx') that identifies the author or the toolchain.
    """
    cp = doc.core_properties
    cp.author = ""
    cp.last_modified_by = ""
    cp.comments = ""
    cp.keywords = ""
    cp.category = ""
    cp.subject = ""
    cp.revision = 1
    if title:
        cp.title = title
    return doc
