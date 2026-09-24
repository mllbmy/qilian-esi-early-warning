# -*- coding: utf-8 -*-
"""诊断：EN 编号（PDF 实测）vs CN 正文引用号"""
import io
import os
import re
import subprocess

# 路径自解析：仓库克隆/解压到任意目录均可运行
PC = os.path.dirname(os.path.abspath(__file__))


def rd(p):
    return io.open(os.path.join(PC, p), encoding="utf-8", errors="replace").read()


# 1) EN PDF 参考文献区实测编号
txt = subprocess.run(["pdftotext", "-layout", os.path.join(PC, "manuscript.pdf"), "-"],
                     capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
ref = txt.split("References")[-1]
for m in re.finditer(r"\[(\d+)\]\s*([^\n]{0,95})", ref):
    n = int(m.group(1))
    if n >= 12:
        print("EN [%d] %s" % (n, m.group(2).strip()))

# 2) EN 正文引用号（按 aux 映射）
aux = rd("manuscript.aux")
CITE = dict(re.findall(r"\\bibcite\{([^}]+)\}\{(\d+)\}", aux))
tex = rd("manuscript.tex")
print("\nEN 正文各段落引用号:")
for para in [p.strip() for p in tex.split("\n\n") if p.strip() and not p.strip().startswith("%")]:
    nums = [CITE.get(k.strip(), "?") for m in re.findall(r"\\cite[pt]?\{([^}]*)\}", para)
            for k in m.split(",") if k.strip()]
    if nums:
        head = re.sub(r"\s+", " ", para)[:52]
        print("   [%s] %s" % (",".join(nums), head))

# 3) CN 正文引用号
cn = rd("build_word_cn.py")
nums = sorted({int(x) for x in re.findall(r"\[(\d+(?:,\d+)*)\]", cn) for x in x.split(",")})
print("\nCN 正文出现的引用号集合:", nums)
print("CN 参考文献条目数:", len(re.findall(r'^\s*"\[\d+\]', cn, re.M)))