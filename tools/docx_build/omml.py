# -*- coding: utf-8 -*-
"""LaTeX (math mode) -> OMML (Office Math Markup) converter.

Produces real, editable Word equations: the returned body is placed inside an
<m:oMath> element, so Word's equation editor can open and edit it.

The converter is deliberately closed-vocabulary: it covers exactly the commands
that occur in this manuscript (see math_inventory.py) and raises Unsupported on
anything else, so a silent partial conversion is impossible.

Design notes
------------
* Scripts bind to the immediately preceding atom, exactly as in TeX, so
  ``40.5^{\\circ}`` renders identically (the degree hangs off the "5").
* ``\\sum`` becomes m:nary with a populated operand. The following complete
  product/group belongs inside m:e, so Word never shows an empty argument box.
* An empty base with a script (``km$^2$``, ``mm$^{-1}$``) becomes m:sSup/m:sSub
  with an empty m:e.
* ASCII ``-`` and ``*`` are preserved (not mapped to U+2212/U+2217) so the text
  layer stays searchable; every other symbol maps to its Unicode glyph.
"""
import re
import xml.sax.saxutils as _sax

# --------------------------------------------------------------------------- #
# symbol tables
# --------------------------------------------------------------------------- #
GREEK = {
    "alpha": "\u03b1", "beta": "\u03b2", "gamma": "\u03b3", "delta": "\u03b4",
    "epsilon": "\u03b5", "varepsilon": "\u03b5", "zeta": "\u03b6", "eta": "\u03b7",
    "theta": "\u03b8", "iota": "\u03b9", "kappa": "\u03ba", "lambda": "\u03bb",
    "mu": "\u03bc", "nu": "\u03bd", "xi": "\u03be", "pi": "\u03c0",
    "rho": "\u03c1", "sigma": "\u03c3", "tau": "\u03c4", "upsilon": "\u03c5",
    "phi": "\u03c6", "varphi": "\u03c6", "chi": "\u03c7", "psi": "\u03c8",
    "omega": "\u03c9",
    "Gamma": "\u0393", "Delta": "\u0394", "Theta": "\u0398", "Lambda": "\u039b",
    "Xi": "\u039e", "Pi": "\u03a0", "Sigma": "\u03a3", "Phi": "\u03a6",
    "Psi": "\u03a8", "Omega": "\u03a9",
}
OPERATORS = {
    "times": "\u00d7", "pm": "\u00b1", "mp": "\u2213", "cdot": "\u22c5",
    "div": "\u00f7", "ast": "\u2217", "star": "\u22c6",
    "le": "\u2264", "leq": "\u2264", "ge": "\u2265", "geq": "\u2265",
    "ne": "\u2260", "neq": "\u2260", "approx": "\u2248", "sim": "\u223c",
    "simeq": "\u2243", "equiv": "\u2261", "propto": "\u221d",
    "in": "\u2208", "notin": "\u2209", "subset": "\u2282", "subseteq": "\u2286",
    "cup": "\u222a", "cap": "\u2229", "emptyset": "\u2205",
    "rightarrow": "\u2192", "to": "\u2192", "leftarrow": "\u2190",
    "leftrightarrow": "\u2194", "Rightarrow": "\u21d2", "mapsto": "\u21a6",
    "uparrow": "\u2191", "downarrow": "\u2193",
    "partial": "\u2202", "nabla": "\u2207", "infty": "\u221e",
    "ldots": "\u2026", "cdots": "\u22ef", "dots": "\u2026",
    "angle": "\u2220", "perp": "\u22a5", "parallel": "\u2225",
    "degree": "\u00b0", "circ": "\u00b0", "prime": "\u2032",
}
UPRIGHT_FN = {"max", "min", "ln", "log", "exp", "sin", "cos", "tan", "cot",
              "lim", "arg", "det", "mod", "gcd", "sup", "inf", "deg"}
SPACES = {",": "\u2009", ";": "\u2005", ":": "\u2005",
          "quad": "\u2003", "qquad": "\u2003\u2003"}
ACCENTS = {"hat": "\u0302", "widehat": "\u0302", "bar": "\u0304",
           "tilde": "\u0303", "widetilde": "\u0303", "dot": "\u0307",
           "ddot": "\u0308", "vec": "\u20d7"}
UPRIGHT_ARG = {"mathrm", "text", "textrm", "textnormal", "mathsf", "texttt",
               "mathbf", "mathit", "operatorname"}
DROPPED = {"label", "nonumber", "notag", "textstyle", "displaystyle",
           "limits", "nolimits", "protect", "rm", "it", "bf",
           "left.", "right."}
BIGOPS = {"sum": "\u2211", "prod": "\u220f", "int": "\u222b",
          "bigcup": "\u22c3", "bigcap": "\u22c2"}
ESCAPED_OK = set("{}%&_#$")


