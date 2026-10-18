# -*- coding: utf-8 -*-
"""R43 —— 中文表 5 表注尾句口径统一（NGBM「情景模型」→ 三模型并列 + 等权混合为 carried-forward）。

背景：R42 已按实算把 NGBM 判为不合格（C=0.604 过关，P=0.684 距 0.70 差 0.016）。
英文 Table 7 表注（manuscript.tex L342）基准说法：
  "The projection is reported for all three models because none of them dominates across
   validation schemes, and their equal-weight mixture (0.438 in 2028) is the value carried forward."
即 carried-forward 值是**等权混合 0.438**，NGBM 只是三成员之一，英文全文无「NGBM 为情景模型」。
中文表 5 表注尾句仍写「本文以 NGBM 为情景模型」，与英文口径不一致，且紧邻刚写入的
「NGBM 按该判据为不合格」而自相矛盾，故本轮只改这一句。

做法：raw `word/document.xml` 字面替换（先用标签容忍索引器确认目标落在**同一个 w:t** 内）
      + `assert 命中数 == 1`；其余 34 个 zip 部件必须逐字节相同。

用法:
    python cn_r43_align.py --dry-run
    python cn_r43_align.py --apply
    python cn_r43_align.py --verify SRC OUT
"""
import hashlib
import os
import re
import struct
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SRC = r"D:\比赛\论文\交付\2.0版本\JMS CN 论文_2.0版本.docx"
WORKDIR = r"D:\比赛\论文\_r43_work"
TARGET = "word/document.xml"

NOTE_ANCHOR = "精度等级按灰色模型惯例判定"

# ---- 唯一改动：表 5 表注尾句 -------------------------------------------------
OLD = "；本文以 NGBM 为情景模型，不宣称其为最优模型。"
NEW = "；三模型并列报告，以三者等权混合（2028 年 0.438）为外推采用值，不宣称单一最优模型。"

# R42 已写入、本轮必须原样保持的表注片段（改动面之外）
KEEP = ["（分母 n）", "按该判据为不合格", "NGBM 距 P>0.70 的阈值仅 0.016"]

# 表 5 三行（行 0 为表头）；RMSE / MAE / C / P / 2024 / 2028
EXPECT_ROWS = [
    ("0.046", "0.032", "0.603", "0.789", "0.469", "0.448"),
    ("0.046", "0.037", "0.604", "0.684", "0.424", "0.380"),
    ("0.104", "0.068", "1.320", "0.526", "0.485", "0.485"),
]


# ============================================================ 标签容忍的索引
def tokenize(xml):
    toks, i, n = [], 0, len(xml)
    while i < n:
        if xml[i] == '<':
            j, inq = i + 1, None
            while j < n:
                c = xml[j]
                if inq:
                    if c == inq:
                        inq = None
                elif c in '"\'':
                    inq = c
                elif c == '>':
                    break
                j += 1
            toks.append(('tag', i, j + 1, xml[i:j + 1]))
            i = j + 1
        else:
            j = xml.find('<', i)
            j = n if j < 0 else j
            toks.append(('text', i, j, xml[i:j]))
            i = j
    return toks


def tag_name(tag):
    m = re.match(r'</?\s*([A-Za-z0-9_:.-]+)', tag)
    return m.group(1) if m else None


