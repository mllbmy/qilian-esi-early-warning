# -*- coding: utf-8 -*-
"""Minimal Word-COM round-trip test for the OMML produced by omml.py."""
import os
import sys

sys.path.insert(0, r"D:\比赛\论文\_r45_work\wb")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.shared import Pt, Cm
import omml

OUT = r"D:\比赛\论文\_r45_work\wb\mtest.docx"

doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
for m in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
    setattr(sec, m, Cm(2.5))
st = doc.styles["Normal"]
st.font.name = "Times New Roman"
st.font.size = Pt(10)
st.paragraph_format.space_after = Pt(0)
st.paragraph_format.line_spacing = 1.0


def add_math_par(latex, label="", display=False):
    p = doc.add_paragraph()
    if label:
        p.paragraph_format.tab_stops.add_tab_stop(Cm(7.8), WD_TAB_ALIGNMENT.CENTER)
        p.paragraph_format.tab_stops.add_tab_stop(Cm(16.0), WD_TAB_ALIGNMENT.RIGHT)
        p.add_run("\t")
    p._p.append(omml.omml_element(latex, display=display))
    if label:
        p.add_run("\t" + label)
    return p


def add_inline(prefix, latex, suffix=""):
    p = doc.add_paragraph()
    if prefix:
        p.add_run(prefix)
    p._p.append(omml.omml_element(latex))
    if suffix:
        p.add_run(suffix)
    return p


doc.add_paragraph("OMML round-trip test").runs[0].bold = True

doc.add_paragraph("1. Inline math with letters/digits/sub/sup:")
add_inline("The value ", r"q=0.80", " is high and ")
add_inline("", r"\alpha=0.4", " holds.")
add_inline("Units: km", r"^2", " and mm")
add_inline("", r"^{-1}", " and ")
add_inline("temperature 36.0--40.5", r"^{\circ}", "N.")

doc.add_paragraph("2. Inline with scripts and Greek:")
add_inline("weight ", r"w^{A}_j", ", prime ")
add_inline("", r"x'_{ij}", ", sigma ")
add_inline("", r"\sigma_h^2", ", nary ")
add_inline("", r"\sum_j w_j=1", ", ge ")
add_inline("", r"\alpha\ge0.9", ".")

doc.add_paragraph("3. Display equation (weighted mixture), numbered:")
add_math_par(r"w_j=\alpha\,w^{A}_j+(1-\alpha)\,w^{E}_j,\qquad \alpha\in[0,1],", "(1)", display=True)

doc.add_paragraph("4. Display equation with cases (2x2 matrix):")
add_math_par(r"x'_{ij}=\begin{cases}\dfrac{x_{ij}-\min_j}{\max_j-\min_j}, & \text{positive},\\[2mm] \dfrac{\max_j-x_{ij}}{\max_j-\min_j}, & \text{negative},\end{cases}", "(2)", display=True)

doc.add_paragraph("5. Display equation with \\left( \\right), hat accents, nary:")
add_math_par(r"\hat x^{(0)}(k+1)=\left(1-e^{\hat a}\right)\left(x^{(0)}(1)-\frac{\hat b}{\hat a}\right)e^{-\hat a k}.", "(3)", display=True)
add_math_par(r"q=1-\frac{\sum_{h=1}^{L}N_h\sigma_h^2}{N\sigma^2},", "(4)", display=True)
add_math_par(r"\mathrm{ESI}_i=\sum_{j=1}^{m}w_j\,x'_{ij},\qquad \mathrm{ESI}\in[0,1].", "(5)", display=True)

doc.add_paragraph("6. Operators and symbols:")
add_inline("", r"11\times19", ", ")
add_inline("", r"0.8\pm0.1", ", ")
add_inline("", r"p \le 0.001", ", ")
add_inline("", r"2.4\times10^{-5}", ", ")
add_inline("", r"q_{\mathrm{int}}>\max(q_1,q_2)", ".")

doc.save(OUT)
print("saved", OUT, os.path.getsize(OUT), "bytes")