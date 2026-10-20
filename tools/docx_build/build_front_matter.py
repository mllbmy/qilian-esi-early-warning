# -*- coding: utf-8 -*-
"""Build the JMS submission Title Page and Cover Letter (both carry identity).
Output: 交付/2.1版本/Title_Page_JMS_2.1版本.docx and Cover_Letter_JMS_2.1版本.docx
Identity values come from paper-code/author_local.py (git-ignored)."""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, r"D:\比赛\论文\paper-code")

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt

from author_local import (AFFIL_EN, AFFIL_EN_LINES, AUTHOR_EN_DISPLAY, CREDIT_EN, EMAIL, ORCID)
from docxbuild_lib import scrub_metadata

OUTDIR = r"D:\比赛\论文\交付\2.1版本"
MANUSCRIPT_TEX = r"D:\比赛\论文\paper-code\manuscript.tex"


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
DATE = "October 20, 2026"


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
         "NDVI product and Natural Earth - for making their data freely available. "
         "No individual or organisation provided assistance that requires separate "
         "acknowledgement.", after=10)

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
        ("Data availability", "The climate data are CRU TS 4.10 (openly available from "
                              "the Climatic Research Unit, University of East Anglia) and "
                              "the land-cover data are the China Land Cover Dataset "
                              "(CLCD, Yang and Huang 2021, 2024; Zenodo record 12779975). "
                              "The analysis scripts, the processed intermediate datasets, "
                              "the result tables and the figure-generation code are "
                              "available at the anonymised repository mirror "
                              + ANON_REPO + " (read-only, for peer review). The same "
                              "material is deposited in Zenodo; the record is restricted "
                              "while the manuscript is under review and will be released "
                              "publicly with a permanent DOI upon acceptance. The "
                              "re-processing boundary (which land-cover epochs can be "
                              "rebuilt from the raw tiles inside the package) is stated in "
                              "the Data availability statement of the manuscript."),
        ("Author contributions", CREDIT_EN),
        ("Use of AI", "DeepSeek (an AI language model) was used to assist with "
                      "manuscript drafting, structuring and language editing. The author "
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
    out = os.path.join(OUTDIR, "Title_Page_JMS_2.1版本.docx")
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
    body = [
        "I am pleased to submit the above-titled original research article for "
        "consideration as a research paper in the Journal of Mountain Science.",

        "Mountain protected areas concentrate conservation value and management pressure "
        "at the same time, yet their management often lacks quantitative early-warning "
        "instruments that convert routine monitoring data into actionable signals. The "
        "manuscript addresses this gap in the Qilian Mountain region of northwestern "
        "China, the setting of the Qilian Mountain National Park. It combines a DPSI "
        "weighted indicator framework (the Response layer is retained as an unweighted "
        "policy background rather than an indicator), combined AHP-entropy weighting, "
        "three forecasting models (GM(1,1), the nonlinear grey Bernoulli model NGBM and "
        "ARIMA(0,1,1)) and GeoDetector association analysis, and uses openly available "
        "data only (CRU TS 4.10 climate and CLCD 30 m land cover, 2005-2023).",

        "Four results are likely to interest the journal's readership. First, the "
        "ecological security index (ESI) peaks at 0.676 in 2010 and stands at 0.478 in "
        "2023, a mild-warning state in 16 of the 19 years. Second, forecasting is "
        "presented as an ensemble problem rather than a single-model extrapolation: no "
        "model dominates across five validation schemes, the inverse-RMSE mixture gives "
        "0.447 for 2028, and a logit-scale residual bootstrap keeps every interval inside "
        "the [0,1] support of the index, so the 2028 grade alone is shown not to support "
        "a management decision. Third, the indicator system is tested for internal "
        "redundancy: three exact identities are identified and the duplicated "
        "ecological-land column is removed without changing a single warning grade. "
        "Fourth, the spatially stratified associations are separated from the mechanical "
        "component contributed by factors that are themselves index inputs (mechanical "
        "share 0.20-0.87), and the significance of the association statistics is "
        "re-examined with block permutation that respects the strong spatial "
        "autocorrelation of the sample.",

        "The work extends the reserve-scale grey-model early-warning framework of Liu et "
        "al. (2023, J Nat Conserv 73: 126394) in three respects that are rarely combined "
        "in comparable DPSIR-based assessments of mountain protected areas: the "
        "sensitivity of the ESI and of its warning grade to the subjective-objective "
        "weighting ratio is tested across the full interval (alpha = 0-1); three forecast "
        "models are compared under five validation schemes with an explicit "
        "monotonicity diagnosis, which is required because the observed series is "
        "non-monotonic and therefore violates the linear grey-model assumption; and the "
        "regional time series is linked to county-level heterogeneity through "
        "factor-detector and interaction-detector statistics. Because the readership "
        "includes mountain-region managers as well as scientists, the output is expressed "
        "as warning grades, bounded intervals and response rules rather than as index "
        "values alone, and the framework is transferable to other mountain national parks "
        "where long-term monitoring is sparse but open geospatial data are available.",

        "The complete analysis pipeline, the processed intermediate datasets and all "
        "result tables are available at the anonymised repository mirror " + ANON_REPO +
        " (read-only, provided for peer review). The same material has been deposited in "
        "Zenodo; the record is restricted while the manuscript is under review, so that it "
        "can be inspected without disclosing authorship, and it will be released publicly "
        "with a permanent DOI upon acceptance. Because the Zenodo record is restricted "
        "during review, a share link is provided to the editorial office separately; "
        "please request it if it has not been attached to this submission.",

        "Declarations. The manuscript is original, has not been published previously, in "
        "whole or in part, and is not under consideration for publication elsewhere. It "
        "is a single-author study: I conceived the work, carried out all analyses, and "
        "approve the submitted version and its submission to the Journal of Mountain "
        "Science. The author declares no competing financial or non-financial interests. "
        "The research received no specific funding. The manuscript file used for review "
        "contains no author-identifying information; the author's name, affiliation, "
        "e-mail, ORCID and the ethics declarations are provided on the separate Title "
        "Page. Figures are supplied as vector PDF files that meet the journal's "
        "requirements for figure width and in-figure lettering, and all tables are "
        "Word-editable tables. DeepSeek (an AI language model) was used to assist with "
        "language editing; I reviewed and take full responsibility for the content.",

        "Thank you for your time and consideration. I look forward to hearing from you.",
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
    out = os.path.join(OUTDIR, "Cover_Letter_JMS_2.1版本.docx")
    d.save(out)
    return out


if __name__ == "__main__":
    if "REPLACE-WITH-MIRROR-ID" in ANON_REPO:
        print("!! WARNING: the anonymous-mirror URL is still the placeholder;")
        print("!!          run  python paper-code/set_anon_repo.py <mirror-url>  before submitting")
    os.makedirs(OUTDIR, exist_ok=True)
    print("title page:", title_page())
    print("cover letter:", cover_letter())
