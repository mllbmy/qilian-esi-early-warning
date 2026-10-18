# -*- coding: utf-8 -*-
"""Self-verify every in-library md5-manifest entry (measured, not asserted)."""
import hashlib
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
MAN = r"D:\比赛\论文\交付\2.0版本\md5清单_2.0版本.txt"
ROOT = os.path.dirname(MAN)
LINE = re.compile(r"^([0-9A-Fa-f]{32})\s{2,}(.+?)\s{2,}(\d+)\s*KB\s*(.*)$")
SKIP_PREFIX = ("(历史，文件已不在库)", "(目录，不计校验)")


def md5(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


entries, skipped, ok, bad, missing = [], [], [], [], []
for ln, raw in enumerate(io.open(MAN, encoding="utf-8"), 1):
    line = raw.strip()
    if not line or line.startswith(("==", "格式:", "生成时间:", "JMS ", "────")):
        continue
    if line.startswith(SKIP_PREFIX):
        skipped.append((ln, line[:80]))
        continue
    m = LINE.match(line)
    if not m:
        continue
    listed, path, kb, note = m.group(1).upper(), m.group(2).strip(), int(m.group(3)), m.group(4)
    full = os.path.join(ROOT, path)
    entries.append((ln, path, listed))
    if not os.path.isfile(full):
        missing.append((ln, path))
        continue
    actual = md5(full)
    size_kb = int(round(os.path.getsize(full) / 1024.0))
    if actual == listed:
        ok.append((ln, path, actual, size_kb, kb))
    else:
        bad.append((ln, path, listed, actual, size_kb, kb))

print("=" * 78)
print("manifest:", MAN)
print("in-library entries parsed :", len(entries))
print("  verified OK             :", len(ok))
print("  md5 MISMATCH            :", len(bad))
print("  FILE MISSING            :", len(missing))
print("  skipped (marked)        :", len(skipped))
for ln, path, listed, actual, size_kb, kb in bad:
    print("  !! L%-4d %-46s listed=%s actual=%s  (%d KB vs %d KB)"
          % (ln, path, listed, actual, size_kb, kb))
for ln, path in missing:
    print("  !! L%-4d MISSING %s" % (ln, path))
print()
print("size(KB) discrepancies (md5 still OK):")
n = 0
for ln, path, actual, size_kb, kb in ok:
    if abs(size_kb - kb) >= 1:
        n += 1
        print("   L%-4d %-46s listed=%d actual=%d" % (ln, path, kb, size_kb))
print("   count:", n)
print()
print("--- the two entries changed this round ---")
for ln, path, actual, size_kb, kb in ok:
    if "投稿用" in path or "_旧版_论文_EN_2.0" in path:
        print("   L%-4d OK  %-42s %s  %d KB" % (ln, path, actual, size_kb))