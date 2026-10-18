# -*- coding: utf-8 -*-
"""R40 —— 中文稿三处口径对齐（表 5 / §4.10 / §4.1）。

只改交付 docx 的 `word/document.xml`：标签容忍的字面替换，每次替换 assert 命中数 == 1；
其余 34 个 zip 部件字节不变。英文稿（manuscript.tex / PDF）本轮未改动。

用法:
    python cn_r40_align.py --dry-run     # 只定位与打印目标，不写文件
    python cn_r40_align.py --apply       # 写出 _r40_work 下的新 docx（不覆盖交付件）
    python cn_r40_align.py --verify OUT  # 逐部件字节比对 + 不变量 + 目标内容复核

数值出处：data/r29_forecast_8ind.csv、data/r29_2028_range.csv、data/r32_validation_8ind.csv、
data/r32_validation_8ind_vs9.csv、data/results_obstacle.csv、data/r28_obstacle_sensitivity.csv、
data/r29_weights_8ind_criteria.csv。改动的 22 个段落见 R40 报告。
"""
import sys, os, re, struct, json, zipfile, hashlib
from xml.sax.saxutils import escape, unescape

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SRC_PREV = r"D:\比赛\论文\交付\2.0版本\_旧版_2.0_R39.docx"      # R39 留档（本轮的输入）
SRC_DEFAULT = SRC_PREV if os.path.exists(SRC_PREV) else r"D:\比赛\论文\交付\2.0版本\JMS CN 论文_2.0版本.docx"
WORKDIR = r"D:\比赛\论文\_r40_work"
TARGET = "word/document.xml"

# ============================================================ 新文本（来自 CSV / 英文定稿）
CAP_OLD = "2005–2023 ESI 序列的预测模型对比"
CAP_NEW = "八指标主口径 ESI 序列（α=0.4）的预测模型对比"

NOTE_NEW = (
    "注：表中 RMSE/MAE 为八指标主口径 2005–2023 全序列拟合精度，C、P 为后验差比值与小误差概率；"
    "2024 与 2028 两列为八指标主口径（α=0.4）下三模型的点预测（结果表 r29_forecast_8ind.csv、r29_2028_range.csv）。"
    "精度等级按灰色模型惯例判定——合格（C<0.50，P>0.80）、勉强合格（C<0.65，P>0.70）、其余为不合格；"
    "本文以 NGBM 为情景模型，不宣称其为最优模型。八指标主口径下五种验证方案的 RMSE 排序（结果表 r32_validation_8ind.csv）："
    "单次留出 ARIMA 0.037 < GM(1,1) 0.040 < NGBM 0.089；2013 年起滚动一步 GM(1,1) 0.036 < ARIMA 0.049 < NGBM 0.070；"
    "2015 年起滚动一步 GM(1,1) 0.040 < ARIMA 0.055 < NGBM 0.064；滚动五步 GM(1,1) 0.039 < ARIMA 0.041 < NGBM 0.110；"
    "LOOCV ARIMA 0.078 < GM(1,1) 0.086 < NGBM 0.102（ARIMA 在 19 折中 15 折最优）。"
    "九指标口径对照（同一协议，仅输入序列不同）：单次留出 GM(1,1) 0.065、NGBM 0.069、ARIMA 0.040；"
    "2013 年起滚动一步 GM(1,1) 0.052 < ARIMA 0.053 < NGBM 0.059；2015 年起滚动一步 NGBM 0.051 < GM(1,1) 0.055 < ARIMA 0.059；"
    "滚动五步 ARIMA 0.050 < GM(1,1) 0.087 ≈ NGBM 0.088；LOOCV GM(1,1) 0.089 < ARIMA 0.101 < NGBM 0.127"
    "（GM(1,1) 在 19 年中 15 年最优）。九指标口径的无泄漏变体（归一化范围与熵权在训练窗内重估）"
    "排序逆转为 NGBM 0.047 < ARIMA 0.085 < GM(1,1) 0.099。"
)

BODY_OLD = ("模型比较方面（五种验证方案在九指标口径下计算，八指标主口径仅重算留出方案，见本节注）："
            "单次留出的 RMSE 为 NGBM 0.069、GM(1,1) 0.065、ARIMA 0.040")
