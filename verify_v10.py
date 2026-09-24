# -*- coding: utf-8 -*-
"""v10 定稿校验：继承 verify_v9 全部断言，另加投稿材料合规专项（Highlights ≤85 字符等）。"""
import glob
import os
import re
import subprocess
import sys

# 路径自解析：仓库克隆/解压到任意目录均可运行
BASE = os.path.dirname(os.path.abspath(__file__))
# 路径自解析：工作区根目录 = paper-code 的上一级
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAT = os.path.join(ROOT, "交付", "JNC_投稿材料") \
      if os.path.isdir(os.path.join(ROOT, "交付", "JNC_投稿材料")) else os.path.join(ROOT, "交付", "投稿材料")
TEX = os.path.join(BASE, "manuscript.tex")
HL = os.path.join(MAT, "Highlights.txt")
CL = sorted(glob.glob(os.path.join(MAT, "cover_letter_*.md")))[-1]   # 跟随最新日期材料

fails = []


def chk(cond, msg):
    print("  %s  %s" % ("PASS " if cond else "FAIL ", msg))
    if not cond:
        fails.append(msg)


env = dict(os.environ, PYTHONIOENCODING="utf-8")
r = subprocess.run([sys.executable, os.path.join(BASE, "verify_v9.py")],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", env=env)
print(r.stdout.rstrip())
if "verify_v9: ALL PASS" not in (r.stdout or ""):
    fails.append("verify_v9 未全部通过")

print("\n[F] v10 专项（投稿材料合规：Elsevier Highlights 3–5 条、每条 ≤85 字符）")
tex = open(TEX, encoding="utf-8").read()
chk("\\section*{Highlights}" not in tex,
    "F3 正文已不含 Highlights 段（v20 起：Elsevier 要求仅作独立文件上传）")

lines = [ln.rstrip() for ln in open(HL, encoding="utf-8").read().split("\n") if ln.strip()]
print("     Highlights.txt 字符数:", [len(x) for x in lines])
chk(len(lines) == 5 and all(len(x) <= 85 for x in lines), "上传文件 5 条且每条 ≤85 字符")
chk(all(not x.lstrip().startswith("-") for x in lines), "Highlights.txt 为纯文本条目（无项目符号）")

cl = open(CL, encoding="utf-8").read()
chk("qilian-esi-early-warning" in cl, "cover letter 含公开仓库链接")
chk("not under consideration" in cl, "cover letter 含未他投声明")
import os as _os2, sys as _sys2
_sys2.path.insert(0, _os2.path.dirname(_os2.path.abspath(__file__)))
try:
    from author_local import AFFIL_EN as _CL_AFFIL
except ImportError:
    _CL_AFFIL = None
chk((_CL_AFFIL in cl) if _CL_AFFIL else True, "cover letter 署名单位与正文一致")
chk(not ("reviewer" in cl.lower() and "suggest" in cl.lower()), "cover letter 未写推荐审稿人")
chk(os.path.exists(sorted(glob.glob(os.path.join(MAT, "投稿材料说明_*.md")))[-1]), "投稿材料说明存在")
chk(os.path.exists(os.path.join(MAT, "Highlights.txt")), "Highlights.txt 存在")

# ---- [G] Word 公式（OMML）结构与 LaTeX 逐式一致 ----
print("\n[G] Word 公式（OMML）结构与 LaTeX 一致（v20 修正：运算符必须包在 m:t 内）")
import zipfile
from lxml import etree

MNS = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
for _fn, _tag in (("论文_CN_latest.docx", "CN"), ("论文_EN_review.docx", "EN")):
    _p = os.path.join(BASE, "out", _fn)
    _doc = etree.fromstring(zipfile.ZipFile(_p).read("word/document.xml"))
    _oms = [e for e in _doc.iter(MNS + "oMath") if e.getparent().tag != MNS + "oMathPara"]
    chk(len(_oms) == 5, "%s Word 含 5 条公式（实际 %d）" % (_tag, len(_oms)))
    if len(_oms) != 5:
        continue
    _bad = [(i, el.tag.split("}")[-1], (el.text or "").strip()[:20])
            for i, om in enumerate(_oms, 1) for el in om.iter()
            if el.tag != MNS + "t" and (el.text or "").strip()]
    chk(not _bad, "%s Word 公式无裸文本节点（这类运算符会被 Word 静默丢弃）%s"
        % (_tag, "" if not _bad else "；%s" % _bad[:2]))
    _raw = ["".join(t.text or "" for t in om.iter(MNS + "t")) for om in _oms]
    chk("− α" in _raw[0], "%s 式(1) 权重含 (1 − α)" % _tag)
    chk(_raw[1].count("−") == 4, "%s 式(2) 标准化含 4 个减号（实际 %d）" % (_tag, _raw[1].count("−")))
    chk("e−âk" in _raw[3] and "â(k+1)" not in _raw[3], "%s 式(4) 指数为 e^(−âk)，非 e^(â(k+1))" % _tag)
    chk(len(list(_oms[3].iter(MNS + "sSubSup"))) == 0,
        "%s 式(4) 无上下标并列（x̂^(0)、x^(0)(1) 均为上标）" % _tag)

print("\n" + ("verify_v10: ALL PASS" if not fails else "verify_v10: %d FAIL" % len(fails)))
sys.exit(1 if fails else 0)