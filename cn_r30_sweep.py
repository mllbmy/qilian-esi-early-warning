# -*- coding: utf-8 -*-
'''R30 final CN sweep: the last two stale R28 values.'''
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
P = r'D:\比赛\论文\_r28_work\cn_document.xml'
xml = open(P, encoding='utf-8').read()


def flexible(old):
    return re.compile('(?:<[^>]*>)*'.join(re.escape(c) for c in old), re.S)


def rep(old, new, label, want=1):
    global xml
    hits = list(flexible(old).finditer(xml))
    assert len(hits) == want, '%s: hits=%d want %d' % (label, len(hits), want)
    for m in reversed(hits):
        xml = xml[:m.start()] + new + xml[m.end():]
    print('%-24s %d replacement(s)' % (label, len(hits)))


rep('0.56–0.59', '0.54（NGBM 分块口径）、0.43（等权混合）', 'cn grade prob')
rep('r=0.705', 'r=0.721', 'cn ndvi r', want=2)
open(P, 'w', encoding='utf-8', newline='\n').write(xml)
print('xml now %d chars' % len(xml))