class Unsupported(Exception):
    pass


# --------------------------------------------------------------------------- #
# tokenizer
# --------------------------------------------------------------------------- #
def tokenize(s):
    toks = []
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c == "\\":
            nxt = s[i + 1] if i + 1 < n else ""
            if nxt == "\\":
                toks.append(("rowsep", None)); i += 2; continue
            if nxt in ESCAPED_OK:
                toks.append(("char", nxt)); i += 2; continue
            if nxt == " ":
                toks.append(("space", " ")); i += 2; continue
            if nxt in SPACES:
                toks.append(("space", SPACES[nxt])); i += 2; continue
            if nxt == "!":
                i += 2; continue
            m = re.match(r"\\([A-Za-z]+)", s[i:])
            if m:
                name = m.group(1)
                i += 1 + len(name)
                # TeX swallows white space after a control word: "\hat b" is
                # \hat{b}, not \hat{<space>}b.
                while i < n and s[i] in " \t\n":
                    i += 1
                toks.append(("cmd", name)); continue
            raise Unsupported("stray backslash in %r" % s)
        if c in "{}":
            toks.append((c, None)); i += 1; continue
        if c in "_^":
            toks.append((c, None)); i += 1; continue
        if c == "&":
            toks.append(("amp", None)); i += 1; continue
        if c == "'":
            toks.append(("prime", None)); i += 1; continue
        if c in " \t\n":
            toks.append(("space", " ")); i += 1; continue
        toks.append(("char", c)); i += 1
    return toks


# --------------------------------------------------------------------------- #
# parser:  atom = {"nodes":[node,...], "sub":[node,...]|None, "sup":[...]|None}
# --------------------------------------------------------------------------- #
def _parse_group(toks, i):
    """Parse one {...} group, or a single atom, starting at index i."""
    if i < len(toks) and toks[i][0] == "{":
        atoms, i = _parse_seq(toks, i + 1, stop={"}"})
        if i < len(toks) and toks[i][0] == "}":
            i += 1
        return atoms, i
    return _parse_seq(toks, i, max_atoms=1)


def _parse_seq(toks, i, stop=(), max_atoms=None):
    atoms = []
    while i < len(toks):
        k, v = toks[i]
        if k == "}":
            break
        if k == "amp" and "amp" in stop:
            break
        if k == "rowsep" and "rowsep" in stop:
            break
        if k == "cmd" and v in stop:
            break
        if max_atoms is not None and len(atoms) >= max_atoms:
            break

        add = []          # atoms contributed by this token
        node = None       # single node contributed by this token

        if k == "cmd":
            if v in DROPPED:
                if i + 1 < len(toks) and toks[i + 1][0] == "{":
                    _, i = _parse_group(toks, i + 1)
                else:
                    i += 1
                continue
            if v in ("frac", "dfrac", "tfrac", "cfrac"):
                num, i = _parse_group(toks, i + 1)
                den, i = _parse_group(toks, i)      # i already sits after num
                node = ("frac", num, den)
            elif v == "sqrt":
                arg, i = _parse_group(toks, i + 1)
                node = ("sqrt", arg)
            elif v in UPRIGHT_ARG:
                arg, i = _parse_group(toks, i + 1)
                node = ("upnodes", arg)
            elif v in ACCENTS:
                arg, i = _parse_group(toks, i + 1)
                node = ("acc", ACCENTS[v], arg)
            elif v in BIGOPS:
                node = ("bigop", BIGOPS[v]); i += 1
            elif v == "left":
                i += 1
                beg = ""
                if i < len(toks) and toks[i][0] in ("char", "space"):
                    beg = toks[i][1]; i += 1
                inner, i = _parse_seq(toks, i, stop={"right"})
                end = ""
                if i < len(toks) and toks[i] == ("cmd", "right"):
                    i += 1
                    if i < len(toks) and toks[i][0] in ("char", "space"):
                        end = toks[i][1]; i += 1
                if beg == ".":
                    beg = ""
                if end == ".":
                    end = ""
                node = ("delim", beg, end, inner)
            elif v == "right":
                raise Unsupported("\\right without \\left")
            elif v in GREEK:
                node = ("run", GREEK[v]); i += 1
            elif v in OPERATORS:
                node = ("run", OPERATORS[v]); i += 1
            elif v in UPRIGHT_FN:
                node = ("up", v); i += 1
            elif v in SPACES:
                node = ("space", SPACES[v]); i += 1
            elif v in ("begin", "end"):
                raise Unsupported("\\%s{...} must be handled before parsing" % v)
            else:
                raise Unsupported("unknown command \\%s" % v)
        elif k == "prime":
            # a prime is a superscript on the previous atom (x'_{ij})
            prime_atom = {"nodes": [("run", "\u2032")], "sub": None, "sup": None}
            if not atoms:
                atoms.append({"nodes": [], "sub": None, "sup": [("run", "\u2032")]})
            else:
                a = atoms[-1]
                a["sup"] = (a["sup"] or []) + [prime_atom]
            i += 1
            continue
        elif k in ("char", "space"):
            node = ("run" if k == "char" else "space", v); i += 1
        elif k == "{":
            grp, i = _parse_group(toks, i)
            add = grp
        elif k in ("_", "^"):
            if not atoms:
                atoms.append({"nodes": [], "sub": None, "sup": None})
            arg, i = _parse_group(toks, i + 1)
            a = atoms[-1]
            key = "sub" if k == "_" else "sup"
            a[key] = (a[key] or []) + arg
            continue
        else:
            raise Unsupported("unexpected token %r" % (k,))

        if node is not None:
            add = [{"nodes": [node], "sub": None, "sup": None}]
        atoms.extend(add)
    return atoms, i