BODY_NEW = ("模型比较方面（五种验证方案在八指标主口径下按同一协议重算，九指标口径列作对照，见本节注）："
            "八指标主口径下单次留出的 RMSE 为 ARIMA 0.037、GM(1,1) 0.040、NGBM 0.089"
            "（九指标对照为 NGBM 0.069、GM(1,1) 0.065、ARIMA 0.040）")

OBST_NEW = (
    "障碍度按 O_ij=(1-x′_ij)·w_j 计算，并经 O*_ij=O_ij/Σ_j O_ij 在年内跨指标归一化（各项之和为 1）；"
    "阶段值取阶段内年值的算术平均。阶段划分本身是描述性的：峰值年 2010 是唯一有效判据，"
    "Pettitt 检验未给出显著变点（K=56，p=0.148，变点 2016），分段均值差最大点在 2008 年，政策期划分无法用本文数据验证。"
    "障碍度诊断（Jing et al., 2024）显示约束条件存在阶段性转变：八指标主口径下，"
    "恢复期（2005–2010）的主要障碍为水域占比（0.274）、森林占比（0.260）与草地占比（0.127），反映水资源与森林规模不足；"
    "平台期（2011–2023）转为草地变化率（0.384）、耕地占比（0.218）与水域占比（0.099），"
    "表明草地动态与耕地扩张已成为主导约束（图 10）。阶段均值是权重条件量："
    "归档九指标障碍度表的组合权重下，平台期首位仍为草地变化率（0.364），其次为耕地占比（0.206）；"
    "仅熵权时平台期首位仍为草地变化率（0.368）、其次耕地；等权时首位变为耕地占比（0.218）；"
    "仅 AHP 时恢复期首位变为森林占比（0.246）。独立复算与归档阶段值最大差 0.014"
    "（差异最大的是草地变化率与生态用地占比），四权重方案 × 两阶段明细见结果表 r28_obstacle_sensitivity.csv。"
)

AHP_OLD = "为信息量最大的信号；组合权重（"
AHP_NEW = ("为信息量最大的信号；AHP 准则权重（规则 A 将存活准则归一）突出状态层三项指标"
           "（草地、森林与水域占比，各 0.195）与影响层草地变化率（0.198），"
           "以规则 D 重解 4×4 存活矩阵作敏感性时与规则 A 的最大差为 0.0122（状态层）；组合权重（")

# 表 5（第 8 张表，索引 7）：(行, 列, 旧值, 新值)；GM 的 P=0.789 与 ARIMA 的 P=0.632 原本一致，故不在列
CELLS = [
    (1, 1, "0.052", "0.047"), (1, 2, "0.035", "0.034"), (1, 3, "0.597", "0.603"),
    (1, 5, "0.510", "0.469"), (1, 6, "0.493", "0.448"),
    (2, 0, "NGBM (γ=0.20)", "NGBM (γ=0.15)"),
    (2, 1, "0.038", "0.031"), (2, 2, "0.029", "0.024"), (2, 3, "0.442", "0.428"),
    (2, 4, "0.895", "0.947"), (2, 5, "0.446", "0.424"), (2, 6, "0.394", "0.380"),
    (3, 1, "0.098", "0.097"), (3, 2, "0.067", "0.066"), (3, 3, "1.086", "1.090"),
    (3, 5, "0.488", "0.485"), (3, 6, "0.488", "0.485"),
]


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
            if a > fa and b <= la:      # 严格位于首末项之间（末项起点即中段终点）
                edits.append((it, ''))
        edits.append((li, suf))
    edits.sort(key=lambda x: -x[0]['cstart'])
    new = xml
    for it, txt in edits:
        new = new[:it['cstart']] + escape(txt) + new[it['cend']:]
    return new


def edit_para(xml, idx, anchor, old_sub, new_text, label, whole=False):
    cand = [p for p in idx['paras'] if anchor in p['text']]
    assert len(cand) == 1, "%s: 命中段落 %d 个（要求 1）" % (label, len(cand))
    p = cand[0]
    if whole:
        s, e = 0, len(p['text'])
    else:
        assert p['text'].count(old_sub) == 1, "%s: 段内目标 %d 次" % (label, p['text'].count(old_sub))
        s = p['text'].index(old_sub)
        e = s + len(old_sub)
    return replace_in_items(xml, p['wt'], s, e, new_text, label)


def edit_cell(xml, idx, tbl_i, row_i, cell_i, old_text, new_text, label):
    tc = idx['tables'][tbl_i]['rows'][row_i]['cells'][cell_i]
    assert tc['text'] == old_text, "%s: 单元格 %r != %r" % (label, tc['text'], old_text)
    return replace_in_items(xml, tc['wt'], 0, len(tc['text']), new_text, label)


