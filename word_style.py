# -*- coding: utf-8 -*-
"""Word 排版工具：OMML 可编辑公式、三线表、黑体标题"""
from docx.oxml import parse_xml
from docx.oxml.ns import qn
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.enum.table import WD_TABLE_ALIGNMENT

M_NS = 'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"'
W_NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'

# ---------- OMML 构件 ----------
def R(t):
    return f'<m:r><m:t xml:space="preserve">{t}</m:t></m:r>'

def SUB(base, sub):
    return f'<m:sSub><m:e>{base}</m:e><m:sub>{sub}</m:sub></m:sSub>'

def SUP(base, sup):
    return f'<m:sSup><m:e>{base}</m:e><m:sup>{sup}</m:sup></m:sSup>'

def SSUBSUP(base, sub, sup):
    return f'<m:sSubSup><m:e>{base}</m:e><m:sub>{sub}</m:sub><m:sup>{sup}</m:sup></m:sSubSup>'

def FRAC(num, den):
    return f'<m:f><m:num>{num}</m:num><m:den>{den}</m:den></m:f>'

def NARY(op, sub, sup, base):
    return (f'<m:nary><m:naryPr><m:chr m:val="{op}"/>'
            f'<m:limLoc m:val="undOvr"/><m:supHide m:val="0"/><m:subHide m:val="0"/></m:naryPr>'
            f'<m:sub>{sub}</m:sub><m:sup>{sup}</m:sup><m:e>{base}</m:e></m:nary>')

def D(content):
    return (f'<m:d><m:dPr><m:begChr m:val="("/><m:endChr m:val=")"/>'
            f'<m:grow m:val="1"/></m:dPr><m:e>{content}</m:e></m:d>')

# ---------- 公式构件 ----------
def MAT2(row1, row2):
    """2 行 2 列矩阵（OMML），用于 cases 公式"""
    return ('<m:m><m:mPr><m:mcs><m:mc><m:mcPr><m:count m:val="2"/>'
            '<m:mcJc m:val="left"/></m:mcPr></m:mc></m:mcs></m:mPr>'
            f'<m:mr><m:e>{row1[0]}</m:e><m:e>{row1[1]}</m:e></m:mr>'
            f'<m:mr><m:e>{row2[0]}</m:e><m:e>{row2[1]}</m:e></m:mr></m:m>')

def BRACE(content):
    return ('<m:d><m:dPr><m:begChr m:val="{"/><m:endChr m:val=""/>'
            '<m:grow m:val="1"/></m:dPr>'
            f'<m:e>{content}</m:e></m:d>')

def EQNORM():
    """方向标准化：与 EN 式2 一致，一条 cases 公式（正向/负向两行）"""
    xpij = SUB(SUP(R("x"), R("'")), R("ij"))
    xij = SUB(R("x"), R("ij"))
    minj = SUB(R("min"), R("j"))
    maxj = SUB(R("max"), R("j"))
    # 运算符必须包在 R() 里：裸文本会变成 <m:e> 下的 text 节点，Word 渲染时静默丢弃
    pos = FRAC(D(f"{xij}{R(' − ')}{minj}"), D(f"{maxj}{R(' − ')}{minj}"))
    neg = FRAC(D(f"{maxj}{R(' − ')}{xij}"), D(f"{maxj}{R(' − ')}{minj}"))
    rows = MAT2((pos, R(",  正向 positive")), (neg, R(",  负向 negative")))
    return f'{xpij}{R(" = ")}{BRACE(rows)}'

def EQNORM_EN():
    """EQNORM 的纯英文标注版（供 EN Word 使用）"""
    xpij = SUB(SUP(R("x"), R("'")), R("ij"))
    xij = SUB(R("x"), R("ij"))
    minj = SUB(R("min"), R("j"))
    maxj = SUB(R("max"), R("j"))
    pos = FRAC(D(f"{xij}{R(' − ')}{minj}"), D(f"{maxj}{R(' − ')}{minj}"))
    neg = FRAC(D(f"{maxj}{R(' − ')}{xij}"), D(f"{maxj}{R(' − ')}{minj}"))
    rows = MAT2((pos, R(",  positive")), (neg, R(",  negative")))
    return f'{xpij}{R(" = ")}{BRACE(rows)}'

# 以下 EQ1/EQ2 为旧版拆开的两条标准化公式，已由 EQNORM 取代（保留以备回退）
def EQ1():
    xpij = SUB(SUP(R("x"), R("'")), R("ij"))
    xij = SUB(R("x"), R("ij"))
    minj = SUB(R("min"), R("j"))
    maxj = SUB(R("max"), R("j"))
    return (xpij + R(" = ") + FRAC(D(xij + R(" − ") + minj), D(maxj + R(" − ") + minj))
            + R("    (positive)"))

def EQ2():
    xpij = SUB(SUP(R("x"), R("'")), R("ij"))
    xij = SUB(R("x"), R("ij"))
    minj = SUB(R("min"), R("j"))
    maxj = SUB(R("max"), R("j"))
    return (xpij + R(" = ") + FRAC(D(maxj + R(" − ") + xij), D(maxj + R(" − ") + minj))
            + R("    (negative)"))

def EQ3():
    wj = SUB(R("w"), R("j"))
    wA = SUB(SUP(R("w"), R("A")), R("j"))
    wE = SUB(SUP(R("w"), R("E")), R("j"))
    a = R("α")
    one_a = D(R("1") + R(" − ") + a)
    return (wj + R(" = ") + a + wA + R(" + ") + one_a + wE + R(",")
            + R("    ") + a + R(" ∈ [0,1]"))

