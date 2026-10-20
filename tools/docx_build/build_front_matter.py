# -*- coding: utf-8 -*-
"""Build the JMS submission Title Page and Cover Letter (both carry identity).
Output: current_release.DELIVERY (Title Page and Cover Letter)
Identity values come from paper-code/author_local.py (git-ignored)."""
import datetime
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt

from author_local import (AFFIL_EN, AFFIL_EN_LINES, AUTHOR_EN_DISPLAY, CREDIT_EN, EMAIL, ORCID)
from docxbuild_lib import scrub_metadata

from current_release import DELIVERY, PACKAGE, VERSION
OUTDIR = str(DELIVERY)
MANUSCRIPT_TEX = str(PACKAGE / "manuscript.tex")


def anon_repo():
    """Read the anonymous-mirror URL from manuscript.tex (single source of truth)."""
    with open(MANUSCRIPT_TEX, encoding="utf-8") as fh:
        tex = fh.read()
    m = re.search(r"https://anonymous\.4open\.science/r/[A-Za-z0-9._-]+", tex)
    if not m:
        raise SystemExit("anonymous mirror URL not found in manuscript.tex")
    return m.group(0)


ANON_REPO = anon_repo()
TITLE = ("Ecological security early warning in the Qilian Mountain region, China: "
         "temporal dynamics, forecasts, and spatial associations")
DATE = "%s %d, %d" % (datetime.date.today().strftime("%B"), datetime.date.today().day, datetime.date.today().year)


def new_doc():
    d = Document()
    s = d.sections[0]
    s.page_width, s.page_height = Cm(21.0), Cm(29.7)
    s.left_margin = s.right_margin = Cm(2.5)
    s.top_margin = s.bottom_margin = Cm(2.5)
    n = d.styles["Normal"]
    n.font.name = "Times New Roman"
    n.font.size = Pt(10)
    rf = n.element.get_or_add_rPr().get_or_add_rFonts()
    from docx.oxml.ns import qn
    for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rf.set(qn(a), "Times New Roman")
    pf = n.paragraph_format
    pf.line_spacing = 1.0
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    return d


def p(d, text="", size=10, bold=False, italic=False, align=None,
      before=0, after=6, indent=None):
    par = d.add_paragraph()
    if align is not None:
        par.alignment = align
    pf = par.paragraph_format
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    pf.line_spacing = 1.0
    if indent is not None:
        pf.left_indent = Cm(indent)
    if text:
        r = par.add_run(text)
        r.bold = bold
        r.italic = italic
        r.font.size = Pt(size)
    return par


