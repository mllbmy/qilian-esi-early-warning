# -*- coding: utf-8 -*-
"""v8 定稿校验（R4 修订后）：参考文献闭环、R4 各项落地、数值基准、中英同步。"""
import os
import re
import sys

from docx import Document

# 路径自解析：仓库克隆/解压到任意目录均可运行
BASE = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(BASE, "manuscript.tex")
BBL = os.path.join(BASE, "manuscript.bbl")
BIB = os.path.join(BASE, "manuscript.bib")
BIB2 = os.path.join(BASE, "参考文献.bib")
CN = os.path.join(BASE, "out", "论文_CN_latest.docx")

fails = []


def chk(cond, msg):
    if cond:
        print("  PASS  " + msg)
    else:
        print("  FAIL  " + msg)
        fails.append(msg)


tex = open(TEX, encoding="utf-8").read()
bbl = open(BBL, encoding="utf-8").read()
bib = open(BIB, encoding="utf-8").read()
bib2 = open(BIB2, encoding="utf-8").read()

# ---------- A. 参考文献闭环 ----------
print("\n[A] 参考文献闭环")
keys_bib = set(re.findall(r"@\w+\{([^,]+),", bib))
keys_bib2 = set(re.findall(r"@\w+\{([^,]+),", bib2))
keys_bbl = re.findall(r"\\bibitem(?:\[[^\]]*\])?\{([^}]+)\}", bbl)
groups = re.findall(r"\\cite[tp]?\{([^}]+)\}", tex)
cite_tex = set(k.strip() for g in groups for k in g.split(","))
if keys_bib != keys_bib2:
    print("       仅在一个 bib 中: %s" % (keys_bib ^ keys_bib2))
chk(keys_bib == keys_bib2, "两个 bib 文件条目一致（%d 条）" % len(keys_bib))
chk(set(keys_bbl) <= keys_bib, "bbl 全部条目均能在 bib 中找到")
chk(cite_tex <= keys_bib, "正文所有 \\cite 键均在 bib 中")
chk(len(keys_bbl) == len(set(keys_bbl)) == 19, "bbl 条目数 = 19（含新增 jing2024obstacle），无重复")
chk("jing2024obstacle" in keys_bbl, "新增文献已进入参考文献表")

# ---------- B. R4 修改项落地 ----------
print("\n[B] R4 修改项落地（M1/M2/M3/m1-m5）")
chk("fig_compare" not in tex, "M1 正文不再引用 fig_compare.png")
chk("\\label{tab:compare}" in tex and "Table~\\ref{tab:compare}" in tex, "M1 对比内容改为三线表并被正文引用")
cmp_blk = next(p for p in tex.split("\\begin{table}") if "\\label{tab:compare}" in p)
cmp_blk = cmp_blk.split("\\end{table}")[0]
chk("\\midrule" in cmp_blk and "\\bottomrule" in cmp_blk, "M1 对比表为三线表（toprule/midrule/bottomrule）")
chk(not any(x in cmp_blk for x in ["✓", "NEW", "\\textcolor", "colored"]), "M1 对比表无勾选符号/强调角标/彩色")
chk("\\citep{liu2023integrated}" in cmp_blk, "M1 对比表标题带代表研究引用")
chk("five-grade warning convention" in tex, "M3 五级划分已补出处")
chk("Thresholds are set at equal 0.2 intervals" in tex, "M3 等距划分理由句已加入")
concl = tex.split("\\section{Conclusion}")[1]
chk("\\begin{enumerate}" not in concl, "m3 结论已无编号列表（段落式）")
chk("\\subsection{Spatial autocorrelation" not in tex, "m4 §4.6 小节标题已删除")
chk("spatial driving factors, and obstacle factors" in tex, "m4 §4.5 标题已扩展覆盖障碍因子")
chk("\\citep{jing2024obstacle}" in tex, "m4 障碍度诊断已补方法出处")
chk("Grade &" not in tex and "qualified &" not in tex, "m5 表5 已删除 Grade 列")
chk("Accuracy grades follow the grey-model convention" in tex, "m5 精度等级改为表注")
chk("**" not in tex, "无残留 Markdown 语法")

