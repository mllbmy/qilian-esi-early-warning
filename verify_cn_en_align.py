# -*- coding: utf-8 -*-
"""CN↔EN 逐号对应锁 v2：图/表/公式编号顺序 + 图件序列 + 表内数值（小数）集合"""
import io
import os
import re
import sys

from docx import Document as Docx
from docx.table import Table
from docx.text.paragraph import Paragraph

# 路径自解析：仓库克隆/解压到任意目录均可运行
PC = os.path.dirname(os.path.abspath(__file__))
TEX = io.open(os.path.join(PC, "manuscript.tex"), encoding="utf-8").read()
CN = os.path.join(PC, "out", "论文_CN_latest.docx")
FAILS = []


def chk(ok, msg):
    print(("  PASS   " if ok else "  FAIL   ") + msg)
    if not ok:
        FAILS.append(msg)


def decs(text):
    """取小数（科学量值），忽略引用键/表头/单位指数造成的整数噪声"""
    return sorted(round(float(x), 6) for x in re.findall(r"\d+\.\d+", text))


# ---------- EN 侧 ----------
def tex_blocks(env):
    return sorted((m.start(), m.group(1))
                  for m in re.finditer(r"\\begin\{%s\}(.*?)\\end\{%s\}" % (env, env), TEX, re.S))