def title_page():
    d = new_doc()
    p(d, TITLE, size=14, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, after=12)
    p(d, AUTHOR_EN_DISPLAY, size=12, align=WD_ALIGN_PARAGRAPH.CENTER, after=4)
    for i, line in enumerate(AFFIL_EN_LINES):
        p(d, line, size=11, italic=True, align=WD_ALIGN_PARAGRAPH.CENTER, after=(2 if i == len(AFFIL_EN_LINES) - 1 else 0))
    p(d, "*Corresponding author.", size=10, align=WD_ALIGN_PARAGRAPH.CENTER, after=2)
    p(d, "E-mail: %s" % EMAIL, size=10, align=WD_ALIGN_PARAGRAPH.CENTER, after=2)
    p(d, "ORCID: %s" % ORCID, size=10, align=WD_ALIGN_PARAGRAPH.CENTER, after=14)

    p(d, "Acknowledgements", size=11, bold=True, before=6, after=4)
    p(d, "The author thanks the providers of the open datasets used in this study - "
         "CRU TS 4.10 (Climatic Research Unit, University of East Anglia), the China "
         "Land Cover Dataset (CLCD), Copernicus DEM GLO-90, the NOAA CDR AVHRR/VIIRS "
         "NDVI product and Natural Earth - for making their data freely available.", after=10)

    p(d, "Ethics declarations", size=11, bold=True, before=6, after=4)
    items = [
        ("Funding", "This research did not receive any specific grant from funding "
                    "agencies in the public, commercial, or not-for-profit sectors."),
        ("Competing interests", "The author has no relevant financial or "
                                "non-financial interests to disclose."),
        ("Ethics approval", "This study used openly available secondary data only and "
                            "involved no human participants or animals; no ethical "
                            "approval was therefore required."),
        ("Consent to participate", "Not applicable."),
        ("Consent for publication", "Not applicable."),
        ("Data availability", "Source datasets are CRU TS 4.10, CLCD, Copernicus "
                              "DEM GLO-90 and NOAA CDR NDVI. Analysis code, processed "
                              "tables, model outputs and figure generators accompany "
                              "the submission reproduction package and the anonymous "
                              "review mirror " + ANON_REPO + ". The regional land-cover "
                              "table contains five processed epochs; the 2020 tile "
                              "supports direct raw-data reprocessing. The same code and "
                              "processed tables are archived in a public repository; the persistent "
                              "identifier is reported in the published version."),
        ("Author contributions", CREDIT_EN),
        ("Use of AI", "DeepSeek and ChatGPT were used to assist with "
                      "manuscript drafting, language editing and code assistance. The author "
                      "reviewed and edited the content as needed and takes full "
                      "responsibility for the content of the publication."),
    ]
    for head, body in items:
        p(d, head, size=10, bold=True, before=4, after=1)
        p(d, body, after=4)

    p(d, "Suggested reviewers", size=11, bold=True, before=10, after=2)
    p(d, "Three potential reviewers are listed in the Cover Letter; none is at the "
         "author's institution, none has collaborated with the author in recent years, "
         "and none has been involved in the preparation of this manuscript.", after=4)

    scrub_metadata(d, TITLE)
    out = os.path.join(OUTDIR, "Title_Page_JMS_%s版本.docx" % VERSION)
    d.save(out)
    return out