def build_index(xml):
    from xml.sax.saxutils import unescape
    stack, nodes = [], []
    for kind, s, e, txt in tokenize(xml):
        if kind != 'tag':
            continue
        nm = tag_name(txt)
        if nm is None:
            continue
        if txt.startswith('</'):
            top = stack.pop()
            assert top['name'] == nm, "嵌套不匹配: %r" % txt
            top['end'] = s
            nodes.append(top)
            continue
        node = {'name': nm, 'start': s, 'end': e, 'selfclose': txt.endswith('/>')}
        if node['selfclose']:
            nodes.append(node)
        else:
            stack.append(node)
            if nm == 'w:t':
                node['cstart'] = e
    assert not stack, "未闭合元素: %s" % [x['name'] for x in stack]
    wt = []
    for nd in nodes:
        if nd['name'] != 'w:t':
            continue
        if nd['selfclose']:
            nd.update(cstart=nd['end'], cend=nd['end'], text='')
        else:
            assert xml[nd['end']:nd['end'] + 6] == '</w:t>'
            nd['cend'] = nd['end']
            nd['text'] = unescape(xml[nd['cstart']:nd['cend']])
        wt.append(nd)
    wt.sort(key=lambda n: n['cstart'])
    collect = lambda name: sorted([n for n in nodes if n['name'] == name], key=lambda n: n['start'])
    paras, tbls, trs, tcs = collect('w:p'), collect('w:tbl'), collect('w:tr'), collect('w:tc')
    for p in paras:
        p['wt'] = [c for c in wt if p['start'] < c['cstart'] < p['end']]
        p['text'] = ''.join(c['text'] for c in p['wt'])
    for tc in tcs:
        tc['wt'] = [c for c in wt if tc['start'] < c['cstart'] < tc['end']]
        tc['text'] = ''.join(c['text'] for c in tc['wt'])
    for tr in trs:
        tr['cells'] = [c for c in tcs if tr['start'] < c['start'] < tr['end']]
    for tb in tbls:
        tb['rows'] = [r for r in trs if tb['start'] < r['start'] < tb['end']]
    return {'xml': xml, 'wt': wt, 'paras': paras, 'tables': tbls}


def apply_edit(xml):
    idx = build_index(xml)

    # 1) 标签容忍定位：目标句必须完整落在同一个 w:t 内
    cand = [p for p in idx['paras'] if NOTE_ANCHOR in p['text']]
    assert len(cand) == 1, "表注锚点命中段落 %d 个（要求 1）" % len(cand)
    p = cand[0]
    assert p['text'].count(OLD) == 1, "表注段内 %r 出现 %d 次（要求 1）" % (OLD, p['text'].count(OLD))
    holders = [c for c in p['wt'] if OLD in c['text']]
    assert len(holders) == 1, "目标句跨 %d 个 w:t（要求 1，逐字符容忍匹配）" % len(holders)

    # 2) raw 字面替换 + 命中数断言
    hits = xml.count(OLD)
    assert hits == 1, "raw XML 中 %r 命中 %d 次（要求 1）" % (OLD, hits)
    new_xml = xml.replace(OLD, NEW)
    assert new_xml.count(NEW) == 1

    # 3) 整段复核
    idx2 = build_index(new_xml)
    notes = [q['text'] for q in idx2['paras'] if NOTE_ANCHOR in q['text']]
    assert len(notes) == 1, "改后表注段落数异常"
    nt = notes[0]
    assert NEW in nt and OLD not in nt, "旧句未被替换或新句缺失"
    for k in KEEP:
        assert k in nt, "R42 片段被破坏: %r" % k
    assert "以 NGBM 为情景模型" not in nt
    assert "等权混合（2028 年 0.438）" in nt, "carried-forward 口径未写入"

    # 4) 表 5 三行保持 R42 状态
    tb = idx2['tables'][7]
    for ri in (1, 2, 3):
        got = tuple(x['text'] for x in tb['rows'][ri]['cells'][1:])
        assert got == EXPECT_ROWS[ri - 1], "表 5 r%d = %r != %r" % (ri, got, EXPECT_ROWS[ri - 1])
    return new_xml, nt


# ============================================================ zip 读写与验收
def load_parts(path):
    z = zipfile.ZipFile(path)
    return z, {i.filename: z.read(i.filename) for i in z.infolist()}, [i.filename for i in z.infolist()]


def write_docx(zin, order, parts, out):
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for name in order:
            zi = zin.getinfo(name)
            ni = zipfile.ZipInfo(name, date_time=zi.date_time)
            ni.compress_type, ni.external_attr = zi.compress_type, zi.external_attr
            ni.internal_attr, ni.create_system = zi.internal_attr, zi.create_system
            ni.comment = zi.comment
            zout.writestr(ni, parts[name])