def EQ4():
    esi = SUB(R("ESI"), R("i"))
    wj = SUB(R("w"), R("j"))
    xp = SUB(SUP(R("x"), R("'")), R("ij"))
    sum_ = NARY("∑", R("j=1"), R("m"), f"{wj}{xp}")
    return f'{esi}{R(" = ")}{sum_}{R(",    ESI ∈ [0,1]")}'

def EQ5():
    xh1 = SUP(R("x̂"), R("(0)"))                    # x̂^(0)(k+1)
    k1 = R("(k+1)")
    x01 = SUP(R("x"), R("(0)")) + R("(1)")         # x^(0)(1)
    ahat = R("â"); bhat = R("b̂")
    minus = R(" − ")
    one_minus_e = D(R("1") + minus + SUP(R("e"), ahat))
    inner = D(x01 + minus + FRAC(bhat, ahat)) + SUP(R("e"), R("−") + ahat + R("k"))
    # x̂^(0)(k+1) = (1 − e^â)(x^(0)(1) − b̂/â)e^(−âk)
    return xh1 + k1 + R(" = ") + one_minus_e + inner

def EQ6():
    q = R("q")
    Nh = SUB(R("N"), R("h"))
    sh = SUP(R("σ"), R("2"))
    N = R("N"); s2 = SUP(R("σ"), R("2"))
    sum_ = NARY("∑", SUB(R("h"), R("=1")), R("L"), f"{Nh}{sh}")
    return f'{q}{R(" = 1 − ")}{FRAC(sum_, f"{N}{s2}")}'

def OMATH(xml_body):
    return parse_xml(f'<m:oMath {M_NS}>{xml_body}</m:oMath>')

# ---------- 插入带编号的居中公式（三列无线表：左右等宽 | 公式居中 | 编号靠右）----------
def vcenter(table):
    """所有单元格垂直居中"""
    from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
    for row in table.rows:
        for cell in row.cells:
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER

def _set_col_widths(table, widths_cm):
    """显式设置 tblGrid 网格列宽（twips）+ 固定布局，确保 Word 按指定列宽渲染"""
    from docx.oxml import OxmlElement
    tbl = table._tbl
    tblPr = tbl.tblPr
    # 固定布局
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    tblPr.append(layout)
    # tblGrid 网格列宽（cm -> twips: 1cm = 567 twips）
    grid = tbl.find(qn("w:tblGrid"))
    if grid is not None:
        cols = grid.findall(qn("w:gridCol"))
        for gc, w in zip(cols, widths_cm):
            gc.set(qn("w:w"), str(int(w * 567)))
    # 单元格宽度
    for row in table.rows:
        for cell, w in zip(row.cells, widths_cm):
            cell.width = Cm(w)

def add_equation(doc, omml_body, num):
    t = doc.add_table(rows=1, cols=3)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    # 中列最长，左右两列等宽（刚好放下编号）
    widths = [2.5, 11.0, 2.5]
    _set_col_widths(t, widths)
    c0, c1, c2 = t.rows[0].cells
    p1 = c1.paragraphs[0]
    p1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p1._p.append(OMATH(omml_body))
    p2 = c2.paragraphs[0]
    p2.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r = p2.add_run(f"({num})")
    r.font.size = Pt(11)
    vcenter(t)
    _no_borders(t)
    return t

# ---------- 三线表 ----------
def _no_borders(table):
    tblPr = table._tbl.tblPr
    borders = parse_xml(
        f'<w:tblBorders {W_NS}>'
        '<w:top w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
        '<w:left w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
        '<w:bottom w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
        '<w:right w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
        '<w:insideH w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
        '<w:insideV w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
        '</w:tblBorders>')
    tblPr.append(borders)

def make_three_line(table, header_rows=1):
    """三线表：顶线(粗)、表头下线(细)、底线(粗)；无竖线。"""
    tblPr = table._tbl.tblPr
    # 移除已存在的 tblBorders（如来自 Table Grid 样式）
    for old in tblPr.findall(qn("w:tblBorders")):
        tblPr.remove(old)
    borders = parse_xml(
        f'<w:tblBorders {W_NS}>'
        '<w:top w:val="single" w:sz="12" w:space="0" w:color="000000"/>'
        '<w:bottom w:val="single" w:sz="12" w:space="0" w:color="000000"/>'
        '<w:left w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
        '<w:right w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
        '<w:insideH w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
        '<w:insideV w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
        '</w:tblBorders>')
    tblPr.append(borders)
    # 表头下细线
    for row in table.rows[:header_rows]:
        for cell in row.cells:
            tcPr = cell._tc.get_or_add_tcPr()
            for old in tcPr.findall(qn("w:tcBorders")):
                tcPr.remove(old)
            tcBorders = parse_xml(
                f'<w:tcBorders {W_NS}>'
                '<w:bottom w:val="single" w:sz="6" w:space="0" w:color="000000"/>'
                '</w:tcBorders>')
            tcPr.append(tcBorders)

# ---------- 黑体标题 ----------
def heading_cn(doc, text, size, bold=True, align=None):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.font.size = Pt(size)
    r.bold = bold
    r._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), "黑体")
    if align is not None:
        p.alignment = align
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(6)
    return p
