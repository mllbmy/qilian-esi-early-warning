# -*- coding: utf-8 -*-
'''Generate manuscript.bbl in Journal of Mountain Science (Springer name-year) style.

Why this script exists: JMS requires `Author A, Author B (2022) Title. J Mt Sci 17(11):
2591-2610. https://doi.org/...` with no terminal period and at most three authors before
`et al.`, which no bibliography style installed with this TeX distribution provides
(`spbasic.bst` is not in TeX Live/MiKTeX). The .bib file stays the single source of
truth: run bibtex, then this script, then the final pdflatex passes.

Usage: python make_bbl_jms.py [--check]
'''
import argparse
import re
import sys
import unicodedata

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BIB = r'D:\比赛\论文\paper-code\manuscript.bib'
BBL = r'D:\比赛\论文\paper-code\manuscript.bbl'

# Entries present in the .bib but never cited and never present in the .bbl; JMS lists
# only cited works, so they are excluded here (they should also be removed from the .bib).
DEAD = {'dl_conservation_bio_2023', 'du2024dpsir', 'earlywarning_grassland2024',
        'qilian_desertification_gee'}

JOURNAL = {
    'Ecological Indicators': 'Ecol Indic',
    'Environmental Modelling & Software': 'Environ Model Softw',
    'Systems & Control Letters': 'Syst Control Lett',
    'Journal for Nature Conservation': 'J Nat Conserv',
    'Journal of Arid Land': 'J Arid Land',
    'Frontiers in Environmental Science': 'Front Environ Sci',
    'Remote Sensing': 'Remote Sens',
    'Ecosystem Health and Sustainability': 'Ecosyst Health Sustain',
    'Columella -- Journal of Agricultural and Environmental Sciences': 'Columella',
    'Columella - Journal of Agricultural and Environmental Sciences': 'Columella',
    'Environmental Science and Pollution Research': 'Environ Sci Pollut Res',
    'Scientific Data': 'Sci Data',
    'Earth System Science Data': 'Earth Syst Sci Data',
    'Journal of Physics: Conference Series': 'J Phys Conf Ser',
    'Nature Communications': 'Nat Commun',
    'ISPRS International Journal of Geo-Information': 'ISPRS Int J Geo-Inf',
    'Journal of Mountain Science': 'J Mt Sci',
}


def parse_bib(text):
    out = []
    for m in re.finditer(r'@(\w+)\{([^,]+),(.*?)\n\}', text, re.S):
        kind, key, body = m.group(1).lower(), m.group(2).strip(), m.group(3)
        fields = {}
        for fm in re.finditer(r'(\w+)\s*=\s*(\{(?:[^{}]|\{[^{}]*\})*\}|[^,\n]+)', body, re.S):
            name, val = fm.group(1).lower(), fm.group(2).strip()
            if val.startswith('{') and val.endswith('}'):
                val = val[1:-1]
            fields[name] = ' '.join(val.split())
        out.append((kind, key, fields))
    return out


def authors(field):
    """Return [(surname, initials-without-periods)] in bib order."""
    res = []
    for chunk in re.split(r'\s+and\s+', field):
        chunk = chunk.strip()
        if not chunk:
            continue
        if ',' in chunk:
            sur, given = chunk.split(',', 1)
        else:
            parts = chunk.split()
            sur, given = parts[-1], ' '.join(parts[:-1])
        ini = ''.join(p[0] for p in re.findall(r'[A-Za-zÀ-ÿ]+', given))
        res.append((sur.strip(), ini))
    return res


def names(field, limit=3):
    a = authors(field)
    shown = a[:limit]
    s = ', '.join('%s %s' % (sur, ini) if ini else sur for sur, ini in shown)
    if len(a) > limit:
        s += ', et al.'
    return strip_braces(s)


def inline_names(field, limit=3):
    a = authors(field)
    if len(a) == 1:
        return strip_braces(a[0][0])
    if len(a) == 2:
        return '%s and %s' % (strip_braces(a[0][0]), strip_braces(a[1][0]))
    if len(a) > limit:
        return '%s et al.' % strip_braces(a[0][0])
    return ', '.join(strip_braces(x[0]) for x in a[:-1]) + ' and ' + strip_braces(a[-1][0])


def clean(t):
    t = t.replace('--', '-').replace('~', ' ')
    t = re.sub(r'\s+', ' ', t)
    return t.strip()


def strip_braces(t):
    return t.replace('{', '').replace('}', '').strip()


def entry_text(kind, f):
    if kind == 'article':
        body = clean(f.get('title', ''))
        j = JOURNAL.get(clean(f.get('journal', '')), clean(f.get('journal', '')))
        vol = clean(f.get('volume', ''))
        num = clean(f.get('number', ''))
        pag = clean(f.get('pages', ''))
        loc = ('%s(%s): %s' % (vol, num, pag)) if num else ('%s: %s' % (vol, pag) if pag else vol)
        s = '%s. %s %s.' % (body, j, loc)
    elif kind in ('book',):
        s = '%s. %s' % (clean(f.get('title', '')), clean(f.get('publisher', '')))
        if f.get('address'):
            s = '%s. %s' % (clean(f.get('title', '')), clean(f.get('address', '')))
            s += ', %s.' % clean(f.get('publisher', ''))
        s = s.rstrip('.') + '.'
    elif kind in ('techreport', 'misc', 'online'):
        place = clean(f.get('institution', f.get('publisher', f.get('howpublished', ''))))
        addr = clean(f.get('address', ''))
        extra = ', '.join(x for x in [place, addr] if x) or clean(f.get('howpublished', ''))
        s = '%s. %s.' % (clean(f.get('title', '')), extra) if extra else '%s.' % clean(f.get('title', ''))
    else:
        s = '%s.' % clean(f.get('title', ''))
    doi = clean(f.get('doi', ''))
    if doi:
        s = s.rstrip('.') + ' https://doi.org/%s' % doi
    else:
        s = s.rstrip('.') + '.'
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()
    bib = open(BIB, encoding='utf-8').read()
    ents = [e for e in parse_bib(bib) if e[1] not in DEAD]
    items = []
    for kind, key, f in ents:
        if 'author' not in f:
            continue
        first = strip_braces(authors(f['author'])[0][0]).lower()
        label = '%s(%s)' % (inline_names(f['author']), clean(f.get('year', 'n.d.')))
        txt = '%s (%s) %s' % (names(f['author']), clean(f.get('year', 'n.d.')), entry_text(kind, f))
        items.append((first.lower(), label, key, txt))
    items.sort(key=lambda x: x[0])
    bbl = ['\\begin{thebibliography}{%d}' % len(items), '']
    for _f, label, key, txt in items:
        bbl += ['\\bibitem[%s]{%s}' % (label, key), txt, '']
    bbl += ['\\end{thebibliography}', '']
    out = '\n'.join(bbl)
    print('entries rendered: %d (bib %d - dead %d)' % (len(items), len(parse_bib(bib)), len(DEAD)))
    if args.check:
        print(out[:1500])
        return
    open(BBL, 'w', encoding='utf-8', newline='\n').write(out)
    print('written', BBL, len(out), 'chars')


if __name__ == '__main__':
    main()