def raw_parts(path):
    data = open(path, "rb").read()
    out = {}
    for info in zipfile.ZipFile(path).infolist():
        off = info.header_offset
        sig, ver, flag, comp, t, d, crc, csize, usize, nlen, elen = struct.unpack(
            "<IHHHHHIIIHH", data[off:off + 30])
        assert sig == 0x04034b50
        st = off + 30 + nlen + elen
        out[info.filename] = data[st:st + info.compress_size]
    return out


def verify(src, new):
    zi, zn = zipfile.ZipFile(src), zipfile.ZipFile(new)
    ni = [i.filename for i in zi.infolist()]
    nn = [i.filename for i in zn.infolist()]
    ra, rb = raw_parts(src), raw_parts(new)
    du = [n for n in ni if hashlib.md5(zi.read(n)).hexdigest() != hashlib.md5(zn.read(n)).hexdigest()]
    dc = [n for n in ni if hashlib.md5(ra[n]).hexdigest() != hashlib.md5(rb[n]).hexdigest()]
    xml = zn.read(TARGET).decode("utf-8")

    def c(t):
        return len(re.findall(r"<" + t + r"[ />]", xml))

    cols = re.findall(r'<w:color w:val="([0-9A-Fa-f]{6})"', xml)
    print("zip 条目 %d/%d 顺序一致=%s  testzip=%r" % (len(ni), len(nn), ni == nn, zn.testzip()))
    print("相异部件（未压缩字节）: %s   （原始压缩字节）: %s" % (du, dc))
    print("w:tbl %d  w:tr %d  w:tc %d  w:p %d  w:r %d  w:drawing %d  wp:inline %d"
          % (c("w:tbl"), c("w:tr"), c("w:tc"), c("w:p"), c("w:r"), c("w:drawing"), c("wp:inline")))
    print("m:oMath %d  m:oMathPara %d  非黑 w:color %d / %d  （旧句残留 %d）"
          % (len(re.findall(r"<m:oMath[ >]", xml)), len(re.findall(r"<m:oMathPara[ >]", xml)),
             len([x for x in cols if x.upper() != "000000"]), len(cols), xml.count(OLD)))
    print("w:p(索引器口径) src=%d new=%d" % (
        len(build_index(zi.read(TARGET).decode('utf-8'))['paras']), len(build_index(xml)['paras'])))
    assert du == [TARGET] and dc == [TARGET], "除 document.xml 之外的部件发生变化"
    assert len(ni) == 35 and c("w:tbl") == 11 and c("w:drawing") == 10
    assert len(re.findall(r"<m:oMath[ >]", xml)) == 12
    assert not [x for x in cols if x.upper() != "000000"]
    assert zn.testzip() is None
    assert xml.count(OLD) == 0 and xml.count(NEW) == 1
    print("不变量全部通过。")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "--dry-run"
    if mode == "--verify":
        verify(sys.argv[2], sys.argv[3])
        sys.exit(0)
    print("输入:", SRC)
    zin, parts, order = load_parts(SRC)
    xml = parts[TARGET].decode("utf-8")
    if mode == "--dry-run":
        idx = build_index(xml)
        p = [q for q in idx['paras'] if NOTE_ANCHOR in q['text']]
        print("表注段落命中 %d" % len(p))
        print("raw 命中 OLD: %d" % xml.count(OLD))
        print("OLD = %r" % OLD)
        print("NEW = %r" % NEW)
        print("旧句所在 w:t 数: %d" % len([c for c in p[0]['wt'] if OLD in c['text']]))
        for ri, tr in enumerate(idx['tables'][7]['rows']):
            print("  T5 r%d: %s" % (ri, " | ".join(x['text'] for x in tr['cells'])))
        sys.exit(0)
    os.makedirs(WORKDIR, exist_ok=True)
    out = os.path.join(WORKDIR, "JMS CN 论文_2.0版本_r43.docx")
    new_xml, nt = apply_edit(xml)
    parts[TARGET] = new_xml.encode("utf-8")
    write_docx(zin, order, parts, out)
    print("写出:", out, os.path.getsize(out), "B  md5:",
          hashlib.md5(open(out, "rb").read()).hexdigest().upper())
    print("改动 1 处: 表 5 表注尾句")
    print("  旧:", OLD)
    print("  新:", NEW)
    verify(SRC, out)