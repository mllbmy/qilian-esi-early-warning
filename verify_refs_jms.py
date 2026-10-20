# -*- coding: utf-8 -*-
r"""Self-check for the JMS reference list (paper-code/manuscript.bbl).

Independent of make_bbl_jms.py on purpose: it re-parses manuscript.bib, manuscript.tex
and the generated .bbl and re-derives every expectation, so the generator cannot grade
its own homework.

Checks
  1  reference count is 25 and the key set equals the \citep keys used in the .tex
  2  the optional \bibitem[...] label is the short "(Author Year)" form the Word build
     reads, and it agrees with the .bib (first surname, author-count rule, year)
  3  author blocks index at most three authors, then ", et al."
  4  journal names are the registered standard abbreviations (no full names, no dots)
  5  every DOI is \url{https://doi.org/...}, matches the .bib DOI, and no "doi:" prefix
  6  no \bibinfo / \newblock / \DOIprefix / \href machinery left in the bodies
  7  volume / issue / pages appear exactly as recorded in manuscript.bib
  8  punctuation: DOI items end on the \url, non-DOI items end with a full stop
  9  alphabetical order by first-author surname
 10  jms/refs_map.tsv has a header plus 25 rows in the same order as the .bbl
 11  sentence case in article titles (warning only; proper nouns are allowed)
 12  no stray LaTeX (~, doubled spaces, unbalanced braces, "..", "et al..")

Exit code 0 = all checks pass (warnings do not fail).

Usage: python verify_refs_jms.py [-v]
"""
import io
import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.abspath(__file__))
BIB = os.path.join(BASE, "manuscript.bib")
BBL = os.path.join(BASE, "manuscript.bbl")
TEX = os.path.join(BASE, "manuscript.tex")
MAP = os.path.join(BASE, "jms", "refs_map.tsv")

EN = "\u2013"
N = 25

JMS_ABBREV = {
    "Ecological Indicators": "Ecol Indic",
    "Environmental Modelling & Software": "Environ Model Softw",
    "Systems & Control Letters": "Syst Control Lett",
    "Journal for Nature Conservation": "J Nat Conserv",
    "Journal of Arid Land": "J Arid Land",
    "Frontiers in Environmental Science": "Front Environ Sci",
    "Remote Sensing": "Remote Sens",
    "Ecosystem Health and Sustainability": "Ecosyst Health Sustain",
    "Columella -- Journal of Agricultural and Environmental Sciences": "Columella",
    "Environmental Science and Pollution Research": "Environ Sci Pollut Res",
    "Scientific Data": "Sci Data",
    "Earth System Science Data": "Earth Syst Sci Data",
    "Journal of Physics: Conference Series": "J Phys Conf Ser",
    "Journal of Mountain Science": "J Mt Sci",
}
ALLOWED = set(JMS_ABBREV.values())
FULL_NAMES = sorted({k for k in JMS_ABBREV}, key=len, reverse=True)

STOPWORDS = {"Of", "The", "And", "For", "From", "With", "In", "On", "At", "To",
             "As", "By", "Its", "That", "This", "Is", "Are"}

fails, warns = [], []


def fail(check, msg):
    fails.append("[FAIL] %s: %s" % (check, msg))


def warn(check, msg):
    warns.append("[warn] %s: %s" % (check, msg))


# ------------------------------------------------------------------ inputs
def rd(path):
    with io.open(path, encoding="utf-8") as fh:
        return fh.read()


