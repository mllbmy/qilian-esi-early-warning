# -*- coding: utf-8 -*-
"""R42 —— 中文稿表 5 精度四列订正 + 表注判级/分母口径同步。

只改交付 docx 的 `word/document.xml`：标签容忍的字面替换，每次替换 assert 命中数 == 1；
其余 34 个 zip 部件字节不变。

数值出处：`data/r42_table7_accuracy.csv`（由 `run_r42_table7_accuracy.py` 生成，
口径函数 import 自已提交的 `run_r41_accuracy_8ind.py`，已在九指标归档序列上逐格复现
`results_forecast_accuracy.csv`，max|Δ|=4.5e-05）。

用法:
    python cn_r42_align.py --dry-run      # 只定位与打印目标，不写字
    python cn_r42_align.py --apply        # 写出 _r42_work 下的新 docx（不覆盖交付件）
    python cn_r42_align.py --verify SRC OUT
"""
import hashlib
import os
import re
import struct
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SRC = r"D:\比赛\论文\交付\2.0版本\JMS CN 论文_2.0版本.docx"
WORKDIR = r"D:\比赛\论文\_r42_work"
TARGET = "word/document.xml"

# 表 5（第 8 张表，索引 7）：(行, 列, 旧值, 新值)。行 0 为表头。
# 四列 = RMSE（拟合）/ MAE / C / P；2024、2028 两列可复现，不动。
CELLS = [
    (1, 1, "0.047", "0.046"), (1, 2, "0.034", "0.032"),
    (2, 1, "0.031", "0.046"), (2, 2, "0.024", "0.037"),
    (2, 3, "0.428", "0.604"), (2, 4, "0.947", "0.684"),
    (3, 1, "0.097", "0.104"), (3, 2, "0.066", "0.068"),
    (3, 3, "1.090", "1.320"), (3, 4, "0.632", "0.526"),
]

NOTE_ANCHOR = "精度等级按灰色模型惯例判定"
DENOM_ANCHOR = "全序列拟合精度"

# 追加到"全序列拟合精度"之后（对应英文表注的 "(divisor $n$)"）
DENOM_TAIL = "（分母 n）"
# 追加到"其余为不合格"之后（按论文自定规则重判的级次结论）
GRADE_TAIL = ("：GM(1,1) 为勉强合格（C=0.603，P=0.789），"
              "NGBM（C=0.604，P=0.684）与 ARIMA（C=1.320，P=0.526）按该判据为不合格，"
              "NGBM 距 P>0.70 的阈值仅 0.016")


# ============================================================ 标签容忍的索引与替换
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


from xml.sax.saxutils import escape, unescape  # noqa: E402


def replace_in_items(xml, items, s_off, e_off, repl, label):
    cum, pos = [], 0
    for it in items:
        cum.append((pos, pos + len(it['text']), it))
        pos += len(it['text'])
    assert 0 <= s_off < e_off <= pos, "%s: 区间越界" % label
    first = last = None
    for (a, b, it) in cum:
        if first is None and a <= s_off < b:
            first = (a, b, it)
        if a < e_off <= b:
            last = (a, b, it)
            break
    assert first and last, "%s: 区间无法定位" % label
    fa, fb, fi = first
    la, lb, li = last
    pre, suf = fi['text'][:s_off - fa], li['text'][e_off - la:]
    edits = []
    if fi is li:
        edits.append((fi, pre + repl + suf))
    else:
        edits.append((fi, pre + repl))
        for (a, b, it) in cum:
            if a > fa and b <= la:
                edits.append((it, ''))
        edits.append((li, suf))
    edits.sort(key=lambda x: -x[0]['cstart'])
    new = xml
    for it, txt in edits:
        new = new[:it['cstart']] + escape(txt) + new[it['cend']:]
    return new


def edit_cell(xml, tbl_i, row_i, cell_i, old_text, new_text, label):
    tc = build_index(xml)['tables'][tbl_i]['rows'][row_i]['cells'][cell_i]
    assert tc['text'] == old_text, "%s: 单元格 %r != %r" % (label, tc['text'], old_text)
    return replace_in_items(xml, tc['wt'], 0, len(tc['text']), new_text, label)


def edit_para_regex(xml, anchor, pattern, tail, label):
    """在唯一命中 anchor 的段落内，把正则 pattern 匹配到的片段整体替换为 匹配文本+tail。"""
    idx = build_index(xml)
    cand = [p for p in idx['paras'] if anchor in p['text']]
    assert len(cand) == 1, "%s: 命中段落 %d 个（要求 1）" % (label, len(cand))
    p = cand[0]
    ms = list(re.finditer(pattern, p['text']))
    assert len(ms) == 1, "%s: 段内匹配 %d 次（要求 1）" % (label, len(ms))
    m = ms[0]
    repl = m.group(0) + tail
    return replace_in_items(xml, p['wt'], m.start(), m.end(), repl, label)