en_figs, en_tabs, en_stems = [], [], []
for _, body in tex_blocks("figure"):
    img = re.search(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", body)
    cap = re.search(r"\\caption\{(.*?)\}\s*\n", body, re.S)
    stem = re.sub(r"\.(png|pdf)$", "", os.path.basename(img.group(1)))
    en_stems.append(stem)
    en_figs.append((stem, (cap.group(1).strip() if cap else "")))
for _, body in tex_blocks("table"):
    cap = re.search(r"\\caption\{(.*?)\}", body, re.S)
    row = re.search(r"\\midrule(.*?)\\bottomrule", body, re.S)
    en_tabs.append((cap.group(1).strip() if cap else "", decs(row.group(1)) if row else []))
en_eqs = len(re.findall(r"\\begin\{equation\}", TEX))

# ---------- CN 侧 ----------
doc = Docx(CN)
kids = list(doc.element.body.iterchildren())
figs, tabcaps, eqnums, data_tabs, consumed = [], [], [], [], set()
for i, ch in enumerate(kids):
    tag = ch.tag.split("}")[-1]
    if tag == "p":
        p = Paragraph(ch, doc)
        txt = p.text.strip()
        if ch.findall(".//{http://schemas.openxmlformats.org/drawingml/2006/main}blip"):
            cap = ""
            for j, nxt in enumerate(kids[i + 1:], start=i + 1):
                if nxt.tag.split("}")[-1] != "p":
                    break
                t = Paragraph(nxt, doc).text.strip()
                if t:
                    cap, consumed = t, consumed | {j}
                    break
            figs.append(cap)
    elif tag == "tbl":
        t = Table(ch, doc)
        cells = [c.text.strip() for r in t.rows for c in r.cells]
        eqn = [c for c in cells if re.match(r"^\(\d+\)$", c)]
        if eqn and len(t.columns) == 3:
            eqnums.append(int(eqn[0].strip("()")))
        else:
            body = [c.text for r in t.rows[1:] for c in r.cells]   # 去表头行
            data_tabs.append(decs(" ".join(body)))
            # 表注 = 紧邻该表格之前的段落（构建器输出顺序：表注 → 表格）。
            # 不以"段落以表号开头"为判据，避免正文句子（如"表 5 对比了…"）被误计为表注。
            if i > 0 and kids[i - 1].tag.split("}")[-1] == "p":
                ct = Paragraph(kids[i - 1], doc).text.strip()
                m = re.match(r"^表\s*(\d+)", ct)
                if m:
                    tabcaps.append(int(m.group(1)))
                    consumed.add(i - 1)

fig_nums = [int(re.match(r"^图\s*(\d+)", c).group(1)) for c in figs if re.match(r"^图\s*\d", c)]

print("EN 侧：%d 图 / %d 表 / %d 公式" % (len(en_figs), len(en_tabs), en_eqs))
print("CN 侧：%d 图 / %d 表 / %d 公式" % (len(figs), len(tabcaps), len(eqnums)))
print("CN 图号: %s | 表号: %s | 公式号: %s" % (fig_nums, tabcaps, eqnums))

print("\n[1] 数量一一对应")
chk(len(figs) == len(en_figs) == 10, "图数 CN=%d, EN=%d（应均 10，v3 加图轮）" % (len(figs), len(en_figs)))
chk(len(tabcaps) == len(en_tabs) == 8, "表数 CN=%d, EN=%d（应均 8）" % (len(tabcaps), len(en_tabs)))
chk(len(eqnums) == en_eqs == 5, "公式数 CN=%d, EN=%d（应均 5）" % (len(eqnums), en_eqs))

print("\n[2] 编号顺序（与 EN 逐号对应）")
chk(fig_nums == list(range(1, 11)), "CN 图1..图10 顺序递增：%s" % fig_nums)
chk(tabcaps == list(range(1, 9)), "CN 表1..表8 顺序递增：%s" % tabcaps)
chk(eqnums == [1, 2, 3, 4, 5], "CN (1)..(5) 顺序递增（EN 源序 权重/归一化/ESI/GM/q）：%s" % eqnums)

print("\n[3] 图件序列 = EN 源序（同图同序）")
bld = io.open(os.path.join(PC, "build_word_cn.py"), encoding="utf-8").read()
cn_host = [re.sub(r"\.(png|pdf)$", "", x) for x in re.findall(r'fig\("([^"]+)"', bld)]
chk(cn_host == en_stems, "CN fig() 源序 = EN includegraphics 源序\n           CN: %s\n           EN: %s"
    % (cn_host, en_stems))

print("\n[4] 已废弃图版不再出现")
for stale in ("fig6_weights.png", "fig7_county_esi.png", "fig8_interaction.png"):
    chk(stale not in bld, "build_word_cn.py 不再引用 %s" % stale)

print("\n[5] 表内数值（小数）集合与 EN 逐表一致")
chk(len(data_tabs) == len(en_tabs), "CN 数据表数 = %d（应 %d）" % (len(data_tabs), len(en_tabs)))
for idx, (cap, en_v) in enumerate(en_tabs, start=1):
    cn_v = data_tabs[idx - 1] if idx - 1 < len(data_tabs) else []
    chk(cn_v == en_v, "表%d 数值一致（EN %d 个 / CN %d 个）" % (idx, len(en_v), len(cn_v)))
    if cn_v != en_v:
        print("           EN: %s" % en_v)
        print("           CN: %s" % cn_v)

print("\n[6] 参考文献逐字一致（CN Word == EN Word）")
EN_WORD = os.path.join(PC, "out", "论文_EN_review.docx")


def all_text(path):
    """按文档序取出全部文本（含表格单元格）"""
    d = Docx(path)
    out = []
    for ch in d.element.body.iterchildren():
        tag = ch.tag.split("}")[-1]
        if tag == "p":
            out.append(Paragraph(ch, d).text.strip())
        elif tag == "tbl":
            for r in Table(ch, d).rows:
                out.extend(c.text.strip() for c in r.cells)
    return out


cn_txt_list, en_txt_list = all_text(CN), all_text(EN_WORD)


def ref_list(lst, head):
    """作者-年制：参考文献无序号，取标题之后的全部非空段（应为 19 条）"""
    if head not in lst:
        return []
    i = lst.index(head)
    return [p for p in lst[i + 1:] if p.strip()]


cn_refs = ref_list(cn_txt_list, "参考文献")
en_refs = ref_list(en_txt_list, "References")
chk(len(cn_refs) == len(en_refs) == 19,
    "参考文献条数 CN=%d, EN=%d（应均 19）" % (len(cn_refs), len(en_refs)))
chk(cn_refs == en_refs, "CN 与 EN 参考文献逐字一致（同一份 bbl 文本，Harvard 无序号）")
chk(not any(re.match(r"^\[\d+\]", p) for p in cn_refs + en_refs),
    "参考文献已无 [n] 序号前缀（作者-年制）")
if cn_refs != en_refs:
    for a, b in zip(cn_refs, en_refs):
        if a != b:
            print("   CN:", a[:78])
            print("   EN:", b[:78])
            break

print("\n[7] 正文引用号集合一致（含表格单元格）")


AY = re.compile(r"([A-Z][A-Za-z\u00C0-\u024F'\-]+(?: et al\.| & [A-Z][A-Za-z'\-]+| and [A-Z][A-Za-z'\-]+)?), (\d{4})")


def body_cites(lst, stop):
    """返回 (作者-年引用集合, 残留数字引用集合)"""
    out, bad = set(), set()
    for p in lst:
        if p == stop:
            break
        for m in AY.finditer(p):
            out.add("%s, %s" % (m.group(1), m.group(2)))
        for b in re.findall(r"\[(\d{1,2}(?:[,-]\d{1,2})*)\]", p):
            ns = [int(x) for x in re.split(r"[,-]", b)]
            if all(n >= 1 for n in ns):
                bad.add(b)
    return out, bad


cn_set, cn_bad = body_cites(cn_txt_list, "参考文献")
en_set, en_bad = body_cites(en_txt_list, "References")
chk(not cn_bad and not en_bad, "正文已无 [n] 数字引用（CN 残留 %s / EN 残留 %s）" % (sorted(cn_bad), sorted(en_bad)))
chk(cn_set == en_set, "作者-年引用集合一致（CN %d 条 == EN %d 条）" % (len(cn_set), len(en_set)))
if cn_set != en_set:
    print("   CN 缺:", sorted(en_set - cn_set), " CN 多:", sorted(cn_set - en_set))

print("\nverify_cn_en_align: %s" % ("ALL PASS" if not FAILS else "%d FAIL" % len(FAILS)))
sys.exit(1 if FAILS else 0)