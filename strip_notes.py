# -*- coding: utf-8 -*-
"""清理 manuscript.bib 中的内部工作注记（note 字段），避免排进正式参考文献表。
参考文献.bib 保留注记作为工作副本。"""
import os
import re

# 路径自解析：仓库克隆/解压到任意目录均可运行
BASE = os.path.dirname(os.path.abspath(__file__))
BIB = os.path.join(BASE, "manuscript.bib")

src = open(BIB, encoding="utf-8").read()
lines = src.split("\n")
out, removed = [], []
for ln in lines:
    if re.match(r"^\s*note\s*=\s*\{.*\},?\s*$", ln):
        removed.append(ln.strip()[:90])
        continue
    out.append(ln)
new = "\n".join(out)
# 清理可能出现的 “,,” 或 字段末尾孤立逗号问题：把 "},\n}" 规范化
new = re.sub(r",\s*\n\}", "\n}", new)
open(BIB, "w", encoding="utf-8").write(new)

print("已移除内部注记 %d 条：" % len(removed))
for r in removed:
    print("   -", r)

# 展示 tab:compare 区块（校验脚本定位用）
tex = open(os.path.join(BASE, "manuscript.tex"), encoding="utf-8").read()
parts = tex.split("\\begin{table}")
hit = [p for p in parts if "tab:compare" in p]
print("\n包含 tab:compare 的区块数 =", len(hit))
if hit:
    blk = hit[0].split("\\end{table}")[0]
    print("区块内是否含 \\citep{liu2023integrated}:", "\\citep{liu2023integrated}" in blk)
    print("区块前 320 字符:")
    print(blk[:320])