# -*- coding: utf-8 -*-
"""v9 定稿校验：继承 verify_v8 全部断言，另加 v9 专项（§4.3 去掉整句加粗）。"""
import os
import subprocess
import sys

# 路径自解析：仓库克隆/解压到任意目录均可运行
BASE = os.path.dirname(os.path.abspath(__file__))
V8 = os.path.join(BASE, "verify_v8.py")
TEX = os.path.join(BASE, "manuscript.tex")

env = dict(os.environ, PYTHONIOENCODING="utf-8")
r = subprocess.run([sys.executable, V8], capture_output=True, text=True,
                   encoding="utf-8", errors="replace", env=env)
print(r.stdout.rstrip())

fails = []
if "verify_v8: ALL PASS" not in (r.stdout or ""):
    fails.append("verify_v8 未全部通过")

print("\n[E] v9 专项（Qoder R4 复核裁决 B）")
tex = open(TEX, encoding="utf-8").read()
ok = ("\\textbf{NGBM achieved" not in tex
      and "\\emph{NGBM" not in tex
      and "models. NGBM achieved qualified accuracy" in tex)
print("  %s  §4.3 首句已改为普通文字（无 \\textbf、不用 \\emph）"
      % ("PASS " if ok else "FAIL "))
if not ok:
    fails.append("§4.3 加粗未去除")
still_bold = [ln.strip()[:70] for ln in tex.split("\n") if "\\textbf" in ln]
print("  正文其余加粗处（应仅为表 5 内的模型名/数值与 CRediT 署名）：")
for ln in still_bold:
    print("    -", ln)

print("\n" + ("verify_v9: ALL PASS" if not fails else "verify_v9: %d FAIL" % len(fails)))
sys.exit(1 if fails else 0)