def apply_edits(xml):
    rec = []
    for (r, c, old, new) in CELLS:
        xml = edit_cell(xml, 7, r, c, old, new, "T5 r%d c%d" % (r, c))
        rec.append(("cell", r, c, old, new))
    xml = edit_para_regex(xml, DENOM_ANCHOR, r"八指标主口径\s*2005–2023\s*全序列拟合精度",
                          DENOM_TAIL, "T5 note denom")
    rec.append(("note-denom", None, None, "全序列拟合精度", "全序列拟合精度" + DENOM_TAIL))
    xml = edit_para_regex(xml, NOTE_ANCHOR,
                          r"精度等级按灰色模型惯例判定.*?其余为不合格",
                          GRADE_TAIL, "T5 note grade")
    rec.append(("note-grade", None, None, "…其余为不合格", "…其余为不合格" + GRADE_TAIL))
    # 整段精确复核
    idx2 = build_index(xml)
    notes = [p['text'] for p in idx2['paras'] if NOTE_ANCHOR in p['text']]
    assert len(notes) == 1, "表注段落数异常"
    nt = notes[0]
    assert "（分母 n）" in nt and "按该判据为不合格" in nt, "表注未写全"
    assert "；本文以 NGBM 为情景模型，不宣称其为最优模型。" in nt, "表注尾句被破坏"
    # 表格复核：逐行整行比对（GM 的 C/P 未变，故按整行断言）
    tb = idx2['tables'][7]
    expect_rows = [
        ("0.046", "0.032", "0.603", "0.789", "0.469", "0.448"),
        ("0.046", "0.037", "0.604", "0.684", "0.424", "0.380"),
        ("0.104", "0.068", "1.320", "0.526", "0.485", "0.485"),
    ]
    for ri in (1, 2, 3):
        got = tuple(x['text'] for x in tb['rows'][ri]['cells'][1:])
        assert got == expect_rows[ri - 1], "表 5 r%d = %r != %r" % (ri, got, expect_rows[ri - 1])
    return xml, rec


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
        sig, ver, flag, comp, t, d, crc, csize, usize, nlen, elen = struct.unpack("<IHHHHHIIIHH", data[off:off + 30])
        assert sig == 0x04034b50
        st = off + 30 + nlen + elen
        out[info.filename] = data[st:st + info.compress_size]
    return out


def verify(src, new):
    zi, zn = zipfile.ZipFile(src), zipfile.ZipFile(new)
    ni, nn = [i.filename for i in zi.infolist()], [i.filename for i in zn.infolist()]
    ra, rb = raw_parts(src), raw_parts(new)
    du = [n for n in ni if hashlib.md5(zi.read(n)).hexdigest() != hashlib.md5(zn.read(n)).hexdigest()]
    dc = [n for n in ni if hashlib.md5(ra[n]).hexdigest() != hashlib.md5(rb[n]).hexdigest()]
    xml = zn.read(TARGET).decode("utf-8")

    def c(t):
        return len(re.findall(r"<" + t + r"[ />]", xml))

    cols = re.findall(r'<w:color w:val="([0-9A-Fa-f]{6})"', xml)
    par = lambda s: len(re.findall(r"<w:p[ />]", s))
    print("zip 条目 %d/%d 顺序一致=%s  testzip=%r" % (len(ni), len(nn), ni == nn, zn.testzip()))
    print("相异部件（未压缩字节）: %s   （原始压缩字节）: %s" % (du, dc))
    print("w:tbl %d  w:tr %d  w:tc %d  w:p %d  w:r %d  w:drawing %d  wp:inline %d"
          % (c("w:tbl"), c("w:tr"), c("w:tc"), c("w:p"), c("w:r"), c("w:drawing"), c("wp:inline")))
    print("m:oMath %d  m:oMathPara %d  非黑 w:color %d / %d"
          % (len(re.findall(r"<m:oMath[ >]", xml)), len(re.findall(r"<m:oMathPara[ >]", xml)),
             len([x for x in cols if x.upper() != "000000"]), len(cols)))
    print("w:p(索引器口径) src=%d new=%d" % (len(build_index(zi.read(TARGET).decode('utf-8'))['paras']),
                                              len(build_index(xml)['paras'])))
    assert du == [TARGET] and dc == [TARGET], "除 document.xml 之外的部件发生变化"
    assert len(ni) == 35 and c("w:tbl") == 11 and c("w:drawing") == 10
    assert len(re.findall(r"<m:oMath[ >]", xml)) == 12
    assert not [x for x in cols if x.upper() != "000000"]
    assert zn.testzip() is None
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
        for a in (NOTE_ANCHOR, DENOM_ANCHOR):
            print("%-16s 段落命中 %d" % (a, len([p for p in idx['paras'] if a in p['text']])))
        for ri, tr in enumerate(idx['tables'][7]['rows']):
            print("  r%d: %s" % (ri, " | ".join(x['text'] for x in tr['cells'])))
        p = [p for p in idx['paras'] if NOTE_ANCHOR in p['text']][0]
        for pat in (r"八指标主口径\s*2005–2023\s*全序列拟合精度",
                    r"精度等级按灰色模型惯例判定.*?其余为不合格"):
            ms = list(re.finditer(pat, p['text']))
            print("  模式 %-40s 命中 %d -> %r" % (pat[:38], len(ms), ms[0].group(0) if ms else None))
        sys.exit(0)
    os.makedirs(WORKDIR, exist_ok=True)
    out = os.path.join(WORKDIR, "JMS CN 论文_2.0版本_r42.docx")
    new_xml, rec = apply_edits(xml)
    parts[TARGET] = new_xml.encode("utf-8")
    write_docx(zin, order, parts, out)
    print("写出:", out, os.path.getsize(out), "B  md5:",
          hashlib.md5(open(out, "rb").read()).hexdigest().upper())
    print("改动 %d 处:" % len(rec))
    for r in rec:
        print("   ", r)
    verify(SRC, out)