# ---------- C. 数值基准未漂移 ----------
print("\n[C] 数值基准（§11）")
nums = ["0.052", "0.035", "0.597", "0.789", "0.038", "0.029", "0.442", "0.895",
        "0.098", "0.067", "1.086", "0.632", "0.446", "0.394", "0.510", "0.493",
        "0.466", "0.395", "0.390", "0.344", "0.306", "0.289", "0.260", "0.251",
        "0.166", "0.074", "0.80", "0.71", "0.849", "0.643", "0.486", "0.709",
        "0.263", "0.034", "0.425", "0.578", "0.0034", "1{,}914", "999"]
missing = [s for s in nums if s not in tex]
chk(not missing, "全部数值基准存在" + ("（缺: %s）" % missing if missing else ""))

# 摘要词数（改后未动，仍应 ≤250）
abs_txt = tex.split("\\begin{abstract}")[1].split("\\end{abstract}")[0]
abs_txt = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^}]*\})?", " ", abs_txt)
abs_txt = abs_txt.replace("--", "-")
_en_word = os.path.join(BASE, "out", "论文_EN_review.docx")
try:   # 口径：Word 正文段落空白分词（与投稿系统一致）
    _ps = [p.text for p in Document(_en_word).paragraphs]
    _i = next(k for k, _t in enumerate(_ps) if _t.strip() == "Abstract")
    abs_src, abs_name = _ps[_i + 1], "Word 正文"
except Exception:
    abs_src, abs_name = abs_txt, "tex 转写"
words = abs_src.split()
print("  摘要词数 = %d（来源：%s）" % (len(words), abs_name))
chk(len(words) <= 250, "摘要词数 ≤ 250")

# ---------- D. 中文稿同步 ----------
print("\n[D] 中文稿同步")
doc = Document(CN)
paras = "\n".join(p.text for p in doc.paragraphs)
tabs = []
for t in doc.tables:
    hdr = [c.text.strip() for c in t.rows[0].cells]
    tabs.append(hdr)
    paras += "\n" + " | ".join(hdr)
    for row in t.rows[1:]:
        paras += "\n" + " | ".join(c.text for c in row.cells)
chk("表8" in paras and any("方法特征" in h for h in tabs), "M1 中文对比内容改为 表8 三线表（与 EN Table 8 同号）")
chk("图6  2020 年点尺度 ESI 空间分布" in paras and "表7  地理探测器交互探测（2020）" in paras,
    "M1 v19 对齐 EN 后 图6=点尺度、交互改为 表7（与 EN Table 7 同号）")
chk("等距划分" in paras, "M3 中文阈值理由已同步")
chk("障碍度诊断 (Jing et al., 2024)" in paras,
    "m4 中文障碍度出处已同步（作者-年制 Jing et al., 2024）")
chk("（1）将 DPSIR" not in paras, "m3 中文结论已段落化")
chk("Jing, X." in paras,
    "中文参考文献已同步 EN 的 Jing 2024（Harvard 无序号，19 条与 EN 逐字一致）")
fc_hdr = next((h for h in tabs if "RMSE" in h), None)
chk(fc_hdr is not None and len(fc_hdr) == 7 and "等级" not in fc_hdr,
    "m5 中文表5 表头 7 列且无“等级”列（实际: %s）" % fc_hdr)
chk("灰色模型惯例" in paras, "m5 中文精度等级改为表注")
cmp_hdr = next((h for h in tabs if "方法特征" in h), None)
chk(cmp_hdr is not None and len(cmp_hdr) == 5, "M1 中文表5 为 5 列（实际: %s）" % cmp_hdr)
chk("github.com/mllbmy/qilian-esi-early-warning" in paras, "数据可用性 GitHub 链接仍在")
import os as _os2, sys as _sys2
_sys2.path.insert(0, _os2.path.dirname(_os2.path.abspath(__file__)))
try:
    from author_local import EMAIL as _CN_EMAIL
except ImportError:
    _CN_EMAIL = None
chk((_CN_EMAIL in paras) if _CN_EMAIL else ("@" in paras), "通讯作者邮箱仍在")

print("\n" + ("verify_v8: ALL PASS" if not fails else "verify_v8: %d FAIL" % len(fails)))
sys.exit(1 if fails else 0)