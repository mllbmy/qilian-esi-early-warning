# -*- coding: utf-8 -*-
"""把 Word 稿重排为「图文对应」阅读版：每个图/表块移动到**首次引用它的段落之后**。

只移动块的位置，不改动任何文字内容；用于生成阅读/校对版，
不用于投稿件（JMS 要求图表统一置于正文之后）。

用法：
    python make_readable_version.py <源.docx> <输出.docx> --lang en|cn

判定规则
--------
- 图块 = [图片段落, 图注段落]（构建器 fig() 的输出顺序）
- 表块 = [表注段落, 表格元素] (+ 紧随其后、位于文末图表区的表注说明段)
- 正文引用样式：EN `Fig. 7` / `Fig. 10` / `Table 5`；CN `图 7` / `表 5`
- 图注/表注段落本身不参与引用检索，避免"自引用"
- 锚点按 (类型, 编号) 索引，避免"图1 与表1 同号"冲突
- 未找到正文引用的块保持原位置，并在报告中标出
"""
import re
import shutil
import sys

from docx import Document
from docx.oxml.ns import qn

P, T = qn("w:p"), qn("w:tbl")


def body_kids(doc):
    return [k for k in doc.element.body.iterchildren() if k.tag in (P, T)]


def ptext(k):
    return "".join(n.text or "" for n in k.iter(qn("w:t")))


def has_img(k):
    return k.tag == P and k.find(".//" + qn("w:drawing")) is not None


def is_note(k):
    """表注段：居中 + 小字号（构建器 para(..., 9/10, align=CENTER) 的输出）。"""
    if k.tag != P:
        return False
    pPr = k.find(qn("w:pPr"))
    jc = None
    if pPr is not None:
        j = pPr.find(qn("w:jc"))
        if j is not None:
            jc = j.get(qn("w:val"))
    sizes = []
    for sz in k.iter(qn("w:sz")):
        v = sz.get(qn("w:val"))
        if v:
            sizes.append(int(v) / 2.0)
    return jc == "center" and bool(sizes) and max(sizes) <= 9.5


class Layout(object):
    """扫描出：正文结束位置、图/表块、块元素集合、引用锚点。"""

    def __init__(self, els, lang):
        self.els = els
        self.lang = lang
        if lang == "en":
            self.cap_fig = re.compile(r"^Figure\s*(\d+)\s*[.\s]")
            self.cap_tab = re.compile(r"^Table\s*(\d+)\s*[.\s]")
            self.ref_fig = lambda n: re.compile(r"Fig(?:ure)?s?\.?\s*%d(?!\d)" % n)
            self.ref_tab = lambda n: re.compile(r"Tables?\s*%d(?!\d)" % n)
            self.heads = ("References",)
            self.sec_heads = ("Figures", "Tables", "References")
        else:
            self.cap_fig = re.compile(r"^图\s*(\d+)\s")
            self.cap_tab = re.compile(r"^表\s*(\d+)\s")
            self.ref_fig = lambda n: re.compile(r"图\s*%d(?!\d)" % n)
            self.ref_tab = lambda n: re.compile(r"表\s*%d(?!\d)" % n)
            self.heads = ("参考文献",)
            self.sec_heads = ("参考文献",)

        self.tail_start = len(els)
        for i, k in enumerate(els):
            if k.tag == P and ptext(k).strip() in self.heads:
                self.tail_start = i
                break

        self.figs = {}
        self.tabs = {}
        self.block_els = set()
        self._scan()

    def _scan(self):
        els = self.els
        for i, k in enumerate(els):
            if k.tag != P:
                continue
            txt = ptext(k).strip()
            if not txt:
                continue
            m = self.cap_fig.match(txt)
            if m and i > 0 and has_img(els[i - 1]):          # 图注：紧随图片段落
                self.figs[int(m.group(1))] = [els[i - 1], els[i]]
                self.block_els.update([els[i - 1], els[i]])
                continue
            m = self.cap_tab.match(txt)
            if m and i + 1 < len(els) and els[i + 1].tag == T:   # 表注：后随表格
                blk = [els[i], els[i + 1]]
                j = i + 2
                if j < len(els) and els[j].tag == P and is_note(els[j]):
                    nt = ptext(els[j]).strip()
                    if nt and self.cap_fig.match(nt) is None and self.cap_tab.match(nt) is None \
                            and nt not in self.sec_heads:
                        blk.append(els[j])
                self.tabs[int(m.group(1))] = blk
                self.block_els.update(blk)

    def anchors(self):
        """(kind, n) -> 正文区首次引用该图/表的段落元素。"""
        out = {}
        for kind, store, mk in (("fig", self.figs, self.ref_fig), ("tab", self.tabs, self.ref_tab)):
            for n in sorted(store):
                rx = mk(n)
                for k in self.els[:self.tail_start]:
                    if k.tag != P or k in self.block_els:
                        continue
                    if rx.search(ptext(k)):
                        out[(kind, n)] = k
                        break
        return out

    def ref_pos(self, anchor, kind, n):
        rx = self.ref_fig(n) if kind == "fig" else self.ref_tab(n)
        m = rx.search(ptext(anchor))
        return m.start() if m else 10 ** 6

    def report_pairs(self):
        """供报告使用：(类型, 编号, 锚点片段)。"""
        out = []
        for (kind, n), a in sorted(self.anchors().items(), key=lambda kv: (kv[0][0], kv[0][1])):
            out.append((kind, n, ptext(a).strip()[:46]))
        return out


