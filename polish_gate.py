# -*- coding: utf-8 -*-
"""润色闸门（unit level）：与 优化\baseline 快照比对，确保润色只改表达、不动事实。
用法：cd paper-code; python polish_gate.py
"""
import io
import os
import re
import sys

# 路径自解析：工作区根目录 = paper-code 的上一级
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PC = os.path.join(ROOT, "paper-code")
BASE = os.path.join(ROOT, "优化", "baseline")
NUM = re.compile(r"\d+(?:[.,]\d+)*")
CITE = re.compile(r"\\cite[a-z]*\{([^}]*)\}")
REF = re.compile(r"\\(?:ref|eqref)\{([^}]*)\}")
LAB = re.compile(r"\\label\{([^}]*)\}")
fails = []


def load(path, base=False):
    d = BASE if base else os.path.dirname(path)
    return io.open(os.path.join(d, os.path.basename(path)), encoding="utf-8").read()


def strip_identity(t):
    """剔除作者身份信息（邮箱、作者/单位/私有模块引用行）。

    身份信息不进公开库属于有意为之，不应计为"事实漂移"；
    真实事实（数字/引用/图表数）仍按下方签名严格比对。
    """
    t = re.sub(r"\S+@\S+", "", t)
    keep = []
    for ln in t.splitlines():
        if re.search(r"author_local|_AL_|_AUTHOR_|_AFFIL_|通讯作者|\\ead\{|\\author\[", ln):
            continue
        keep.append(ln)
    return "\n".join(keep)


def sig(t):
    t = strip_identity(t)
    return (sorted(NUM.findall(t)),
            sorted(c.strip() for g in CITE.findall(t) for c in g.split(",")),
            sorted(REF.findall(t)), sorted(LAB.findall(t)),
            len(re.findall(r"\\begin\{equation\}", t)), len(re.findall(r"\\begin\{table", t)),
            len(re.findall(r"\\begin\{figure", t)))


def chk(cond, msg):
    print("  %s  %s" % ("PASS " if cond else "FAIL ", msg))
    if not cond:
        fails.append(msg)


for name in ("manuscript.tex", "build_word_cn.py"):
    a = sig(load(os.path.join(BASE, name), True))
    b = sig(load(os.path.join(PC, name), False))
    labels = ("数字集合", "引用键", "交叉引用键", "label", "公式数", "表数", "图数")
    bad = []
    for lb, x, y in zip(labels, a, b):
        if x != y:
            onlya = [i for i in x if i not in y][:6] if isinstance(x, list) else x
            onlyb = [i for i in y if i not in x][:6] if isinstance(y, list) else y
            bad.append("%s: -%s +%s" % (lb, onlya, onlyb))
    chk(not bad, "%s 事实层零漂移（%s）" % (name, bad or "数字/引用/引用键/label/公式表图数全同"))

print()
print("polish_gate: " + ("ALL PASS" if not fails else "%d FAIL" % len(fails)))
sys.exit(1 if fails else 0)