def parse_bib(text):
    entries = {}
    for m in re.finditer(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", text):
        depth, pos = 1, m.end()
        while pos < len(text) and depth:
            depth += {"{": 1, "}": -1}.get(text[pos], 0)
            pos += 1
        body = text[m.end():pos - 1]
        fields = {}
        for fm in re.finditer(r"(?:^|,)\s*(\w+)\s*=\s*(\{(?:[^{}]|\{[^{}]*\})*\}|\"[^\"]*\")",
                              body, re.S):
            val = fm.group(2)
            if val.startswith(("{", '"')):
                val = val[1:-1]
            fields[fm.group(1).lower()] = " ".join(val.split())
        entries[m.group(2)] = (m.group(1).lower(), fields)
    return entries


def dehyph(t):
    return re.sub(r"\s+", " ", re.sub(r"\s*(?:--|---)\s*", ": ", t)).strip()


def authors_of(field):
    out = []
    for chunk in re.split(r"\s+and\s+", re.sub(r"[{}]", "", field)):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "," in chunk:
            sur, given = chunk.split(",", 1)
        else:
            parts = chunk.split()
            sur, given = (parts[-1], " ".join(parts[:-1])) if len(parts) > 1 else (parts[0], "")
        ini = "".join(w[0] for w in re.findall(r"[A-Za-z\u00C0-\u024F]+", given)).upper()
        out.append((sur.strip(), ini))
    return out


def expected_label(auths, year):
    if len(auths) == 1:
        head = auths[0][0]
    elif len(auths) == 2:
        head = "%s and %s" % (auths[0][0], auths[1][0])
    else:
        head = "%s et al." % auths[0][0]
    return "%s(%s)" % (head, year)


bib = parse_bib(rd(BIB))
tex = rd(TEX)
bbl = rd(BBL)
map_text = rd(MAP)

cited = []
for m in re.finditer(r"\\cite[pt]?\*?(?:\[[^\]]*\])*\{([^}]*)\}", tex):
    for k in m.group(1).split(","):
        k = k.strip()
        if k and k not in cited:
            cited.append(k)

items = []           # (key, label, body)
lines = bbl.splitlines()
for i, ln in enumerate(lines):
    m = re.match(r"^\\bibitem\[(.*?)\]\{([^}]*)\}$", ln.strip())
    if m:
        body = ""
        for nxt in lines[i + 1:]:
            if nxt.strip():
                body = nxt.strip()
                break
        label = m.group(1).strip()
        if label.startswith("{") and label.endswith("}"):
            label = label[1:-1].strip()
        items.append((m.group(2), label, body))


# ------------------------------------------------------------------ 1 count/keys
if len(items) != N:
    fail("count", "%d \\bibitem entries, expected %d" % (len(items), N))
keys = [k for k, _l, _b in items]
if len(set(keys)) != len(keys):
    fail("count", "duplicate \\bibitem keys")
if set(keys) != set(cited):
    fail("keys", "cited but missing: %s | present but uncited: %s" % (
        sorted(set(cited) - set(keys)), sorted(set(keys) - set(cited))))
missing_bib = [k for k in keys if k not in bib]
if missing_bib:
    fail("keys", "keys absent from manuscript.bib: %s" % missing_bib)

# ------------------------------------------------------------------ 2..9 per entry
surnames = []
for key, label, body in items:
    kind, f = bib.get(key, ("?", {}))
    auths = authors_of(f.get("author", ""))
    year = f.get("year", "").strip()
    surnames.append((re.sub(r"[{}]", "", auths[0][0]).lower() if auths else key.lower(),
                     auths[0][1] if auths else "", year, key))

    # 2 label contract
    if not re.match(r"^[^()]+\(\d{4}[a-z]?\)$", label):
        fail("label", "%s: %r is not the short 'Author(Year)' form" % (key, label))
    elif auths:
        exp = expected_label(auths, year)
        if label != exp:
            fail("label", "%s: label %r, expected %r" % (key, label, exp))

    # 3 author block
    m = re.match(r"^(.*?)\((\d{4})[a-z]?\)\s(.*)$", body)
    if not m:
        fail("body", "%s: body does not start with 'Authors (Year) Title'" % key)
        continue
    block, byear, rest = m.group(1).strip(), m.group(2), m.group(3)
    if byear != year:
        fail("year", "%s: body year %s, .bib year %s" % (key, byear, year))
    def count_names(text):
        return text.count(",") + text.count(" and ") + 1

    if "et al" in block:
        if not block.endswith(", et al."):
            fail("authors", "%s: 'et al.' block is not '..., et al.' in %r" % (key, block))
        n_shown = count_names(block[:-len(", et al.")])
        if n_shown != 3:
            fail("authors", "%s: %d authors before 'et al.', JMS indexes 3"
                 % (key, n_shown))
        if len(auths) <= 3:
            fail("authors", "%s: 'et al.' used although the .bib lists %d authors"
                 % (key, len(auths)))
    else:
        n_shown = count_names(block)
        if n_shown > 3:
            fail("authors", "%s: %d authors listed (max 3 + et al.)" % (key, n_shown))
        if n_shown != len(auths):
            fail("authors", "%s: %d authors listed, .bib has %d"
                 % (key, n_shown, len(auths)))

    # 4 journal abbreviation
    journal = " ".join(f.get("journal", "").split()).replace("\\&", "&")
    if kind == "article":
        exp_j = JMS_ABBREV.get(journal)
        if exp_j is None:
            fail("journal", "%s: no JMS abbreviation known for %r" % (key, journal))
        elif " %s " % exp_j not in " %s " % rest:
            fail("journal", "%s: abbreviation %r missing from body" % (key, exp_j))
        for full in FULL_NAMES:
            if full in body:
                fail("journal", "%s: full journal name %r left in the entry" % (key, full))
        jpos = rest.find(" " + exp_j + " ") if exp_j else -1
        seg = rest[jpos:] if jpos >= 0 else ""
        for tok in seg.split():
            if re.match(r"^(?:[A-Z][a-z]{1,4}\.)+$", tok):
                fail("journal", "%s: abbreviation %r carries periods" % (key, tok))

    # 5 DOI
    dois = re.findall(r"\\url\{(https://doi\.org/[^}]+)\}", body)
    bib_doi = f.get("doi", "").strip()
    if bib_doi:
        if not dois:
            fail("doi", r"%s: .bib has a DOI but the entry has no \url{https://doi.org/...}"
                 % key)
        elif dois[0] != "https://doi.org/" + bib_doi:
            fail("doi", "%s: DOI %r, .bib says %r" % (key, dois[0], bib_doi))
    if re.search(r"(?i)\bdoi:\s*10\.|\\doi\{|\\DOIprefix", body):
        fail("doi", r"%s: doi: prefix or \doi{} command present" % key)
    if re.search(r"(?i)\bhttps?://(?!doi\.org/)", body):
        fail("doi", "%s: non-DOI URL in the entry" % key)

    # 6 forbidden bibliography machinery
    for cmd in ("\\bibinfo", "\\newblock", "\\DOIprefix", "\\URLprefix", "\\href",
                "\\path", "\\Pubmed"):
        if cmd in body:
            fail("commands", "%s: %s present" % (key, cmd))

    # 7 volume / issue / pages from the .bib
    if kind == "article":
        vol = f.get("volume", "").strip()
        num = f.get("number", "").strip()
        pages = re.sub(r"\s*(?:--|---)\s*", EN, f.get("pages", "").strip())
        if vol and not re.search(r"(?<![\d])%s(?:\(|\s|:)" % re.escape(vol), body):
            fail("fields", "%s: volume %r not found" % (key, vol))
        if num and "(%s)" % num not in body:
            fail("fields", "%s: issue (%s) from .bib missing" % (key, num))
        if not num and re.search(r"\d+\(\d+\)", body):
            warn("fields", "%s: issue printed although .bib has no number field" % key)
        if pages and pages not in body:
            fail("fields", "%s: pages %r not found (en dash expected)" % (key, pages))
    elif kind in ("book", "techreport"):
        pub = f.get("publisher") or f.get("institution", "")
        if pub and " ".join(pub.split()) not in body:
            fail("fields", "%s: publisher %r not found" % (key, pub))
        if ":" not in body:
            warn("fields", "%s: no 'place: publisher' (JMS book example requires it)" % key)

    # 8 punctuation
    if dois:
        if not (body.endswith("}") or re.search(r"\(Accessed on [^()]+\)$", body)):
            fail("punct", "%s: DOI entry must end on the \\url{...}, no full stop" % key)
    elif not re.search(r"[.)]$", body):
        fail("punct", "%s: entry does not end with a full stop" % key)

    # 11 sentence case (warning only)
    if kind == "article":
        exp_j = JMS_ABBREV.get(journal)
        title = rest.split(". " + exp_j + " ")[0] if exp_j and (". " + exp_j + " ") in rest else ""
        if title:
            words = title.split()
            for i, w in enumerate(words[1:], 1):
                core = re.sub(r"[^A-Za-z]", "", w)
                if core in STOPWORDS and not words[i - 1].endswith(":"):
                    warn("case", "%s: %r capitalised mid-title" % (key, core))
            caps, seen, after_colon = 0, 0, True
            for i, w in enumerate(words):
                core = re.sub(r"[^A-Za-z0-9]", "", w)
                if not core:
                    continue
                first = i == 0 or after_colon
                after_colon = w.endswith(":")
                if first or (core.isupper() and len(core) > 1):
                    continue
                seen += 1
                if core[0].isupper():
                    caps += 1
            if seen >= 5 and caps / float(seen) >= 0.6:
                warn("case", "%s: title looks Title-Case (%d/%d words capitalised); JMS "
                     "uses sentence case" % (key, caps, seen))

    # 12 artifacts
    if "~" in body:
        fail("artifacts", "%s: non-breaking-space ~ left in the body" % key)
    if "  " in body:
        fail("artifacts", "%s: doubled space" % key)
    if body.count("{") != body.count("}"):
        fail("artifacts", "%s: unbalanced braces" % key)
    for bad in ("..", "et al..", "et al (", " ,", "et al.. ("):
        if bad in body:
            fail("artifacts", "%s: %r in the body" % (key, bad))

# ------------------------------------------------------------------ 9 order
srt = sorted(surnames, key=lambda t: (t[0], t[1], t[2]))
if [t[3] for t in srt] != keys:
    fail("order", "entries are not alphabetical by first-author surname: %s" % keys)

# ------------------------------------------------------------------ 10 map file
map_rows = [r for r in map_text.splitlines() if r.strip()]
if not map_rows or not map_rows[0].startswith("key\t"):
    fail("map", "refs_map.tsv has no header row")
if len(map_rows) - 1 != N:
    fail("map", "refs_map.tsv has %d data rows, expected %d" % (len(map_rows) - 1, N))
else:
    map_keys = [r.split("\t")[0] for r in map_rows[1:]]
    if map_keys != keys:
        fail("map", "refs_map.tsv order/key differs from manuscript.bbl")
    for r, (_k, _l, body) in zip(map_rows[1:], items):
        cols = r.split("\t")
        if len(cols) != 6:
            fail("map", "row for %s has %d columns, expected 6" % (cols[0], len(cols)))
        elif cols[5] != body:
            fail("map", "row for %s does not match the .bbl body" % cols[0])

# ------------------------------------------------------------------ report
print("manuscript.bbl : %d entries | .bib %d entries | .tex cites %d keys"
      % (len(items), len(bib), len(cited)))
for w in warns:
    print(w)
for f_ in fails:
    print(f_)
print("\n%d checks FAILED, %d warnings" % (len(fails), len(warns)) if fails
      else "\nALL CHECKS PASSED (%d warnings)" % len(warns))
sys.exit(1 if fails else 0)
