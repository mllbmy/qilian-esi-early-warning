# -*- coding: utf-8 -*-
r"""Generate paper-code/manuscript.bbl in Journal of Mountain Science style.

Contract (set by the Lead, 2026-10-20):
  * One \bibitem per reference, 25 items, alphabetical by first-author surname.
  * The optional in-text label keeps its short author-year form, e.g.
        \bibitem[{Harris et al.(2020)}]{cru_ts410}
    because build_word_*.py derives every "(Author Year)" in-text citation from it
    (docx_build/docxbuild_lib.py: Bib._label_from_opt).
  * The body is PLAIN text plus a few LaTeX commands only: \url{}, \&, \%, \_.
    No \bibinfo / \newblock / \DOIprefix.
  * DOIs are written as \url{https://doi.org/...} (no doi: prefix).

Style source: 规范/期刊指南/JMS_Guides_to_Authors_最新版.pdf, section 5.8
  Journal article  Viani C, Chiarle M, Paranunzio R, et al. (2020) Title in sentence
                   case. J Mt Sci 17(11): 2591-2610. https://doi.org/10.1007/...
                   ("Journal names should be in standard abbreviation"; only the first
                   three authors are indexed, then "et al.")
  Book             Shrestha TB, Joshi RM (1996) Title. Kathmandu: WWF, Nepal Program.
  Report/data set  non-article items follow the book form (place: publisher) or the
                   web-resource form for data sets.

manuscript.bib is the single source of truth: author lists, year, volume, issue, pages,
DOI and titles all come from the .bib.  The only things this script adds are (a) the
journal abbreviation (ISO-4 style, verified with Crossref short-container-title where
Crossref carries one), (b) sentence-case repair of titles that the .bib stores in Title
Case (TITLE_OVERRIDES, validated against the .bib character-for-character up to case and
punctuation), and (c) place of publication for the two books (BOOK_PLACE); nothing else
is invented.  Volume/issue/pages are emitted exactly as the .bib records them: an .bib
without a "number" field gets "vol: pages", never a guessed issue.

Usage:  python make_bbl_jms.py            # write manuscript.bbl, jms/refs_map.tsv and
                                        # jms/refs_jms.txt (plain-text mirror)
        python make_bbl_jms.py --check    # print, write nothing
"""
import argparse
import io
import os
import re
import sys
import unicodedata

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.abspath(__file__))
BIB = os.path.join(BASE, "manuscript.bib")
TEX = os.path.join(BASE, "manuscript.tex")
BBL = os.path.join(BASE, "manuscript.bbl")
MAP = os.path.join(BASE, "jms", "refs_map.tsv")

EN = "\u2013"          # en dash, as in the JMS example "2591-2610"
LIMIT = 3              # JMS: index three authors, then "et al."

# ---------------------------------------------------------------- journal names
JOURNAL_ABBREV = {
    "Ecological Indicators": "Ecol Indic",
    "Environmental Modelling & Software": "Environ Model Softw",
    "Environmental Modelling \\& Software": "Environ Model Softw",
    "Systems & Control Letters": "Syst Control Lett",
    "Systems \\& Control Letters": "Syst Control Lett",
    "Journal for Nature Conservation": "J Nat Conserv",
    "Journal of Arid Land": "J Arid Land",
    "Frontiers in Environmental Science": "Front Environ Sci",
    "Remote Sensing": "Remote Sens",
    "Ecosystem Health and Sustainability": "Ecosyst Health Sustain",
    "Columella -- Journal of Agricultural and Environmental Sciences": "Columella",
    "Columella \u2013 Journal of Agricultural and Environmental Sciences": "Columella",
    "Environmental Science and Pollution Research": "Environ Sci Pollut Res",
    "Scientific Data": "Sci Data",
    "Earth System Science Data": "Earth Syst Sci Data",
    "Journal of Physics: Conference Series": "J Phys Conf Ser",
    "Journal of Mountain Science": "J Mt Sci",
    "Biometrics": "Biometrics",
    "Spatial Statistics": "Spat Stat",
}