# --------------------------------------------------------------------------- #
# renderer
# --------------------------------------------------------------------------- #
def _e(t):
    return _sax.escape(t, {'"': "&quot;"})


def _run(text, upright=False):
    if not text:
        return ""
    pr = '<m:rPr><m:sty m:val="p"/></m:rPr>' if upright else ""
    return '<m:r>%s<m:t xml:space="preserve">%s</m:t></m:r>' % (pr, _e(text))


def _flat_text(atoms):
    out = []
    for a in atoms:
        for nd in a["nodes"]:
            t = nd[0]
            if t in ("run", "space", "up"):
                out.append(nd[1])
            elif t == "upnodes":
                out.append(_flat_text(nd[1]))
            else:
                raise Unsupported("non-literal inside a text group: %r" % (t,))
    return "".join(out)


def _render_node(nd, display):
    t = nd[0]
    if t == "run":
        return _run(nd[1])
    if t == "up":
        return _run(nd[1], upright=True)
    if t == "upnodes":
        return _run(_flat_text(nd[1]), upright=True)
    if t == "space":
        return _run(nd[1])
    if t == "frac":
        return "<m:f><m:num>%s</m:num><m:den>%s</m:den></m:f>" % (
            _render_atoms(nd[1], display), _render_atoms(nd[2], display))
    if t == "sqrt":
        return ('<m:rad><m:radPr><m:degHide m:val="1"/></m:radPr><m:deg/>'
                '<m:e>%s</m:e></m:rad>' % _render_atoms(nd[1], display))
    if t == "acc":
        return ('<m:acc><m:accPr><m:chr m:val="%s"/></m:accPr><m:e>%s</m:e></m:acc>'
                % (_e(nd[1]), _render_atoms(nd[2], display)))
    if t == "delim":
        beg, end, inner = nd[1], nd[2], nd[3]
        return ('<m:d><m:dPr><m:begChr m:val="%s"/><m:endChr m:val="%s"/>'
                '<m:grow m:val="1"/></m:dPr><m:e>%s</m:e></m:d>'
                % (_e(beg), _e(end), _render_atoms(inner, display)))
    if t == "mat":
        return _render_mat(nd[1], display)
    raise Unsupported("cannot render node %r" % (t,))


def _render_mat(rows, display):
    cols = max(len(r) for r in rows)
    out = ['<m:m><m:mPr><m:mcs>']
    for _ in range(cols):
        out.append('<m:mc><m:mcPr><m:count m:val="1"/><m:mcJc m:val="left"/>'
                   '</m:mcPr></m:mc>')
    out.append('</m:mcs></m:mPr>')
    for r in rows:
        out.append("<m:mr>")
        for c in range(cols):
            cell = r[c] if c < len(r) else []
            out.append("<m:e>%s</m:e>" % _render_atoms(cell, display))
        out.append("</m:mr>")
    out.append("</m:m>")
    return "".join(out)


def _render_atom(a, display):
    nodes, sub, sup = a["nodes"], a["sub"], a["sup"]
    if len(nodes) == 1 and nodes[0][0] == "bigop":
        op = nodes[0][1]
        lim = "undOvr" if display else "subSup"
        s = _render_atoms(sub, display) if sub else ""
        p = _render_atoms(sup, display) if sup else ""
        return ('<m:nary><m:naryPr><m:chr m:val="%s"/><m:limLoc m:val="%s"/>'
                '<m:supHide m:val="%d"/><m:subHide m:val="%d"/></m:naryPr>'
                '<m:sub>%s</m:sub><m:sup>%s</m:sup><m:e/></m:nary>'
                % (_e(op), lim, 0 if sup else 1, 0 if sub else 1, s, p))
    base = "".join(_render_node(nd, display) for nd in nodes)
    if sub and sup:
        return ("<m:sSubSup><m:e>%s</m:e><m:sub>%s</m:sub><m:sup>%s</m:sup></m:sSubSup>"
                % (base, _render_atoms(sub, display), _render_atoms(sup, display)))
    if sub:
        return ("<m:sSub><m:e>%s</m:e><m:sub>%s</m:sub></m:sSub>"
                % (base, _render_atoms(sub, display)))
    if sup:
        return ("<m:sSup><m:e>%s</m:e><m:sup>%s</m:sup></m:sSup>"
                % (base, _render_atoms(sup, display)))
    return base


