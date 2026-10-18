# -*- coding: utf-8 -*-
'''R30: add the missing CLCD (Yang & Huang, 2024) entry to the Chinese reference list.'''
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
XMLPATH = r'D:\比赛\论文\_r28_work\cn_document.xml'
xml = open(XMLPATH, encoding='utf-8').read()
PARA = re.compile(r'<w:p\b[^>]*>.*?</w:p>', re.S)

ANCHOR = 'Yang, J., Huang, X., 2021. The 30 m annual land cover dataset and its dynamics in China from 1990 to 2019.'
NEW = ('Yang, J., Huang, X., 2024. The 30 m annual land cover datasets and its dynamics in China from 1985 '
       'to 2023: China Land Cover Dataset, 30 m annual land cover (1985–2023), version 1.0.3. Zenodo dataset. '
       'doi: 10.5281/zenodo.12779975（2020 期使用的瓦片记录为 8176941, version 1.0.2）.')

blocks = [(m.start(), m.end(), m.group(0)) for m in PARA.finditer(xml)]
hits = [b for b in blocks if ANCHOR in b[2]]
assert len(hits) == 1, 'anchor hits=%d' % len(hits)
a, b, blk = hits[0]
assert blk.count('<w:t') == 1, 'entry is not a single run: %d' % blk.count('<w:t')
new_blk = blk.replace(ANCHOR, NEW)
assert new_blk != blk
assert xml.count(NEW) == 0
xml = xml[:b] + new_blk + xml[b:]
open(XMLPATH, 'w', encoding='utf-8', newline='\n').write(xml)
print('inserted CLCD 2024 reference entry after the 2021 entry; xml %d chars' % len(xml))
print('new entry occurrences:', xml.count(NEW))