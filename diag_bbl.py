# -*- coding: utf-8 -*-
"""诊断：bbl 条目 vs 正文引用键"""
import io
import os
import re

# 路径自解析：仓库克隆/解压到任意目录均可运行
PC = os.path.dirname(os.path.abspath(__file__))


def rd(p):
    return io.open(os.path.join(PC, p), encoding="utf-8", errors="replace").read()


b = rd("manuscript.bbl")
t = rd("manuscript.tex")
keys = re.findall(r"\\bibitem(?:\[[^\]]*\])?\{([^}]+)\}", b)
print("bbl 条目数:", len(keys))
print(keys)
ck = sorted({k.strip() for m in re.findall(r"\\cite[pt]?\{([^}]*)\}", t)
             for k in m.split(",") if k.strip()})
print("正文引用键数:", len(ck))
print("bbl 缺:", [k for k in ck if k not in keys])
print("bbl 多:", [k for k in keys if k not in ck])
aux = rd("manuscript.aux")
print("aux bibcite 数:", len(re.findall(r"\\bibcite\{", aux)))
print("bbl 是否含 22:", "jing2024obstacle" in keys)