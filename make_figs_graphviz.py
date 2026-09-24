# -*- coding: utf-8 -*-
"""用 Graphviz 渲染两张示意图（概念框架图 / 技术路线图）。

设计原则（v16 重绘的核心修正）：
  此前两图按 11–12 in 宽设计、插入 0.9\\linewidth（5.88 in）时整体缩小到 ~0.5 倍，
  图内 8 pt 字号实际只剩 ~4 pt，肉眼"发虚、看不清"——这才是"丑"的主因，而非配色。
  本脚本按**成品印刷尺寸**出图（自然宽度 ≈ 目标 5.88 in、字号 7.5–8 pt），插入后不再缩小。

输出：figures/fig_dpsir_framework.{pdf,png}、figures/fig2_workflow.{pdf,png}
审计：用 dot -Tplain 读取自然尺寸/节点框/边折线，检查 (1) 节点框两两不重叠
      (2) 边折线不穿过无关节点框 (3) 插入 0.9\\linewidth 后的等效字号 ≥ 7 pt。
"""
import os
import subprocess
import sys

PC = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(PC, "figures")
GV = os.environ.get("DOT_EXE", "dot")
if not os.path.isfile(GV):
    GV = "dot"
TARGET_IN = 5.88          # 0.9\linewidth（\textwidth = 472.03 pt = 6.53 in）
DPI = 600
# (dot 源, 输出名, 字号, 插入宽度)  —— 插入宽度取自 manuscript.tex 的 includegraphics 设置
JOBS = [("fig_dpsir_framework.dot", "fig_dpsir_framework", 8.5, 6.53),
        ("fig2_workflow.dot", "fig2_workflow", 7.5, 5.88)]

fail = []


def run(args):
    return subprocess.run(args, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def audit(dotfile, name, fontsize, target_in):
    """解析 dot -Tplain：自然尺寸、节点框、边折线 → 重叠/穿透审计。"""
    r = run([GV, "-Tplain", dotfile])
    gx = gw = gh = None
    nodes = {}
    edges = []
    for ln in r.stdout.splitlines():
        p = ln.split()
        if not p:
            continue
        if p[0] == "graph":
            gw, gh = float(p[2]), float(p[3])
        elif p[0] == "node":
            nodes[p[1]] = (float(p[2]), float(p[3]), float(p[4]), float(p[5]))
        elif p[0] == "edge":
            n = int(p[3])
            pts = [(float(p[4 + 2 * i]), float(p[5 + 2 * i])) for i in range(n)]
            edges.append((p[1], p[2], pts))

    def inside(x, y, b, pad=-0.02):
        cx, cy, w, h = b
        return (abs(x - cx) < w / 2 + pad) and (abs(y - cy) < h / 2 + pad)

    # 节点框重叠
    names = sorted(nodes)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = nodes[names[i]], nodes[names[j]]
            ox = (a[2] + b[2]) / 2 - abs(a[0] - b[0])
            oy = (a[3] + b[3]) / 2 - abs(a[1] - b[1])
            if ox > 0.005 and oy > 0.005:
                fail.append("%s: 节点框重叠 %s × %s (%.3f×%.3f in)"
                            % (name, names[i], names[j], ox, oy))

    # 边穿透无关节点
    for t, h, pts in edges:
        for i in range(len(pts) - 1):
            (x1, y1), (x2, y2) = pts[i], pts[i + 1]
            for k in range(9):                     # 段上取样
                f = k / 8.0
                x, y = x1 + (x2 - x1) * f, y1 + (y2 - y1) * f
                if f < 0.06 and (x, y) == (x1, y1):
                    continue
                for nm, b in nodes.items():
                    if nm in (t, h):
                        continue
                    if inside(x, y, b):
                        fail.append("%s: 边 %s→%s 穿过节点 %s" % (name, t, h, nm))
                        break

    eff = fontsize * (target_in / gw)
    print("  [%s] 自然尺寸 %.2f × %.2f in（%d 节点 / %d 边）；"
          "插入 %.2f in（%.2f\\linewidth）后缩放 %.2f×、等效字号 %.2f pt"
          % (name, gw, gh, len(nodes), len(edges), target_in,
             target_in / 6.53, target_in / gw, eff))
    if eff < 6.9:
        fail.append("%s: 等效字号 %.2f pt < 7 pt（字太小）" % (name, eff))
    if gh > 8.6:
        fail.append("%s: 图高 %.2f in 过高（> 8.6 in，版面压力大）" % (name, gh))
    return gw, gh


def render(dotfile, stem):
    pdf = os.path.join(FIG, stem + ".pdf")
    png = os.path.join(FIG, stem + ".png")
    for args, out in (([GV, "-Tpdf", "-Gmargin=0", "-Gpad=0", dotfile, "-o", pdf], pdf),
                      ([GV, "-Tpng", "-Gdpi=%d" % DPI, "-Gmargin=0", "-Gpad=0.02",
                        dotfile, "-o", png], png)):
        r = run(args)
        if r.returncode != 0 or not os.path.isfile(out):
            fail.append("渲染失败: %s\n%s" % (stem, (r.stderr or "")[:300]))
            return
    print("  generated: %s.pdf / .png (%d KB)" % (stem, os.path.getsize(pdf) // 1024))


print("== Graphviz 出图（%s）==" % GV)
for dotfile, stem, fs, tgt in JOBS:
    path = os.path.join(FIG, dotfile)
    audit(path, stem, fs, tgt)
    render(path, stem)

# 字体嵌入核验（图注/标签须为 Arial，与正文和其余图一致）
for _, stem, _, _ in JOBS:
    pdffonts = os.path.join(os.path.dirname(GV), "pdffonts.exe")
    exe = pdffonts if os.path.isfile(pdffonts) else "pdffonts"
    if os.path.isfile(exe):
        r = run([exe, os.path.join(FIG, stem + ".pdf")])
        ok = ("Arial" in (r.stdout or "")) or ("Times" in (r.stdout or ""))
        print("  %s 字体: %s" % (stem, "TNR/Arial 已嵌入" if ok else "!! 未见 TNR/Arial"))
        if not ok:
            fail.append("%s 未嵌入 TNR/Arial" % stem)

if fail:
    print("\n!! 审计问题 %d 条：" % len(fail))
    for f in fail:
        print("   -", f)
    sys.exit(1)
print("\nmake_figs_graphviz: ALL PASS")