# ------------------------------------------- sentence case (JMS article titles)
# Only titles whose .bib wording is in Title Case; the string must match the .bib
# after lower-casing and dropping punctuation, otherwise the script refuses to run.
TITLE_OVERRIDES = {
    "jinan_land_esp_2022":
        "Spatiotemporal differentiation of land ecological security and its influencing "
        "factors: A case study in Jinan, Shandong Province, China",
    "china_ecoenv_2024":
        "Long-term dynamic monitoring and driving force analysis of eco-environmental "
        "quality in China",
    "qilian_ez_2024":
        "Integrating landscape ecological risk and ecosystem services for ecological "
        "zoning in the Qilian Mountain National Park",
    "westliaohe_esp_2026":
        "Anthropogenic activities amplify spatiotemporal variations in regional "
        "ecological security patterns dominated by natural factors: Evidence from the "
        "West Liaohe River Basin, China",
    # J. Phys. Conf. Ser. prints this title in Title Case; JMS uses sentence case.
    "althobaiti_ngbm2022":
        "Prediction of CO2 emissions in Saudi Arabia using nonlinear grey Bernoulli "
        "model NGBM(1,1) compared with GM(1,1) model",
    # report: .bib has "Living Planet Report 2020 -- Bending the curve ..."; JMS book
    # examples use a colon, never a double hyphen.
    "wwf2020living":
        "Living Planet Report 2020: Bending the curve of biodiversity loss",
}

# ------------------------------------------------------------- book / report items
# place of publication: taken from the .bib "address" field; the JMS guide requires it,
# so the two books whose .bib entry has no address get their (well-known) city here.
BOOK_PLACE = {"saaty1980analytic": "New York", "ipcc2014climate": "Cambridge"}

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]


# ============================================================ .bib parsing
def _balance(text, pos):
    """Return index of the '}' closing the '{' at pos-1 (pos points just after '{')."""
    depth = 1
    while pos < len(text):
        c = text[pos]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return pos
        pos += 1
    raise ValueError("unbalanced braces in .bib")