def _render_atoms(atoms, display):
    return "".join(_render_atom(a, display) for a in atoms)


# --------------------------------------------------------------------------- #
# cases environment
# --------------------------------------------------------------------------- #
_CASES_RE = re.compile(r"\\begin\{cases\}(.*?)\\end\{cases\}", re.S)


def _split_rows_cols(body):
    body = re.sub(r"\\\\\s*(\[[^\]]*\])?", "\x00", body)
    rows = []
    for r in body.split("\x00"):
        if r.strip() == "":
            continue
        rows.append([c.strip() for c in r.split("&")])
    return rows


def _cell_atoms(cell):
    toks = tokenize(cell)
    atoms, i = _parse_seq(toks, 0)
    if i != len(toks):
        raise Unsupported("unparsed tokens in cases cell: %r" % cell)
    return atoms


def _convert_cases(body, display):
    rows = [[_cell_atoms(c) for c in r] for r in _split_rows_cols(body)]
    return ('<m:d><m:dPr><m:begChr m:val="{"/><m:endChr m:val=""/><m:grow m:val="1"/>'
            '</m:dPr><m:e>%s</m:e></m:d>' % _render_mat(rows, display))


# --------------------------------------------------------------------------- #
# public API
# --------------------------------------------------------------------------- #
def _parse_all(latex):
    toks = tokenize(latex)
    atoms, i = _parse_seq(toks, 0)
    if i != len(toks):
        raise Unsupported("unparsed tokens at %d/%d: %r (rest %r)"
                          % (i, len(toks), toks[i], toks[i:]))
    return atoms


def to_omml_body(latex, display=False):
    """Convert a LaTeX math fragment to the *inner* OMML body (no <m:oMath>)."""
    latex = latex.strip()
    if not latex:
        return ""
    m = _CASES_RE.search(latex)
    if m:
        pre, post = latex[:m.start()].strip(), latex[m.end():].strip()
        out = []
        if pre:
            out.append(_render_atoms(_parse_all(pre), display))
        out.append(_convert_cases(m.group(1), display))
        if post:
            out.append(_render_atoms(_parse_all(post), display))
        return "".join(out)
    return _render_atoms(_parse_all(latex), display)


M_NS = 'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"'


def fill_nary_operands(root):
    """Move a complete following term into each empty n-ary operand.

    Keep sums over products intact. Top-level punctuation, comparisons and
    additive operators terminate the operand; signs within parentheses do not.
    Moving existing nodes preserves symbols, scripts and text order exactly.
    """
    ns = 'http://schemas.openxmlformats.org/officeDocument/2006/math'
    tag = lambda name: '{%s}%s' % (ns, name)
    count = 0
    for nary in reversed(list(root.iter(tag('nary')))):
        operand = nary.find(tag('e'))
        if operand is None or len(operand):
            continue
        depth = 0
        meaningful = False
        following = nary.getnext()
        while following is not None:
            text = ''.join(following.itertext())
            literal = text.strip() if following.tag == tag('r') else ''
            if depth == 0 and literal in {',', ';', '=', '<', '>', '≤', '≥', '≠', '+', '-'} and meaningful:
                break
            if depth == 0 and literal in {')', ']', '}'}:
                break
            if literal in {'(', '[', '{'}:
                depth += 1
            elif literal in {')', ']', '}'}:
                depth -= 1
            next_node = following.getnext()
            operand.append(following)
            meaningful = meaningful or bool(text.strip())
            following = next_node
        if not meaningful:
            raise Unsupported('n-ary operator has no operand')
        count += 1
    return count


def omml_element(latex, display=False):
    """Return a lxml element for <m:oMath> ready to append to a w:p."""
    from docx.oxml import parse_xml
    body = to_omml_body(latex, display)
    element = parse_xml('<m:oMath %s>%s</m:oMath>' % (M_NS, body))
    fill_nary_operands(element)
    return element


def omml_text(latex, display=False):
    """Plain text carried by the converted math (content-preservation checks)."""
    import lxml.etree as ET
    xml = '<m:oMath %s>%s</m:oMath>' % (M_NS, to_omml_body(latex, display))
    return "".join(ET.fromstring(xml.encode("utf-8")).itertext())


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for s in sys.argv[1:]:
        print("%-44s -> %r" % (s, omml_text(s)))
        print("%-44s    %s" % ("", to_omml_body(s)))
