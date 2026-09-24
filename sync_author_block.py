# -*- coding: utf-8 -*-
"""在 manuscript.tex 的作者块与 CRediT 段中写入真实身份信息或中性占位符。

公开复现库不应包含作者身份信息，但本地投稿构建需要真实值。
本脚本提供一条命令的双向切换（真实值取自本地私有模块 author_local.py）：

    python sync_author_block.py --placeholder   # 公开库版本（默认）
    python sync_author_block.py --write         # 本地投稿版本（真实值）
    python sync_author_block.py --status        # 查看当前状态

改动范围仅限 manuscript.tex 的四处：
    \\author[aff1]{…}  /  \\ead{…}  /  organization={…}  /  \\textbf{…}: Methodology, Software, Validation
其余内容一律不动。
"""
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(BASE, "manuscript.tex")
SENTINEL = "[Author]"

RE_AUTHOR = re.compile(r"\\author\[aff1\]\{.*?\\corref\{cor1\}\}", re.S)
RE_EAD = re.compile(r"\\ead\{.*?\}", re.S)
RE_AFFIL = re.compile(r"organization=\{.*?\}", re.S)
RE_CREDIT = re.compile(r"\\textbf\{[^}]*\}: Methodology, Software, Validation", re.S)


def real_values():
    try:
        sys.path.insert(0, BASE)
        import author_local as al
    except ImportError:
        raise SystemExit("找不到 author_local.py —— 无法取得真实作者信息")
    return al.AUTHOR_EN, al.EMAIL, al.AFFIL_EN, al.AUTHOR_EN


def current():
    s = open(TEX, encoding="utf-8").read()
    a = RE_AUTHOR.search(s)
    e = RE_EAD.search(s)
    f = RE_AFFIL.search(s)
    c = RE_CREDIT.search(s)
    grab = lambda m, rx: (re.search(rx, m.group(0), re.S).group(1) if m else "?")

    def au(m):
        return re.search(r"\\author\[aff1\]\{(.*?)\\corref", m.group(0), re.S).group(1).strip() if m else "?"

    return (au(a), grab(e, r"\\ead\{(.*?)\}"), grab(f, r"organization=\{(.*?)\}"),
            (re.search(r"\\textbf\{(.*?)\}: Methodology", c.group(0)).group(1) if c else "?"))


def apply(author, email, affil, credit_name):
    s = open(TEX, encoding="utf-8").read()
    subs = [
        (RE_AUTHOR, r"\author[aff1]{%s\corref{cor1}}" % author),
        (RE_EAD, r"\ead{%s}" % email),
        (RE_AFFIL, "organization={%s}" % affil),
        (RE_CREDIT, r"\textbf{%s}: Methodology, Software, Validation" % credit_name),
    ]
    n = 0
    for rx, rep in subs:
        s, k = rx.subn(lambda _m, r=rep: r, s, count=1)
        n += k
    open(TEX, "w", encoding="utf-8", newline="\n").write(s)
    print("manuscript.tex 已更新 %d/4 处（作者块 + CRediT）" % n)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "--placeholder"
    a, e, f, c = current()
    if mode == "--status":
        print("当前 manuscript.tex 身份字段：")
        print("  author       =", a)
        print("  ead          =", e)
        print("  organization =", f)
        print("  CRediT       =", c)
        print("  判定：", "占位符（公开库版本）" if SENTINEL in a else "真实身份信息（本地投稿版本）")
    elif mode == "--write":
        ra, re_, rf, rc = real_values()
        apply(ra, re_, rf, rc)
    elif mode == "--placeholder":
        apply(SENTINEL, "[email]", "[Affiliation]", SENTINEL)
    else:
        raise SystemExit("用法：python sync_author_block.py --placeholder|--write|--status")