# ============================================================ 主流程
def load_parts(path):
    z = zipfile.ZipFile(path)
    return z, {i.filename: z.read(i.filename) for i in z.infolist()}, [i.filename for i in z.infolist()]


def apply_edits(xml):
    rec = []
    for (r, c, old, new) in CELLS:
        xml = edit_cell(xml, build_index(xml), 7, r, c, old, new, "T5 r%d c%d" % (r, c))
        rec.append(("table", r, c, old, new))
    xml = edit_para(xml, build_index(xml), "序列的预测模型对比", CAP_OLD, CAP_NEW, "T5 caption")
    xml = edit_para(xml, build_index(xml), "精度等级按灰色模型惯例判定", None, NOTE_NEW, "T5 note", whole=True)
    xml = edit_para(xml, build_index(xml), "模型比较方面（五种验证方案", BODY_OLD, BODY_NEW, "body 4.3")
    xml = edit_para(xml, build_index(xml), "障碍度按 O_ij", None, OBST_NEW, "4.10", whole=True)
    xml = edit_para(xml, build_index(xml), "为信息量最大的信号", AHP_OLD, AHP_NEW, "4.1")
    # 整段精确复核
    chk = {p['text']: 1 for p in build_index(xml)['paras']}
    assert NOTE_NEW in chk and OBST_NEW in chk, "整段替换未干净"
    assert "表 5  " + CAP_NEW in chk and AHP_NEW in "".join(chk), "表题/§4.1 异常"
    return xml, rec


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
    c = lambda t: len(re.findall(r"<" + t + r"[ />]", xml))
    cols = re.findall(r'<w:color w:val="([0-9A-Fa-f]{6})"', xml)
    print("zip 条目 %d/%d 顺序一致=%s  testzip=%r" % (len(ni), len(nn), ni == nn, zn.testzip()))
    print("相异部件（未压缩字节）: %s   （原始压缩字节）: %s" % (du, dc))
    print("w:tbl %d  w:tr %d  w:tc %d  w:p %d  w:r %d  w:drawing %d  wp:inline %d"
          % (c("w:tbl"), c("w:tr"), c("w:tc"), c("w:p"), c("w:r"), c("w:drawing"), c("wp:inline")))
    print("m:oMath %d  m:oMathPara %d  非黑 w:color %d / %d"
          % (len(re.findall(r"<m:oMath[ >]", xml)), len(re.findall(r"<m:oMathPara[ >]", xml)),
             len([x for x in cols if x.upper() != "000000"]), len(cols)))
    assert du == [TARGET] and dc == [TARGET], "除 document.xml 之外的部件发生变化"
    assert len(ni) == 35 and c("w:tbl") == 11 and c("w:drawing") == 10
    assert len(re.findall(r"<m:oMath[ >]", xml)) == 12
    assert not [x for x in cols if x.upper() != "000000"]


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "--dry-run"
    src = sys.argv[3] if len(sys.argv) > 3 else SRC_DEFAULT
    if mode == "--verify":
        verify(src, sys.argv[2]); sys.exit(0)
    print("输入:", src)
    zin, parts, order = load_parts(src)
    xml = parts[TARGET].decode("utf-8")
    if mode == "--dry-run":
        idx = build_index(xml)
        for a in ("序列的预测模型对比", "精度等级按灰色模型惯例判定", "模型比较方面（五种验证方案",
                  "障碍度按 O_ij", "为信息量最大的信号"):
            print("%-24s 段落命中 %d" % (a, len([p for p in idx['paras'] if a in p['text']])))
        for ri, tr in enumerate(idx['tables'][7]['rows']):
            print("  r%d: %s" % (ri, " | ".join(x['text'] for x in tr['cells'])))
        sys.exit(0)
    os.makedirs(WORKDIR, exist_ok=True)
    out = os.path.join(WORKDIR, "JMS CN 论文_2.0版本_r40.docx")
    new_xml, rec = apply_edits(xml)
    parts[TARGET] = new_xml.encode("utf-8")
    write_docx(zin, order, parts, out)
    print("写出:", out, os.path.getsize(out), "B  md5:", hashlib.md5(open(out, "rb").read()).hexdigest().upper())
    verify(src, out)