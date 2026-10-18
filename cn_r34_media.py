# -*- coding: utf-8 -*-
"""R34: replace the Chinese manuscript's embedded figure bitmaps with the current English figures.

Applied to Figs 2, 3, 4, 5 and 6 (CN numbering) so that the embedded bitmaps match the figures the
Chinese text now describes.  Bitmaps are rasterised at the pixel size of the media they replace, so
the frame/size in the document is unchanged.  Captions are edited through a run-splitting-tolerant
literal match on the paragraph's own text.
"""
import hashlib
import os
import re
import sys
import zipfile

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import fitz

SRC = r'D:\比赛\论文\交付\2.0版本\JMS CN 论文_2.0版本.docx'
BASE = r'D:\比赛\论文\paper-code'
zin = zipfile.ZipFile(SRC)
names = zin.namelist()
all_old = {n: zin.read(n) for n in names}
xml = all_old['word/document.xml'].decode('utf-8')
rels = all_old['word/_rels/document.xml.rels'].decode('utf-8')
RID = dict(re.findall(r'Id="(rId\d+)"[^>]*Target="([^"]+)"', rels))
PARA = re.compile(r'<w:p\b[^>]*>.*?</w:p>', re.S)

# CN caption -> current English figure
TARGETS = {
    '图 2': 'figures/fig_dpsir_framework.pdf',
    '图 3': 'figures/fig_indicator_trends.pdf',
    '图 4': 'figures/fig3_esi_timeseries.pdf',
    '图 5': 'figures/fig_weights.pdf',
    '图 6': 'figures/fig4_alpha_sensitivity.pdf',
}
CAPTION = re.compile(r'^\s*图\s*(\d+)\s{2}')
plan, blocks = [], []
for m in PARA.finditer(xml):
    b = m.group(0)
    txt = ''.join(re.findall(r'<w:t[^>]*>(.*?)</w:t>', b, re.S))
    cm = CAPTION.match(txt)
    blip = re.search(r'<a:blip[^>]*r:embed="(rId\d+)"', b)
    if blip:
        blocks.append(('IMG', m.start(), 'word/' + RID[blip.group(1)].lstrip('/')))
    elif cm:
        blocks.append(('CAP', m.start(), txt))
for i, it in enumerate(blocks):
    if it[0] == 'CAP':
        key = '图 %s' % CAPTION.match(it[2]).group(1)
        if key in TARGETS:
            prev = next((blocks[j] for j in range(i - 1, -1, -1) if blocks[j][0] == 'IMG'), None)
            plan.append((key, prev[2], TARGETS[key], it[2]))
print('planned:', [(k, os.path.basename(m), os.path.basename(p)) for k, m, p, _ in plan])
assert len(plan) == 5 and len({k for k, _, _, _ in plan}) == 5, 'mapping not one-to-one'

new_media, skipped = {}, []
for key, media, pdf, _ in plan:
    old = fitz.open(stream=all_old[media], filetype='png')
    w, h = int(round(old[0].rect.width)), int(round(old[0].rect.height))
    doc = fitz.open(os.path.join(BASE, pdf))
    zoom = w / doc[0].rect.width
    pix = doc[0].get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    ar_old, ar_new = w / h, pix.width / pix.height
    if abs(ar_new - ar_old) / ar_old > 0.02:
        # The drawing frame in the docx encodes the original aspect ratio; forcing a
        # different-aspect bitmap into it would stretch the figure, so this one is left
        # as the archived original and the caption carries the specification note.
        skipped.append(key)
        print('%s: SKIPPED (aspect %.3f vs %.3f; frame unchanged)' % (key, ar_old, ar_new))
        continue
    new_media[media] = pix.tobytes('png')
    print('%s: %s -> %s %dx%d (%d B, was %d)' % (key, os.path.basename(pdf), media,
                                                 pix.width, pix.height, len(new_media[media]),
                                                 len(all_old[media])))
    assert abs(pix.width - w) <= 1 and abs(pix.height - h) <= 1, 'size changed for %s' % media

NEWCAP = {
    '图 2': '图 2  分析框架：DPSIR 因果链与 ESI 预警管线（八项加权指标 + 无权重政策背景层；虚线箭头为管理反馈）',
    '图 3': '图 3  八项加权指标变化趋势（2005–2023，主口径；生态用地列与状态层重复，改作无权重政策背景层、不参与赋权，故不绘制；圆点为五个土地覆被观测时点）',
    '图 5': '图 5  熵权、AHP 与组合权重（α=0.4；八指标主口径，生态用地列已剔除）',
    '图 6': '图 6  2023 年 ESI 对权重比例 α 的敏感性（八指标主口径 0.415→0.573，九指标对照 0.425→0.578；无年份变级的 α 区间由九指标 0.3–0.4 扩大到八指标 0.4–0.8）',
}


def flexible(old):
    return re.compile('(?:<[^>]*>)*'.join(re.escape(c) for c in old), re.S)


patched = xml
for key, media, pdf, old_txt in plan:
    if key not in NEWCAP:
        continue
    hits = list(flexible(old_txt).finditer(patched))
    assert len(hits) == 1, 'caption %s hits=%d' % (key, len(hits))
    patched = patched[:hits[0].start()] + NEWCAP[key] + patched[hits[0].end():]
    print('caption rewritten:', key)

zout = zipfile.ZipFile(SRC, 'w', zipfile.ZIP_DEFLATED)
for item in zin.infolist():
    data = (patched.encode('utf-8') if item.filename == 'word/document.xml'
            else new_media.get(item.filename, all_old[item.filename]))
    zi = zipfile.ZipInfo(item.filename, date_time=item.date_time)
    zi.compress_type = item.compress_type
    zi.external_attr = item.external_attr
    zout.writestr(zi, data)
zout.close()
z2 = zipfile.ZipFile(SRC)
diff = [n for n in names if z2.read(n) != all_old[n]]
print('parts differing from the previous CN build:', diff)
print('testzip:', z2.testzip(), '| entries', len(names), len(z2.namelist()))
t = z2.read('word/document.xml').decode('utf-8')
print('paragraphs', t.count('<w:p '), 'tbls', t.count('<w:tbl>'), 'drawings', t.count('<w:drawing>'),
      'oMath', t.count('<m:oMath'), 'nonblack',
      len([c for c in re.findall(r'w:color w:val="([^"]+)"', t) if c.upper() not in ('000000', 'AUTO')]))
print('md5:', hashlib.md5(open(SRC, 'rb').read()).hexdigest().upper(),
      'bytes:', len(open(SRC, 'rb').read()))