def cover_letter():
    d = new_doc()
    p(d, DATE, after=10)
    p(d, "Prof. Dr. Editor-in-Chief", after=0)
    p(d, "Journal of Mountain Science", after=0)
    p(d, "Institute of Mountain Hazards and Environment, Chinese Academy of Sciences / Springer",
      after=12)
    p(d, "Subject: submission of an original research article", size=10, bold=True, after=2)
    p(d, TITLE, size=10, italic=True, after=10)
    p(d, "Dear Editor,", after=8)
    import csv
    def rows(name):
        with open(PACKAGE / "data" / name, encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    fc = rows("r47_forecast.csv")
    bt = rows("r47_bootstrap.csv")
    mix = next(float(r["value"]) for r in fc if r["model"] == "Mixture" and r["year"] == "2028")
    env = next(r for r in bt if r["model"] == "Mixture" and r["year"] == "2028")
    body = [
        "I submit the above-titled original research article for consideration in the "
        "Journal of Mountain Science.",
        "Mountain protected areas often have sparse environmental observations. This "
        "study examines how indicator construction and forecasting choices affect "
        "ecological-security warning grades in the Qilian Mountain region, China. "
        "It combines an eight-indicator regional DPSI index, AHP-entropy weighting, "
        "three forecasting models and a separate six-indicator spatial analysis, "
        "using CRU TS climate and five CLCD land-cover epochs over 2005-2023.",
        "The study reports three results. Removing a redundant ecological-land "
        "indicator preserves all historical warning grades, whereas changing the "
        "derived grassland-change indicator alters both grades and the peak year. "
        "Retrospective rolling forecasts compare GM(1,1), NGBM and ARIMA with naive "
        "and drift benchmarks on common time origins. The rolling-five-year-weighted "
        f"mixture projects a 2028 index of {mix:.3f}, with a central 95% conditional "
        f"bootstrap envelope of {float(env['lo']):.3f}-{float(env['hi']):.3f}. "
        "Finally, spatial target-overlap diagnostics distinguish associations that "
        "depend on index inputs, while an exhaustive periodic-shift reference and "
        "an independent NDVI comparison describe their spatial context.",
        "The paper concerns mountain environmental change and conservation monitoring, "
        "and it identifies monitoring priorities conditional on index definition and "
        "spatial scale.",
        "The analysis scripts, processed tables, model outputs and figure generators "
        "accompany the submission reproduction package and the anonymous review mirror "
        + ANON_REPO + ". The same code and processed tables are archived in a public "
        "repository, whose persistent identifier will be given in the published version.",
        "The manuscript is original, has not been published, and is not under "
        "consideration elsewhere. I am the sole author and approve this submission. "
        "There are no competing interests and no specific funding. Author identity "
        "and declarations appear on the separate Title Page. Figures are supplied "
        "as vector PDFs and tables are editable in Word. DeepSeek and ChatGPT assisted "
        "with drafting, language editing and code assistance; I reviewed the "
        "work and take full responsibility for its content.",
        "Thank you for considering this manuscript.",
    ]
    for t in body:
        p(d, t, after=7)

    p(d, "Sincerely,", before=8, after=14)
    p(d, AUTHOR_EN_DISPLAY.replace("*", ""), bold=True, after=0)
    for line in AFFIL_EN_LINES:
        p(d, line, after=0)
    p(d, "E-mail: %s" % EMAIL, after=0)
    p(d, "ORCID: %s" % ORCID, after=0)

    d.add_page_break()
    p(d, "Suggested reviewers", size=11, bold=True, after=6)
    p(d, "None of the suggested reviewers is at my institution, none has collaborated "
         "with me in recent years, and none has been involved in the preparation or "
         "review of this manuscript.", after=8)
    rows = [
        ("1", "Prof. Karsten Grunewald",
         "Leibniz Institute of Ecological Urban and Regional Development (IOR), Dresden, Germany",
         "k.grunewald@ioer.de",
         "Landscape ecology; ecological risk and ecosystem-service assessment in mountain regions"),
        ("2", "Prof. Jinfeng Wang",
         "State Key Laboratory of Resources and Environmental Information System, IGSNRR, "
         "Chinese Academy of Sciences, Beijing, China",
         "wangjf@lreis.ac.cn",
         "Spatial statistics; spatial stratified heterogeneity; originator of the GeoDetector "
         "q-statistic and interaction detector"),
        ("3", "Prof. Yu-Pin Lin",
         "Department of Bioenvironmental Systems Engineering, National Taiwan University, "
         "Taipei, Taiwan",
         "yplin@ntu.edu.tw",
         "Geostatistics; land-use change modelling; ecosystem-service and conservation "
         "spatial planning"),
    ]
    tab = d.add_table(rows=1 + len(rows), cols=5)
    tab.style = "Table Grid"
    hdr = ["#", "Name", "Affiliation (country)", "E-mail", "Research area"]
    for j, h in enumerate(hdr):
        c = tab.rows[0].cells[j]
        c.text = ""
        r = c.paragraphs[0].add_run(h)
        r.bold = True
        r.font.size = Pt(9)
    for i, row in enumerate(rows, 1):
        for j, v in enumerate(row):
            c = tab.rows[i].cells[j]
            c.text = ""
            r = c.paragraphs[0].add_run(v)
            r.font.size = Pt(9)
    widths = [Cm(0.8), Cm(3.2), Cm(5.0), Cm(3.6), Cm(4.2)]
    for row in tab.rows:
        for j, w in enumerate(widths):
            row.cells[j].width = w

    scrub_metadata(d, "Cover Letter - " + TITLE)
    out = os.path.join(OUTDIR, "Cover_Letter_JMS_%s版本.docx" % VERSION)
    d.save(out)
    return out


if __name__ == "__main__":
    if "REPLACE-WITH-MIRROR-ID" in ANON_REPO:
        print("!! WARNING: the anonymous-mirror URL is still the placeholder;")
        print("!!          run  python paper-code/set_anon_repo.py <mirror-url>  before submitting")
    os.makedirs(OUTDIR, exist_ok=True)
    print("title page:", title_page())
    print("cover letter:", cover_letter())