def parse_bib(text):
    entries = {}
    for m in re.finditer(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", text):
        start = m.end()
        end = _balance(text, start)
        entries[m.group(2)] = (m.group(1).lower(), parse_fields(text[start:end]))
    return entries


def parse_fields(body):
    fields, pos, n = {}, 0, len(body)
    while pos < n:
        m = re.compile(r"\s*(\w+)\s*=\s*", re.S).match(body, pos)
        if not m:
            break
        name, pos = m.group(1).lower(), m.end()
        if pos < n and body[pos] == "{":
            end = _balance(body, pos + 1)
            val, pos = body[pos + 1:end], end + 1
        elif pos < n and body[pos] == '"':
            end = body.index('"', pos + 1)
            val, pos = body[pos + 1:end], end + 1
        else:
            end = body.find(",", pos)
            end = n if end < 0 else end
            val, pos = body[pos:end], end
        fields[name] = " ".join(val.split())
        m2 = re.compile(r"\s*,?\s*").match(body, pos)
        pos = m2.end()
    return fields


def strip_braces(t):
    return t.replace("{", "").replace("}", "")


def dehyph(t):
    """-- / -- used as a colon in titles/reports."""
    t = re.sub(r"\s*(?:--|---)\s*", ": ", t)
    return re.sub(r"\s+", " ", t).strip()


# ============================================================ names
def split_authors(field):
    out = []
    for chunk in re.split(r"\s+and\s+", strip_braces(field)):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "," in chunk:
            sur, given = chunk.split(",", 1)
        else:
            parts = chunk.split()
            sur, given = (parts[-1], " ".join(parts[:-1])) if len(parts) > 1 else (parts[0], "")
        ini = "".join(w[0] for w in re.findall(r"[A-Za-z\u00C0-\u024F]+", given))
        out.append((sur.strip(), ini.upper() if ini else ""))
    return out


def author_block(auths):
    """JMS: 'Wang JF, Zhang TL, Fu BJ' + ', et al.' when more than three authors."""
    shown = auths[:LIMIT]
    s = ", ".join(("%s %s" % (sur, ini)).strip() for sur, ini in shown)
    if len(auths) > LIMIT:
        s += ", et al."
    return s


def cite_label(auths, year):
    """Short natbib label: the exact in-text '(Author Year)' string the Word build reads."""
    n = len(auths)
    if n == 1:
        head = auths[0][0]
    elif n == 2:
        head = "%s and %s" % (auths[0][0], auths[1][0])
    else:
        head = "%s et al." % auths[0][0]
    return "%s(%s)" % (head, year)


# ============================================================ titles
def norm_title(t):
    """Comparison key: letters+digits only, lower case."""
    t = strip_braces(t).lower()
    return re.sub(r"[^0-9a-z]+", "", t)


def title_of(key, f):
    raw = " ".join(strip_braces(f.get("title", "")).split())
    if key in TITLE_OVERRIDES:
        new = TITLE_OVERRIDES[key]
        if norm_title(new) != norm_title(raw):
            raise SystemExit("TITLE_OVERRIDES[%s] does not match manuscript.bib\n"
                             "  bib : %s\n  over: %s" % (key, raw, new))
        return new
    return dehyph(raw) if " -- " in raw else raw


# ============================================================ rendering
def render_article(key, f, auths, year):
    journal = " ".join(f.get("journal", "").split())
    j = JOURNAL_ABBREV.get(journal)
    if not j:
        raise SystemExit("no journal abbreviation registered for %r (key %s); add it to "
                         "JOURNAL_ABBREV -- do not invent one" % (journal, key))
    vol = f.get("volume", "").strip()
    num = f.get("number", "").strip()
    pages = re.sub(r"\s*(?:--|---)\s*", EN, f.get("pages", "").strip())
    loc = "%s(%s)" % (vol, num) if num else vol
    if pages:
        loc += ": " + pages
    body = "%s (%s) %s. %s %s." % (author_block(auths), year, title_of(key, f), j, loc)
    doi = f.get("doi", "").strip()
    if doi:
        body += r" \url{https://doi.org/%s}" % doi
    return body


def render_booklike(key, f, auths, year, kind):
    title = title_of(key, f)
    if kind == "techreport":
        pub = f.get("institution") or f.get("publisher", "")
        place = f.get("address", "") or BOOK_PLACE.get(key, "")
    else:  # book
        pub = f.get("publisher", "")
        place = f.get("address", "") or BOOK_PLACE.get(key, "")
    pub, place = " ".join(pub.split()), " ".join(place.split())
    # JMS book example: "Shrestha TB, Joshi RM (1996) Title. Kathmandu: WWF, Nepal Program."
    where = "%s: %s" % (place, pub) if place else pub
    edition = (", %s edn" % f["edition"]) if f.get("edition") else ""
    body = "%s (%s) %s%s. %s." % (author_block(auths), year, title, edition, where)
    if f.get("url"):
        body += r" \url{%s}" % f["url"]
        acc = re.search(r"accessed\s+(\d{4})-(\d{2})-(\d{2})", f.get("note", ""))
        if acc:
            y, mo, d = map(int, acc.groups())
            body += " (Accessed on %d %s %d)" % (d, MONTHS[mo - 1], y)
    return body


def render_dataset(key, f, auths, year):
    """@misc data set: JMS web-resource form (title, host, DOI, access date)."""
    title = title_of(key, f)
    note = " ".join(f.get("note", "").split())
    ver = re.search(r"version\s+([0-9][0-9A-Za-z.\-]*)", note, re.I)
    host = f.get("publisher") or f.get("howpublished", "")
    host = " ".join(host.split())
    desc = "%s data set" % host if host else "data set"
    if ver:
        desc += ", version %s" % ver.group(1).rstrip(".")
    body = "%s (%s) %s. %s." % (author_block(auths), year, title, desc)
    doi = f.get("doi", "").strip()
    if doi:
        body += r" \url{https://doi.org/%s}" % doi
    acc = re.search(r"accessed\s+(\d{4})-(\d{2})-(\d{2})", note)
    if acc:
        y, mo, d = int(acc.group(1)), int(acc.group(2)), int(acc.group(3))
        body += " (Accessed on %d %s %d)" % (d, MONTHS[mo - 1], y)
    return body


def render(key, kind, f):
    if "author" not in f:
        raise SystemExit("entry %s has no author field" % key)
    auths = split_authors(f["author"])
    year = f.get("year", "").strip()
    if kind == "article":
        return render_article(key, f, auths, year)
    if kind in ("book",):
        return render_booklike(key, f, auths, year, "book")
    if kind in ("techreport", "report", "manual"):
        return render_booklike(key, f, auths, year, "techreport")
    if kind in ("misc", "online", "dataset"):
        return render_dataset(key, f, auths, year)
    raise SystemExit("unhandled bib entry type %r for key %s" % (kind, key))


# ============================================================ keys cited in .tex
def cited_keys(tex_path):
    with io.open(tex_path, encoding="utf-8") as fh:
        tex = fh.read()
    keys = []
    for m in re.finditer(r"\\cite[pt]?\*?(?:\[[^\]]*\])*\{([^}]*)\}", tex):
        for k in m.group(1).split(","):
            k = k.strip()
            if k and k not in keys:
                keys.append(k)
    return keys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="print the .bbl, write nothing")
    args = ap.parse_args()

    with io.open(BIB, encoding="utf-8") as fh:
        bib = parse_bib(fh.read())
    cited = cited_keys(TEX)
    missing = [k for k in cited if k not in bib]
    if missing:
        raise SystemExit("cited but absent from manuscript.bib: %s" % ", ".join(missing))
    uncited = sorted(set(bib) - set(cited))
    if uncited:
        print("WARNING: %d .bib entries are never cited and are left out: %s"
              % (len(uncited), ", ".join(uncited)))

    rows = []
    for key in cited:
        kind, f = bib[key]
        auths = split_authors(f["author"])
        year = f.get("year", "").strip()
        rows.append({
            "key": key,
            "kind": kind,
            "surname": unicodedata.normalize("NFKD", auths[0][0]).encode("ascii", "ignore").decode() or auths[0][0],
            "initials": auths[0][1],
            "year": year,
            "label": cite_label(auths, year),
            "text": render(key, kind, f),
            "journal": JOURNAL_ABBREV.get(" ".join(f.get("journal", "").split()), ""),
            "vol": f.get("volume", "").strip(),
            "num": f.get("number", "").strip(),
            "pages": re.sub(r"\s*(?:--|---)\s*", EN, f.get("pages", "").strip()),
            "doi": f.get("doi", "").strip(),
        })

    rows.sort(key=lambda r: (r["surname"].lower(), r["initials"], r["year"]))

    out = ["% Auto-generated by make_bbl_jms.py -- Journal of Mountain Science style.",
           "% Source of truth: manuscript.bib.  Do not edit by hand; re-run the script.",
           r"\begin{thebibliography}{%d}" % len(rows),
           r"\def\UrlBreaks{\do\/\do\-}\def\UrlBigBreaks{\do\/}"]
    for r in rows:
        out.append(r"\bibitem[{%s}]{%s}" % (r["label"], r["key"]))
        out.append(r["text"])
        out.append("")
    out.append(r"\end{thebibliography}")
    bbl = "\n".join(out) + "\n"

    if args.check:
        print(bbl)
    else:
        with io.open(BBL, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(bbl)
        os.makedirs(os.path.dirname(MAP), exist_ok=True)
        with io.open(MAP, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("key\tfirst_author_year\tjournal_abbrev\tvolume_issue_pages\tdoi\t"
                     "rendered_line\n")
            for r in rows:
                fh.write("%s\t%s\t%s\t%s\t%s\t%s\n" % (
                    r["key"], r["label"], r["journal"],
                    ("%s(%s): %s" % (r["vol"], r["num"], r["pages"]) if r["num"]
                     else ("%s: %s" % (r["vol"], r["pages"]) if r["pages"] else r["vol"])),
                    r["doi"], r["text"]))
        # plain-text mirror for the Word reference list (no LaTeX commands)
        with io.open(os.path.join(BASE, "jms", "refs_jms.txt"), "w",
                     encoding="utf-8", newline="\n") as fh:
            for r in rows:
                t = re.sub(r"\\url\{([^}]*)\}", r"\1", r["text"])
                t = (t.replace("$_2$", "2").replace("\\&", "&")
                      .replace("\\_", "_").replace("\\%", "%"))
                fh.write(t + "\n")
        print("wrote %s (%d entries, %d chars)" % (BBL, len(rows), len(bbl)))
        print("wrote %s" % MAP)
        print("wrote %s" % os.path.join(BASE, "jms", "refs_jms.txt"))

    for r in rows:
        print("  %-30s %-22s %s" % (r["key"], r["label"], r["text"][:90]))


if __name__ == "__main__":
    main()