def cleanup_tail(doc, lay):
    """EN：图表搬空后，删除文末残留的空段与 "Figures"/"Tables" 标题（绝不删内容）。"""
    els = body_kids(doc)
    head = next((i for i, k in enumerate(els) if k.tag == P and ptext(k).strip() in lay.heads), None)
    if head is None:
        return 0, []
    ref_last = None
    for i in range(head + 1, len(els)):
        k = els[i]
        if k.tag == P and k not in lay.block_els:
            t = ptext(k).strip()
            if t and t not in lay.sec_heads:
                ref_last = k
    if ref_last is None:
        return 0, []
    drop, keep = [], []
    cur = ref_last.getnext()
    while cur is not None:
        nxt = cur.getnext()
        if cur.tag in (P, T):
            t = ptext(cur).strip()
            if cur in lay.block_els or cur.tag == T:
                keep.append(cur)
            elif (not t) or t in lay.sec_heads:
                drop.append(cur)
            else:
                keep.append(cur)
        cur = nxt
    for el in drop:
        el.getparent().remove(el)
    return len(drop), keep


def move(src, out, lang):
    shutil.copyfile(src, out)
    doc = Document(out)
    lay = Layout(body_kids(doc), lang)
    anchors = lay.anchors()

    plan, missing = {}, []
    for kind, store in (("fig", lay.figs), ("tab", lay.tabs)):
        for n, blk in sorted(store.items()):
            a = anchors.get((kind, n))
            if a is None:
                missing.append((kind, n))
                continue
            plan.setdefault(id(a), (a, []))[1].append((kind, n))

    for anchor, items in plan.values():
        items.sort(key=lambda kv: (lay.ref_pos(anchor, kv[0], kv[1]), 0 if kv[0] == "fig" else 1, kv[1]))
        cur = anchor
        for kind, n in items:
            for el in (lay.figs[n] if kind == "fig" else lay.tabs[n]):
                cur.addnext(el)
                cur = el

    cleaned, leftover = (0, [])
    if lang == "en":
        cleaned, leftover = cleanup_tail(doc, lay)
    doc.save(out)
    return lay, anchors, missing, cleaned, leftover


def verify(path, lang):
    doc = Document(path)
    els = body_kids(doc)
    lay = Layout(els, lang)
    bad = []
    for kind, store, mk in (("图", lay.figs, lay.ref_fig), ("表", lay.tabs, lay.ref_tab)):
        for n in sorted(store):
            i = els.index(store[n][0])
            j = i - 1
            while j >= 0 and els[j] in lay.block_els:
                j -= 1
            prev = els[j] if j >= 0 else None
            if prev is None or prev.tag != P or not mk(n).search(ptext(prev)):
                bad.append("%s%d" % (kind, n))
    tail_left = [el for el in els[lay.tail_start + 1:] if el in lay.block_els]
    print("  校验：%s（未就位：%s；文末残留图表块 %d）" % (
        "通过 ✓" if not bad and not tail_left else "需检查", ", ".join(bad) or "无", len(tail_left)))
    return not bad and not tail_left


if __name__ == "__main__":
    src, out = sys.argv[1], sys.argv[2]
    lang = sys.argv[sys.argv.index("--lang") + 1] if "--lang" in sys.argv else "en"
    lay, anchors, missing, cleaned, leftover = move(src, out, lang)
    print("=== %s ===" % out)
    print("  图块 %d：%s | 表块 %d：%s" % (
        len(lay.figs), sorted(lay.figs), len(lay.tabs), sorted(lay.tabs)))
    print("  引用锚点命中 %d/%d" % (len(anchors), len(lay.figs) + len(lay.tabs)))
    if missing:
        print("  ⚠ 无正文引用、保持原位：%s" % ["%s%d" % m for m in missing])
    if cleaned:
        print("  文末残留清理 %d 个元素（空段/图表区标题）" % cleaned)
    if leftover:
        print("  ⚠ 文末仍有内容未清理：%d 个元素" % len(leftover))
    print("  对应关系（前 20 条）：")
    for kind, n, snippet in Layout(body_kids(Document(out)), lang).report_pairs()[:20]:
        print("     %s%-3d ← %s" % ("图" if kind == "fig" else "表", n, snippet))
    verify(out, lang)